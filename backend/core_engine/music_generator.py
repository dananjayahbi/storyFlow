"""Dynamic background-music generation for documentary projects.

The subsystem is built around Meta AudioCraft **MusicGen-Small**
(``facebook/musicgen-small``).  It turns a list of documentary script
segments (narration text + measured TTS duration) into one continuous,
evolving instrumental soundtrack:

1. A deterministic music planner keeps the same BPM and root key for every
   scene (the "anchor") and only changes instrumentation / mood, so adjacent
   prompts cannot drift into a different key or tempo.
2. Segment 0 is generated cold from its text prompt.  Every later segment
   uses :meth:`MusicGen.generate_continuation` with the trailing 3 seconds of
   the previous raw audio tensor as an acoustic prompt.
3. The generated chunks are joined with a 3 second **equal-power** (constant
   power) crossfade, which keeps the perceived loudness flat through the
   transition.
4. :func:`mix_background_music` multiplexes the finished music bed with the
   narration and applies voice-activated side-chain ducking
   (-10 dB … -14 dB by default).

Heavy imports (``torch`` / ``audiocraft``) are deliberately lazy: importing
this module must never break Django on a CPU-only machine.  Generation raises
:class:`MusicGenerationError` with actionable setup instructions when the
runtime is not usable.
"""

from __future__ import annotations

import gc
import hashlib
import importlib.util
import logging
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

import numpy as np

logger = logging.getLogger(__name__)

# ── Model / timing constants ──────────────────────────────────────────────
MUSICGEN_MODEL = "facebook/musicgen-small"
MUSICGEN_SAMPLE_RATE = 32_000
CONTINUATION_TAIL_SECONDS = 3.0
CROSSFADE_SECONDS = 3.0
CROSSFADE_MS = int(CROSSFADE_SECONDS * 1000)
DEFAULT_MUSIC_GAIN_DB = -18.0
DEFAULT_DUCKING_DB = -12.0

# ── Generation limits / mastering ─────────────────────────────────────────
# MusicGen drifts out of distribution during long continuations.  Measured on
# the 6 GB GPU (scripts/diagnose_musicgen_seams.py): 30 s hops produced peaks
# of 1.6-2.2 with thousands of samples above full scale and a 10 dB
# block-to-block loudness spread, while 12 s hops stayed clean (peak 0.43, no
# overs, 1.8 dB spread).  Blocks are therefore generated in short hops and
# every hop is levelled to one common loudness, so a block change reads as a
# musical transition instead of a hard cut.
MAX_GENERATION_SECONDS = 12.0
# Common loudness for every generated hop (BGM sits under narration, so it is
# kept well below full scale before the mix applies its own gain).
TARGET_CHUNK_RMS_DBFS = -16.0
# Loudness matching may lift a quiet hop by at most this much so a near-silent
# passage (codec hiss) is not blown up.  Turning a loud hop *down* is uncapped.
MAX_CHUNK_BOOST_DB = 18.0
# Decoded MusicGen audio is not bounded to ±1.0.  The track is scaled — never
# clipped — to this ceiling before it is written, because hard clipping is
# what made the end of a soundtrack sound harsh and "unrealistic".
MASTER_PEAK_CEILING = 0.95

# ── Noise floor ───────────────────────────────────────────────────────────
# MusicGen leaves a broadband floor between the notes that is roughly constant
# in absolute terms while the music around it swings by 15 dB or more.  Level
# matching (above) therefore pumps that floor: measured on a real three-block
# track the 2-6 kHz band sat at -80 dB in the loud middle and at -31 dB in the
# quiet final hops, so the floor switched on and off at hop boundaries — which
# is what "high frequency noise interrupting the music" sounds like.  Every hop
# is therefore de-noised *before* it is level-matched.
NOISE_FRAME_SECONDS = 0.064
NOISE_HOP_SECONDS = 0.016
# Percentile of each bin's magnitude that is taken as the stationary floor.
NOISE_PERCENTILE = 15.0
# A low percentile sits below the noise's mean level, so it is scaled up
# before subtraction to aim at the actual floor rather than its quietest
# instants.  Measured trade-off on reference material: 1.0 → 4.5 dB of noise
# removed, 2.0 → ~9 dB, while a sustained chord of partials stays within
# 0.3 dB either way (spectral peaks are protected separately).
NOISE_FLOOR_SCALE = 2.0
# A hop may never be stripped by more than this, so a sustained musical
# partial that happens to sit in the floor estimate still comes through.
MAX_NOISE_REDUCTION_DB = 12.0
# Below this frequency the music is dense and loud enough to mask its own
# floor; leaving it untouched also protects bass fundamentals.
NOISE_CUTOFF_HZ = 250.0
# A bin standing this far above its spectral neighbours is a musical partial,
# not noise, and is never attenuated.
NOISE_PEAK_PROTECT_DB = 4.0
NOISE_PEAK_PROTECT_BINS = 12
# Gains are averaged over this many frames so the gate cannot chatter.
NOISE_SMOOTH_FRAMES = 3

# ── High-band balance ─────────────────────────────────────────────────────
# MusicGen's high band sits far below the musical body through most of a
# track and rises steeply in the bright closing hops.  Measured on the
# reported track in 5 s windows, the 2-6 kHz band sat 27-35 dB under the
# 500 Hz-2 kHz body through the clean middle but only 9-14 dB under it
# across the closing 35 s - a 20 dB collapse of the balance, which is what
# the report called high frequency noise.  Only the excess is pulled back.
HF_TILT_BODY_BAND = (500.0, 2_000.0)
HF_TILT_BAND = (2_000.0, 8_000.0)
# Where the high band should sit, in dB below the body.  Measured on the
# reported track in 5 s windows: its clean middle sits at -27 to -35 dB, its
# opening - which the reporter called "good enough" - at -12 to -19 dB, and
# its noisy closing section at -8.9 to -14.1 dB.  -18 dB pulls the closing
# section back to at least the brightness of that accepted opening.
HF_TILT_TARGET_DB = 18.0
# Most correction allowed, so a deliberately bright climax keeps its edge.
HF_TILT_MAX_DB = 10.0
# Correction is smoothed over this window: a slow shelf, never a gate.
HF_TILT_SMOOTH_SECONDS = 3.0
# The shelf starts just above the melody's fundamentals and is fully in by
# 2.6 kHz, where the reported ending's excess actually sits (its strongest
# components at the end were overtones at 1.5-2.5 kHz, not the melody itself,
# which lives below 1 kHz).  Starting it at the body band's own upper edge
# would have left the correction at the foot of the shelf, where it barely
# acts.
HF_TILT_RAMP_BAND = (1_400.0, 2_600.0)

# ── Ending ────────────────────────────────────────────────────────────────
# A generated score must not stop dead: the video ends with it, so the last
# seconds resolve into silence instead of cutting off mid-note.
TAIL_FADE_SECONDS = 4.0
# Longest fade the tail fade may claim, as a fraction of the track, so short
# clips keep a recognisable ending.
TAIL_FADE_MAX_FRACTION = 0.25
# Crossfade used when the music bed has to be looped to cover a longer
# narration timeline.  Loop joins must be smooth because the source now ends
# with a fade that must not appear in the middle of the video.
MUSIC_LOOP_CROSSFADE_SECONDS = 2.0

# Only one MusicGen model may live on the 6 GB target GPU at a time.
_MODEL_LOCK = threading.Lock()
_CACHED_MODEL = None

# ── Prompt planner palette ────────────────────────────────────────────────
_BPM_PALETTE = (60, 66, 70, 76, 80, 88, 92)
_KEY_PALETTE = ("C", "D", "E", "F", "G", "A", "B")
_MODE_PALETTE = ("minor", "major")

# (keywords, instrumentation + emotional tone).  The anchor (BPM/key) is
# applied separately so only colouration changes between scenes.
_MOOD_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("mystery", "secret", "hidden", "ancient", "ruin", "crypt", "lost"),
        "quiet mystery, low cello, sparse felt piano",
    ),
    (
        ("tension", "danger", "threat", "chase", "storm", "war", "conflict"),
        "rising tension, pulsing synth bass, minimal percussion",
    ),
    (
        ("wonder", "discovery", "space", "cosmos", "galaxy", "ocean", "vast"),
        "sense of awe, warm string swells, airy pads",
    ),
    (
        ("sad", "loss", "memory", "farewell", "grief", "alone", "regret"),
        "melancholic piano, soft bowed strings",
    ),
    (
        ("hope", "dawn", "future", "triumph", "rise", "light", "rebirth"),
        "hopeful, bright strings, gentle pulse",
    ),
    (
        ("action", "battle", "fast", "escape", "race", "fight", "explosion"),
        "driving percussion, staccato strings, urgent pulse",
    ),
    (
        ("calm", "nature", "forest", "peace", "river", "quiet", "gentle"),
        "calm, ambient pads, soft acoustic guitar",
    ),
    (
        ("city", "industrial", "machine", "technology", "factory"),
        "restrained electronic pulse, muted arpeggios, low synth",
    ),
)


class MusicGenerationError(RuntimeError):
    """Raised when MusicGen cannot run or generation fails."""


@dataclass
class MusicSegment:
    """One script block plus the duration measured after TTS."""

    index: int
    text: str
    image_prompt: str = ""
    duration: float = 0.0

    @property
    def safe_duration(self) -> float:
        try:
            return max(0.5, float(self.duration or 0.0))
        except (TypeError, ValueError):
            return 0.5


@dataclass
class MusicPlan:
    """The anchor tokens and per-segment MusicGen prompts."""

    bpm: int
    root_key: str
    mode: str
    prompts: list[str]
    anchor: str
    style: str = "cinematic documentary score"
    metadata: dict = field(default_factory=dict)

    def __iter__(self):
        return iter(self.prompts)

    def __len__(self):
        return len(self.prompts)

    def to_dict(self) -> dict:
        return {
            "bpm": self.bpm,
            "root_key": self.root_key,
            "mode": self.mode,
            "anchor": self.anchor,
            "style": self.style,
            "prompts": list(self.prompts),
            **self.metadata,
        }


