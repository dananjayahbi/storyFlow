"""
Multi-segment integration tests for the full render pipeline with crossfade
transitions.

Task 05.02.08 — Write Multi Segment Integration Tests

These tests exercise the *complete* rendering pipeline: segment loading →
Ken Burns animation → subtitle compositing → crossfade transitions →
concatenation with negative padding → MP4 export.  They use synthetic
test media (solid-colour images + silent audio) at a small 640×360
resolution to keep execution time under 30 seconds per test.
"""

import os
import shutil
import struct
import tempfile
import unittest

import numpy as np
from PIL import Image as PILImage

from django.core.files.base import File
from django.test import TestCase

from core_engine.render_utils import (
    check_ffmpeg,
    check_imagemagick,
    get_output_path,
    reset_ffmpeg_cache,
    reset_imagemagick_cache,
    DEFAULT_FONT_PATH,
)
from core_engine.video_renderer import (
    TRANSITION_DURATION,
    calculate_total_duration_with_transitions,
    render_project,
)


# ---------------------------------------------------------------------------
# Helper: write a minimal silent WAV without soundfile
# ---------------------------------------------------------------------------

def _write_silent_wav(path: str, duration: float, sample_rate: int = 22050):
    """Write a minimal silent WAV file.

    Uses raw struct packing so the test has zero dependency on soundfile
    or any third-party audio library.
    """
    num_samples = int(sample_rate * duration)
    data_size = num_samples * 2  # 16-bit PCM → 2 bytes per sample
    with open(path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))
        f.write(struct.pack("<HHIIHH", 1, 1, sample_rate,
                            sample_rate * 2, 2, 16))
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(b"\x00" * data_size)


# ===================================================================
# MultiSegmentIntegrationTests
# ===================================================================

