"""End-to-end check for Issues #17 and #13: levels, seams, noise, ending.

Runs the full Django -> CUDA worker -> MP3 path for a three-block script with
the same block lengths as the reported track, then reports:

* per-block loudness of the *finished* MP3 (blocks used to differ by 10+ dB),
* the level step at every block seam,
* how many samples hit or exceeded full scale (the source of the harsh,
  "unrealistic" end of the track),
* the 2-6 kHz high band's share of the energy every 5 s, and how far it sits
  above/below the 500 Hz-2 kHz body - the "high frequency noise" of Issue #13
  showed up as this balance collapsing from -27..-35 dB to -9 dB near the end,
* the level of the last second, the last 200 ms and the final sample — the
  track used to stop dead at full level.

Usage::

    backend\\venv\\Scripts\\python.exe backend\\manage.py shell -c ^
      "exec(open(r'scripts\\verify_issue17.py', encoding='utf-8-sig').read())"
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

from api.models import Account, BGMClip, Project, Segment
from api import music_service

DURATIONS = (30.4, 31.76, 33.6)
# ``__file__`` is Django's own module under ``shell -c``, so resolve the repo
# from the working directory (run this from the repository root).
PROJECT_ROOT = os.getcwd()
DEST = os.path.join(PROJECT_ROOT, "models", "issue17-after.mp3")


def rms_db(x):
    return 20.0 * np.log10(max(float(np.sqrt(np.mean(np.asarray(x) ** 2))), 1e-9))


def main():
    account = Account.objects.create(name="Issue17 Check", section="facebook")
    project = Project.objects.create(
        title="Issue17 Check", section="facebook", account=account
    )
    texts = [
        "A quiet morning over the wetland, mist sitting on the still water.",
        "Through the afternoon the beavers carry branches across the pond.",
        "At dusk the dam holds and the whole valley settles into silence.",
    ]
    for i, duration in enumerate(DURATIONS):
        Segment.objects.create(
            project=project,
            sequence_index=i,
            text_content=texts[i],
            image_prompt="wetland",
            audio_duration=duration,
        )

    segments = music_service.segments_from_project(project)
    task_id = music_service.new_task_id("music_issue17")
    started = __import__("time").time()
    result = music_service.generate_soundtrack_task(
        task_id=task_id,
        account_id=str(account.pk),
        section="facebook",
        segments=segments,
        project_id=str(project.pk),
        name="Issue17 After",
        plan_options={"bpm": 66, "root_key": "C", "mode": "major"},
        attach_to_project=True,
    )
    elapsed = __import__("time").time() - started

    clip = BGMClip.objects.get(pk=result["clip_id"])
    with open(clip.file.path, "rb") as src, open(DEST, "wb") as out:
        shutil.copyfileobj(src, out)

    # ── analyse the finished MP3 ──────────────────────────────────────────
    wav = tempfile.mktemp(suffix=".wav")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", DEST,
         "-ac", "1", "-ar", "32000", wav],
        check=True,
    )
    import soundfile as sf

    audio, sr = sf.read(wav, dtype="float32")
    os.remove(wav)

    peak = float(np.max(np.abs(audio)))
    overs = int(np.sum(np.abs(audio) >= 0.999))
    report = {
        "generation_seconds": round(elapsed, 1),
        "duration": round(len(audio) / sr, 3),
        "peak": round(peak, 4),
        "samples_at_full_scale": overs,
        "clipped_percent": round(100.0 * overs / max(len(audio), 1), 4),
    }

    # Block lengths after stitching are the script durations (the crossfade
    # consumes the duplicated continuation prompt).
    boundaries = [0.0]
    for duration in DURATIONS:
        boundaries.append(boundaries[-1] + duration)
    block_levels = []
    for i in range(len(DURATIONS)):
        start, end = int(boundaries[i] * sr), int(boundaries[i + 1] * sr)
        block_levels.append(round(rms_db(audio[start:end]), 2))
    report["block_levels_db"] = block_levels
    report["block_spread_db"] = round(max(block_levels) - min(block_levels), 2)

    # Level step at each seam: compare the 0.5 s before/after the boundary.
    steps = []
    for boundary in boundaries[1:-1]:
        before = rms_db(audio[int((boundary - 0.5) * sr):int(boundary * sr)])
        after = rms_db(audio[int(boundary * sr):int((boundary + 0.5) * sr)])
        steps.append(round(float(after - before), 2))
    report["seam_steps_db"] = steps

    # 1 s loudness profile so the whole arc is visible.
    profile = [
        round(rms_db(audio[s:s + sr]), 1)
        for s in range(0, len(audio) - sr, sr)
    ]
    report["per_second_db"] = profile

    # Quality guard: MusicGen output must stay tonal, not noise.
    frame = 4096
    flats = []
    for start in range(0, len(audio) - frame, frame):
        chunk = audio[start:start + frame]
        spec = np.abs(np.fft.rfft(chunk * np.hanning(frame))) ** 2 + 1e-12
        flats.append(float(np.exp(np.mean(np.log(spec))) / np.mean(spec)))
    report["spectral_flatness"] = round(float(np.mean(flats)), 6)

    # ── Issue #13: high-frequency balance and the ending ──────────────────
    def band_db(segment, low, high):
        spectrum = np.abs(np.fft.rfft(segment * np.hanning(len(segment)))) ** 2
        freqs = np.fft.rfftfreq(len(segment), 1.0 / sr)
        mask = (freqs >= low) & (freqs < high)
        return 10.0 * np.log10(spectrum[mask].sum() + 1e-30)

    shares, balances = [], []
    step = 5 * sr
    for start in range(0, len(audio) - step, step):
        segment = audio[start:start + step]
        high = band_db(segment, 2000, 6000)
        body = band_db(segment, 500, 2000)
        total = band_db(segment, 0, sr / 2)
        shares.append(round(100.0 * 10 ** ((high - total) / 10), 3))
        balances.append(round(high - body, 1))
    report["hf_share_pct_5s"] = shares
    report["hf_minus_body_db_5s"] = balances
    report["hf_balance_first_half_db"] = round(max(balances[:len(balances) // 2]), 1)
    report["hf_balance_last_10s_db"] = round(min(balances[-2:]), 1)

    report["tail_1s_db"] = round(rms_db(audio[-sr:]), 2)
    report["tail_200ms_db"] = round(rms_db(audio[-sr // 5:]), 2)
    report["last_sample_abs"] = round(abs(float(audio[-1])), 6)
    report["body_level_db"] = round(rms_db(audio[: len(audio) // 2]), 2)

    report["clip_duration"] = clip.duration
    report["attached"] = bool(
        project.refresh_from_db() or project.active_bgm_id == clip.id
    )

    path = clip.file.path
    clip.delete()
    try:
        os.remove(path)
    except OSError:
        pass
    project.delete()
    account.delete()

    print("ISSUE17_REPORT " + json.dumps(report))
    return 0


# exec()'d by ``manage.py shell -c``, where ``__name__`` is not ``__main__``.
main()
