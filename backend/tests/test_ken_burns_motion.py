"""Smart Ken Burns motion-planning tests (Feature update #12, Issue #31).

The planner must:
* keep a single highlighted rectangle sufficiently visible at every point
  of the animation (at most 10 % may leave the frame);
* choose a motion that produces a visible amount of movement instead of a
  frozen-looking pan;
* fall back to a zoom when a large subject leaves too little panning room;
* vary pan/zoom motions instead of producing the same shot every time.
"""

from django.test import SimpleTestCase

from core_engine.ken_burns import (
    FOCUS_OVERFLOW_RATIO,
    MIN_PAN_ROOM,
    MIN_PAN_TRAVEL,
    MIN_ZOOM_SPAN,
    MOTION_PAN,
    MOTION_PAN_ZOOM,
    MOTION_PRESETS,
    MOTION_ZOOM_IN,
    MOTION_ZOOM_OUT,
    PAN_SPEED_TARGET,
    focus_area_clipped_fraction,
    focus_area_inside_crop,
    get_focus_area_bounds,
    normalise_focus_areas,
    plan_ken_burns_motion,
    sample_ken_burns_motion,
)


SOURCE_WIDTH = 2400
SOURCE_HEIGHT = 1350
OUTPUT_WIDTH = 1920
OUTPUT_HEIGHT = 1080
ZOOM = 1.3

ZOOM_MOTIONS = {MOTION_ZOOM_IN, MOTION_ZOOM_OUT, MOTION_PAN_ZOOM}


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


def _motion_amount(plan):
    """Return the largest visible change produced by *plan*.

    Pan is measured as a fraction of the crop width/height and zoom as a
    fraction of the crop scale.  Either value above the planner's minimum
    means the shot is visibly animating.
    """
    start_x, start_y = plan["start_centre"]
    end_x, end_y = plan["end_centre"]
    ref_w = (plan["start_crop"][0] + plan["end_crop"][0]) / 2.0
    ref_h = (plan["start_crop"][1] + plan["end_crop"][1]) / 2.0
    pan = max(
        abs(end_x - start_x) / max(1.0, ref_w),
        abs(end_y - start_y) / max(1.0, ref_h),
    )
    zoom = abs(plan["end_scale"] - plan["start_scale"])
    return max(pan, zoom)


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
                        overflow_ratio=FOCUS_OVERFLOW_RATIO,
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
                        overflow_ratio=FOCUS_OVERFLOW_RATIO,
                    ),
                    f"segment {index} ({plan['motion']}) lost the subject",
                )

    def test_at_most_ten_percent_of_the_subject_leaves_the_frame(self):
        """Issue #31 allows a small overflow, but never more than 10 %."""
        cases = (
            {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
            {"x": 0.005, "y": 0.005, "w": 0.99, "h": 0.99},
            {"x": 0.36, "y": 0.34, "w": 0.18, "h": 0.22},
            {"x": 0.0, "y": 0.0, "w": 0.25, "h": 0.25},
            {"x": 0.75, "y": 0.75, "w": 0.25, "h": 0.25},
        )
        for focus in cases:
            for index in range(len(MOTION_PRESETS)):
                plan = _plan(segment_index=index, focus_area=focus, duration=5.0)
                for x, y, crop_w, crop_h in _sample_all(plan):
                    clipped_w, clipped_h = focus_area_clipped_fraction(
                        focus, x, y, crop_w, crop_h,
                        SOURCE_WIDTH, SOURCE_HEIGHT,
                    )
                    self.assertLessEqual(
                        clipped_w, FOCUS_OVERFLOW_RATIO + 0.005,
                        f"{focus} @ {index} clipped {clipped_w:.3f} of width",
                    )
                    self.assertLessEqual(
                        clipped_h, FOCUS_OVERFLOW_RATIO + 0.005,
                        f"{focus} @ {index} clipped {clipped_h:.3f} of height",
                    )

    def test_overflow_ratio_gives_more_pan_room_than_strict_bounds(self):
        focus = {"x": 0.4, "y": 0.4, "w": 0.2, "h": 0.2}
        strict = get_focus_area_bounds(
            focus, 1000, 1000, 400, 400, overflow_ratio=0.0,
        )
        relaxed = get_focus_area_bounds(
            focus, 1000, 1000, 400, 400,
            overflow_ratio=FOCUS_OVERFLOW_RATIO,
        )
        self.assertLess(relaxed[0], strict[0])
        self.assertGreater(relaxed[1], strict[1])
        self.assertLess(relaxed[2], strict[2])
        self.assertGreater(relaxed[3], strict[3])

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
                        overflow_ratio=FOCUS_OVERFLOW_RATIO,
                    ),
                    f"segment {index} ({plan['motion']}) lost the subject",
                )
        self.assertTrue(
            motions & {MOTION_ZOOM_IN, MOTION_ZOOM_OUT}
            or motions & {MOTION_PAN_ZOOM},
            f"expected a zoom motion, got {motions}",
        )

    def test_large_subject_switches_to_a_zoom_when_pan_cannot_be_seen(self):
        """A subject that nearly fills the frame must not produce a static pan."""
        focus = {"x": 0.005, "y": 0.005, "w": 0.99, "h": 0.99}
        plan = _plan(segment_index=0, focus_area=focus, duration=5.0)
        self.assertLess(plan["pan_room"], MIN_PAN_ROOM)
        self.assertIn(plan["motion"], ZOOM_MOTIONS)
        self.assertGreaterEqual(
            abs(plan["end_scale"] - plan["start_scale"]),
            MIN_ZOOM_SPAN - 1e-6,
        )
        self.assertGreater(plan["zoom_speed"], 0.0)

    def test_every_plan_has_visible_motion(self):
        """Issue #31: too-slow moves are replaced; no clip should look frozen."""
        cases = (
            None,
            {"x": 0.44, "y": 0.44, "w": 0.1, "h": 0.12},
            {"x": 0.2, "y": 0.2, "w": 0.5, "h": 0.5},
            {"x": 0.005, "y": 0.005, "w": 0.99, "h": 0.99},
            {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
            {"x": 0.0, "y": 0.0, "w": 0.25, "h": 0.25},
            {"x": 0.75, "y": 0.75, "w": 0.25, "h": 0.25},
        )
        for focus in cases:
            for duration in (1.0, 3.0, 5.0, 8.0, 15.0):
                for index in range(len(MOTION_PRESETS)):
                    plan = _plan(
                        segment_index=index,
                        focus_area=focus,
                        duration=duration,
                    )
                    amount = _motion_amount(plan)
                    self.assertGreaterEqual(
                        amount, MIN_PAN_TRAVEL - 1e-6,
                        f"{focus} @ {index}, {duration}s -> "
                        f"{plan['motion']} only moved {amount:.4f}",
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
                overflow_ratio=FOCUS_OVERFLOW_RATIO,
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

    def test_clipped_fraction_helper_measures_overflow(self):
        focus = {"x": 0.4, "y": 0.4, "w": 0.2, "h": 0.2}
        clipped_w, clipped_h = focus_area_clipped_fraction(
            focus, 800, 450, 960, 540, SOURCE_WIDTH, SOURCE_HEIGHT,
        )
        self.assertEqual((clipped_w, clipped_h), (0.0, 0.0))
        clipped_w, clipped_h = focus_area_clipped_fraction(
            focus, 1100, 650, 480, 270, SOURCE_WIDTH, SOURCE_HEIGHT,
        )
        self.assertGreater(clipped_w, 0.0)
        self.assertGreater(clipped_h, 0.0)
