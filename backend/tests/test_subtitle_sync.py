"""Tests for audio-accurate subtitle timing (Issue #29)."""

import math
import os
import shutil
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Account, GlobalSettings, Project, Segment
from core_engine import subtitle_sync
from core_engine.subtitle_engine import chunk_and_time


class InlineTaskManager:
    def is_cancelled(self, task_id):
        return False

    def update_task_progress(self, *args, **kwargs):
        return None

    def add_completed_segment(self, *args, **kwargs):
        return None

    def add_error(self, *args, **kwargs):
        return None

    def submit_task(self, task_fn, task_id=None):
        task_fn()
        return task_id


def _write_tone_bursts(path, bursts, gap_seconds=0.4, sample_rate=16000):
    import numpy as np
    import soundfile as sf

    parts = []
    for index, duration in enumerate(bursts):
        samples = int(sample_rate * duration)
        time = np.arange(samples) / sample_rate
        tone = 0.12 * np.sin(2 * math.pi * 220 * time).astype('float32')
        parts.append(tone)
        if index < len(bursts) - 1:
            parts.append(np.zeros(int(sample_rate * gap_seconds), dtype='float32'))
    sf.write(path, np.concatenate(parts), sample_rate)


class SentenceSplitTests(SimpleTestCase):
    def test_splits_sentences_and_keeps_abbreviations(self):
        sentences = subtitle_sync.split_sentences(
            'Dr. Smith arrived. The CIA left! Did it work? Yes.'
        )
        self.assertEqual(len(sentences), 4)
        self.assertEqual(sentences[0], 'Dr. Smith arrived.')
        self.assertEqual(sentences[1], 'The CIA left!')

    def test_proportional_estimate_covers_exact_duration(self):
        timings = subtitle_sync.estimate_sentence_timings(
            'One short line. A much longer second sentence with many words.',
            7.5,
        )
        self.assertEqual(len(timings), 2)
        self.assertEqual(timings[0]['start'], 0.0)
        self.assertAlmostEqual(
            timings[-1]['end'], 7.5, places=2
        )
        self.assertAlmostEqual(
            timings[0]['end'], timings[1]['start'], places=3
        )


class SilenceDetectionTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def test_detects_real_pauses_in_synthetic_audio(self):
        path = os.path.join(self.tmp, 'bursts.wav')
        _write_tone_bursts(path, [1.0, 1.0, 1.0], gap_seconds=0.4)

        silences = subtitle_sync.detect_silences(path)
        self.assertEqual(len(silences), 2)
        first_centre = sum(silences[0]) / 2
        second_centre = sum(silences[1]) / 2
        self.assertAlmostEqual(first_centre, 1.2, delta=0.12)
        self.assertAlmostEqual(second_centre, 2.6, delta=0.12)

    def test_builds_sentence_spans_snapped_to_pauses(self):
        path = os.path.join(self.tmp, 'bursts.wav')
        _write_tone_bursts(path, [1.0, 1.0, 1.0], gap_seconds=0.4)
        timings = subtitle_sync.build_audio_timings(
            'First sentence. Second sentence. Third sentence.',
            path,
            3.8,
        )
        self.assertEqual(timings['version'], subtitle_sync.TIMINGS_VERSION)
        self.assertEqual(timings['method'], 'vad-snap')
        sentences = timings['sentences']
        self.assertEqual(len(sentences), 3)
        self.assertEqual(sentences[0]['start'], 0.0)
        self.assertAlmostEqual(sentences[0]['end'], 1.2, delta=0.15)
        self.assertAlmostEqual(sentences[1]['start'], 1.2, delta=0.15)
        self.assertAlmostEqual(sentences[1]['end'], 2.6, delta=0.15)
        self.assertAlmostEqual(sentences[-1]['end'], 3.8, places=2)

    def test_missing_audio_falls_back_to_proportional(self):
        timings = subtitle_sync.build_audio_timings(
            'One. Two. Three.',
            os.path.join(self.tmp, 'missing.wav'),
            3.0,
        )
        self.assertEqual(timings['method'], 'proportional')
        self.assertEqual(len(timings['sentences']), 3)


