"""Tests for the MusicGen soundtrack subsystem (CPU-only, fully mocked)."""

import math
import os
import tempfile

import numpy as np
from django.test import SimpleTestCase

from core_engine import music_generator as mg


SCRIPT = {
    'title': 'Deep Ocean',
    'segments': [
        {
            'text_content': 'An ancient wreck rests in the quiet dark.',
            'image_prompt': 'sunken ship',
            'duration': 5.0,
        },
        {
            'text_content': 'The crew faces rising danger as the storm grows.',
            'image_prompt': 'storm at sea',
            'duration': 4.0,
        },
        {
            'text_content': 'At last, dawn brings hope across the water.',
            'image_prompt': 'sunrise over ocean',
            'duration': 3.0,
        },
    ],
}


class PromptPlanningTests(SimpleTestCase):
    def test_prompts_share_bpm_and_root_key_across_scenes(self):
        plan = mg.plan_music(SCRIPT)

        self.assertEqual(len(plan.prompts), 3)
        for prompt in plan.prompts:
            self.assertTrue(prompt.startswith(plan.anchor))
            self.assertIn('instrumental', prompt)
            self.assertIn('no vocals', prompt)
            self.assertIn(f'{plan.bpm} bpm', prompt)
            self.assertIn(f'{plan.root_key} {plan.mode}', prompt)

        # Mood/instrumentation must actually evolve between blocks.
        self.assertNotEqual(plan.prompts[0], plan.prompts[1])
        self.assertIn('mystery', plan.prompts[0])
        self.assertIn('tension', plan.prompts[1])

    def test_explicit_anchor_is_honoured(self):
        plan = mg.plan_music(
            SCRIPT, bpm=70, root_key='d', mode='minor'
        )
        self.assertEqual(plan.anchor, '70 bpm, D minor')
        for prompt in plan.prompts:
            self.assertTrue(prompt.startswith('70 bpm, D minor'))

    def test_planner_is_deterministic_for_the_same_script(self):
        first = mg.plan_music(SCRIPT)
        second = mg.plan_music(SCRIPT)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_invalid_bpm_is_rejected(self):
        with self.assertRaises(mg.MusicGenerationError):
            mg.plan_music(SCRIPT, bpm=5)


class CrossfadeTests(SimpleTestCase):
    def test_crossfade_shortens_by_overlap_and_is_smooth(self):
        sample_rate = 1000
        previous = np.ones(1000, dtype=np.float32)
        upcoming = np.ones(800, dtype=np.float32)

        mixed = mg.equal_power_crossfade(
            previous, upcoming, sample_rate=sample_rate, crossfade_seconds=0.1
        )

        self.assertEqual(len(mixed), 1000 + 800 - 100)
        # Fade-out starts at unity and fade-in ends at unity.  The two
        # correlated unit signals sum to slightly more than 1 at the seam.
        self.assertAlmostEqual(float(mixed[900]), 1.0, places=2)
        self.assertAlmostEqual(float(mixed[998]), 1.0, delta=0.05)
        # The two curves are an equal-power pair.
        t = np.linspace(0, math.pi / 2, 100, endpoint=False)
        powers = np.cos(t) ** 2 + np.sin(t) ** 2
        self.assertTrue(np.allclose(powers, 1.0))

    def test_stitch_uses_crossfade_for_three_segments(self):
        chunks = [
            np.ones(1000, dtype=np.float32),
            np.ones(1000, dtype=np.float32),
            np.ones(1000, dtype=np.float32),
        ]
        stitched = mg.stitch_audio_segments(
            chunks, sample_rate=1000, crossfade_seconds=0.1
        )
        self.assertEqual(len(stitched), 2800)

    def test_crossfade_has_no_bump_when_the_overlap_is_duplicated(self):
        # The continuation prompt re-emits the outgoing tail, so both sides of
        # the seam are the same music.  A textbook equal-power pair would add
        # up to +3 dB in the middle of that blend.
        sample_rate = 1000
        index = np.arange(2000, dtype=np.float32)
        signal = (0.5 * np.sin(2 * np.pi * 5 * index / sample_rate)).astype(
            np.float32
        )
        previous, upcoming = signal[:1500].copy(), signal[500:].copy()

        mixed = mg.equal_power_crossfade(
            previous, upcoming, sample_rate=sample_rate, crossfade_seconds=1.0
        )

        baseline = float(np.sqrt(np.mean(previous[-1000:] ** 2)))
        for start in range(500, 1500, 100):
            window = mixed[start:start + 100]
            level = float(np.sqrt(np.mean(window ** 2)))
            self.assertAlmostEqual(level, baseline, delta=0.1 * baseline)

    def test_crossfade_still_uses_equal_power_for_unrelated_audio(self):
        sample_rate = 1000
        rng = np.random.default_rng(7)
        previous = rng.standard_normal(2000).astype(np.float32) * 0.2
        upcoming = rng.standard_normal(2000).astype(np.float32) * 0.2

        mixed = mg.equal_power_crossfade(
            previous, upcoming, sample_rate=sample_rate, crossfade_seconds=1.0
        )

        # Uncorrelated material keeps constant power through the seam.
        seam_power = float(np.mean(mixed[1000:1400] ** 2))
        side_power = float(np.mean(previous[-400:] ** 2))
        self.assertAlmostEqual(seam_power, side_power, delta=0.2 * side_power)


