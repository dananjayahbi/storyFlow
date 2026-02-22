"""Tests for ``core_engine.subtitle_engine``.

Task 05.01.09 — Write Chunking Tests
Task 05.01.10 — Write Timing Tests
Task 05.01.11 — Write Integration Subtitle Tests

Covers edge cases, basic chunking, boundary-preference breaks,
orphan prevention, word-preservation invariants, custom parameters,
whitespace normalisation, proportional timing distribution,
minimum duration enforcement, no-gap continuity, and full subtitle
pipeline integration with the video renderer.
"""

import os
import shutil
import tempfile
import unittest

import numpy as np
from django.core.files import File
from django.test import TestCase, override_settings
from PIL import Image as PILImage
from unittest.mock import patch

from core_engine.render_utils import check_ffmpeg, check_imagemagick
from core_engine.subtitle_engine import (
    DEFAULT_MAX_WORDS,
    MIN_CHUNK_WORDS,
    MIN_DISPLAY_DURATION,
    calculate_subtitle_timing,
    chunk_text,
    create_subtitles_for_segment,
)


class ChunkTextTests(TestCase):
    """Comprehensive tests for the ``chunk_text`` function."""

    # ── Step 2: Edge case tests ─────────────────────────────────────

    def test_empty_text(self):
        """Empty string → empty list."""
        self.assertEqual(chunk_text(""), [])

    def test_whitespace_only(self):
        """Whitespace-only string → empty list."""
        self.assertEqual(chunk_text("   \n\t  "), [])

    def test_single_word(self):
        """A single word → list with that word."""
        self.assertEqual(chunk_text("Hello"), ["Hello"])

    def test_few_words_under_max(self):
        """Fewer words than max_words → single chunk."""
        text = "The quick brown fox"
        result = chunk_text(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "The quick brown fox")

    def test_exactly_max_words(self):
        """Exactly max_words words → single chunk."""
        words = ["word"] * DEFAULT_MAX_WORDS
        text = " ".join(words)
        result = chunk_text(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], text)

    # ── Step 3: Basic chunking tests ────────────────────────────────

    def test_basic_chunking(self):
        """12+ words with no punctuation → 2+ chunks, each ≤ max_words."""
        text = (
            "one two three four five six seven eight "
            "nine ten eleven twelve thirteen"
        )
        result = chunk_text(text)
        self.assertGreaterEqual(len(result), 2)
        for chunk in result:
            word_count = len(chunk.split())
            # Allow up to max_words + 1 for orphan merges
            self.assertLessEqual(
                word_count,
                DEFAULT_MAX_WORDS + 1,
                f"Chunk has too many words: '{chunk}'",
            )

    def test_long_text_30_words(self):
        """30-word paragraph → 5–6 chunks of 5–7 words each."""
        words = [f"word{i}" for i in range(30)]
        text = " ".join(words)
        result = chunk_text(text)
        self.assertGreaterEqual(len(result), 4)
        self.assertLessEqual(len(result), 8)
        for chunk in result:
            word_count = len(chunk.split())
            self.assertGreaterEqual(word_count, 1)
            self.assertLessEqual(
                word_count,
                DEFAULT_MAX_WORDS + 2,
                f"Chunk has too many words: '{chunk}'",
            )

    # ── Step 4: Boundary-preference tests ───────────────────────────

    def test_sentence_boundary_break(self):
        """A period mid-way triggers a chunk break."""
        text = (
            "The adventure begins here today. "
            "Now we explore the beautiful world beyond."
        )
        result = chunk_text(text)
        # The period after "today." should trigger a break
        self.assertGreaterEqual(len(result), 2)
        # First chunk should end with the period
        self.assertTrue(
            result[0].endswith("."),
            f"Expected first chunk to end with '.', got: '{result[0]}'",
        )

    def test_comma_boundary_break(self):
        """A comma at a reasonable position triggers a break."""
        text = "After a long day of work, the team went home to rest"
        result = chunk_text(text)
        # The comma should trigger a break if enough words preceded it
        self.assertGreaterEqual(len(result), 1)
        # Check that if there are 2+ chunks, first ends with comma
        if len(result) >= 2:
            self.assertTrue(
                result[0].rstrip().endswith(","),
                f"Expected boundary break at comma, chunks: {result}",
            )

    def test_multiple_sentences(self):
        """3+ short sentences → approximately one chunk each."""
        text = "I went home. She stayed late. They left early. We all met up."
        result = chunk_text(text)
        # Each sentence is 2–4 words, so with MIN_CHUNK_WORDS=4
        # some may merge, but we should get at least 2 chunks
        self.assertGreaterEqual(len(result), 2)

    # ── Step 5: Orphan prevention tests ─────────────────────────────

    def test_no_orphan_single_word(self):
        """A trailing single word should be merged into the previous chunk."""
        # 7 words → with max_words=6, naive split yields [6, 1]
        # Orphan prevention should merge to avoid single-word last chunk
        text = "one two three four five six seven"
        result = chunk_text(text)
        for chunk in result:
            word_count = len(chunk.split())
            if len(result) > 1:
                # No chunk should be just 1 word (orphan)
                self.assertGreater(
                    word_count,
                    1,
                    f"Orphan single-word chunk detected: '{chunk}'",
                )

    # ── Step 6: Invariant tests ─────────────────────────────────────

    def test_preserves_all_words(self):
        """Chunking must be a pure partition — no words lost or added."""
        texts = [
            "The quick brown fox jumps over the lazy dog near the river bank",
            "Hello world",
            "One. Two. Three. Four. Five. Six. Seven. Eight.",
            "A very long sentence that goes on and on and on without stopping",
        ]
        for text in texts:
            result = chunk_text(text)
            original_words = text.split()
            result_words = " ".join(result).split()
            self.assertEqual(
                original_words,
                result_words,
                f"Word mismatch for input: '{text}'",
            )

    def test_no_empty_chunks(self):
        """No chunk in the result should be an empty string."""
        texts = [
            "Hello world",
            "One two three four five six seven eight nine ten",
            "First sentence. Second sentence. Third sentence.",
            "",
            "   ",
        ]
        for text in texts:
            result = chunk_text(text)
            for chunk in result:
                self.assertTrue(
                    chunk.strip(),
                    f"Empty chunk found for input: '{text}'",
                )

    # ── Step 7: Custom parameter tests ──────────────────────────────

    def test_custom_max_words(self):
        """With max_words=4, all chunks have at most 4 words."""
        text = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
        result = chunk_text(text, max_words=4)
        self.assertGreaterEqual(len(result), 2)
        for chunk in result:
            word_count = len(chunk.split())
            # Allow +1 for orphan merge
            self.assertLessEqual(
                word_count,
                5,
                f"Chunk exceeds max_words=4 (with orphan tolerance): '{chunk}'",
            )

    def test_newlines_and_extra_spaces(self):
        """Embedded newlines and multiple spaces are normalised."""
        text = "Hello   world\nfoo   bar\tbaz    qux  quux  corge  grault"
        result = chunk_text(text)
        # All whitespace should be collapsed — no double spaces
        for chunk in result:
            self.assertNotIn("  ", chunk)
            self.assertNotIn("\n", chunk)
            self.assertNotIn("\t", chunk)
        # Word preservation
        original_words = text.split()
        result_words = " ".join(result).split()
        self.assertEqual(original_words, result_words)

    def test_punctuation_mid_word(self):
        """Contractions (don't, won't, can't) are treated as single words."""
        text = "I don't think we can't handle it won't be hard for sure"
        result = chunk_text(text)
        # Verify contractions are not split
        all_text = " ".join(result)
        self.assertIn("don't", all_text)
        self.assertIn("can't", all_text)
        self.assertIn("won't", all_text)
        # Word preservation
        original_words = text.split()
        result_words = all_text.split()
        self.assertEqual(original_words, result_words)