class SubtitleChunkTimingTests(SimpleTestCase):
    def _timings(self):
        return {
            'version': 1,
            'method': 'vad-snap',
            'total': 6.0,
            'sentences': [
                {'text': 'One', 'start': 0.0, 'duration': 2.0, 'end': 2.0},
                {'text': 'Two', 'start': 2.0, 'duration': 4.0, 'end': 6.0},
            ],
        }

    def test_chunks_follow_measured_sentence_spans(self):
        chunks, timings = subtitle_sync.chunk_text_with_sentence_timings(
            'One short sentence. A much longer second sentence with several '
            'words in it.',
            6.0,
            self._timings(),
        )
        self.assertIsNotNone(chunks)
        self.assertIsNotNone(timings)
        self.assertTrue(chunks)
        self.assertEqual(timings[0][0], 0.0)
        # Every later chunk starts where the previous one ended.
        for previous, current in zip(timings, timings[1:]):
            self.assertAlmostEqual(
                previous[0] + previous[1], current[0], places=3
            )
        self.assertAlmostEqual(timings[-1][0] + timings[-1][1], 6.0, places=3)

    def test_sentence_count_mismatch_returns_none(self):
        self.assertIsNone(
            subtitle_sync.chunk_text_with_sentence_timings(
                'Only one sentence.', 6.0, self._timings()
            )
        )

    def test_chunk_and_time_falls_back_cleanly(self):
        chunks, timings = chunk_and_time('One. Two. Three.', 3.0, None)
        self.assertTrue(chunks)
        self.assertAlmostEqual(timings[-1][0] + timings[-1][1], 3.0, places=3)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AudioTimingsPersistenceTests(APITestCase):
    def setUp(self):
        self.addCleanup(
            lambda: shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        )
        self.account = Account.objects.create(name='Sync Account')
        self.project = Project.objects.create(
            title='Sync Project', account=self.account
        )
        self.segment = Segment.objects.create(
            project=self.project,
            sequence_index=0,
            text_content='First sentence. Second sentence.',
        )
        GlobalSettings.load()

    @patch('core_engine.model_loader.KokoroModelLoader.is_model_available', return_value=True)
    @patch('core_engine.subtitle_sync.build_audio_timings')
    @patch('core_engine.tts.synthesize')
    def test_generation_persists_measured_timings(
        self, mock_synthesize, mock_timings, _mock_model
    ):
        mock_synthesize.return_value = {
            'success': True,
            'duration': 2.0,
            'engine': 'kokoro',
        }
        mock_timings.return_value = {
            'version': 1,
            'method': 'vad-snap',
            'total': 2.0,
            'sentences': [
                {'text': 'First sentence.', 'start': 0.0, 'duration': 1.0, 'end': 1.0},
                {'text': 'Second sentence.', 'start': 1.0, 'duration': 1.0, 'end': 2.0},
            ],
        }
        manager = InlineTaskManager()
        with patch('api.views.get_task_manager', return_value=manager):
            response = self.client.post(
                f'/api/segments/{self.segment.id}/generate-audio/'
            )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.segment.refresh_from_db()
        self.assertEqual(self.segment.audio_timings['method'], 'vad-snap')
        self.assertEqual(len(self.segment.audio_timings['sentences']), 2)

    def test_removing_audio_clears_timings(self):
        self.segment.audio_file = 'audio/fake.wav'
        self.segment.audio_duration = 2.0
        self.segment.audio_timings = {'version': 1, 'sentences': []}
        self.segment.save()
        response = self.client.delete(
            f'/api/segments/{self.segment.id}/remove-audio/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.segment.refresh_from_db()
        self.assertEqual(self.segment.audio_timings, {})
        self.assertIsNone(self.segment.audio_duration)