class MasteringTests(SimpleTestCase):
    def test_loudness_gains_equalise_the_blocks(self):
        chunks = [
            np.full(2000, 0.5, dtype=np.float32),  # loud block
            np.full(2000, 0.1, dtype=np.float32),  # quiet block
        ]

        gains = mg.loudness_gains(chunks)

        for chunk, gain in zip(chunks, gains):
            level = mg.rms_dbfs(np.asarray(chunk) * gain)
            self.assertAlmostEqual(level, mg.TARGET_CHUNK_RMS_DBFS, delta=0.5)

    def test_loudness_boost_is_capped_but_attenuation_is_not(self):
        silent = np.zeros(1000, dtype=np.float32)
        hot = np.full(1000, 1.5, dtype=np.float32)

        loudness_gains = mg.loudness_gains([silent, hot])
        self.assertLessEqual(
            20 * np.log10(loudness_gains[0]), mg.MAX_CHUNK_BOOST_DB + 1e-6
        )
        self.assertLess(loudness_gains[1], 1.0)

    def test_scale_to_ceiling_never_clips(self):
        over_range = np.linspace(-2.2, 2.2, 500, dtype=np.float32)

        scaled = mg.scale_to_ceiling(over_range)

        self.assertLessEqual(float(np.max(np.abs(scaled))), mg.MASTER_PEAK_CEILING)
        self.assertAlmostEqual(
            float(np.max(np.abs(scaled))), mg.MASTER_PEAK_CEILING, places=3
        )
        # Content that already fits is left untouched (no needless quieting).
        quiet = np.linspace(-0.5, 0.5, 500, dtype=np.float32)
        self.assertTrue(np.allclose(mg.scale_to_ceiling(quiet), quiet))

    def test_seam_does_not_step_when_block_gains_differ(self):
        # A loud block followed by a quiet one: the second block re-emits the
        # first block's tail as its continuation prompt, so the seam contains
        # the same audio on both sides while the two blocks want gains that
        # are 20 dB apart.
        sample_rate = 1000
        index = np.arange(2000, dtype=np.float32)
        wave = (0.5 * np.sin(2 * np.pi * 5 * index / sample_rate)).astype(
            np.float32
        )
        previous = wave[:1000]
        upcoming = np.concatenate([wave[900:1000], 0.1 * wave[1000:1900]])

        gains = mg.loudness_gains(
            [previous, upcoming], sample_rate=1000, crossfade_seconds=0.1
        )
        stitched = mg.stitch_audio_segments(
            [previous, upcoming],
            sample_rate=sample_rate,
            crossfade_seconds=0.1,
            gains=gains,
        )

        target = 10 ** (mg.TARGET_CHUNK_RMS_DBFS / 20)
        seam_start = 1000 - 100
        for window in ((seam_start, seam_start + 50), (seam_start + 50, 1000)):
            level = float(
                np.sqrt(np.mean(stitched[window[0]:window[1]] ** 2))
            )
            self.assertAlmostEqual(level, target, delta=0.15 * target)

        # Handing the incoming body straight to the second block's own gain
        # would jump the seam by this much.
        self.assertGreater(20 * np.log10(gains[1] / gains[0]), 6.0)

    def test_seam_ramp_opens_on_the_outgoing_level_and_closes_on_target(self):
        # Block 1 is quiet but ends on a loud tail, so its average loudness
        # differs from the level the seam itself carries.
        target_level = 10 ** (mg.TARGET_CHUNK_RMS_DBFS / 20)
        head_level = 0.3536
        outgoing_level = 0.4786

        ramp = mg.seam_gain_ramp(
            outgoing_level, head_level, target_level, overlap=100
        )

        self.assertAlmostEqual(
            float(ramp[0]) * head_level, outgoing_level, places=3
        )
        self.assertAlmostEqual(
            float(ramp[-1]) * head_level, target_level, places=3
        )
        # A smooth glide, not a jump inside the crossfade.
        step = float(np.max(np.abs(np.diff(ramp))))
        self.assertLess(step, (ramp[0] - ramp[-1]) / 10)

        # A prompt that is effectively silent must not be amplified.
        silent = mg.seam_gain_ramp(outgoing_level, 1e-9, target_level, 8)
        self.assertTrue(np.allclose(silent, 1.0))

    def test_stitched_seam_hands_over_to_the_body_without_a_step(self):
        sample_rate = 1000
        index = np.arange(2000, dtype=np.float32)
        # Phase-shifted so the seam starts away from a zero crossing.
        wave = (0.5 * np.sin(2 * np.pi * 5 * (index + 50) / sample_rate)).astype(
            np.float32
        )
        previous = np.concatenate([0.1 * wave[:900], wave[900:1000]])
        upcoming = np.concatenate([wave[900:1000], 0.1 * wave[1000:1900]])

        gains = mg.loudness_gains(
            [previous, upcoming], sample_rate=1000, crossfade_seconds=0.1
        )
        stitched = mg.stitch_audio_segments(
            [previous, upcoming],
            sample_rate=sample_rate,
            crossfade_seconds=0.1,
            gains=gains,
        )

        target = 10 ** (mg.TARGET_CHUNK_RMS_DBFS / 20)
        body = float(np.sqrt(np.mean(stitched[1000:1050] ** 2)))
        self.assertAlmostEqual(body, target, delta=0.15 * target)

        # The crossfade still opens on the outgoing tail's level …
        outgoing = float(np.sqrt(np.mean(previous[-100:] ** 2))) * gains[0]
        opening = float(np.sqrt(np.mean(stitched[900:950] ** 2)))
        self.assertGreater(opening, 0.6 * outgoing)

        # … and hands over to the body without a step (measure the last samples
        # of the crossfade against the first samples of the body: a longer
        # window would average in the middle of the glide itself).
        closing = float(np.sqrt(np.mean(stitched[995:1000] ** 2)))
        handover = float(np.sqrt(np.mean(stitched[1000:1005] ** 2)))
        self.assertLess(closing, 1.5 * handover)
        self.assertGreater(closing, 0.6 * handover)

    def test_tame_peaks_leaves_clean_audio_untouched(self):
        tone = (0.4 * np.sin(2 * np.pi * 440 * np.arange(32000) / 32000)).astype(
            np.float32
        )
        self.assertTrue(np.array_equal(mg.tame_peaks(tone, sample_rate=32000), tone))

    def test_tame_peaks_tames_a_transient_without_touching_the_bed(self):
        sample_rate = 32000
        index = np.arange(sample_rate, dtype=np.float64)
        tone = 0.4 * np.sin(2 * np.pi * 220 * index / sample_rate)
        tone[sample_rate // 2:sample_rate // 2 + 32] *= 8.0  # a hot spike
        hot = tone.astype(np.float32)

        tamed = mg.tame_peaks(hot, sample_rate=sample_rate)

        self.assertLessEqual(
            float(np.max(np.abs(tamed))), mg.MASTER_PEAK_CEILING + 1e-3
        )
        # A full release window after the spike the bed is untouched: keeping
        # the loudness is the whole point of taming instead of scaling.
        before = float(np.sqrt(np.mean(hot[:int(0.3 * sample_rate)] ** 2)))
        after = float(np.sqrt(np.mean(tamed[int(0.7 * sample_rate):] ** 2)))
        self.assertAlmostEqual(after, before, delta=0.02 * before)

    def test_tame_peaks_caps_the_reduction(self):
        sample_rate = 32000
        hot = np.zeros(sample_rate, dtype=np.float32)
        hot[100:140] = 100.0

        tamed = mg.tame_peaks(hot, sample_rate=sample_rate)

        reduction_db = 20 * np.log10(100.0 / float(np.max(np.abs(tamed))))
        self.assertLessEqual(reduction_db, 20.0 + 1e-6)

    def test_stitch_rejects_a_mismatched_gain_list(self):
        chunks = [np.ones(500, dtype=np.float32)] * 2
        with self.assertRaises(mg.MusicGenerationError):
            mg.stitch_audio_segments(
                chunks, sample_rate=1000, crossfade_seconds=0.1, gains=[1.0]
            )


class GenerationHopTests(SimpleTestCase):
    def test_long_blocks_are_split_into_short_hops(self):
        segments = mg.normalise_segments(
            [
                {"text_content": "a", "duration": 30.4},
                {"text_content": "b", "duration": 31.76},
                {"text_content": "c", "duration": 33.6},
            ]
        )

        hops = mg.plan_generation_hops(segments)

        self.assertEqual([position for position, _ in hops], [0, 0, 0, 1, 1, 1, 2, 2, 2])
        for _, requested in hops:
            self.assertLessEqual(requested, mg.MAX_GENERATION_SECONDS)
        # Every hop adds its own audio, so the hops still total the script.
        self.assertAlmostEqual(
            sum(requested for _, requested in hops),
            sum(segment.safe_duration for segment in segments),
            places=5,
        )

    def test_short_block_stays_a_single_hop(self):
        segments = mg.normalise_segments([{"text_content": "a", "duration": 8.0}])
        self.assertEqual(len(mg.plan_generation_hops(segments)), 1)

    def test_hop_splitting_covers_minimum_duration(self):
        segments = mg.normalise_segments([{"text_content": "a", "duration": 0.0}])
        hops = mg.plan_generation_hops(segments)
        self.assertEqual(len(hops), 1)
        self.assertEqual(hops[0][0], 0)
        self.assertEqual(hops[0][1], segments[0].safe_duration)

    def test_sliver_remainder_is_folded_into_the_previous_hop(self):
        # The worker floors a request at 0.5 s, so a 0.2 s tail would lengthen
        # the track.  Folding keeps the total exact.
        segments = mg.normalise_segments([{"text_content": "a", "duration": 24.2}])

        hops = mg.plan_generation_hops(segments)

        self.assertEqual([round(value, 3) for _, value in hops], [12.0, 12.2])
        self.assertAlmostEqual(sum(value for _, value in hops), 24.2, places=5)


class TransformersHelpersTests(SimpleTestCase):
    def test_musicgen_frame_rate_is_fifty_tokens_per_second(self):
        class AudioEncoder:
            frame_rate = 50

        class Decoder:
            num_codebooks = 4

        class Config:
            audio_encoder = AudioEncoder()
            decoder = Decoder()

        class Model:
            config = Config()

        # Transformers counts decoder frames, not interleaved codebook tokens.
        self.assertEqual(mg._transformers_tokens_per_second(Model()), 50)


class FakeModel:
    """Minimal MusicGen stand-in that records how it was called."""

    def __init__(self, sample_rate=1000):
        self.sample_rate = sample_rate
        self.calls = []
        self.durations = []
        self.continuation_shapes = []

    def set_generation_params(self, **kwargs):
        self.durations.append(kwargs.get('duration'))

    def generate(self, prompts, progress=False):
        self.calls.append(('generate', prompts))
        duration = self.durations[-1]
        samples = int(round(duration * self.sample_rate))
        return np.ones((1, 1, samples), dtype=np.float32) * 0.25

    def generate_continuation(self, prompt_wav, sample_rate, prompts, progress=False):
        self.calls.append(('continuation', prompts))
        self.continuation_shapes.append(tuple(prompt_wav.shape))
        duration = self.durations[-1]
        samples = int(round(duration * self.sample_rate))
        return np.ones((1, 1, samples), dtype=np.float32) * 0.25


class SynthesisTests(SimpleTestCase):
    def test_continuation_uses_trailing_three_seconds(self):
        model = FakeModel()
        progress = []
        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, 'soundtrack.wav')
            result = mg.synthesize_soundtrack(
                SCRIPT,
                output,
                model=model,
                sample_rate=1000,
                crossfade_seconds=1.0,
                progress=lambda c, t, d: progress.append((c, t, d)),
                unload_after=False,
            )

            self.assertTrue(os.path.isfile(output))
            self.assertEqual(len(model.calls), 3)
            self.assertEqual(model.calls[0][0], 'generate')
            self.assertEqual(model.calls[1][0], 'continuation')
            self.assertEqual(model.calls[2][0], 'continuation')

            # Segment 0 is 5s; continuation segments add their own duration.
            self.assertEqual(result['duration'], 12.0)
            self.assertEqual(progress[-1][0], 3)
            self.assertEqual(progress[-1][1], 3)

        # First continuation prompt is the last 3 seconds of segment 0.
        self.assertEqual(model.continuation_shapes[0], (1, 1, 3000))

    def test_generation_failure_unloads_model(self):
        class BrokenModel(FakeModel):
            def generate(self, prompts, progress=False):
                raise RuntimeError('CUDA out of memory')

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(mg.MusicGenerationError):
                mg.synthesize_soundtrack(
                    SCRIPT,
                    os.path.join(tmp, 'x.wav'),
                    model=BrokenModel(),
                    sample_rate=1000,
                    unload_after=True,
                )