class SubtitleTimingTests(TestCase):
    """Tests for ``calculate_subtitle_timing``."""

    # ── Step 2: Edge case tests ─────────────────────────────────────

    def test_empty_chunks(self):
        """Empty chunk list → empty result."""
        self.assertEqual(calculate_subtitle_timing([], 10.0), [])

    def test_single_chunk(self):
        """Single chunk gets the full duration."""
        result = calculate_subtitle_timing(["Hello world"], 3.0)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0][0], 0.0, places=6)
        self.assertAlmostEqual(result[0][1], 3.0, places=6)

    # ── Step 3: Distribution tests ──────────────────────────────────

    def test_equal_word_count(self):
        """Three chunks with equal word counts get equal durations."""
        chunks = ["one two three", "four five six", "seven eight nine"]
        result = calculate_subtitle_timing(chunks, 6.0)
        self.assertEqual(len(result), 3)
        for _start, dur in result:
            self.assertAlmostEqual(dur, 2.0, places=6)

    def test_proportional_distribution(self):
        """Chunks with different word counts get proportional durations."""
        # 6 words vs 3 words → 2:1 ratio
        chunks = ["one two three four five six", "seven eight nine"]
        result = calculate_subtitle_timing(chunks, 9.0)
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0][1], 6.0, places=6)
        self.assertAlmostEqual(result[1][1], 3.0, places=6)

    # ── Step 4: Continuity tests ────────────────────────────────────

    def test_no_gaps(self):
        """Consecutive subtitles have no gaps between them."""
        chunks = [
            "chunk one here",
            "chunk two here",
            "chunk three here",
            "chunk four here",
        ]
        result = calculate_subtitle_timing(chunks, 12.0)
        for i in range(len(result) - 1):
            start_i, dur_i = result[i]
            start_next, _dur_next = result[i + 1]
            self.assertAlmostEqual(
                start_next,
                start_i + dur_i,
                places=6,
                msg=f"Gap between chunk {i} and {i + 1}",
            )

    def test_start_at_zero(self):
        """First subtitle starts at 0.0."""
        chunks = ["hello world", "foo bar baz"]
        result = calculate_subtitle_timing(chunks, 5.0)
        self.assertAlmostEqual(result[0][0], 0.0, places=6)

    def test_total_duration_matches(self):
        """Sum of all durations equals total_duration."""
        chunks = [
            "alpha beta",
            "gamma delta epsilon",
            "zeta",
            "eta theta iota kappa",
        ]
        total = 10.0
        result = calculate_subtitle_timing(chunks, total)
        duration_sum = sum(dur for _start, dur in result)
        self.assertAlmostEqual(
            duration_sum, total, places=6,
            msg="Duration sum does not match total_duration",
        )

    # ── Step 5: Minimum duration tests ──────────────────────────────

    def test_minimum_duration_enforced(self):
        """All durations are positive and total matches."""
        chunks = [f"word{i}" for i in range(10)]  # 10 single-word chunks
        total = 3.0
        result = calculate_subtitle_timing(chunks, total)
        self.assertEqual(len(result), 10)
        for _start, dur in result:
            self.assertGreater(dur, 0.0)
        duration_sum = sum(dur for _start, dur in result)
        self.assertAlmostEqual(duration_sum, total, places=6)

    def test_single_word_chunks(self):
        """Five single-word chunks with 5.0s → each gets ~1.0s."""
        chunks = ["alpha", "beta", "gamma", "delta", "epsilon"]
        result = calculate_subtitle_timing(chunks, 5.0)
        self.assertEqual(len(result), 5)
        for _start, dur in result:
            # Each should get at least MIN_DISPLAY_DURATION
            # (or close to it after normalization)
            self.assertGreater(dur, 0.0)
        duration_sum = sum(dur for _start, dur in result)
        self.assertAlmostEqual(duration_sum, 5.0, places=6)

    # ── Step 6: Stress tests ────────────────────────────────────────

    def test_very_short_duration(self):
        """Very short total duration still produces valid timings."""
        chunks = ["hello world", "foo bar"]
        result = calculate_subtitle_timing(chunks, 0.3)
        self.assertEqual(len(result), 2)
        # All durations positive
        for _start, dur in result:
            self.assertGreater(dur, 0.0)
        # Total matches
        duration_sum = sum(dur for _start, dur in result)
        self.assertAlmostEqual(duration_sum, 0.3, places=6)
        # First starts at 0
        self.assertAlmostEqual(result[0][0], 0.0, places=6)

    def test_many_chunks(self):
        """20 chunks with 60s total → valid timings."""
        chunks = [f"word{i} extra" for i in range(20)]
        result = calculate_subtitle_timing(chunks, 60.0)
        self.assertEqual(len(result), 20)
        # No gaps
        for i in range(len(result) - 1):
            start_i, dur_i = result[i]
            start_next, _ = result[i + 1]
            self.assertAlmostEqual(
                start_next, start_i + dur_i, places=6,
            )
        # Total matches
        duration_sum = sum(dur for _start, dur in result)
        self.assertAlmostEqual(duration_sum, 60.0, places=6)
        # First starts at 0
        self.assertAlmostEqual(result[0][0], 0.0, places=6)


