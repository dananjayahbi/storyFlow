"""
Tests for crossfade transition logic and duration adjustment math.

Task 05.02.07 — Write Crossfade Tests
"""

from unittest.mock import MagicMock, patch, call

from django.test import TestCase

from core_engine.video_renderer import (
    TRANSITION_DURATION,
    apply_crossfade_transitions,
    calculate_total_duration_with_transitions,
    vfx,
)


def create_mock_clip(duration: float) -> MagicMock:
    """Create a MagicMock that behaves like a MoviePy VideoClip.

    The mock has:
    - ``duration`` attribute set to the given value.
    - ``with_effects()`` method that returns a **new** MagicMock (to
      simulate MoviePy 2.x immutable-clip semantics), while recording
      what effects were passed.
    """
    clip = MagicMock()
    clip.duration = duration
    # with_effects returns a new mock each time (like MoviePy's
    # immutable API), but we record the call on the original mock.
    new_clip = MagicMock()
    new_clip.duration = duration
    clip.with_effects.return_value = new_clip
    return clip


class CrossfadeTransitionTests(TestCase):
    """Unit tests for apply_crossfade_transitions and duration math."""

    # ==================================================================
    # apply_crossfade_transitions tests
    # ==================================================================

    def test_empty_clips(self):
        """Empty list returns empty list — no effects applied."""
        result = apply_crossfade_transitions([])
        self.assertEqual(result, [])

    def test_single_clip_no_transition(self):
        """Single clip is returned unchanged — no crossfade effects."""
        clip = create_mock_clip(5.0)
        result = apply_crossfade_transitions([clip])

        self.assertEqual(len(result), 1)
        # The returned clip should be the same object (no with_effects call).
        self.assertIs(result[0], clip)
        clip.with_effects.assert_not_called()

    def test_two_clips_crossfade(self):
        """Two clips: first→CrossFadeOut only, last→CrossFadeIn only."""
        clip_a = create_mock_clip(5.0)
        clip_b = create_mock_clip(5.0)

        result = apply_crossfade_transitions([clip_a, clip_b])
        self.assertEqual(len(result), 2)

        # First clip: with_effects called with CrossFadeOut only.
        clip_a.with_effects.assert_called_once()
        effects_a = clip_a.with_effects.call_args[0][0]
        self.assertEqual(len(effects_a), 1)
        self.assertIsInstance(effects_a[0], vfx.CrossFadeOut)

        # Second clip: with_effects called with CrossFadeIn only.
        clip_b.with_effects.assert_called_once()
        effects_b = clip_b.with_effects.call_args[0][0]
        self.assertEqual(len(effects_b), 1)
        self.assertIsInstance(effects_b[0], vfx.CrossFadeIn)

    def test_three_clips_crossfade(self):
        """Three clips: first→out, middle→both, last→in."""
        clips = [create_mock_clip(5.0) for _ in range(3)]
        result = apply_crossfade_transitions(clips)

        self.assertEqual(len(result), 3)

        # First clip: CrossFadeOut only.
        clips[0].with_effects.assert_called_once()
        fx0 = clips[0].with_effects.call_args[0][0]
        self.assertEqual(len(fx0), 1)
        self.assertIsInstance(fx0[0], vfx.CrossFadeOut)

        # Middle clip: both CrossFadeIn and CrossFadeOut.
        clips[1].with_effects.assert_called_once()
        fx1 = clips[1].with_effects.call_args[0][0]
        self.assertEqual(len(fx1), 2)
        types_1 = {type(e) for e in fx1}
        self.assertIn(vfx.CrossFadeIn, types_1)
        self.assertIn(vfx.CrossFadeOut, types_1)

        # Last clip: CrossFadeIn only.
        clips[2].with_effects.assert_called_once()
        fx2 = clips[2].with_effects.call_args[0][0]
        self.assertEqual(len(fx2), 1)
        self.assertIsInstance(fx2[0], vfx.CrossFadeIn)

    def test_clip_count_preserved(self):
        """Five clips in → exactly five clips out."""
        clips = [create_mock_clip(3.0) for _ in range(5)]
        result = apply_crossfade_transitions(clips)
        self.assertEqual(len(result), 5)

    def test_custom_transition_duration(self):
        """Custom transition_duration=1.0 is passed to effects."""
        clip_a = create_mock_clip(5.0)
        clip_b = create_mock_clip(5.0)

        apply_crossfade_transitions([clip_a, clip_b], transition_duration=1.0)

        # First clip: CrossFadeOut(1.0).
        fx_a = clip_a.with_effects.call_args[0][0]
        self.assertIsInstance(fx_a[0], vfx.CrossFadeOut)
        self.assertEqual(fx_a[0].duration, 1.0)

        # Second clip: CrossFadeIn(1.0).
        fx_b = clip_b.with_effects.call_args[0][0]
        self.assertIsInstance(fx_b[0], vfx.CrossFadeIn)
        self.assertEqual(fx_b[0].duration, 1.0)

    def test_original_list_not_mutated(self):
        """The input list is not modified by apply_crossfade_transitions."""
        clip_a = create_mock_clip(5.0)
        clip_b = create_mock_clip(5.0)
        original = [clip_a, clip_b]
        original_copy = list(original)

        apply_crossfade_transitions(original)
        self.assertEqual(original, original_copy)

    def test_default_transition_duration_is_0_5(self):
        """TRANSITION_DURATION constant equals 0.5."""
        self.assertEqual(TRANSITION_DURATION, 0.5)

    # ==================================================================
    # calculate_total_duration_with_transitions tests
    # ==================================================================

    def test_empty_durations(self):
        """Empty list → 0.0."""
        self.assertEqual(
            calculate_total_duration_with_transitions([]), 0.0
        )

    def test_single_duration(self):
        """[5.0] → 5.0 (zero transitions)."""
        self.assertEqual(
            calculate_total_duration_with_transitions([5.0]), 5.0
        )

    def test_two_clips_duration(self):
        """[5.0, 5.0] → 9.5 (one transition)."""
        self.assertAlmostEqual(
            calculate_total_duration_with_transitions([5.0, 5.0]), 9.5
        )

    def test_three_clips_duration(self):
        """[5.0, 5.0, 5.0] → 14.0 (two transitions)."""
        self.assertAlmostEqual(
            calculate_total_duration_with_transitions([5.0, 5.0, 5.0]), 14.0
        )

    def test_five_clips_duration(self):
        """[3.0]*5 → 13.0 (four transitions)."""
        self.assertAlmostEqual(
            calculate_total_duration_with_transitions(
                [3.0, 3.0, 3.0, 3.0, 3.0]
            ),
            13.0,
        )

    def test_varying_durations(self):
        """[2.0, 5.0, 3.0] → 9.0."""
        self.assertAlmostEqual(
            calculate_total_duration_with_transitions([2.0, 5.0, 3.0]), 9.0
        )

    def test_custom_transition_duration_math(self):
        """[5.0, 5.0] with td=1.0 → 9.0."""
        self.assertAlmostEqual(
            calculate_total_duration_with_transitions([5.0, 5.0], 1.0), 9.0
        )

    def test_very_short_clips_duration(self):
        """[0.1, 0.1] with default 0.5s td → −0.3 (no clamping)."""
        result = calculate_total_duration_with_transitions([0.1, 0.1])
        self.assertAlmostEqual(result, -0.3)