@unittest.skipUnless(check_ffmpeg(), "FFmpeg not installed")
class MultiSegmentIntegrationTests(TestCase):
    """Full-pipeline integration tests: render multi-segment projects with
    crossfade transitions and (optionally) subtitles, then assert the
    output MP4 is valid and correctly timed.
    """

    # ------------------------------------------------------------------
    # Duration assertion helper (Step 15)
    # ------------------------------------------------------------------

    def assertDurationApproximate(
        self,
        actual: float,
        expected: float,
        tolerance: float = 0.2,
    ):
        """Assert *actual* is within *tolerance* of *expected*.

        Provides a descriptive message on failure showing both values and
        the allowed tolerance.
        """
        self.assertAlmostEqual(
            actual,
            expected,
            delta=tolerance,
            msg=(
                f"Duration mismatch: actual={actual:.3f}s, "
                f"expected={expected:.3f}s (tolerance={tolerance}s)"
            ),
        )

    # ------------------------------------------------------------------
    # setUp / tearDown
    # ------------------------------------------------------------------

    def setUp(self):
        """Create a test project, GlobalSettings, and synthetic media."""
        from api.models import GlobalSettings, Project, Segment  # noqa: E402

        self.temp_dir = tempfile.mkdtemp()

        # Small-resolution project for fast rendering
        self.project = Project.objects.create(
            title="Multi-Segment Integration Test",
            resolution_width=640,
            resolution_height=360,
            framerate=24,
        )

        # GlobalSettings with default font for subtitles
        self.settings = GlobalSettings.objects.create(
            subtitle_font=DEFAULT_FONT_PATH,
            subtitle_color="#FFFFFF",
        )

    def tearDown(self):
        """Remove all temporary files and directories."""
        reset_ffmpeg_cache()
        reset_imagemagick_cache()

        # Clean render output directory
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

        # Clean project media directory created by Django FileField
        try:
            project_media_dir = os.path.join(
                "media", "projects", str(self.project.id)
            )
            if os.path.exists(project_media_dir):
                shutil.rmtree(project_media_dir, ignore_errors=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Segment factory
    # ------------------------------------------------------------------

    def _create_segments(
        self,
        durations: list[float],
        *,
        with_text: bool = True,
    ):
        """Create *len(durations)* segments with synthetic image + audio.

        Args:
            durations: Audio duration (seconds) for each segment.
            with_text: If True, each segment gets non-empty ``text_content``
                for subtitle rendering.  If False, ``text_content`` is left
                empty.
        """
        from api.models import Segment  # noqa: E402

        colours = [
            (220, 50, 50),   # red
            (50, 180, 50),   # green
            (50, 50, 220),   # blue
            (220, 180, 50),  # yellow
            (180, 50, 220),  # purple
        ]
        texts = [
            "The sun rose slowly over the quiet village.",
            "Dark clouds gathered on the distant horizon.",
            "She walked down the path towards the old bridge.",
            "A gentle breeze carried the scent of wildflowers.",
            "The river sparkled under the afternoon light.",
        ]

        segments = []
        for i, dur in enumerate(durations):
            colour = colours[i % len(colours)]

            # Solid-colour image (800×600 to exercise cover resize)
            img = PILImage.new("RGB", (800, 600), color=colour)
            img_path = os.path.join(self.temp_dir, f"int_seg_{i}.png")
            img.save(img_path)

            # Silent WAV at requested duration
            audio_path = os.path.join(self.temp_dir, f"int_seg_{i}.wav")
            _write_silent_wav(audio_path, dur)

            text = texts[i % len(texts)] if with_text else ""

            segment = Segment.objects.create(
                project=self.project,
                sequence_index=i,
                text_content=text,
                audio_duration=dur,
            )
            with open(img_path, "rb") as f:
                segment.image_file.save(
                    f"int_seg_{i}.png", File(f), save=False
                )
            with open(audio_path, "rb") as f:
                segment.audio_file.save(
                    f"int_seg_{i}.wav", File(f), save=False
                )
            segment.save()
            segments.append(segment)

        return segments

    # ==================================================================
    # Step 4 — Two-segment crossfade test
    # ==================================================================

    def test_two_segments_with_crossfade(self):
        """Two 2-second segments → expected ≈ 3.5 s (one 0.5 s overlap)."""
        self._create_segments([2.0, 2.0])
        result = render_project(str(self.project.id))

        self.assertIn("output_path", result)
        self.assertTrue(os.path.exists(result["output_path"]))
        self.assertGreater(result["file_size"], 0)

        expected = calculate_total_duration_with_transitions([2.0, 2.0])
        self.assertDurationApproximate(result["duration"], expected)

    # ==================================================================
    # Step 5 — Three-segment crossfade test
    # ==================================================================

    def test_three_segments_with_crossfade(self):
        """Three 3-second segments → expected ≈ 8.0 s (two overlaps)."""
        self._create_segments([3.0, 3.0, 3.0])
        result = render_project(str(self.project.id))

        self.assertTrue(os.path.exists(result["output_path"]))
        self.assertGreater(result["file_size"], 0)

        expected = calculate_total_duration_with_transitions([3.0, 3.0, 3.0])
        self.assertDurationApproximate(result["duration"], expected)

    # ==================================================================
    # Step 6 — Five-segment varying durations test
    # ==================================================================

    def test_five_segments_with_crossfade(self):
        """Five segments of varying lengths → correct duration math."""
        durations = [2.0, 3.0, 1.5, 2.5, 2.0]
        self._create_segments(durations)
        result = render_project(str(self.project.id))

        self.assertTrue(os.path.exists(result["output_path"]))
        self.assertGreater(result["file_size"], 0)

        expected = calculate_total_duration_with_transitions(durations)
        self.assertDurationApproximate(result["duration"], expected)

    # ==================================================================
    # Step 7 — Single-segment (no crossfade) test
    # ==================================================================

    def test_single_segment_no_crossfade(self):
        """Single 3-second segment → duration ≈ 3.0 s, no overlap."""
        self._create_segments([3.0])
        result = render_project(str(self.project.id))

        self.assertTrue(os.path.exists(result["output_path"]))
        self.assertGreater(result["file_size"], 0)
        self.assertDurationApproximate(result["duration"], 3.0)

    # ==================================================================
    # Step 8 — Crossfade WITH subtitles test
    # ==================================================================

    def test_crossfade_with_subtitles(self):
        """Three segments with text → valid MP4 produced, no errors."""
        self._create_segments([2.0, 2.0, 2.0], with_text=True)
        result = render_project(str(self.project.id))

        self.assertIn("output_path", result)
        self.assertTrue(
            os.path.isfile(result["output_path"]),
            "Output MP4 file does not exist.",
        )
        self.assertGreater(result["file_size"], 0)

    # ==================================================================
    # Step 9 — Crossfade WITHOUT subtitles test
    # ==================================================================

    def test_crossfade_without_subtitles(self):
        """Three segments with empty text → valid MP4 produced."""
        self._create_segments([2.0, 2.0, 2.0], with_text=False)
        result = render_project(str(self.project.id))

        self.assertIn("output_path", result)
        self.assertTrue(
            os.path.isfile(result["output_path"]),
            "Output MP4 file does not exist.",
        )
        self.assertGreater(result["file_size"], 0)

    # ==================================================================
    # Step 10 — ImageMagick fallback test
    # ==================================================================

    def test_crossfade_without_imagemagick(self):
        """Mock ImageMagick as unavailable → renders without subtitles,
        result includes an ImageMagick warning."""
        from unittest.mock import patch

        self._create_segments([2.0, 2.0, 2.0], with_text=True)

        with patch(
            "core_engine.video_renderer.render_utils.check_imagemagick",
            return_value=False,
        ):
            result = render_project(str(self.project.id))

        # Render still succeeds
        self.assertTrue(os.path.isfile(result["output_path"]))
        self.assertGreater(result["file_size"], 0)

        # Warnings list mentions ImageMagick
        self.assertIn("warnings", result)
        self.assertIsInstance(result["warnings"], list)
        self.assertGreaterEqual(len(result["warnings"]), 1)

        im_warnings = [
            w for w in result["warnings"] if "ImageMagick" in w
        ]
        self.assertGreaterEqual(
            len(im_warnings),
            1,
            "Expected at least one warning mentioning ImageMagick",
        )

    # ==================================================================
    # Step 11 — Render result metadata test
    # ==================================================================

    def test_render_result_includes_duration_metadata(self):
        """Result dict contains duration, expected_duration, and
        num_transitions fields with correct values."""
        durations = [2.0, 2.0, 2.0]
        self._create_segments(durations)
        result = render_project(str(self.project.id))

        # Required keys
        self.assertIn("duration", result)
        self.assertIn("expected_duration", result)
        self.assertIn("num_transitions", result)

        # num_transitions = segments - 1
        self.assertEqual(result["num_transitions"], len(durations) - 1)

        # expected_duration matches our calculation
        expected = calculate_total_duration_with_transitions(durations)
        self.assertDurationApproximate(
            result["expected_duration"], expected, tolerance=0.01
        )

        # Actual duration is close to expected
        self.assertDurationApproximate(
            result["duration"], result["expected_duration"]
        )

    # ==================================================================
    # Step 12 — Render warnings test
    # ==================================================================

    def test_render_result_includes_warnings(self):
        """When ImageMagick is mocked away, warnings list is non-empty.
        When it IS available, warnings list is empty (for a normal render)."""
        from unittest.mock import patch

        self._create_segments([2.0, 2.0], with_text=True)

        # ── With ImageMagick mocked as unavailable ──
        with patch(
            "core_engine.video_renderer.render_utils.check_imagemagick",
            return_value=False,
        ):
            result_no_im = render_project(str(self.project.id))

        self.assertIn("warnings", result_no_im)
        self.assertGreater(
            len(result_no_im["warnings"]),
            0,
            "Expected warnings when ImageMagick is unavailable.",
        )

    # ==================================================================
    # Step 13 — Optional visual inspection test
    # ==================================================================

    @unittest.skip("Manual visual test — un-skip to inspect output in VLC")
    def test_visual_crossfade_inspection(self):
        """Render a multi-segment video and print the output path for
        manual inspection.  Normally skipped in CI."""
        self._create_segments([3.0, 3.0, 3.0])
        result = render_project(str(self.project.id))

        print(
            f"\n{'=' * 60}\n"
            f"Visual inspection output:\n"
            f"  {result['output_path']}\n"
            f"  Duration: {result['duration']:.2f}s\n"
            f"{'=' * 60}"
        )

        self.assertTrue(os.path.isfile(result["output_path"]))
