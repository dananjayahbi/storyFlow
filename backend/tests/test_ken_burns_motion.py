"""Smart Ken Burns motion-planning tests (Feature update #12).

The planner must keep a single highlighted rectangle inside the frame at
every point of the animation, choose a practical speed from the free space
around that rectangle, and vary pan/zoom motions instead of producing a
static or rushed shot.
"""

from django.test import SimpleTestCase

from core_engine.ken_burns import (
    MIN_PAN_ROOM,
    MOTION_PAN,
    MOTION_PAN_ZOOM,
    MOTION_PRESETS,
    MOTION_ZOOM_IN,
    MOTION_ZOOM_OUT,
    PAN_SPEED_TARGET,
    focus_area_inside_crop,
    normalise_focus_areas,
    plan_ken_burns_motion,
    sample_ken_burns_motion,
)


SOURCE_WIDTH = 2400
SOURCE_HEIGHT = 1350
OUTPUT_WIDTH = 1920
OUTPUT_HEIGHT = 1080
ZOOM = 1.3


def _plan(segment_index=0, duration=5.0, focus_area=None, zoom=ZOOM):
    return plan_ken_burns_motion(
        segment_index=segment_index,
        duration=duration,
        source_width=SOURCE_WIDTH,
        source_height=SOURCE_HEIGHT,
        output_width=OUTPUT_WIDTH,
        output_height=OUTPUT_HEIGHT,
        zoom_intensity=zoom,
        focus_area=focus_area,
    )


def _sample_all(plan, steps=80):
    duration = plan["duration"]
    return [
        sample_ken_burns_motion(plan, duration * step / steps, duration)
        for step in range(steps + 1)
    ]


class KenBurnsMotionPlannerTests(SimpleTestCase):
    def test_single_focus_area_is_never_allowed_to_leave_the_frame(self):
        focus = {"x": 0.36, "y": 0.34, "w": 0.18, "h": 0.22}
        for index in range(len(MOTION_PRESETS)):
            plan = _plan(segment_index=index, focus_area=focus)
            for x, y, crop_w, crop_h in _sample_all(plan):
                self.assertTrue(
                    focus_area_inside_crop(
                        focus, x, y, crop_w, crop_h,
                        SOURCE_WIDTH, SOURCE_HEIGHT,
                    ),
                    f"segment {index} ({plan['motion']}) lost the subject",
                )

    def test_full_frame_focus_area_is_contained(self):
        """A rectangle covering the whole frame must still stay visible."""
        focus = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
        for index in range(len(MOTION_PRESETS)):
            plan = _plan(segment_index=index, focus_area=focus, duration=6.0)
            for x, y, crop_w, crop_h in _sample_all(plan):
                self.assertTrue(
                    focus_area_inside_crop(
                        focus, x, y, crop_w, crop_h,
                        SOURCE_WIDTH, SOURCE_HEIGHT,
                    ),
                    f"segment {index} ({plan['motion']}) lost the subject",
                )

    def test_zoom_motion_also_keeps_the_subject_inside(self):
        focus = {"x": 0.18, "y": 0.22, "w": 0.55, "h": 0.45}
        motions = set()
        for index in range(len(MOTION_PRESETS)):
            plan = _plan(segment_index=index, focus_area=focus, duration=7.0)
            motions.add(plan["motion"])
            for x, y, crop_w, crop_h in _sample_all(plan):
                self.assertTrue(
                    focus_area_inside_crop(
                        focus, x, y, crop_w, crop_h,
                        SOURCE_WIDTH, SOURCE_HEIGHT,
                    ),
                    f"segment {index} ({plan['motion']}) lost the subject",
                )
        self.assertTrue(
            motions & {MOTION_ZOOM_IN, MOTION_ZOOM_OUT}
            or motions & {MOTION_PAN_ZOOM},
            f"expected a zoom motion, got {motions}",
        )

    def test_large_subject_uses_zoom_or_shortens_the_pan(self):
        focus = {"x": 0.005, "y": 0.005, "w": 0.99, "h": 0.99}
        plan = _plan(segment_index=0, focus_area=focus, duration=5.0)
        self.assertLess(plan["pan_room"], MIN_PAN_ROOM)
        if plan["motion"] == MOTION_PAN:
            self.assertLessEqual(plan["pan_speed"], PAN_SPEED_TARGET)
        else:
            self.assertIn(
                plan["motion"],
                {MOTION_ZOOM_IN, MOTION_ZOOM_OUT, MOTION_PAN_ZOOM},
            )

    def test_pan_speed_is_comfortable_and_capped_by_available_room(self):
        focus = {"x": 0.44, "y": 0.44, "w": 0.1, "h": 0.12}
        plan = _plan(segment_index=0, focus_area=focus, duration=5.0)
        self.assertEqual(plan["motion"], MOTION_PAN)
        self.assertGreater(plan["pan_speed"], 0.0)
        self.assertLessEqual(plan["pan_speed"], PAN_SPEED_TARGET * 1.05)

    def test_presets_produce_more_than_one_motion(self):
        motions = {
            _plan(segment_index=index, duration=5.0)["motion"]
            for index in range(len(MOTION_PRESETS))
        }
        self.assertGreaterEqual(len(motions), 2, motions)

    def test_sampling_with_zero_duration_stays_at_the_start(self):
        focus = {"x": 0.3, "y": 0.3, "w": 0.2, "h": 0.2}
        plan = _plan(segment_index=0, focus_area=focus, duration=0.0)
        start = sample_ken_burns_motion(plan, 99.0, 0.0)
        self.assertEqual(start[2:], plan["start_crop"])
        self.assertTrue(
            focus_area_inside_crop(
                focus, *start, SOURCE_WIDTH, SOURCE_HEIGHT,
            )
        )

    def test_legacy_focus_area_lists_use_the_first_rectangle(self):
        first = {"x": 0.2, "y": 0.2, "w": 0.2, "h": 0.2}
        areas = normalise_focus_areas([
            first,
            {"x": 0.7, "y": 0.7, "w": 0.2, "h": 0.2},
        ])
        self.assertEqual(areas, [first])
        plan = _plan(segment_index=0, focus_area=[first, areas[0]])
        self.assertEqual(plan["focus_area"], first)

    def test_containment_helper_detects_a_violation(self):
        focus = {"x": 0.4, "y": 0.4, "w": 0.2, "h": 0.2}
        self.assertTrue(
            focus_area_inside_crop(
                focus, 800, 450, 960, 540, SOURCE_WIDTH, SOURCE_HEIGHT,
            )
        )
        self.assertFalse(
            focus_area_inside_crop(
                focus, 0, 0, 640, 360, SOURCE_WIDTH, SOURCE_HEIGHT,
            )
        )
