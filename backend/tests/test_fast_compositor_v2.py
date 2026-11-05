"""Tests for the selectable Pipeline v2 parallel compositor."""

import os
import shutil
import tempfile
from unittest.mock import patch

import cv2
import numpy as np
from django.test import SimpleTestCase

from core_engine.fast_compositor import fast_render_segments
from core_engine.fast_compositor_v2 import (
    _build_timeline,
    _worker_count,
    fast_render_segments_v2,
)


def _frame_count(path: str) -> int:
    capture = cv2.VideoCapture(path)
    try:
        return int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()


class FastCompositorV2Tests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="storyflow-v2-test-")
        self.image_paths = []
        for index, colour in enumerate(((220, 40, 40), (40, 160, 220))):
            path = os.path.join(self.temp_dir, f"image_{index}.jpg")
            image = np.zeros((180, 320, 3), dtype=np.uint8)
            image[:, :] = colour
            cv2.imwrite(path, image)
            self.image_paths.append(path)

        self.segments = [
            {
                "image_path": self.image_paths[0],
                "audio_duration": 5.0,
                "text_content": "",
                "sequence_index": 0,
                "focus_x": 0.5,
                "focus_y": 0.5,
            },
            {
                "image_path": self.image_paths[1],
                "audio_duration": 5.0,
                "text_content": "",
                "sequence_index": 1,
                "focus_x": 0.5,
                "focus_y": 0.5,
            },
        ]

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _render(
        self, renderer, name: str, workers: int = 2, on_progress=None,
    ):
        output = os.path.join(self.temp_dir, name)
        with patch.dict(os.environ, {"STORYFLOW_V2_WORKERS": str(workers)}):
            return renderer(
                segment_data=self.segments,
                output_path=output,
                resolution=(320, 180),
                fps=2,
                zoom_intensity=1.3,
                subtitle_settings={"enabled": False},
                logo_settings=None,
                audio_path=None,
                use_nvenc=False,
                crossfade_duration=0.5,
                inter_segment_silence=0.0,
                on_progress=on_progress,
            ), output

    def test_timeline_matches_v1_math(self):
        ranges, durations, total, duration = _build_timeline(
            self.segments, fps=2, crossfade_duration=0.5,
            inter_segment_silence=0.0,
        )
        self.assertEqual(durations, [5.0, 5.0])
        self.assertEqual(ranges, [(0, 10), (9, 19)])
        self.assertEqual(total, 19)
        self.assertAlmostEqual(duration, 9.5)

    def test_worker_count_is_capped(self):
        with patch.dict(os.environ, {"STORYFLOW_V2_WORKERS": "12"}):
            self.assertLessEqual(_worker_count(10_000, 30, True), 4)
            self.assertGreaterEqual(_worker_count(10_000, 30, True), 1)

    def test_v2_renders_the_same_frame_count_as_v1(self):
        stats_v2, output_v2 = self._render(
            fast_render_segments_v2, "v2.mp4", workers=2,
        )
        self.assertEqual(stats_v2["pipeline"], "v2")
        self.assertEqual(stats_v2["workers"], 2)
        self.assertEqual(stats_v2["frames_rendered"], 19)
        self.assertTrue(os.path.isfile(output_v2))
        self.assertGreater(os.path.getsize(output_v2), 0)
        self.assertEqual(_frame_count(output_v2), 19)

        _stats_v1, output_v1 = self._render(
            fast_render_segments, "v1.mp4", workers=1,
        )
        self.assertEqual(_frame_count(output_v1), _frame_count(output_v2))

    def test_reports_live_frame_progress_with_rate_and_eta(self):
        """v2 must expose frames rendered, generation rate and remaining time."""
        events = []

        def on_progress(current, total, message):
            events.append((current, total, message))

        stats, output = self._render(
            fast_render_segments_v2,
            "v2-progress.mp4",
            workers=2,
            on_progress=on_progress,
        )

        frame_events = [
            event for event in events
            if event[2].startswith("Rendering frames…")
        ]
        self.assertTrue(frame_events, events)
        self.assertTrue(
            any(
                f"/{stats['frames_rendered']} (" in message
                and "fps" in message
                and "remaining)" in message
                for _current, _total, message in frame_events
            ),
            frame_events,
        )
        # The final frame report must account for every generated frame.
        self.assertEqual(
            frame_events[-1][0], stats["frames_rendered"],
        )
        self.assertTrue(os.path.isfile(output))

    def test_empty_segment_list_is_rejected(self):
        with self.assertRaises(ValueError):
            fast_render_segments_v2(
                segment_data=[],
                output_path=os.path.join(self.temp_dir, "empty.mp4"),
                resolution=(320, 180),
                fps=2,
                zoom_intensity=1.3,
                subtitle_settings={"enabled": False},
                logo_settings=None,
                audio_path=None,
            )
