"""Audio-aware subtitle timing (Issue #29).

The legacy subtitle engine distributes a segment's duration across chunks by
word count.  That drifts whenever the voice pauses, slows down, or reads a
different number of words in the TTS script.  This module measures the real
speech boundaries in the generated audio and stores them on the segment:

1. Split the text that was sent to TTS into sentences.
2. Detect silence gaps in the WAV with a tiny energy VAD.
3. Snap each expected sentence boundary to the nearest real pause.
4. Keep the measured sentence spans in ``Segment.audio_timings``.
5. When rendering, split the *subtitle* text into the same sentences and
   distribute each measured span across its subtitle chunks.

Everything is standard-library + numpy/soundfile, so alignment is fast
(O(audio samples)) and does not need an ASR model.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Iterable

logger = logging.getLogger(__name__)

TIMINGS_VERSION = 1
FRAME_SECONDS = 0.02
MIN_SILENCE = 0.11
MIN_SPEECH_GAP = 0.07
PEAK_RATIO = 0.06
NOISE_MULTIPLIER = 2.5

_ABBREVIATIONS = {
    'mr', 'mrs', 'ms', 'dr', 'prof', 'st', 'jr', 'sr', 'vs', 'etc',
    'e.g', 'i.e', 'u.s', 'u.k', 'no', 'fig', 'approx',
}
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')
_WORD_CHARS = re.compile(r'[^\w]', re.UNICODE)


def split_sentences(text: str) -> list[str]:
    """Split *text* into sentences without breaking common abbreviations."""
    if not text or not text.strip():
        return []

    normalized = re.sub(r'\s+', ' ', str(text)).strip()
    raw_parts = _SENTENCE_SPLIT.split(normalized)
    sentences: list[str] = []
    buffer = ''

    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        buffer = f'{buffer} {part}'.strip() if buffer else part
        last_token = buffer.rstrip('"\'”’)]}').rsplit(' ', 1)[-1].lower()
        last_token = last_token.rstrip('.')
        if last_token in _ABBREVIATIONS:
            continue
        sentences.append(buffer)
        buffer = ''

    if buffer:
        sentences.append(buffer)
    return sentences


def _weight(text: str) -> int:
    """Character weight: closer to speech duration than raw word count."""
    return max(len(_WORD_CHARS.sub('', text)), 1)


def estimate_sentence_timings(
    text: str, total_duration: float
) -> list[dict]:
    """Proportional fallback when the audio itself cannot be analysed."""
    sentences = split_sentences(text)
    if not sentences or total_duration <= 0:
        return []

    weights = [_weight(sentence) for sentence in sentences]
    total_weight = sum(weights)
    timings: list[dict] = []
    cursor = 0.0
    for index, (sentence, weight) in enumerate(zip(sentences, weights)):
        if index == len(sentences) - 1:
            duration = max(total_duration - cursor, 0.0)
        else:
            duration = (weight / total_weight) * total_duration
        timings.append({
            'text': sentence,
            'start': round(cursor, 3),
            'duration': round(duration, 3),
            'end': round(cursor + duration, 3),
        })
        cursor += duration
    return timings


def _load_mono(audio_path: str):
    import numpy as np
    import soundfile as sf

    audio, sample_rate = sf.read(audio_path, dtype='float32', always_2d=False)
    if audio is None or len(audio) == 0:
        return None, 0
    if getattr(audio, 'ndim', 1) > 1:
        audio = audio.mean(axis=1)
    return np.asarray(audio, dtype='float32'), int(sample_rate)


def detect_silences(
    audio_path: str,
    *,
    min_silence: float = MIN_SILENCE,
    frame_seconds: float = FRAME_SECONDS,
) -> list[tuple[float, float]]:
    """Return ``(start, end)`` silence gaps detected in *audio_path*.

    A simple RMS threshold is enough for clean narration: it is O(samples),
    deterministic, and never mistakes background music for speech because the
    narration file is exported without BGM.
    """
    try:
        import numpy as np

        audio, sample_rate = _load_mono(audio_path)
        if audio is None or sample_rate <= 0:
            return []

        frame_size = max(int(sample_rate * frame_seconds), 1)
        frame_count = len(audio) // frame_size
        if frame_count < 3:
            return []

        frames = audio[: frame_count * frame_size].reshape(frame_count, frame_size)
        rms = np.sqrt(np.mean(frames * frames, axis=1))
        peak = float(np.max(rms))
        if peak <= 1e-7:
            return []
        noise = float(np.percentile(rms, 20))
        threshold = max(noise * NOISE_MULTIPLIER, peak * PEAK_RATIO, 1e-5)
        is_speech = rms > threshold

        # Close tiny drop-outs inside a word (e.g. a stop consonant).
        min_gap_frames = max(int(MIN_SPEECH_GAP / frame_seconds), 1)
        for start in range(frame_count):
            if is_speech[start]:
                continue
            end = start
            while end < frame_count and not is_speech[end]:
                end += 1
            if (
                0 < start
                and end < frame_count
                and (end - start) <= min_gap_frames
            ):
                is_speech[start:end] = True

        silences: list[tuple[float, float]] = []
        start = None
        for index, speaking in enumerate(is_speech):
            if not speaking and start is None:
                start = index
            elif speaking and start is not None:
                gap = (index - start) * frame_seconds
                if gap >= min_silence:
                    silences.append((start * frame_seconds, index * frame_seconds))
                start = None
        if start is not None:
            gap = (frame_count - start) * frame_seconds
            if gap >= min_silence:
                silences.append((start * frame_seconds, frame_count * frame_seconds))
        return silences
    except Exception as exc:  # noqa: BLE001 - timing must never break TTS
        logger.debug('Silence detection failed for %s: %s', audio_path, exc)
        return []


def _snap_boundaries(
    expected: Iterable[float],
    silences: list[tuple[float, float]],
    total_duration: float,
) -> list[float]:
    expected = list(expected)
    if not expected:
        return []
    centres = [(start + end) / 2.0 for start, end in silences if end > start]
    tolerance = max(0.35, total_duration / max(len(expected) + 1, 2) * 0.55)
    used: set[int] = set()
    snapped: list[float] = []
    latest = 0.0

    for position in expected:
        best_index = None
        best_distance = None
        for index, centre in enumerate(centres):
            if index in used:
                continue
            distance = abs(centre - position)
            if best_distance is None or distance < best_distance:
                best_index, best_distance = index, distance
        if best_index is not None and best_distance is not None and best_distance <= tolerance:
            used.add(best_index)
            value = centres[best_index]
        else:
            value = position
        value = min(max(value, 0.0), max(total_duration - 0.05, 0.0))
        if value <= latest:
            value = min(latest + 0.05, max(total_duration - 0.05, 0.0))
        snapped.append(value)
        latest = value

    return snapped


def build_audio_timings(
    text: str,
    audio_path: str,
    total_duration: float,
) -> dict:
    """Measure sentence spans for *text* inside the generated WAV."""
    if not text or not text.strip() or not total_duration or total_duration <= 0:
        return {}

    sentences = split_sentences(text)
    if not sentences:
        return {}

    weights = [_weight(sentence) for sentence in sentences]
    total_weight = sum(weights) or 1
    expected: list[float] = []
    cursor = 0.0
    for weight in weights[:-1]:
        cursor += (weight / total_weight) * total_duration
        expected.append(cursor)

    silences = detect_silences(audio_path)
    boundaries = _snap_boundaries(expected, silences, total_duration)
    points = [0.0, *boundaries, float(total_duration)]

    measured: list[dict] = []
    for index, sentence in enumerate(sentences):
        start = points[index]
        end = points[index + 1]
        if end <= start:
            end = min(start + 0.05, total_duration)
        measured.append({
            'text': sentence,
            'start': round(start, 3),
            'duration': round(max(end - start, 0.0), 3),
            'end': round(end, 3),
        })

    return {
        'version': TIMINGS_VERSION,
        'method': 'vad-snap' if silences else 'proportional',
        'total': round(float(total_duration), 3),
        'sentences': measured,
    }


def chunk_text_with_sentence_timings(
    text: str,
    total_duration: float,
    audio_timings: dict | None,
) -> tuple[list[str], list[tuple[float, float]]] | None:
    """Split subtitle text into chunks using measured sentence spans.

    Returns ``None`` when the subtitle text and the TTS text do not have the
    same sentence count; the caller then falls back to proportional timing.
    """
    if not audio_timings or not text or not text.strip():
        return None
    measured = audio_timings.get('sentences')
    if not isinstance(measured, list) or not measured:
        return None

    sentences = split_sentences(text)
    if len(sentences) != len(measured):
        return None

    from core_engine.subtitle_engine import chunk_text

    chunks: list[str] = []
    timings: list[tuple[float, float]] = []

    for sentence, entry in zip(sentences, measured):
        try:
            start = float(entry.get('start', 0.0))
            end = float(entry.get('end', start + float(entry.get('duration', 0.0))))
        except (TypeError, ValueError):
            return None
        end = min(max(end, start), float(total_duration))
        sentence_chunks = chunk_text(sentence)
        if not sentence_chunks:
            continue
        weights = [_weight(chunk) for chunk in sentence_chunks]
        weight_total = sum(weights) or 1
        cursor = start
        for index, (chunk, weight) in enumerate(zip(sentence_chunks, weights)):
            if index == len(sentence_chunks) - 1:
                duration = max(end - cursor, 0.0)
            else:
                duration = (weight / weight_total) * max(end - start, 0.0)
            chunks.append(chunk)
            timings.append((cursor, duration))
            cursor += duration

    if not chunks:
        return None
    return chunks, timings


def timings_sentence_count(audio_timings: dict | None) -> int:
    """Small helper used by the editor/tests to inspect stored timings."""
    if not isinstance(audio_timings, dict):
        return 0
    sentences = audio_timings.get('sentences')
    return len(sentences) if isinstance(sentences, list) else 0


def timing_drift_seconds(
    timings: list[tuple[float, float]], total_duration: float
) -> float:
    """Absolute difference between rendered subtitle coverage and audio."""
    if not timings:
        return float(total_duration or 0.0)
    end = timings[-1][0] + timings[-1][1]
    return abs(float(total_duration) - end)


def safe_math_isclose(a: float, b: float, tolerance: float = 0.05) -> bool:
    """Tiny wrapper so tests can express float tolerance without numpy."""
    return math.isclose(a, b, abs_tol=tolerance)
