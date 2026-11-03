"""Diagnose block-to-block seams in a generated MusicGen soundtrack.

Runs the same chunk loop as ``synthesize_soundtrack_transformers`` but keeps
the raw chunks so we can measure, for every seam:

* the loudness of the outgoing tail vs. the incoming head,
* the correlation between the two overlap regions (they should be the same
  music — the outgoing tail is fed back as the continuation prompt),
* the stitched level trace across the crossfade window,
* clipping introduced by the final ``np.clip(..., -1, 1)``.

Usage::

    backend\\qwen_tts\\.venv\\Scripts\\python.exe scripts\\diagnose_musicgen_seams.py
"""

from __future__ import annotations

import argparse
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import numpy as np

from core_engine import music_generator as mg


def db(value: float) -> float:
    return 20.0 * np.log10(max(float(value), 1e-9))


def rms(audio: np.ndarray) -> float:
    audio = np.asarray(audio, dtype=np.float64).reshape(-1)
    if not audio.size:
        return 0.0
    return float(np.sqrt(np.mean(audio ** 2)))


def correlation(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64).reshape(-1)
    b = np.asarray(b, dtype=np.float64).reshape(-1)
    n = min(a.size, b.size)
    if n == 0:
        return 0.0
    a, b = a[:n], b[:n]
    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom > 1e-12 else 0.0


def generate_chunks(
    model_dir: str,
    durations: list[float],
    *,
    plan_options: dict | None = None,
    prompts: list[str] | None = None,
    use_hops: bool = True,
) -> tuple[list[np.ndarray], int, list[str]]:
    segments = [
        {
            "text_content": (
                "Slow introduction to the wetland at dawn, mist over the "
                "water, quiet reeds moving in the wind."
                if i == 0
                else (
                    "Mid scene, the beavers work through the afternoon, "
                    "branches carried across the pond."
                    if i == len(durations) - 1
                    else "Calm development, water flowing steadily over the dam."
                )
            ),
            "image_prompt": "wetland",
            "duration": duration,
        }
        for i, duration in enumerate(durations)
    ]
    plan = mg.plan_music(segments, **(plan_options or {}))
    if prompts:
        if len(prompts) != len(durations):
            raise SystemExit("--prompts must contain one prompt per duration")
        plan.prompts = list(prompts)
    normalised = mg.normalise_segments(segments)
    # Mirror the production pipeline: blocks are generated in short hops, each
    # conditioned on the previous hop's tail (``use_hops=False`` reproduces the
    # old one-chunk-per-block behaviour for comparison).
    steps = (
        mg.plan_generation_hops(normalised)
        if use_hops
        else [(position, segment.safe_duration)
              for position, segment in enumerate(normalised)]
    )
    model, processor, sample_rate = mg.load_transformers_musicgen(
        model_dir, device="cuda"
    )
    chunks: list[np.ndarray] = []
    last_raw: np.ndarray | None = None
    tail_samples = int(round(mg.CONTINUATION_TAIL_SECONDS * sample_rate))
    try:
        for step_index, (position, requested) in enumerate(steps):
            continuation = None
            if step_index > 0 and last_raw is not None and last_raw.size:
                continuation = (
                    last_raw[-tail_samples:]
                    if last_raw.size > tail_samples
                    else last_raw
                )
            chunk = mg._generate_transformers_chunk(
                model,
                processor,
                plan.prompts[position],
                requested,
                continuation,
                device="cuda",
            )
            chunks.append(chunk)
            last_raw = chunk
            print(
                f"chunk {len(chunks)}: block={position + 1} "
                f"requested={requested:.2f}s got={len(chunk) / sample_rate:.3f}s "
                f"rms={db(rms(chunk)):.2f} dB peak={np.max(np.abs(chunk)):.3f}",
                flush=True,
            )
    finally:
        del model, processor
        import gc

        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
    return chunks, sample_rate, plan.prompts


def band_db(audio: np.ndarray, sample_rate: int, low: float, high: float) -> float:
    """Power of *audio* inside ``[low, high)`` Hz, in dB."""
    size = audio.size
    if size < 4:
        return -200.0
    windowed = audio * np.hanning(size)
    spectrum = np.abs(np.fft.rfft(windowed)) ** 2
    freqs = np.fft.rfftfreq(size, 1.0 / sample_rate)
    mask = (freqs >= low) & (freqs < high)
    return float(10.0 * np.log10(spectrum[mask].sum() + 1e-30))