# ── Environment / status ──────────────────────────────────────────────────


def engine_status() -> dict:
    """Return a JSON-serialisable snapshot of the MusicGen runtime.

    The external CUDA worker is preferred: Django itself is Python 3.14/CPU
    while the Python 3.11 TTS venv has CUDA PyTorch and Transformers.  Never
    raises: a missing dependency is reported as ``available: False``.
    """
    external = None
    try:
        from core_engine import musicgen_client

        external = musicgen_client.probe()
        if external.get("available"):
            return {
                "engine": "musicgen",
                "backend": "transformers",
                "model": MUSICGEN_MODEL,
                "model_dir": external.get("model_dir"),
                "installed": True,
                "torch_installed": True,
                "torch_version": external.get("torch_version"),
                "transformers_version": external.get("transformers_version"),
                "cuda_available": True,
                "device": "cuda",
                "available": True,
                "python": external.get("python"),
                "python_version": external.get("python_version"),
                "gpu": external.get("gpu"),
                "vram_total_gb": external.get("vram_total_gb"),
                "vram_free_gb": external.get("vram_free_gb"),
                "weights_verified": external.get("weights_verified"),
                "reason": None,
                "sample_rate": MUSICGEN_SAMPLE_RATE,
                "continuation_tail_seconds": CONTINUATION_TAIL_SECONDS,
                "crossfade_ms": CROSSFADE_MS,
            }
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not probe external MusicGen worker: %s", exc)

    installed = importlib.util.find_spec("audiocraft") is not None
    torch_version = None
    cuda_available = False
    torch_installed = importlib.util.find_spec("torch") is not None
    torch_error = None

    if torch_installed:
        try:
            import torch  # noqa: WPS433 (lazy import is intentional)

            torch_version = getattr(torch, "__version__", "unknown")
            cuda_available = bool(torch.cuda.is_available())
        except Exception as exc:  # pragma: no cover - broken installs
            torch_error = str(exc)
            torch_installed = False
            cuda_available = False

    allow_cpu = _allow_cpu()
    available = bool(
        installed and torch_installed and (cuda_available or allow_cpu)
    )

    if installed and not cuda_available and not allow_cpu:
        reason = (
            "CUDA is not available. MusicGen on the target 6 GB GPU requires "
            "a CUDA build of PyTorch. Install one from "
            "https://pytorch.org/get-started/locally/ or set "
            "MUSICGEN_ALLOW_CPU=1 for slow CPU testing."
        )
    elif not installed:
        reason = (
            "AudioCraft is not installed. Run `pip install audiocraft` inside "
            "a Python 3.9-3.12 environment with a CUDA build of PyTorch."
        )
    elif torch_error:
        reason = f"PyTorch could not be imported: {torch_error}"
    elif available:
        reason = None
    else:
        reason = "MusicGen is not available in this environment."

    if not available and external and external.get("reason"):
        reason = external["reason"]

    return {
        "engine": "musicgen",
        "backend": "audiocraft" if installed else "unavailable",
        "model": MUSICGEN_MODEL,
        "model_dir": external.get("model_dir") if external else None,
        "installed": installed,
        "torch_installed": torch_installed,
        "torch_version": torch_version,
        "cuda_available": cuda_available,
        "device": "cuda" if cuda_available else ("cpu" if allow_cpu else None),
        "available": available,
        "python": sys.version.split()[0],
        "reason": reason,
        "sample_rate": MUSICGEN_SAMPLE_RATE,
        "continuation_tail_seconds": CONTINUATION_TAIL_SECONDS,
        "crossfade_ms": CROSSFADE_MS,
    }