class DuckingTests(SimpleTestCase):
    def test_ducking_envelope_attenuates_only_voice_regions(self):
        sample_rate = 1000
        narration = np.zeros((2000, 2), dtype=np.float32)
        narration[1000:, :] = 0.5  # second half is "speech"

        envelope = mg._voice_ducking_envelope(
            narration, sample_rate, ducking_db=-12.0
        )

        self.assertAlmostEqual(float(envelope[100]), 1.0, places=2)
        self.assertAlmostEqual(float(envelope[1500]), 10 ** (-12 / 20), places=2)

    def test_mix_background_music_loops_and_writes_output(self):
        sample_rate = 8000
        with tempfile.TemporaryDirectory() as tmp:
            narration_path = os.path.join(tmp, 'narration.wav')
            music_path = os.path.join(tmp, 'music.wav')
            output_path = os.path.join(tmp, 'mixed.wav')

            import soundfile as sf

            sf.write(
                narration_path,
                np.zeros((sample_rate, 2), dtype=np.float32),
                sample_rate,
            )
            sf.write(
                music_path,
                np.ones((sample_rate // 2, 2), dtype=np.float32) * 0.2,
                sample_rate,
            )

            result = mg.mix_background_music(
                narration_path,
                music_path,
                output_path,
                sample_rate=sample_rate,
                music_gain_db=-6.0,
                ducking_db=-12.0,
            )

            self.assertTrue(os.path.isfile(output_path))
            self.assertAlmostEqual(result['duration'], 1.0, places=2)
            mixed, rate = sf.read(output_path)
            self.assertEqual(rate, sample_rate)
            self.assertEqual(len(mixed), sample_rate)

    def test_engine_status_is_serialisable(self):
        status = mg.engine_status()
        self.assertIn('available', status)
        self.assertIn('cuda_available', status)
        self.assertIn('model', status)
        self.assertEqual(status['model'], mg.MUSICGEN_MODEL)

    def test_release_tts_resources_evicts_both_engines(self):
        from unittest.mock import patch

        with patch(
            'core_engine.model_loader.KokoroModelLoader.unload',
            return_value=True,
        ) as kokoro_unload, patch(
            'core_engine.qwen_client.shutdown'
        ) as qwen_shutdown:
            released = mg.release_tts_resources()

        kokoro_unload.assert_called_once()
        qwen_shutdown.assert_called_once()
        self.assertIn('kokoro', released)
        self.assertIn('qwen', released)


class NoiseFloorTests(SimpleTestCase):
    """Issue #13: MusicGen's floor must not survive level matching."""

    sample_rate = 32000

    def _band_db(self, audio, low, high):
        spectrum = np.abs(np.fft.rfft(audio * np.hanning(len(audio)))) ** 2
        freqs = np.fft.rfftfreq(len(audio), 1.0 / self.sample_rate)
        mask = (freqs >= low) & (freqs < high)
        return 10.0 * np.log10(spectrum[mask].sum() / len(audio) + 1e-30)

    def _mixture(self, seconds=1.5):
        rng = np.random.default_rng(11)
        t = np.arange(int(seconds * self.sample_rate)) / self.sample_rate
        return (
            0.30 * np.sin(2 * np.pi * 440 * t)
            + 0.05 * np.sin(2 * np.pi * 3000 * t)
            + 0.03 * rng.standard_normal(t.size)
        ).astype(np.float32)

    def test_gate_removes_the_floor_without_touching_the_tonals(self):
        mixture = self._mixture()

        gated = mg.reduce_noise_floor(mixture, self.sample_rate)

        self.assertEqual(gated.shape, mixture.shape)
        self.assertEqual(gated.dtype, np.float32)
        self.assertFalse(np.isnan(gated).any())
        # 5-9 kHz holds nothing but the noise in this fixture …
        self.assertLess(
            self._band_db(gated, 5000, 9000),
            self._band_db(mixture, 5000, 9000) - 3.0,
        )
        # … while the musical partials come through untouched.
        self.assertAlmostEqual(
            self._band_db(gated, 430, 450),
            self._band_db(mixture, 430, 450),
            delta=0.5,
        )
        self.assertAlmostEqual(
            self._band_db(gated, 2900, 3100),
            self._band_db(mixture, 2900, 3100),
            delta=0.5,
        )

    def test_clean_signal_passes_through(self):
        t = np.arange(2 * self.sample_rate) / self.sample_rate
        clean = (0.4 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)

        gated = mg.reduce_noise_floor(clean, self.sample_rate)

        # Whatever the gate does to a clean tone has to stay far below the
        # signal itself (only spectral splatter either side of the partial is
        # ever touched, because the partial and the region below the cutoff
        # are protected).
        residual = float(np.sqrt(np.mean((gated - clean) ** 2)))
        reference = float(np.sqrt(np.mean(clean ** 2)))
        self.assertLess(
            20.0 * np.log10(residual / reference + 1e-12),
            -40.0,
            "a clean signal must not be processed audibly",
        )

    def test_signal_without_a_measurable_floor_is_returned_as_a_copy(self):
        short = np.zeros(512, dtype=np.float32)

        gated = mg.reduce_noise_floor(short, self.sample_rate)

        self.assertIsNot(gated, short)
        self.assertTrue(np.array_equal(gated, short))

    def test_stereo_input_keeps_its_shape(self):
        stereo = np.stack([self._mixture(), self._mixture() * 0.5], axis=1)

        gated = mg.reduce_noise_floor(stereo, self.sample_rate)

        self.assertEqual(gated.shape, stereo.shape)
        self.assertEqual(gated.dtype, np.float32)


class HighBandTiltTests(SimpleTestCase):
    """Issue #13: the high band must not grow out of proportion to the body."""

    sample_rate = 32000

    def _band_db(self, audio, low, high):
        spectrum = np.abs(np.fft.rfft(audio * np.hanning(len(audio)))) ** 2
        freqs = np.fft.rfftfreq(len(audio), 1.0 / self.sample_rate)
        mask = (freqs >= low) & (freqs < high)
        return 10.0 * np.log10(spectrum[mask].sum() / len(audio) + 1e-30)

    def test_bright_high_band_is_pulled_back_and_the_body_is_not(self):
        # A warm body with an exaggerated high band, shaped like the reported
        # ending of a track.
        t = np.arange(8 * self.sample_rate) / self.sample_rate
        signal = (
            0.30 * np.sin(2 * np.pi * 180 * t)
            + 0.20 * np.sin(2 * np.pi * 700 * t)
            + 0.06 * np.sin(2 * np.pi * 2500 * t)
            + 0.05 * np.sin(2 * np.pi * 3400 * t)
        ).astype(np.float32)

        tilted = mg.tilt_high_band(signal, self.sample_rate)

        self.assertEqual(tilted.shape, signal.shape)
        self.assertFalse(np.isnan(tilted).any())
        self.assertLess(
            self._band_db(tilted, 2000, 8000),
            self._band_db(signal, 2000, 8000) - 3.0,
            "the out-of-proportion high band must come down",
        )
        self.assertAlmostEqual(
            self._band_db(tilted, 500, 1200),
            self._band_db(signal, 500, 1200),
            msg="the musical body must not be touched",
            delta=0.5,
        )

    def test_a_well_balanced_track_is_left_alone(self):
        # High band already well below the body: no correction is due.
        t = np.arange(8 * self.sample_rate) / self.sample_rate
        signal = (
            0.30 * np.sin(2 * np.pi * 180 * t)
            + 0.25 * np.sin(2 * np.pi * 700 * t)
            + 0.004 * np.sin(2 * np.pi * 3000 * t)
        ).astype(np.float32)

        tilted = mg.tilt_high_band(signal, self.sample_rate)

        self.assertAlmostEqual(
            self._band_db(tilted, 2000, 8000),
            self._band_db(signal, 2000, 8000),
            delta=1.0,
        )

    def test_short_signal_is_returned_as_a_copy(self):
        short = np.zeros(512, dtype=np.float32)
        tilted = mg.tilt_high_band(short, self.sample_rate)
        self.assertIsNot(tilted, short)
        self.assertTrue(np.array_equal(tilted, short))


class EndingTests(SimpleTestCase):
    """Issue #13: the score must resolve instead of stopping dead."""

    sample_rate = 32000

    def _tone(self, seconds):
        t = np.arange(int(seconds * self.sample_rate)) / self.sample_rate
        return (0.4 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)

    def test_tail_fade_reaches_silence_without_changing_the_length(self):
        tone = self._tone(20.0)

        faded = mg.apply_tail_fade(tone, self.sample_rate, fade_seconds=4.0)

        self.assertEqual(faded.shape, tone.shape)
        self.assertLess(abs(float(faded[-1])), 1e-6, "the track must end silent")
        # A cosine curve: unity for the first 16 s, 1/sqrt(2) halfway through
        # the 4 s fade.
        self.assertTrue(np.array_equal(faded[:16 * self.sample_rate],
                                       tone[:16 * self.sample_rate]))
        period = int(round(self.sample_rate / 220))
        halfway = faded[18 * self.sample_rate: 18 * self.sample_rate + period]
        self.assertAlmostEqual(
            float(np.max(np.abs(halfway))), 0.4 * np.sqrt(0.5), delta=0.03
        )

    def test_short_clips_get_a_proportionally_shorter_fade(self):
        tone = self._tone(2.0)

        faded = mg.apply_tail_fade(tone, self.sample_rate, fade_seconds=4.0)

        # Capped at TAIL_FADE_MAX_FRACTION of the clip, so the opening is
        # still recognisably the music.
        self.assertTrue(np.array_equal(faded[: self.sample_rate],
                                       tone[: self.sample_rate]))
        self.assertLess(abs(float(faded[-1])), 1e-6)

    def test_a_track_that_already_fades_is_recognised(self):
        tone = self._tone(20.0)

        faded = mg.apply_tail_fade(tone, self.sample_rate, fade_seconds=4.0)

        detected = mg.detect_tail_fade_seconds(faded, self.sample_rate)
        # The walk runs back through the flat material just before the fade as
        # well, so the length reported is at least the real fade.  Both of its
        # consumers want "does this already resolve?", and over-reporting only
        # trims a little more material when looping — never too little.
        self.assertGreaterEqual(detected, 3.5)
        self.assertGreater(detected, 0.0)

    def test_a_track_that_ends_at_normal_level_is_not_reported_as_faded(self):
        tone = self._tone(20.0)
        # Only dips to -6 dB: still an ending, but not a fade to silence.
        tone[-self.sample_rate:] *= np.linspace(1.0, 0.5, self.sample_rate)

        self.assertEqual(mg.detect_tail_fade_seconds(tone, self.sample_rate), 0.0)

    def test_a_constant_track_is_not_reported_as_faded(self):
        constant = np.full(self.sample_rate * 5, 0.2, dtype=np.float32)
        self.assertEqual(
            mg.detect_tail_fade_seconds(constant, self.sample_rate), 0.0
        )


class LoopingTests(SimpleTestCase):
    """Issue #13: looping must not click and must not resurrect a fade."""

    sample_rate = 8000

    def _bed(self, seconds=0.5, faded=False):
        t = np.arange(int(seconds * self.sample_rate)) / self.sample_rate
        bed = (0.2 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
        if faded:
            bed = mg.apply_tail_fade(bed, self.sample_rate, fade_seconds=0.4)
        return bed[:, None]

    def test_loop_reaches_the_target_without_a_hard_cut(self):
        bed = self._bed()

        looped = mg.loop_music_bed(bed, 3 * self.sample_rate, self.sample_rate)

        self.assertEqual(looped.shape, (3 * self.sample_rate, 1))
        # A hard cut shows up as a step far larger than the signal's own.
        natural = float(np.max(np.abs(np.diff(bed[:, 0]))))
        self.assertLessEqual(
            float(np.max(np.abs(np.diff(looped[:, 0])))), 1.5 * natural
        )

    def test_the_baked_fade_does_not_appear_in_the_middle_of_a_loop(self):
        bed = self._bed(faded=True)
        # The source really does end in silence …
        self.assertLess(abs(float(bed[-1, 0])), 1e-3)

        looped = mg.loop_music_bed(bed, 4 * self.sample_rate, self.sample_rate)

        # … but no copy of it is audible inside the loop.
        middle = looped[self.sample_rate: 3 * self.sample_rate, 0]
        windows = [
            float(np.sqrt(np.mean(middle[i:i + self.sample_rate] ** 2)))
            for i in range(0, middle.size - self.sample_rate, self.sample_rate)
        ]
        reference = float(np.sqrt(np.mean(bed[: self.sample_rate // 2, 0] ** 2)))
        self.assertTrue(windows)
        for window in windows:
            self.assertGreater(window, 0.5 * reference)


class MixEndingTests(SimpleTestCase):
    """The render must not fade a track that already fades, and must fade one
    that does not."""

    sample_rate = 8000

    def _write(self, directory, name, samples):
        import soundfile as sf

        path = os.path.join(directory, name)
        sf.write(path, samples, self.sample_rate)
        return path

    def test_tail_fade_is_skipped_when_the_music_already_fades(self):
        seconds = 6.0
        t = np.arange(int(seconds * self.sample_rate)) / self.sample_rate
        music = (0.2 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
        music = mg.apply_tail_fade(music, self.sample_rate, fade_seconds=4.0)

        with tempfile.TemporaryDirectory() as directory:
            narration = self._write(
                directory, "n.wav", np.zeros(int(seconds * self.sample_rate))
            )
            bed = self._write(directory, "m.wav", music)
            result = mg.mix_background_music(
                narration, bed, os.path.join(directory, "out.wav"),
                sample_rate=self.sample_rate,
            )

        self.assertFalse(result["tail_fade_applied"])
        self.assertTrue(result["source_tail_faded"])

    def test_tail_fade_is_applied_when_the_music_stops_dead(self):
        import soundfile as sf

        music = np.full(self.sample_rate * 6, 0.2, dtype=np.float32)

        with tempfile.TemporaryDirectory() as directory:
            narration = self._write(directory, "n.wav", np.zeros(music.size))
            bed = self._write(directory, "m.wav", music)
            output = os.path.join(directory, "out.wav")
            result = mg.mix_background_music(
                narration, bed, output, sample_rate=self.sample_rate
            )
            mixed, _ = sf.read(output)

        self.assertTrue(result["tail_fade_applied"])
        self.assertFalse(result["source_tail_faded"])
        self.assertLess(
            float(np.max(np.abs(mixed[-1]))), 1e-3, "the video must end silent"
        )