def hf_report(audio: np.ndarray, sample_rate: int) -> str:
    """High-band (2-6 kHz) level of *audio*: mean, quiet-frame floor, share.

    ``floor`` is the 10th-percentile frame level, which is what a listener
    hears as hiss between the notes; ``share`` is the band's percentage of
    the total energy.
    """
    frame = int(0.5 * sample_rate)
    step = frame // 2
    mean_levels: list[float] = []
    floor_levels: list[float] = []
    shares: list[float] = []
    for start in range(0, max(audio.size - frame, 1), step):
        seg = audio[start:start + frame]
        if seg.size < frame // 2:
            break
        hf = band_db(seg, sample_rate, 2000, 6000)
        total = band_db(seg, sample_rate, 0, sample_rate / 2)
        mean_levels.append(hf)
        floor_levels.append(hf)
        shares.append(100.0 * 10 ** ((hf - total) / 10.0))
    if not mean_levels:
        return "hf: n/a"
    mean_levels.sort()
    floor_levels.sort()
    return (
        f"hf_2_6k mean={np.mean(mean_levels):.1f} dB "
        f"floor={floor_levels[max(0, len(floor_levels) // 10)]:.1f} dB "
        f"share={np.mean(shares):.2f}%"
    )


def report(chunks: list[np.ndarray], sample_rate: int, prompts: list[str]) -> None:
    crossfade = mg.CROSSFADE_SECONDS
    overlap = int(round(crossfade * sample_rate))
    print("\n=== seams ===")
    for i in range(1, len(chunks)):
        out_tail = chunks[i - 1][-overlap:]
        in_head = chunks[i][:overlap]
        step_db = db(rms(in_head)) - db(rms(out_tail))
        print(
            f"seam {i}: outgoing tail {db(rms(out_tail)):.2f} dB -> "
            f"incoming head {db(rms(in_head)):.2f} dB "
            f"(step {step_db:+.2f} dB, correlation "
            f"{correlation(out_tail, in_head):+.3f})"
        )

    stitched = mg.stitch_audio_segments(
        chunks, sample_rate=sample_rate, crossfade_seconds=crossfade
    )
    peak = float(np.max(np.abs(stitched)))
    clipped = int(np.sum(np.abs(stitched) > 1.0))
    print(f"\nstitched: {len(stitched) / sample_rate:.3f}s peak={peak:.3f} "
          f"samples_over_full_scale={clipped}")

    # 100 ms loudness trace across every crossfade window.
    for i in range(1, len(chunks)):
        window_start = sum(len(c) for c in chunks[:i]) / sample_rate - crossfade
        print(f"\n-- crossfade {i} window at {window_start:.2f}s --")
        t = window_start - 1.0
        while t < window_start + crossfade + 1.0:
            a0 = int(t * sample_rate)
            a1 = int((t + 0.1) * sample_rate)
            if 0 <= a0 < a1 <= stitched.size:
                print(
                    f"   {t:7.2f}s {db(rms(stitched[a0:a1])):7.2f} dB "
                    f"peak={np.max(np.abs(stitched[a0:a1])):.3f}"
                )
            t += 0.1

    # Loudness spread across the raw chunks (the root cause of hard switches).
    print("\n=== chunk loudness spread ===")
    levels = [db(rms(c)) for c in chunks]
    for i, (chunk, level) in enumerate(zip(chunks, levels)):
        peak = float(np.max(np.abs(chunk)))
        crest = db(peak) - level
        overs = int(np.sum(np.abs(chunk) > 1.0))
        # 5 s profile: MusicGen can drift in level during long generations.
        profile = []
        step = 5 * sample_rate
        for start in range(0, chunk.size, step):
            profile.append(f"{db(rms(chunk[start:start + step])):.1f}")
        print(
            f"chunk {i + 1}: {level:.2f} dB peak={peak:.3f} "
            f"crest={crest:.1f} dB overs={overs} "
            f"5s_profile=[{' '.join(profile)}] "
            f"{hf_report(chunk, sample_rate)}"
        )
    print(f"spread: {max(levels) - min(levels):.2f} dB")

    # The noise-floor gate the pipeline applies before level matching
    # (Issue #13): how much floor does it take out of each hop, and does the
    # hop's music survive?
    gated = [mg.reduce_noise_floor(chunk, sample_rate) for chunk in chunks]
    print("\n=== noise floor gate (raw -> gated) ===")
    for i, (raw, clean) in enumerate(zip(chunks, gated)):
        level_delta = db(rms(clean)) - db(rms(raw))
        print(
            f"chunk {i + 1}: level {db(rms(raw)):6.2f} -> {db(rms(clean)):6.2f} dB "
            f"({level_delta:+.2f}) | raw {hf_report(raw, sample_rate)} | "
            f"gated {hf_report(clean, sample_rate)}"
        )

    # The same chunks through the mastering chain the pipeline now applies.
    gains = mg.loudness_gains(
        gated, sample_rate=sample_rate, crossfade_seconds=crossfade
    )
    mastered = mg.stitch_audio_segments(
        gated,
        sample_rate=sample_rate,
        crossfade_seconds=crossfade,
        gains=gains,
    )
    mastered = mg.tilt_high_band(mastered, sample_rate)
    mastered = mg.tame_peaks(mastered, sample_rate=sample_rate)
    mastered = mg.scale_to_ceiling(mastered)
    mastered = mg.apply_tail_fade(mastered, sample_rate)
    master_peak = float(np.max(np.abs(mastered)))
    master_overs = int(np.sum(np.abs(mastered) >= 1.0))
    print(
        "\n=== mastered (denoise + loudness match + high-band tilt + ceiling + fade) ===\n"
        f"gains dB: {[round(20 * np.log10(g), 2) for g in gains]}\n"
        f"peak={master_peak:.3f} samples_over_full_scale={master_overs} "
        f"duration={len(mastered) / sample_rate:.3f}s "
        f"tail_1s={db(rms(mastered[-sample_rate:])):.2f} dB"
    )

    # Block levels and seam steps of the finished track.
    boundaries = [0.0]
    overlap_samples = int(round(crossfade * sample_rate))
    for position, chunk in enumerate(chunks):
        # The first chunk is appended whole; every later chunk contributes its
        # length minus the overlap the crossfade consumes.
        grown = len(chunk) - (0 if position == 0 else overlap_samples)
        boundaries.append(boundaries[-1] + grown / sample_rate)
    block_levels = [
        db(rms(mastered[int(a * sample_rate):int(b * sample_rate)]))
        for a, b in zip(boundaries[:-1], boundaries[1:])
    ]
    print(f"mastered block levels dB: {[round(x, 2) for x in block_levels]}")
    print(
        "mastered block spread: "
        f"{max(block_levels) - min(block_levels):.2f} dB"
    )
    seam_steps = []
    for boundary in boundaries[1:-1]:
        before = db(
            rms(mastered[int((boundary - 0.5) * sample_rate):int(boundary * sample_rate)])
        )
        after = db(
            rms(mastered[int(boundary * sample_rate):int((boundary + 0.5) * sample_rate)])
        )
        seam_steps.append(round(float(after - before), 2))
    print(f"mastered seam steps dB: {seam_steps}")

    # Does mastering itself add high-frequency content, or is it already in
    # the raw hops?  And how does the 2-6 kHz share grow along the track?
    raw_stitched = mg.stitch_audio_segments(
        chunks, sample_rate=sample_rate, crossfade_seconds=crossfade
    )
    print(f"raw stitched  : {hf_report(raw_stitched, sample_rate)}")
    print(f"mastered track: {hf_report(mastered, sample_rate)}")
    growth = []
    step = 5 * sample_rate
    for start in range(0, mastered.size - step, step):
        seg = mastered[start:start + step]
        hf = band_db(seg, sample_rate, 2000, 6000)
        body = band_db(seg, sample_rate, 500, 2000)
        total = band_db(seg, sample_rate, 0, sample_rate / 2)
        growth.append(
            f"{start / sample_rate:.0f}s:{100 * 10 ** ((hf - total) / 10):.2f}%"
            f"/{hf - body:+.0f}dB"
        )
    print(
        "mastered 5s [share / (2-6k - 500-2k)]: [" + " ".join(growth) + "]"
    )
    for prompt in prompts:
        print(f"prompt: {prompt[:90]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=os.path.join(PROJECT_ROOT, "models", "musicgen-small"),
    )
    parser.add_argument(
        "--durations",
        default="10,10,10",
        help="Comma separated segment durations in seconds.",
    )
    parser.add_argument(
        "--prompts",
        default=None,
        help="Pipe separated MusicGen prompts (one per duration).",
    )
    parser.add_argument("--bpm", type=int, default=None)
    parser.add_argument("--root-key", default=None)
    parser.add_argument("--mode", default=None)
    parser.add_argument(
        "--no-hops",
        action="store_true",
        help="Generate one chunk per block instead of the production hops.",
    )
    args = parser.parse_args()
    durations = [float(value) for value in args.durations.split(",")]
    plan_options = {
        key: value
        for key, value in (
            ("bpm", args.bpm),
            ("root_key", args.root_key),
            ("mode", args.mode),
        )
        if value is not None
    }
    prompts = args.prompts.split("|") if args.prompts else None
    chunks, sample_rate, plan_prompts = generate_chunks(
        args.model,
        durations,
        plan_options=plan_options,
        prompts=prompts,
        use_hops=not args.no_hops,
    )
    report(chunks, sample_rate, plan_prompts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