def _allow_cpu() -> bool:
    return os.environ.get("MUSICGEN_ALLOW_CPU", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


# ── Script parsing / prompt planning ─────────────────────────────────────


def _as_segment(item, index: int) -> MusicSegment:
    if isinstance(item, MusicSegment):
        return item
    if not isinstance(item, dict):
        raise MusicGenerationError(
            f"Segment {index} must be an object, got {type(item).__name__}."
        )
    text = (
        item.get("text_content")
        or item.get("text")
        or item.get("narration")
        or ""
    )
    duration = (
        item.get("duration")
        if item.get("duration") is not None
        else item.get("audio_duration")
    )
    try:
        duration_value = float(duration or 0.0)
    except (TypeError, ValueError):
        duration_value = 0.0
    return MusicSegment(
        index=index,
        text=str(text),
        image_prompt=str(item.get("image_prompt") or ""),
        duration=duration_value,
    )


def normalise_segments(raw) -> list[MusicSegment]:
    """Accept a script dict or a list of segment dicts/objects."""
    if isinstance(raw, dict):
        raw = raw.get("segments")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise MusicGenerationError(
            "A script must contain a `segments` list."
        )
    segments = [_as_segment(item, i) for i, item in enumerate(raw)]
    if not segments:
        raise MusicGenerationError("The script has no segments.")
    return segments


def _seed_anchor(segments: Sequence[MusicSegment]) -> tuple[int, str, str]:
    source = "|".join(
        f"{seg.index}:{seg.text[:160]}:{seg.image_prompt[:80]}"
        for seg in segments
    )
    digest = hashlib.sha256(source.encode("utf-8")).digest()
    bpm = _BPM_PALETTE[digest[0] % len(_BPM_PALETTE)]
    key = _KEY_PALETTE[digest[1] % len(_KEY_PALETTE)]
    mode = _MODE_PALETTE[digest[2] % len(_MODE_PALETTE)]
    return bpm, key, mode


def _mood_for_text(text: str) -> str:
    haystack = (text or "").lower()
    for keywords, description in _MOOD_RULES:
        if any(word in haystack for word in keywords):
            return description
    return "ambient, restrained strings, subtle low pulse"


def plan_music(
    raw_segments,
    *,
    bpm: int | None = None,
    root_key: str | None = None,
    mode: str | None = None,
    style: str = "instrumental cinematic documentary score",
) -> MusicPlan:
    """Build anchor-consistent MusicGen prompts for every script block.

    The same ``"<bpm> bpm, <key> <mode>"`` token is inserted at the front of
    every prompt.  Only the instrumentation/mood phrase changes, fulfilling
    the "agent anchor consistency" requirement.
    """
    segments = normalise_segments(raw_segments)
    seed_bpm, seed_key, seed_mode = _seed_anchor(segments)

    chosen_bpm = int(bpm) if bpm else seed_bpm
    chosen_key = (root_key or seed_key).strip().upper()
    chosen_mode = (mode or seed_mode).strip().lower()
    if chosen_mode not in ("major", "minor"):
        chosen_mode = seed_mode
    if not 30 <= chosen_bpm <= 220:
        raise MusicGenerationError("BPM must be between 30 and 220.")
    if not chosen_key:
        raise MusicGenerationError("A root key is required.")

    anchor = f"{chosen_bpm} bpm, {chosen_key} {chosen_mode}"
    prompts: list[str] = []
    total = len(segments)

    for position, segment in enumerate(segments):
        mood = _mood_for_text(segment.text)
        scene_note = ""
        if position == 0:
            scene_note = "slow introduction, sparse opening"
        elif position == total - 1:
            scene_note = "final scene, gradual resolution, gentle fade"
        else:
            scene_note = "mid-scene development, seamless ambient transition"

        prompts.append(
            f"{anchor}, {style}, {mood}, {scene_note}, "
            "purely instrumental, no vocals, no choir, no lyrics, "
            "continuous evolving texture"
        )

    return MusicPlan(
        bpm=chosen_bpm,
        root_key=chosen_key,
        mode=chosen_mode,
        prompts=prompts,
        anchor=anchor,
        style=style,
        metadata={
            "segment_count": total,
            "total_duration": round(
                sum(seg.safe_duration for seg in segments), 3
            ),
        },
    )


# ── Audio maths ───────────────────────────────────────────────────────────


def _to_mono_float32(audio) -> np.ndarray:
    """Normalise torch tensors / numpy arrays to a 1-D float32 waveform."""
    if hasattr(audio, "detach"):
        audio = audio.detach()
    if hasattr(audio, "cpu"):
        audio = audio.cpu()
    if hasattr(audio, "float"):
        audio = audio.float()
    if hasattr(audio, "numpy"):
        audio = audio.numpy()

    array = np.asarray(audio, dtype=np.float32)
    if array.ndim == 0:
        raise MusicGenerationError("Generated audio is empty.")
    if array.ndim >= 2:
        # (batch, channels, samples) or (channels, samples)
        array = array.reshape(-1, array.shape[-1]) if array.ndim == 3 else array
        array = np.mean(array, axis=0)
    return np.ascontiguousarray(array.reshape(-1), dtype=np.float32)


def rms_dbfs(audio) -> float:
    """RMS level of *audio* in dBFS (silence reports -120 dBFS)."""
    array = np.asarray(audio, dtype=np.float64).reshape(-1)
    if not array.size:
        return -120.0
    value = float(np.sqrt(np.mean(array ** 2)))
    return float(max(-120.0, 20.0 * np.log10(max(value, 1e-6))))


def _gain_for_level(
    level_dbfs: float, target_dbfs: float, max_boost_db: float
) -> float:
    """Linear gain that moves *level_dbfs* onto *target_dbfs*.

    Boosting is capped so a near-silent region (codec hiss) is not blown up;
    turning a hot region down is never capped.
    """
    gain_db = min(target_dbfs - level_dbfs, max_boost_db)
    return float(10.0 ** (gain_db / 20.0))


def loudness_gains(
    chunks: Iterable[np.ndarray],
    *,
    sample_rate: int = MUSICGEN_SAMPLE_RATE,
    crossfade_seconds: float = CROSSFADE_SECONDS,
    target_dbfs: float = TARGET_CHUNK_RMS_DBFS,
    max_boost_db: float = MAX_CHUNK_BOOST_DB,
) -> list[float]:
    """Per-chunk gains that bring every generated hop to ``target_dbfs``.

    Blocks generated from different prompts drift apart by 10 dB or more;
    equalising their loudness is what turns a block change from a hard cut
    into a musical transition.  For every hop after the first the leading
    ``crossfade_seconds`` are excluded from the measurement: that region is
    the previous hop's tail repeated by the continuation prompt, not new
    material, and measuring the hop's own body is what keeps the blocks
    comparable.
    """
    gains: list[float] = []
    for index, chunk in enumerate(chunks):
        array = np.asarray(chunk, dtype=np.float32).reshape(-1)
        body = array
        if index > 0 and array.size:
            overlap = min(
                int(round(crossfade_seconds * sample_rate)), array.size
            )
            if array.size > overlap:
                body = array[overlap:]
        gains.append(_gain_for_level(rms_dbfs(body), target_dbfs, max_boost_db))
    return gains


def tame_peaks(
    audio: np.ndarray,
    *,
    sample_rate: int = MUSICGEN_SAMPLE_RATE,
    ceiling: float = MASTER_PEAK_CEILING,
    window_seconds: float = 0.005,
    release_seconds: float = 0.08,
    lookahead_blocks: int = 1,
    max_reduction_db: float = 20.0,
) -> np.ndarray:
    """Tame isolated over-range peaks so the track keeps its loudness.

    A raw hop can peak above ±2.0 while its body sits at the target loudness.
    Scaling the whole track down for those few samples costs ~8 dB of
    loudness everywhere (measured: −24 dBFS instead of the −16 dBFS target),
    which is the difference between an audible music bed and a nearly
    inaudible one.

    The gain curve is the minimum of the per-block required gain over a window
    that reaches ``lookahead_blocks`` into the future and ``release_seconds``
    into the past, then linearly interpolated between block centres.  Every
    interpolated value therefore stays at or below the requirement of the
    block it sits in, so nothing overshoots; the attack is anticipated one
    block early (no click) and the release takes ~80 ms (no audible dip).
    Reduction is capped at ``max_reduction_db``, and :func:`scale_to_ceiling`
    is still applied afterwards as the hard guarantee.
    """
    array = np.asarray(audio, dtype=np.float32)
    if not array.size or float(np.max(np.abs(array))) <= ceiling:
        return array

    block = max(1, int(round(window_seconds * sample_rate)))
    length = array.size
    blocks = int(math.ceil(length / block))
    padded = np.zeros(blocks * block, dtype=np.float64)
    padded[:length] = np.abs(array.astype(np.float64))
    peaks = padded.reshape(blocks, block).max(axis=1)

    floor_gain = 10.0 ** (-max_reduction_db / 20.0)
    raw_gain = np.maximum(
        floor_gain, np.minimum(1.0, ceiling / np.maximum(peaks, 1e-9))
    )

    look = max(1, int(lookahead_blocks))
    release = max(look, int(round(release_seconds / window_seconds)))
    offsets = np.arange(-look, release + 1)
    positions = np.arange(blocks)
    gain = raw_gain.copy()
    for offset in offsets:
        gain = np.minimum(gain, raw_gain[np.clip(positions + offset, 0, blocks - 1)])

    centres = (positions + 0.5) * block
    curve = np.interp(np.arange(length, dtype=np.float64), centres, gain)
    return (array * curve.astype(np.float32)).astype(np.float32)


def scale_to_ceiling(
    audio: np.ndarray, ceiling: float = MASTER_PEAK_CEILING
) -> np.ndarray:
    """Scale *audio* down so its peak fits under *ceiling* (never clips)."""
    array = np.asarray(audio, dtype=np.float32)
    if not array.size:
        return array
    peak = float(np.max(np.abs(array)))
    if peak <= ceiling or peak <= 0.0:
        return array
    # The 1e-9 guard keeps the float32 rounding of the product at or below the
    # ceiling instead of a hair above it.
    gain = (np.float64(ceiling) * (1.0 - 1e-9)) / np.float64(peak)
    return (array.astype(np.float64) * gain).astype(np.float32)


def reduce_noise_floor(
    audio: np.ndarray,
    sample_rate: int = MUSICGEN_SAMPLE_RATE,
    *,
    frame_seconds: float = NOISE_FRAME_SECONDS,
    hop_seconds: float = NOISE_HOP_SECONDS,
    percentile: float = NOISE_PERCENTILE,
    floor_scale: float = NOISE_FLOOR_SCALE,
    max_reduction_db: float = MAX_NOISE_REDUCTION_DB,
    cutoff_hz: float = NOISE_CUTOFF_HZ,
    peak_protect_db: float = NOISE_PEAK_PROTECT_DB,
    peak_protect_bins: int = NOISE_PEAK_PROTECT_BINS,
    smooth_frames: int = NOISE_SMOOTH_FRAMES,
) -> np.ndarray:
    """Remove the stationary noise floor MusicGen leaves between the notes.

    Each hop of a generated track carries a broadband floor that is roughly
    constant in absolute terms while the music around it swings by 15 dB or
    more.  Left alone, level matching pumps that floor: measured on a real
    three-block track the 2-6 kHz band sat at -80 dB in the loud middle and at
    -31 dB in the quiet final hops, so the floor switched on and off at hop
    boundaries — audible as high-frequency noise interrupting the music and
    worst near the end, where the hops are quietest and get the biggest boost.

    The gate works per frequency bin:

    * the floor of a bin is its ``percentile`` magnitude over time, so content
      that is present only occasionally (the music) is never mistaken for it;
    * a bin standing ``peak_protect_db`` above its spectral neighbours is a
      musical partial and is never touched, which keeps sustained notes and
      bright timbres intact;
    * reduction is capped at ``max_reduction_db`` and gains are smoothed over
      ``smooth_frames`` so the gate cannot chatter or swallow an attack.

    The signal is reflected at both ends before framing so the analysis
    window never zeroes a sample that has no neighbour to reconstruct it.
    """
    array = np.asarray(audio, dtype=np.float32)
    if not array.size:
        return array
    if array.ndim == 2:
        channels = [
            reduce_noise_floor(
                array[:, channel],
                sample_rate,
                frame_seconds=frame_seconds,
                hop_seconds=hop_seconds,
                percentile=percentile,
                floor_scale=floor_scale,
                max_reduction_db=max_reduction_db,
                cutoff_hz=cutoff_hz,
                peak_protect_db=peak_protect_db,
                peak_protect_bins=peak_protect_bins,
                smooth_frames=smooth_frames,
            )
            for channel in range(array.shape[1])
        ]
        return np.stack(channels, axis=1).astype(np.float32)
    if array.ndim != 1:
        raise MusicGenerationError(
            f"Audio must be 1-D or 2-D, got shape {array.shape}."
        )
    return _reduce_noise_floor_mono(
        array,
        sample_rate,
        frame_seconds=frame_seconds,
        hop_seconds=hop_seconds,
        percentile=percentile,
        floor_scale=floor_scale,
        max_reduction_db=max_reduction_db,
        cutoff_hz=cutoff_hz,
        peak_protect_db=peak_protect_db,
        peak_protect_bins=peak_protect_bins,
        smooth_frames=smooth_frames,
    )


def _reduce_noise_floor_mono(
    signal: np.ndarray,
    sample_rate: int,
    *,
    frame_seconds: float,
    hop_seconds: float,
    percentile: float,
    floor_scale: float,
    max_reduction_db: float,
    cutoff_hz: float,
    peak_protect_db: float,
    peak_protect_bins: int,
    smooth_frames: int,
) -> np.ndarray:
    frame = max(32, int(round(frame_seconds * sample_rate)))
    hop = max(1, int(round(hop_seconds * sample_rate)))
    if signal.size < 3 * frame:
        # Too short to estimate a floor from; a copy keeps the contract that
        # this function never returns its input buffer.
        return signal.astype(np.float32, copy=True)

    frames, window, padded_size, n_frames = _stft_frames(signal, frame, hop)
    spectrum = np.fft.rfft(frames, axis=1)
    magnitude = np.abs(spectrum)
    freqs = np.fft.rfftfreq(frame, 1.0 / sample_rate)

    # The floor of each bin: its magnitude in the quietest ``percentile`` % of
    # frames.
    floor = np.percentile(magnitude, percentile, axis=0)

    # Compare with the spectral neighbours so a partial (a peak) is not read
    # as floor.  The edges of the convolution are zero-padded, so they fall
    # back to the bin itself, which never protects by accident.
    width = max(1, min(int(peak_protect_bins), (floor.size - 1) // 2))
    kernel = np.ones(2 * width + 1, dtype=np.float64) / (2 * width + 1)
    pedestal = np.convolve(floor, kernel, mode="same")[: floor.size]
    pedestal[:width] = floor[:width]
    pedestal[-width:] = floor[-width:]
    partial = floor > pedestal * (10.0 ** (peak_protect_db / 20.0))

    ceiling_gain = 10.0 ** (-max_reduction_db / 20.0)
    # Spectral subtraction: take the estimated floor out of every bin, but
    # never attenuate by more than ``max_reduction_db``.  ``floor_scale``
    # compensates for the percentile sitting below the noise's mean level.
    estimate = floor * max(float(floor_scale), 0.0)
    gain = 1.0 - estimate[None, :] / np.maximum(magnitude, 1e-12)
    gain = np.clip(gain, ceiling_gain, 1.0)
    gain[:, partial] = 1.0
    gain[:, freqs < cutoff_hz] = 1.0

    # Smooth in time so the gate cannot chatter on individual frames.
    gain = _smooth_gain_over_time(gain, smooth_frames)

    rendered = np.fft.irfft(spectrum * gain, n=frame, axis=1) * window
    return _overlap_add(rendered, window, hop, padded_size, n_frames, signal)


def _stft_frames(
    signal: np.ndarray, frame: int, hop: int
) -> tuple[np.ndarray, np.ndarray, int, int]:
    """Reflect-pad *signal* and window it into overlapping frames.

    Reflecting first means the analysis window (which is zero at its ends)
    never sits on a sample that has no neighbour to reconstruct it from.
    """
    window = np.hanning(frame).astype(np.float64)
    padded = np.pad(signal.astype(np.float64), (frame, frame), mode="reflect")
    n_frames = 1 + (padded.size - frame) // hop
    starts = hop * np.arange(n_frames)
    frames = padded[starts[:, None] + np.arange(frame)[None, :]] * window
    return frames, window, padded.size, n_frames


def _overlap_add(
    rendered: np.ndarray,
    window: np.ndarray,
    hop: int,
    padded_size: int,
    n_frames: int,
    source: np.ndarray,
) -> np.ndarray:
    """Windowed overlap-add, normalised so a pass-through reconstructs exactly."""
    frame = window.size
    total = np.zeros(padded_size, dtype=np.float64)
    norm = np.zeros(padded_size, dtype=np.float64)
    for index in range(n_frames):
        begin = index * hop
        end = begin + frame
        total[begin:end] += rendered[index]
        norm[begin:end] += window ** 2
    total /= np.maximum(norm, 1e-12)
    return total[frame:frame + source.size].astype(np.float32)


def _smooth_gain_over_time(gain: np.ndarray, smooth_frames: int) -> np.ndarray:
    """Moving-average *gain* along time with edge replication."""
    smoothing = max(1, int(smooth_frames))
    frames = gain.shape[0]
    if smoothing <= 1 or frames <= 1:
        return gain
    pad = smoothing // 2
    # ``pad`` samples of replication on each side make the centred window
    # sum to exactly ``frames`` samples for every output index.
    extended = np.pad(gain, ((pad, pad), (0, 0)), mode="edge")
    smoothed = np.zeros_like(gain)
    for offset in range(smoothing):
        smoothed += extended[offset:offset + frames, :]
    return smoothed / smoothing


def tilt_high_band(
    audio: np.ndarray,
    sample_rate: int = MUSICGEN_SAMPLE_RATE,
    *,
    frame_seconds: float = NOISE_FRAME_SECONDS,
    hop_seconds: float = NOISE_HOP_SECONDS,
    body_band: tuple[float, float] = HF_TILT_BODY_BAND,
    tilt_band: tuple[float, float] = HF_TILT_BAND,
    target_db: float = HF_TILT_TARGET_DB,
    max_reduction_db: float = HF_TILT_MAX_DB,
    smooth_seconds: float = HF_TILT_SMOOTH_SECONDS,
    ramp_band: tuple[float, float] = HF_TILT_RAMP_BAND,
) -> np.ndarray:
    """Pull back the high band when it is disproportionately loud.

    Measured on a reported track, the 2-6 kHz band sat 27-35 dB below the
    500 Hz-2 kHz body through the clean middle and only 9-14 dB below it
    across the closing 35 s — the "high frequency noise that grows much
    worse near the end".  The
    gate in :func:`reduce_noise_floor` removes a *stationary floor*, but it
    deliberately leaves spectral peaks alone, so bright high-register content
    survives it.  This stage handles that remainder.

    The amount of high band is compared with the body frame by frame, and
    everything above ``target_db`` is pulled down, capped at
    ``max_reduction_db``.  The correction is smoothed over ``smooth_seconds``
    and rolled in over ``ramp_band``, so it is a slow, gentle shelf rather
    than a per-frame gate: no chattering, no timbre steps at hop seams, and
    nothing below ``ramp_band`` is touched at all.
    """
    array = np.asarray(audio, dtype=np.float32)
    if not array.size:
        return array
    if array.ndim == 2:
        channels = [
            tilt_high_band(
                array[:, channel],
                sample_rate,
                frame_seconds=frame_seconds,
                hop_seconds=hop_seconds,
                body_band=body_band,
                tilt_band=tilt_band,
                target_db=target_db,
                max_reduction_db=max_reduction_db,
                smooth_seconds=smooth_seconds,
                ramp_band=ramp_band,
            )
            for channel in range(array.shape[1])
        ]
        return np.stack(channels, axis=1).astype(np.float32)
    if array.ndim != 1:
        raise MusicGenerationError(
            f"Audio must be 1-D or 2-D, got shape {array.shape}."
        )

    frame = max(32, int(round(frame_seconds * sample_rate)))
    hop = max(1, int(round(hop_seconds * sample_rate)))
    if array.size < 3 * frame:
        return array.astype(np.float32, copy=True)

    frames, window, padded_size, n_frames = _stft_frames(array, frame, hop)
    spectrum = np.fft.rfft(frames, axis=1)
    freqs = np.fft.rfftfreq(frame, 1.0 / sample_rate)

    def band_power(low: float, high: float) -> np.ndarray:
        mask = (freqs >= low) & (freqs < high)
        if not mask.any():
            return np.zeros(n_frames, dtype=np.float64)
        return np.abs(spectrum[:, mask]) ** 2 @ np.ones(int(mask.sum()))

    body_db = 10.0 * np.log10(band_power(*body_band) + 1e-30)
    tilt_db = 10.0 * np.log10(band_power(*tilt_band) + 1e-30)

    # How far the high band sticks out above where it should sit, in dB.
    excess = (tilt_db - body_db) + float(target_db)
    amount = np.clip(excess, 0.0, float(max_reduction_db))

    # Slow, centred smoothing so the shelf glides across hop seams instead of
    # stepping, and so a single bright hit cannot duck the whole passage.
    smooth = max(1, int(round(smooth_seconds / hop_seconds)))
    pad = smooth // 2
    extended = np.pad(amount, (pad, pad), mode="edge")
    kernel = np.ones(smooth, dtype=np.float64) / smooth
    amount = np.convolve(extended, kernel, mode="same")[pad:pad + n_frames]

    # Roll the correction in across ``ramp_band`` so it is a shelf, not a wall.
    low_hz, high_hz = ramp_band
    if high_hz <= low_hz:
        shelf = np.ones(freqs.size, dtype=np.float64)
    else:
        position = np.clip(
            (np.log(np.maximum(freqs, 1e-6)) - math.log(low_hz))
            / (math.log(high_hz) - math.log(low_hz)),
            0.0,
            1.0,
        )
        shelf = position

    gain = 10.0 ** (-(amount[:, None] * shelf[None, :]) / 20.0)
    rendered = np.fft.irfft(spectrum * gain, n=frame, axis=1) * window
    return _overlap_add(rendered, window, hop, padded_size, n_frames, array)


def apply_tail_fade(
    audio: np.ndarray,
    sample_rate: int = MUSICGEN_SAMPLE_RATE,
    fade_seconds: float = TAIL_FADE_SECONDS,
    max_fraction: float = TAIL_FADE_MAX_FRACTION,
) -> np.ndarray:
    """Fade the last *fade_seconds* of *audio* out to silence.

    A generated score otherwise stops dead: the video ends with it, so the
    music should resolve into silence rather than cut off mid-note.  The curve
    is a cosine (equal power), which keeps perceived loudness falling smoothly
    and leaves the final sample exactly zero.  Short clips get a proportionally
    shorter fade so they keep a recognisable ending.
    """
    array = np.asarray(audio, dtype=np.float32)
    if not array.size or fade_seconds <= 0:
        return array
    length = int(array.shape[0])
    fade = min(int(round(fade_seconds * sample_rate)), int(length * max_fraction))
    if fade < 2:
        return array
    curve = np.cos(np.linspace(0.0, math.pi / 2.0, fade, dtype=np.float64))
    faded = array.copy()
    tail = faded[-fade:]
    if faded.ndim > 1:
        curve = curve[:, None]
    faded[-fade:] = tail * curve.astype(np.float32)
    return faded


def detect_tail_fade_seconds(
    audio: np.ndarray,
    sample_rate: int = MUSICGEN_SAMPLE_RATE,
    *,
    max_seconds: float = 8.0,
    window_seconds: float = 0.05,
    end_window_seconds: float = 0.01,
    drop_ratio: float = 0.15,
    start_ratio: float = 0.5,
) -> float:
    """Length of the fade-out that already ends *audio*, or ``0.0``.

    The generated soundtrack now resolves into silence on its own, so the
    render-time mix must not fade the same region a second time — two fades
    stacked would cut the music out several seconds early.  The test is strict
    on purpose: the tail has to decay monotonically to near silence *and* start
    from around the loudest level of the scanned region.  A track that simply
    ends at normal level therefore still gets the mix's own fade.

    The endpoint is measured over a short window so a brief fade (a short clip
    gets a proportionally short one) is still recognised, while the decay walk
    uses a longer window so musical variation cannot fake a fade.
    """
    array = np.asarray(audio, dtype=np.float32)
    if array.ndim > 1:
        energy = np.sum(array.astype(np.float64) ** 2, axis=1)
    else:
        energy = array.astype(np.float64) ** 2
    length = int(energy.size)
    window = max(1, int(round(window_seconds * sample_rate)))
    scan = min(length // 2, int(round(max_seconds * sample_rate)))
    if scan < 4 * window:
        return 0.0

    starts = np.arange(length - scan, length - window + 1, window)
    levels = np.array(
        [math.sqrt(float(energy[start:start + window].mean())) for start in starts]
    )
    peak = float(levels.max())
    if peak <= 0.0:
        return 0.0

    # The tail must actually reach (near) silence …
    end_window = max(1, int(round(end_window_seconds * sample_rate)))
    end_level = math.sqrt(float(energy[-end_window:].mean()))
    if end_level > drop_ratio * peak:
        return 0.0

    # … and it must decay from around the loudest level of the scanned
    # region, otherwise it is only a quiet passage, not a fade.
    index = len(levels) - 1
    while index > 0 and levels[index - 1] >= levels[index] * 0.99:
        index -= 1
    if len(levels) - index < 4:  # under 200 ms: a note ending, not a fade
        return 0.0
    if levels[index] < start_ratio * peak:
        return 0.0
    return (len(levels) - index) * window / float(sample_rate)


def _crossfade_channels(
    previous: np.ndarray,
    upcoming: np.ndarray,
    sample_rate: int,
    crossfade_seconds: float,
) -> np.ndarray:
    """``equal_power_crossfade`` for mono or multi-channel audio."""
    previous = np.asarray(previous, dtype=np.float32)
    upcoming = np.asarray(upcoming, dtype=np.float32)
    if previous.ndim == 1:
        return equal_power_crossfade(
            previous, upcoming, sample_rate, crossfade_seconds
        )
    channels = [
        equal_power_crossfade(
            previous[:, channel],
            upcoming[:, channel],
            sample_rate,
            crossfade_seconds,
        )
        for channel in range(previous.shape[1])
    ]
    return np.stack(channels, axis=1).astype(np.float32)


def loop_music_bed(
    music: np.ndarray,
    target_length: int,
    sample_rate: int,
    crossfade_seconds: float = MUSIC_LOOP_CROSSFADE_SECONDS,
) -> np.ndarray:
    """Tile *music* out to *target_length* samples with smooth joins.

    Two things the old ``np.tile`` got wrong are fixed here: the loop points
    were hard cuts (an audible click every lap), and the generated track now
    ends with a musical fade-out which must not appear in the middle of a
    longer video — so that fade is stripped from the copies that are joined
    together, and the render's own tail fade closes the video instead.
    """
    source = np.asarray(music, dtype=np.float32)
    if target_length <= 0 or not source.size:
        return source
    squeeze = source.ndim == 1
    if squeeze:
        source = source[:, None]

    fade_samples = int(
        round(detect_tail_fade_seconds(source, sample_rate) * sample_rate)
    )
    body = source[: source.shape[0] - fade_samples] if fade_samples else source
    if body.shape[0] < max(1, source.shape[0] // 2):
        body = source

    # Keep every join below half a copy so a join always makes progress.
    overlap = min(int(round(crossfade_seconds * sample_rate)), body.shape[0] // 2)
    overlap = max(overlap, 1)
    join_seconds = overlap / float(sample_rate)

    out = body
    # Growth per join; loop while another copy still would not reach the end.
    while out.shape[0] + body.shape[0] - overlap < target_length:
        out = _crossfade_channels(out, body, sample_rate, join_seconds)
    if out.shape[0] < target_length:
        out = _crossfade_channels(out, body, sample_rate, join_seconds)

    result = out[:target_length]
    return result[:, 0] if squeeze else result


def seam_gain_ramp(
    outgoing_level: float,
    head_level: float,
    target_level: float,
    overlap: int,
    *,
    max_boost_db: float = MAX_CHUNK_BOOST_DB,
) -> np.ndarray:
    """Per-sample gains gliding the incoming overlap to the right level.

    ``outgoing_level`` is the RMS the outgoing tail already has (its own
    loudness gain applied), ``head_level`` the RMS of the incoming overlap
    (the prompt copy) and ``target_level`` the loudness the incoming body is
    normalised to.  The ramp starts where the outgoing material is, so the
    seam opens without a step, and ends on the target, so the overlap hands
    over to the body without a step.  The requested level is capped at
    target/outgoing plus ``max_boost_db`` so a near-silent prompt cannot be
    amplified into hiss.
    """
    if overlap <= 0:
        return np.zeros(0, dtype=np.float32)
    if head_level <= 1e-6:
        return np.ones(overlap, dtype=np.float32)

    max_level = max(target_level, outgoing_level) * 10.0 ** (
        max_boost_db / 20.0
    )
    start = min(outgoing_level, max_level) / head_level
    end = min(target_level, max_level) / head_level
    return np.linspace(start, end, overlap, dtype=np.float32)


def overlap_correlation(previous: np.ndarray, upcoming: np.ndarray) -> float:
    """Pearson correlation of the two crossfade overlap regions."""
    a = np.asarray(previous, dtype=np.float64).reshape(-1)
    b = np.asarray(upcoming, dtype=np.float64).reshape(-1)
    size = min(a.size, b.size)
    if size == 0:
        return 0.0
    a = a[:size] - a[:size].mean()
    b = b[:size] - b[:size].mean()
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator <= 1e-12:
        return 0.0
    return float(np.clip(float(np.dot(a, b)) / denominator, -0.5, 0.99))


def _rms_level(audio: np.ndarray) -> float:
    array = np.asarray(audio, dtype=np.float64).reshape(-1)
    if not array.size:
        return 0.0
    return float(np.sqrt(np.mean(array ** 2)))


def equal_power_crossfade(
    previous: np.ndarray,
    upcoming: np.ndarray,
    sample_rate: int = MUSICGEN_SAMPLE_RATE,
    crossfade_seconds: float = CROSSFADE_SECONDS,
) -> np.ndarray:
    """Join two waveforms with a correlation-corrected crossfade.

    The overlap is (almost always) the *same* music twice: the outgoing tail
    is fed back as the continuation prompt and re-emitted at the head of the
    incoming chunk.  Blending two correlated copies with a textbook
    equal-power pair raises the level by up to +3 dB mid-seam, which is
    audible as a swell at every block change.  The actual correlation of the
    overlap is therefore measured and the curve corrected so that:

    * ``rho = 1`` (duplicated audio) collapses to a linear crossfade, keeping
      the level flat through the seam,
    * ``rho = 0`` (unrelated audio) keeps ``cos² + sin² = 1``, so independent
      material keeps constant power with no dip.
    """
    previous = np.asarray(previous, dtype=np.float32).reshape(-1)
    upcoming = np.asarray(upcoming, dtype=np.float32).reshape(-1)
    if previous.size == 0:
        return upcoming.copy()
    if upcoming.size == 0:
        return previous.copy()

    overlap = min(
        int(round(crossfade_seconds * sample_rate)),
        previous.size,
        upcoming.size,
    )
    if overlap <= 1:
        return np.concatenate([previous, upcoming]).astype(np.float32)

    # Equal-power curve sampled so fade-out ends at ~0 and fade-in at ~1.
    t = np.linspace(0.0, math.pi / 2.0, overlap, endpoint=False, dtype=np.float64)
    rho = overlap_correlation(previous[-overlap:], upcoming[:overlap])
    correction = 1.0 / np.sqrt(np.maximum(1e-6, 1.0 + rho * np.sin(2.0 * t)))
    correction = np.clip(correction, 0.5, 1.5).astype(np.float32)
    fade_out = (np.cos(t) * correction).astype(np.float32)
    fade_in = (np.sin(t) * correction).astype(np.float32)

    blended = previous[-overlap:] * fade_out + upcoming[:overlap] * fade_in
    return np.concatenate(
        [previous[:-overlap], blended, upcoming[overlap:]]
    ).astype(np.float32)


def stitch_audio_segments(
    chunks: Iterable[np.ndarray],
    sample_rate: int = MUSICGEN_SAMPLE_RATE,
    crossfade_seconds: float = CROSSFADE_SECONDS,
    gains: Sequence[float] | None = None,
    *,
    target_dbfs: float = TARGET_CHUNK_RMS_DBFS,
    max_boost_db: float = MAX_CHUNK_BOOST_DB,
) -> np.ndarray:
    """Crossfade-stitch an iterable of waveforms into one continuous track.

    ``gains`` come from :func:`loudness_gains` and set each block's body to
    the same loudness.  The overlap, however, is the previous block's tail
    repeated verbatim by the continuation prompt, so giving the incoming
    chunk its own gain there would step the level by the ratio of the two
    gains (measured at 10 dB in real tracks).  The overlap is therefore
    *glided* instead:

    * it starts at the level the outgoing tail actually has, so the seam
      begins without a step, and
    * it ends at the target loudness, so it hands over to the incoming body
      without a step either.
    """
    chunk_list = [
        np.asarray(chunk, dtype=np.float32).reshape(-1) for chunk in chunks
    ]
    if not chunk_list:
        raise MusicGenerationError("No audio chunks were generated.")
    if gains is None:
        gains = [1.0] * len(chunk_list)
    gains = list(gains)
    if len(gains) != len(chunk_list):
        raise MusicGenerationError(
            "Each generated chunk needs exactly one loudness gain."
        )

    target_level = 10.0 ** (target_dbfs / 20.0)
    result = (chunk_list[0] * np.float32(gains[0])).astype(np.float32)
    for index in range(1, len(chunk_list)):
        chunk = chunk_list[index]
        overlap = min(
            int(round(crossfade_seconds * sample_rate)),
            result.size,
            chunk.size,
        )
        scaled = (chunk * np.float32(gains[index])).astype(np.float32)
        if overlap > 1:
            head = chunk[:overlap]
            ramp = seam_gain_ramp(
                _rms_level(result[-overlap:]),
                _rms_level(head),
                target_level,
                overlap,
                max_boost_db=max_boost_db,
            )
            if ramp.size == overlap and not np.all(ramp == 1.0):
                scaled[:overlap] = head * ramp
        result = equal_power_crossfade(
            result, scaled, sample_rate, crossfade_seconds
        )
    return result


# ── Model lifecycle ───────────────────────────────────────────────────────


def release_tts_resources() -> list[str]:
    """Unload every resident TTS model before MusicGen takes the GPU.

    The target machine has 6 GB of VRAM, so Qwen3-TTS (child process) and
    Kokoro (ONNX) must be evicted *before* MusicGen-Small is loaded.  The
    TaskManager runs one job at a time, so this is safe to call from the
    music worker: no TTS inference can be in flight.

    Returns the names of the resources that were actually released.
    """
    released: list[str] = []

    try:
        from core_engine.model_loader import KokoroModelLoader

        if KokoroModelLoader.unload():
            released.append('kokoro')
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not unload Kokoro before MusicGen: %s", exc)

    try:
        from core_engine import qwen_client

        # shutdown() stops the worker process, which is the only way to
        # guarantee its CUDA context no longer holds VRAM.
        qwen_client.shutdown()
        released.append('qwen')
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not unload Qwen TTS before MusicGen: %s", exc)

    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:  # pragma: no cover - torch may be absent
        pass

    logger.info("Released TTS resources before MusicGen: %s", released or 'none')
    return released


def load_musicgen(device: str | None = None, *, force_reload: bool = False):
    """Load MusicGen-Small in half precision and return the model.

    The model is cached in-process (the API serialises requests through a
    single worker) and guarded by ``_MODEL_LOCK`` so two generations can
    never allocate VRAM at the same time.
    """
    global _CACHED_MODEL

    with _MODEL_LOCK:
        if _CACHED_MODEL is not None and not force_reload:
            return _CACHED_MODEL

        try:
            import torch
        except Exception as exc:  # pragma: no cover - broken installs
            raise MusicGenerationError(
                "PyTorch is required for MusicGen. Install a CUDA build of "
                "torch first."
            ) from exc

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda" and not torch.cuda.is_available():
            raise MusicGenerationError(
                "CUDA is required for MusicGen. Verify `torch.cuda.is_available()`."
            )
        if device == "cpu" and not _allow_cpu():
            raise MusicGenerationError(
                "MusicGen is configured for CUDA but only CPU is available. "
                "Install a CUDA PyTorch build or set MUSICGEN_ALLOW_CPU=1."
            )

        try:
            from audiocraft.models import MusicGen
        except Exception as exc:
            raise MusicGenerationError(
                "AudioCraft is not installed. Run `pip install audiocraft` in "
                "a Python 3.9-3.12 environment with CUDA PyTorch."
            ) from exc

        try:
            model = MusicGen.get_pretrained(MUSICGEN_MODEL, device=device)
            if device == "cuda":
                # Half precision keeps the 300M checkpoint around 1.2 GB VRAM.
                model.lm = model.lm.to(dtype=torch.float16)
            model.set_generation_params(use_sampling=True, top_k=250)
        except Exception as exc:
            raise MusicGenerationError(
                f"MusicGen failed to load ({MUSICGEN_MODEL}): {exc}"
            ) from exc

        _CACHED_MODEL = model
        logger.info("MusicGen loaded on %s (half precision).", device)
        return model


def load_transformers_musicgen(model_dir: str, device: str = "cuda"):
    """Load the same MusicGen-Small weights through Hugging Face Transformers.

    Transformers implements the identical AudioCraft MusicGen checkpoint
    (``facebook/musicgen-small``) and works with the CUDA Python 3.11
    environment already used by Qwen TTS, so the Django process can delegate
    inference to a GPU worker without installing AudioCraft on Python 3.14.
    """
    try:
        import torch
        from transformers import AutoProcessor, MusicgenForConditionalGeneration
    except Exception as exc:  # pragma: no cover - depends on worker env
        raise MusicGenerationError(
            "Transformers/torch could not be imported in the MusicGen worker."
        ) from exc

    if device == "cuda" and not torch.cuda.is_available():
        raise MusicGenerationError(
            "CUDA is not available in the MusicGen worker environment."
        )
    if not os.path.isdir(model_dir):
        raise MusicGenerationError(
            f"MusicGen model not found at {model_dir}. Download it from "
            "https://huggingface.co/facebook/musicgen-small."
        )

    dtype = torch.float16 if device == "cuda" else torch.float32
    try:
        model = MusicgenForConditionalGeneration.from_pretrained(
            model_dir,
            dtype=dtype,
            low_cpu_mem_usage=True,
        )
        model.to(device)
        model.eval()
        processor = AutoProcessor.from_pretrained(model_dir)
    except Exception as exc:
        raise MusicGenerationError(
            f"Could not load MusicGen from {model_dir}: {exc}"
        ) from exc

    sample_rate = int(
        getattr(
            getattr(model.config, "audio_encoder", None),
            "sampling_rate",
            MUSICGEN_SAMPLE_RATE,
        )
    )
    logger.info(
        "Transformers MusicGen loaded from %s on %s (%.1f GB VRAM).",
        model_dir,
        device,
        (torch.cuda.memory_allocated(0) / 1e9) if device == "cuda" else 0.0,
    )
    return model, processor, sample_rate


def _transformers_tokens_per_second(model) -> int:
    """Decoder frames per audio second (EnCodec emits 50 frames/second).

    Transformers' MusicGen ``max_new_tokens`` counts *frames per codebook*,
    not the interleaved codebook total.  One second of audio therefore needs
    ``frame_rate`` new tokens (50 for the official checkpoints).
    """
    audio_encoder = getattr(model.config, "audio_encoder", None)
    frame_rate = getattr(audio_encoder, "frame_rate", None)
    try:
        return max(1, int(frame_rate) if frame_rate else 50)
    except (TypeError, ValueError):
        return 50


def _generate_transformers_chunk(
    model,
    processor,
    prompt: str,
    duration: float,
    continuation=None,
    device: str = "cuda",
):
    """Generate one MusicGen chunk (cold start or audio-prompt continuation)."""
    import torch

    duration = max(0.5, float(duration))
    frames = int(round(duration * _transformers_tokens_per_second(model)))
    # MusicGen's codebook delay pattern trims (num_codebooks - 1) frames when
    # the generated ids are de-interleaved; add them back so the decoded audio
    # matches the requested duration.
    num_codebooks = int(getattr(model.config.decoder, "num_codebooks", 4) or 4)
    max_new_tokens = max(1, frames + max(0, num_codebooks - 1))

    try:
        inputs = processor(
            text=[prompt],
            padding=True,
            return_tensors="pt",
        ).to(device)
        kwargs = {
            "do_sample": True,
            "guidance_scale": 3.0,
            "max_new_tokens": max_new_tokens,
        }
        if continuation is not None and len(continuation):
            # The whole model (including the EnCodec audio encoder) is loaded
            # in FP16 on CUDA, so the acoustic prompt must match that dtype.
            model_dtype = next(model.parameters()).dtype
            prompt_tensor = torch.from_numpy(
                np.asarray(continuation, dtype=np.float32).reshape(1, 1, -1)
            ).to(device=device, dtype=model_dtype)
            kwargs["input_values"] = prompt_tensor

        with torch.inference_mode():
            audio = model.generate(**inputs, **kwargs)
    except Exception as exc:
        raise MusicGenerationError(
            f"MusicGen (Transformers) inference failed: {exc}"
        ) from exc

    return _to_mono_float32(audio)


def plan_generation_hops(
    segments: Sequence[MusicSegment],
    max_seconds: float = MAX_GENERATION_SECONDS,
) -> list[tuple[int, float]]:
    """Split every script block into hops no longer than *max_seconds*.

    MusicGen drifts during long continuations: measured on the target GPU, a
    33 s hop produced peaks above 1.5 (hard clipping when written) and a 27 dB
    loudness swing inside one block, while 12 s hops stayed clean.  A 33.6 s
    block therefore becomes 12 + 12 + 9.6 s of new audio, each hop
    conditioned on the 3 s tail of the previous one and reusing its block's
    prompt, so the block stays musically continuous.
    """
    limit = max(0.5, float(max_seconds))
    hops: list[tuple[int, float]] = []
    for position, segment in enumerate(segments):
        remaining = float(segment.safe_duration)
        while remaining > 1e-6:
            requested = min(remaining, limit)
            leftover = remaining - requested
            if 0.0 < leftover < 0.5:
                # A sliver shorter than the model's 0.5 s floor would be
                # generated at 0.5 s and lengthen the track; fold it into this
                # hop instead (at most 0.5 s over the soft limit).
                requested = remaining
                leftover = 0.0
            hops.append((position, requested))
            remaining = leftover
    return hops


def synthesize_soundtrack_transformers(
    segments,
    output_path: str,
    *,
    model_dir: str,
    plan: MusicPlan | None = None,
    crossfade_seconds: float = CROSSFADE_SECONDS,
    bpm: int | None = None,
    root_key: str | None = None,
    mode: str | None = None,
    style: str = "instrumental cinematic documentary score",
    progress: Callable[[int, int, str], None] | None = None,
    device: str = "cuda",
) -> dict:
    """Generate the full soundtrack with Transformers on a CUDA GPU.

    This is the worker-side implementation used on machines where Django runs
    on a Python version that AudioCraft cannot import.  The model is fully
    unloaded when the worker exits, so VRAM returns to the OS.
    """
    segments = normalise_segments(segments)
    plan = plan or plan_music(
        segments, bpm=bpm, root_key=root_key, mode=mode, style=style
    )

    model, processor, sample_rate = load_transformers_musicgen(
        model_dir, device=device
    )
    total = len(segments)
    hops = plan_generation_hops(segments)
    total_steps = len(hops)
    chunks: list[np.ndarray] = []
    last_raw: np.ndarray | None = None
    tail_samples = int(round(CONTINUATION_TAIL_SECONDS * sample_rate))

    try:
        for step, (position, requested) in enumerate(hops):
            continuation = None
            if step > 0 and last_raw is not None and last_raw.size:
                tail = last_raw[-tail_samples:] if last_raw.size > tail_samples else last_raw
                continuation = tail

            # Transformers returns the audio prompt *plus* the requested
            # continuation, so a hop only asks for the new Δt seconds.  The 3 s
            # overlap is supplied by the prompt and removed by the
            # correlation-corrected crossfade below.
            logger.info(
                "Transformers MusicGen hop %d/%d (block %d/%d) — duration=%.2fs%s",
                step + 1,
                total_steps,
                position + 1,
                total,
                requested,
                " (continuation)" if continuation is not None else " (cold)",
            )
            chunk = _generate_transformers_chunk(
                model,
                processor,
                plan.prompts[position],
                requested,
                continuation,
                device=device,
            )
            # Strip each hop's stationary floor *before* loudness matching:
            # otherwise the boost a quiet hop needs pumps that floor, and it
            # switches on and off at hop boundaries as audible high-frequency
            # noise (Issue #13).
            chunk = reduce_noise_floor(chunk, sample_rate)
            chunks.append(chunk)
            last_raw = chunk
            if progress:
                progress(
                    step + 1,
                    total_steps,
                    f"Generated music {step + 1}/{total_steps}",
                )

        gains = loudness_gains(
            chunks,
            sample_rate=sample_rate,
            crossfade_seconds=crossfade_seconds,
        )
        stitched = stitch_audio_segments(
            chunks,
            sample_rate=sample_rate,
            crossfade_seconds=crossfade_seconds,
            gains=gains,
        )
        # Pull back the high band where it has grown out of proportion to the
        # body (Issue #13): a slow shelf across the whole track, so it glides
        # across the seams instead of stepping.
        stitched = tilt_high_band(stitched, sample_rate)
        # Never clip: decoded hops regularly exceed ±1.0 and hard clipping is
        # what made the end of a track sound harsh.  Tame isolated peaks first
        # so the ceiling does not have to scale the whole track down.
        stitched = tame_peaks(stitched, sample_rate=sample_rate)
        stitched = scale_to_ceiling(stitched)
        # … and resolve into silence instead of stopping dead under the last
        # frame of the video.
        stitched = apply_tail_fade(stitched, sample_rate)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        import soundfile as sf

        sf.write(
            output_path,
            np.clip(stitched, -1.0, 1.0),
            sample_rate,
            subtype="PCM_16",
        )
        duration = len(stitched) / float(sample_rate)
        return {
            "output_path": output_path,
            "duration": round(duration, 3),
            "sample_rate": sample_rate,
            "segments": total,
            "generation_steps": total_steps,
            "crossfade_seconds": crossfade_seconds,
            "chunk_durations": [
                round(len(chunk) / float(sample_rate), 3) for chunk in chunks
            ],
            "chunk_gains_db": [round(20.0 * math.log10(gain), 2) for gain in gains],
            "target_rms_dbfs": TARGET_CHUNK_RMS_DBFS,
            "noise_reduction_db": MAX_NOISE_REDUCTION_DB,
            "tail_fade_seconds": TAIL_FADE_SECONDS,
            "master_peak": round(float(np.max(np.abs(stitched))), 4),
            "master_tail_level_db": round(rms_dbfs(stitched[-sample_rate:]), 2),
            "device": device,
            "backend": "transformers",
            "model_dir": model_dir,
            "plan": plan.to_dict(),
        }
    finally:
        # The worker process normally exits immediately after this, but keep
        # the explicit release so a reused worker also returns VRAM.
        try:
            del model
            del processor
        except UnboundLocalError:  # pragma: no cover
            pass
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except Exception:  # pragma: no cover
            pass


def cleanup_model(model=None) -> None:
    """Drop the cached model and flush CUDA memory (VRAM protection)."""
    global _CACHED_MODEL
    target = model if model is not None else _CACHED_MODEL
    if target is not None and target is _CACHED_MODEL:
        _CACHED_MODEL = None
    try:
        del target
    except UnboundLocalError:  # pragma: no cover - defensive
        pass
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("CUDA cache flushed after MusicGen generation.")
    except Exception:  # pragma: no cover - torch always present in production
        pass


# ── Generation ────────────────────────────────────────────────────────────


def _generate_chunk(model, prompt: str, duration: float, continuation=None):
    """Call MusicGen (cold start or continuation) and return a float32 array."""
    duration = max(0.5, float(duration))
    try:
        model.set_generation_params(duration=duration)
    except Exception:
        # Older AudioCraft builds accept duration on generate() instead.
        pass

    try:
        if continuation is None:
            wav = model.generate([prompt], progress=False)
        else:
            import torch

            prompt_tensor = torch.from_numpy(
                np.asarray(continuation, dtype=np.float32).reshape(1, 1, -1)
            )
            try:
                wav = model.generate_continuation(
                    prompt_tensor,
                    MUSICGEN_SAMPLE_RATE,
                    [prompt],
                    progress=False,
                )
            except TypeError:
                wav = model.generate_continuation(
                    prompt_tensor,
                    MUSICGEN_SAMPLE_RATE,
                    [prompt],
                )
    except MusicGenerationError:
        raise
    except Exception as exc:
        raise MusicGenerationError(f"MusicGen inference failed: {exc}") from exc

    chunk = _to_mono_float32(wav)
    if chunk.size == 0:
        raise MusicGenerationError("MusicGen returned an empty waveform.")
    return chunk


def synthesize_soundtrack(
    segments,
    output_path: str,
    *,
    model=None,
    plan: MusicPlan | None = None,
    sample_rate: int = MUSICGEN_SAMPLE_RATE,
    crossfade_seconds: float = CROSSFADE_SECONDS,
    bpm: int | None = None,
    root_key: str | None = None,
    mode: str | None = None,
    style: str = "instrumental cinematic documentary score",
    progress: Callable[[int, int, str], None] | None = None,
    unload_after: bool = True,
) -> dict:
    """Generate and stitch the full soundtrack for *segments*.

    The pipeline is strictly sequential: only one segment is on the GPU at a
    time, and the model is unloaded (GC + ``torch.cuda.empty_cache()``) when
    the loop finishes.
    """
    segments = normalise_segments(segments)
    plan = plan or plan_music(
        segments, bpm=bpm, root_key=root_key, mode=mode, style=style
    )

    # On this installation the Django runtime is Python 3.14/CPU-only, while
    # the CUDA worker lives in the shared Python 3.11 TTS venv.  Prefer the
    # external worker so inference never falls back to the CPU.
    if model is None:
        from core_engine import musicgen_client

        if musicgen_client.is_available():
            # Fail loudly instead of silently falling back to CPU inference.
            return musicgen_client.run_soundtrack(
                segments=segments,
                plan=plan,
                output_path=output_path,
                sample_rate=sample_rate,
                crossfade_seconds=crossfade_seconds,
                progress=progress,
            )

    owns_model = model is None
    if model is None:
        model = load_musicgen()

    total = len(segments)
    chunks: list[np.ndarray] = []
    last_raw: np.ndarray | None = None
    tail_samples = int(round(CONTINUATION_TAIL_SECONDS * sample_rate))

    try:
        for position, segment in enumerate(segments):
            duration = segment.safe_duration
            continuation = None
            target_duration = duration

            if position > 0 and last_raw is not None and last_raw.size:
                tail = last_raw[-tail_samples:] if last_raw.size > tail_samples else last_raw
                continuation = tail
                # Generate the overlap too, then crossfade it away.
                target_duration = duration + crossfade_seconds

            logger.info(
                "MusicGen segment %d/%d — prompt=%r duration=%.2fs%s",
                position + 1,
                total,
                plan.prompts[position],
                target_duration,
                " (continuation)" if continuation is not None else " (cold)",
            )
            chunk = _generate_chunk(
                model, plan.prompts[position], target_duration, continuation
            )
            # Strip the hop's stationary floor before loudness matching so the
            # boost a quiet hop needs cannot pump it into audible hiss.
            chunk = reduce_noise_floor(chunk, sample_rate)
            chunks.append(chunk)
            last_raw = chunk
            if progress:
                progress(
                    position + 1,
                    total,
                    f"Generated music {position + 1}/{total}",
                )

        gains = loudness_gains(
            chunks,
            sample_rate=sample_rate,
            crossfade_seconds=crossfade_seconds,
        )
        stitched = stitch_audio_segments(
            chunks,
            sample_rate=sample_rate,
            crossfade_seconds=crossfade_seconds,
            gains=gains,
        )
        # Pull back the high band where it has grown out of proportion to the
        # body (Issue #13).
        stitched = tilt_high_band(stitched, sample_rate)
        # Scale, never clip: MusicGen can decode above ±1.0.
        stitched = tame_peaks(stitched, sample_rate=sample_rate)
        stitched = scale_to_ceiling(stitched)
        # … then resolve into silence instead of stopping dead.
        stitched = apply_tail_fade(stitched, sample_rate)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        import soundfile as sf

        sf.write(
            output_path,
            np.clip(stitched, -1.0, 1.0),
            sample_rate,
            subtype="PCM_16",
        )
    finally:
        if owns_model and unload_after:
            cleanup_model(model)

    duration = len(stitched) / float(sample_rate)
    logger.info(
        "Soundtrack written to %s (%.2fs, %d segment(s)).",
        output_path,
        duration,
        total,
    )
    return {
        "output_path": output_path,
        "duration": round(duration, 3),
        "sample_rate": sample_rate,
        "segments": total,
        "generation_steps": len(chunks),
        "crossfade_seconds": crossfade_seconds,
        "chunk_gains_db": [round(20.0 * math.log10(gain), 2) for gain in gains],
        "target_rms_dbfs": TARGET_CHUNK_RMS_DBFS,
        "noise_reduction_db": MAX_NOISE_REDUCTION_DB,
        "tail_fade_seconds": TAIL_FADE_SECONDS,
        "master_peak": round(float(np.max(np.abs(stitched))), 4),
        "master_tail_level_db": round(rms_dbfs(stitched[-sample_rate:]), 2),
        "plan": plan.to_dict(),
    }


# ── Narration / music multiplexing (side-chain ducking) ──────────────────


def _decode_audio(path: str, sample_rate: int) -> np.ndarray:
    """Read *path* as a (samples, 2) float32 array at *sample_rate*.

    ``soundfile`` handles WAV/FLAC/Ogg and recent libsndfile builds also
    support MP3.  Anything it cannot read is decoded through FFmpeg.
    """
    try:
        import soundfile as sf

        data, source_rate = sf.read(
            path, always_2d=True, dtype="float32"
        )
        data = np.asarray(data, dtype=np.float32)
        if source_rate != sample_rate:
            data = _resample(data, source_rate, sample_rate)
        return _to_stereo(data)
    except Exception:
        pass

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise MusicGenerationError(
            "FFmpeg is required to decode MP3 music for mixing."
        )
    handle, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(handle)
    try:
        result = subprocess.run(
            [
                ffmpeg,
                "-nostdin",
                "-y",
                "-i",
                path,
                "-ac",
                "2",
                "-ar",
                str(sample_rate),
                "-f",
                "wav",
                wav_path,
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise MusicGenerationError(
                "Could not decode the music track with FFmpeg."
            )
        import soundfile as sf

        data, _rate = sf.read(wav_path, always_2d=True, dtype="float32")
        return _to_stereo(np.asarray(data, dtype=np.float32))
    finally:
        try:
            os.remove(wav_path)
        except OSError:
            pass


def _to_stereo(data: np.ndarray) -> np.ndarray:
    array = np.asarray(data, dtype=np.float32)
    if array.ndim == 1:
        array = array.reshape(-1, 1)
    if array.shape[1] == 1:
        array = np.repeat(array, 2, axis=1)
    elif array.shape[1] > 2:
        array = array[:, :2]
    return array


def _resample(data: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate or source_rate <= 0:
        return data
    target_length = max(1, int(round(len(data) * target_rate / source_rate)))
    source_positions = np.linspace(0, len(data) - 1, num=len(data))
    target_positions = np.linspace(0, len(data) - 1, num=target_length)
    channels = [
        np.interp(target_positions, source_positions, data[:, channel])
        for channel in range(data.shape[1])
    ]
    return np.stack(channels, axis=1).astype(np.float32)


def _voice_ducking_envelope(
    narration: np.ndarray,
    sample_rate: int,
    ducking_db: float = DEFAULT_DUCKING_DB,
    threshold_db: float = -38.0,
    attack_seconds: float = 0.025,
    release_seconds: float = 0.30,
) -> np.ndarray:
    """Return a per-sample gain curve that ducks music under active speech."""
    mono = np.mean(np.abs(narration), axis=1).astype(np.float32)
    if mono.size == 0:
        return np.ones(0, dtype=np.float32)

    # 50 ms RMS windows, vectorised, then smoothed at ~100 Hz.
    control_rate = 100.0
    block = max(1, int(round(sample_rate / control_rate)))
    usable = (mono.size // block) * block
    if usable:
        frames = mono[:usable].reshape(-1, block)
        rms = np.sqrt(np.mean(frames * frames, axis=1))
    else:
        rms = np.array([np.sqrt(np.mean(mono * mono))], dtype=np.float32)

    rms_db = 20.0 * np.log10(np.maximum(rms, 1e-9))
    duck_gain = 10.0 ** (float(ducking_db) / 20.0)
    targets = np.where(rms_db > threshold_db, duck_gain, 1.0).astype(np.float32)

    dt = 1.0 / control_rate
    smoothed = np.empty_like(targets)
    current = 1.0
    attack_coeff = 1.0 - math.exp(-dt / max(1e-3, attack_seconds))
    release_coeff = 1.0 - math.exp(-dt / max(1e-3, release_seconds))
    for index, target in enumerate(targets):
        coeff = attack_coeff if target < current else release_coeff
        current += (target - current) * coeff
        smoothed[index] = current

    control_positions = (np.arange(smoothed.size) + 0.5) * block
    sample_positions = np.arange(mono.size)
    envelope = np.interp(sample_positions, control_positions, smoothed)
    return envelope.astype(np.float32)


def apply_music_echo(
    audio: np.ndarray,
    sample_rate: int,
    amount_percent: float = 0.0,
    *,
    delay_ms: float = 180.0,
    feedback: float = 0.35,
    taps: int = 3,
) -> np.ndarray:
    """Add a short stereo/dual-mono echo to the music bed.

    ``amount_percent`` is the wet level (0 = dry, 100 = maximum).  The echo is
    deliberately simple: a handful of decaying taps at ``delay_ms`` spacing.
    It is applied to the music only, before the bed is mixed under the
    narration, so the voice stays intelligible.
    """
    if amount_percent <= 0.0 or audio.size == 0:
        return audio

    wet = max(0.0, min(100.0, float(amount_percent))) / 100.0
    delay = max(1, int(round(sample_rate * max(1.0, delay_ms) / 1000.0)))
    echoed = audio.astype(np.float32, copy=True)
    for tap in range(1, max(1, int(taps)) + 1):
        shift = delay * tap
        if shift >= audio.shape[0]:
            break
        gain = 0.5 * wet * (feedback ** (tap - 1))
        echoed[shift:] += audio[:-shift] * gain
    return echoed


def apply_narration_gain(
    narration_path: str,
    output_path: str,
    gain_db: float = 0.0,
    *,
    sample_rate: int = 44_100,
) -> dict:
    """Scale a narration-only track by *gain_db*.

    Used by the Settings playground when no background track is selected but
    the TTS voice volume still needs to be previewed.  Writes a 16-bit WAV so
    the result can be muxed into the existing base video.
    """
    narration = _decode_audio(narration_path, sample_rate)
    if narration.size == 0:
        raise MusicGenerationError("The narration track is empty.")

    gain = 10.0 ** (float(gain_db) / 20.0)
    scaled = narration * gain
    np.clip(scaled, -1.0, 1.0, out=scaled)

    destination = os.path.abspath(str(output_path))
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    import soundfile as sf

    sf.write(destination, scaled, sample_rate, subtype="PCM_16")
    logger.info(
        "Narration gain applied: %s (%.1f dB)", destination, gain_db
    )
    return {
        "output_path": destination,
        "duration": round(narration.shape[0] / float(sample_rate), 3),
        "narration_gain_db": gain_db,
    }


def mix_background_music(
    narration_path: str,
    music_path: str,
    output_path: str | None = None,
    *,
    sample_rate: int = 44_100,
    music_gain_db: float = DEFAULT_MUSIC_GAIN_DB,
    ducking_db: float = DEFAULT_DUCKING_DB,
    echo_percent: float = 0.0,
    narration_gain_db: float = 0.0,
    ducking_threshold_db: float = -38.0,
    fade_seconds: float = 0.75,
    tail_fade_seconds: float = TAIL_FADE_SECONDS,
    loop_music: bool = True,
) -> dict:
    """Mix a music bed under a narration track with side-chain ducking.

    The music is looped/trimmed to the narration length, optionally given a
    short echo, attenuated by *music_gain_db*, then ducked by *ducking_db*
    whenever the narration RMS is above *ducking_threshold_db*.  The narration
    itself is scaled by *narration_gain_db* (0 dB leaves it untouched), which
    lets the operator balance the TTS voice against the music.  The result is
    written as a 16-bit WAV.

    ``fade_seconds`` fades the bed in so the start (and every loop point) is
    click-free.  ``tail_fade_seconds`` closes the video smoothly — unless the
    music already ends with a fade of its own, in which case fading again
    would cut it out several seconds early.
    """
    narration = _decode_audio(narration_path, sample_rate)
    music = _decode_audio(music_path, sample_rate)

    if narration.size == 0:
        raise MusicGenerationError("The narration track is empty.")
    if music.size == 0:
        raise MusicGenerationError("The music track is empty.")

    target_length = narration.shape[0]
    if music.shape[0] < target_length:
        if loop_music:
            music = loop_music_bed(music, target_length, sample_rate)
        else:
            pad = target_length - music.shape[0]
            music = np.pad(music, ((0, pad), (0, 0)))
    music = music[:target_length]
    music = apply_music_echo(music, sample_rate, echo_percent)

    envelope = _voice_ducking_envelope(
        narration,
        sample_rate,
        ducking_db=ducking_db,
        threshold_db=ducking_threshold_db,
    )
    base_gain = 10.0 ** (float(music_gain_db) / 20.0)
    voice_gain = 10.0 ** (float(narration_gain_db) / 20.0)

    # Does the bed already resolve into silence on its own?  Fading the same
    # region twice would pull the music out of the video far too early.
    already_faded = detect_tail_fade_seconds(music, sample_rate) > 0.0

    # Short fade in avoids a click where the bed starts (and after a loop).
    fade = min(int(fade_seconds * sample_rate), target_length // 2)
    if fade > 0:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)[:, None]
        music[:fade] *= ramp

    tail = min(int(tail_fade_seconds * sample_rate), target_length // 2)
    tail_applied = bool(tail > 0 and not already_faded)
    if tail_applied:
        ramp = np.linspace(0.0, 1.0, tail, dtype=np.float32)[:, None]
        music[-tail:] *= ramp[::-1]

    mixed = narration * voice_gain + music * (base_gain * envelope[:, None])
    np.clip(mixed, -1.0, 1.0, out=mixed)

    destination = output_path or narration_path
    temporary = None
    if os.path.abspath(destination) == os.path.abspath(narration_path):
        handle, temporary = tempfile.mkstemp(suffix=".wav")
        os.close(handle)
        destination = temporary

    import soundfile as sf

    sf.write(destination, mixed, sample_rate, subtype="PCM_16")
    if temporary:
        os.replace(temporary, narration_path)
        destination = narration_path

    logger.info(
        "Music mixed under narration: %s (gain %.1f dB, ducking %.1f dB, "
        "echo %.0f%%, voice %.1f dB, music %.2fs, narration %.2fs)",
        destination,
        music_gain_db,
        ducking_db,
        echo_percent,
        narration_gain_db,
        music.shape[0] / sample_rate,
        narration.shape[0] / sample_rate,
    )
    return {
        "output_path": destination,
        "duration": round(target_length / float(sample_rate), 3),
        "music_gain_db": music_gain_db,
        "ducking_db": ducking_db,
        "echo_percent": echo_percent,
        "narration_gain_db": narration_gain_db,
        "tail_fade_applied": tail_applied,
        "source_tail_faded": already_faded,
    }