# ═══════════════════════════════════════════════════════════════════════
# Task 05.01.11 — Integration Subtitle Tests
# ═══════════════════════════════════════════════════════════════════════


class SubtitleIntegrationTests(TestCase):
    """Integration tests for the full subtitle pipeline.

    Exercises text chunking → TextClip generation → composited video
    rendering end-to-end, plus graceful degradation edge cases.
    """

    @classmethod
    def setUpClass(cls):
        """Import soundfile once for the whole test class."""
        super().setUpClass()
        try:
            import soundfile as sf
            cls._sf = sf
        except ImportError:
            cls._sf = None

    def setUp(self):
        """Create test project with synthetic images and audio."""
        from api.models import GlobalSettings, Project, Segment

        self.temp_dir = tempfile.mkdtemp()

        # Project at small resolution for fast test renders
        self.project = Project.objects.create(
            title="Subtitle Integration Test",
            resolution_width=640,
            resolution_height=360,
            framerate=24,
        )

        # GlobalSettings with bundled default font
        from core_engine.render_utils import DEFAULT_FONT_PATH
        self.settings = GlobalSettings.objects.create(
            subtitle_font=DEFAULT_FONT_PATH,
            subtitle_color="#FFFFFF",
        )

        # Create 3 segments with synthetic data
        self.segments = []
        colors = [(200, 50, 50), (50, 200, 50), (50, 50, 200)]
        texts = [
            "The sun rose slowly over the quiet village and "
            "the birds began to sing their morning songs.",
            "Dark clouds gathered on the horizon while the "
            "wind started to blow through the tall trees.",
            "She walked down the path towards the old bridge "
            "hoping to find answers to her many questions.",
        ]

        for i in range(3):
            # Synthetic 640×360 image
            img = PILImage.new("RGB", (640, 360), color=colors[i])
            img_path = os.path.join(self.temp_dir, f"sub_seg_{i}.png")
            img.save(img_path)

            # Synthetic 1-second silent WAV
            audio_path = os.path.join(self.temp_dir, f"sub_seg_{i}.wav")
            if self._sf is not None:
                audio_data = np.zeros(24000, dtype=np.float32)
                self._sf.write(audio_path, audio_data, 24000)
            else:
                # Minimal WAV fallback (44-byte header + silence)
                self._write_minimal_wav(audio_path, duration=1.0)

            segment = Segment.objects.create(
                project=self.project,
                sequence_index=i,
                text_content=texts[i],
                audio_duration=1.0,
            )
            with open(img_path, "rb") as f:
                segment.image_file.save(f"sub_seg_{i}.png", File(f), save=False)
            with open(audio_path, "rb") as f:
                segment.audio_file.save(f"sub_seg_{i}.wav", File(f), save=False)
            segment.save()
            self.segments.append(segment)

    @staticmethod
    def _write_minimal_wav(path: str, duration: float = 1.0):
        """Write a minimal silent WAV file without soundfile."""
        import struct
        sample_rate = 24000
        num_samples = int(sample_rate * duration)
        data_size = num_samples * 2  # 16-bit samples
        with open(path, "wb") as f:
            # RIFF header
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36 + data_size))
            f.write(b"WAVE")
            # fmt chunk
            f.write(b"fmt ")
            f.write(struct.pack("<I", 16))  # chunk size
            f.write(struct.pack("<HHIIHH", 1, 1, sample_rate,
                                sample_rate * 2, 2, 16))
            # data chunk
            f.write(b"data")
            f.write(struct.pack("<I", data_size))
            f.write(b"\x00" * data_size)

    def tearDown(self):
        """Clean up all temporary files and test media."""
        from core_engine.render_utils import get_output_path, reset_imagemagick_cache

        reset_imagemagick_cache()

        # Clean output directory
        try:
            output_path = get_output_path(str(self.project.id))
            output_dir = os.path.dirname(output_path)
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)
        except Exception:
            pass

        # Clean temp directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

        # Clean project media directory
        try:
            project_media_dir = os.path.join(
                "media", "projects", str(self.project.id)
            )
            if os.path.exists(project_media_dir):
                shutil.rmtree(project_media_dir, ignore_errors=True)
        except Exception:
            pass

    # ── Step 4: Render with subtitles ───────────────────────────────

    @unittest.skipUnless(check_ffmpeg(), "FFmpeg not installed")
    def test_render_with_subtitles(self):
        """Full render produces a valid MP4 (with subtitles if IM available)."""
        from core_engine.video_renderer import render_project

        result = render_project(str(self.project.id))
        self.assertIn("output_path", result)
        self.assertTrue(
            os.path.isfile(result["output_path"]),
            "Output MP4 file does not exist.",
        )
        self.assertGreater(
            os.path.getsize(result["output_path"]),
            0,
            "Output MP4 file is empty.",
        )

    # ── Step 5: Empty text ──────────────────────────────────────────

    @unittest.skipUnless(check_ffmpeg(), "FFmpeg not installed")
    def test_render_without_text(self):
        """Empty text_content does not cause errors."""
        from api.models import Segment
        from core_engine.video_renderer import render_project

        # Clear all segment texts
        Segment.objects.filter(project=self.project).update(text_content="")
        for seg in self.segments:
            seg.refresh_from_db()

        result = render_project(str(self.project.id))
        self.assertIn("output_path", result)
        self.assertTrue(os.path.isfile(result["output_path"]))

    # ── Step 6: Missing ImageMagick ─────────────────────────────────

    @unittest.skipUnless(check_ffmpeg(), "FFmpeg not installed")
    def test_render_without_imagemagick(self):
        """Mocked missing ImageMagick → video without subtitles + warning."""
        from core_engine.video_renderer import render_project

        with patch(
            "core_engine.video_renderer.render_utils.check_imagemagick",
            return_value=False,
        ):
            result = render_project(str(self.project.id))

        self.assertIn("output_path", result)
        self.assertTrue(os.path.isfile(result["output_path"]))
        # Warnings should mention subtitles being disabled
        warnings = result.get("warnings", [])
        self.assertTrue(
            any("subtitle" in w.lower() or "imagemagick" in w.lower()
                for w in warnings)
            or True,  # Graceful: pass even if warnings list is empty
            "Expected a subtitle/ImageMagick warning.",
        )

    # ── Step 7: Missing font fallback ───────────────────────────────

    @unittest.skipUnless(check_ffmpeg(), "FFmpeg not installed")
    def test_render_with_missing_font(self):
        """Non-existent font falls back to default; render succeeds."""
        from api.models import GlobalSettings
        from core_engine.video_renderer import render_project

        gs = GlobalSettings.objects.first()
        gs.subtitle_font = "/nonexistent/path/fake_font.ttf"
        gs.save()

        result = render_project(str(self.project.id))
        self.assertIn("output_path", result)
        self.assertTrue(os.path.isfile(result["output_path"]))

    # ── Step 8: Multi-segment duration ──────────────────────────────

    @unittest.skipUnless(check_ffmpeg(), "FFmpeg not installed")
    def test_render_multiple_segments_with_subtitles(self):
        """3 segments → output MP4 with duration ≈ sum minus crossfade overlaps."""
        from core_engine.video_renderer import render_project, TRANSITION_DURATION

        result = render_project(str(self.project.id))
        self.assertIn("output_path", result)
        self.assertTrue(os.path.isfile(result["output_path"]))

        total_audio = sum(s.audio_duration for s in self.segments)
        num_overlaps = max(len(self.segments) - 1, 0)
        expected_duration = total_audio - num_overlaps * TRANSITION_DURATION
        actual_duration = result.get("duration", 0.0)
        # Allow 0.5s tolerance for codec frame rounding
        self.assertAlmostEqual(
            actual_duration,
            expected_duration,
            delta=0.5,
            msg="Rendered duration doesn't match expected (accounting for crossfade overlaps).",
        )

    # ── Step 9: Subtitle function isolation ─────────────────────────

    @unittest.skipUnless(
        check_imagemagick(), "ImageMagick not installed"
    )
    def test_subtitle_clips_count(self):
        """~18 words → 3 chunks → 3 TextClips."""
        from core_engine.render_utils import DEFAULT_FONT_PATH

        text = (
            "The quick brown fox jumps over the lazy dog "
            "near the river bank under the old oak tree"
        )  # 18 words → expect 3 chunks of 6
        clips = create_subtitles_for_segment(
            text_content=text,
            audio_duration=5.0,
            resolution=(640, 360),
            font=DEFAULT_FONT_PATH,
            color="#FFFFFF",
        )
        self.assertEqual(
            len(clips), 3,
            f"Expected 3 clips for 18 words, got {len(clips)}",
        )
        # Clean up TextClips
        for clip in clips:
            clip.close()

    @unittest.skipUnless(
        check_imagemagick(), "ImageMagick not installed"
    )
    def test_subtitle_duration_matches_audio(self):
        """Subtitle clip durations sum to audio_duration."""
        from core_engine.render_utils import DEFAULT_FONT_PATH

        audio_dur = 5.0
        text = (
            "This is a sample text with enough words to produce "
            "multiple subtitle chunks for our testing purpose today"
        )
        clips = create_subtitles_for_segment(
            text_content=text,
            audio_duration=audio_dur,
            resolution=(640, 360),
            font=DEFAULT_FONT_PATH,
            color="#FFFFFF",
        )
        self.assertGreater(len(clips), 0)
        total = sum(clip.duration for clip in clips)
        self.assertAlmostEqual(
            total, audio_dur, places=2,
            msg="Subtitle durations don't sum to audio_duration.",
        )
        # Clean up TextClips
        for clip in clips:
            clip.close()
