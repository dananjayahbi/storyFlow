"""Tests for the MusicGen worker's checkpoint integrity guard."""

import os
import tempfile
from unittest import mock

from django.test import SimpleTestCase

from core_engine import musicgen_worker as worker


class WeightsIntegrityTests(SimpleTestCase):
    def setUp(self):
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()
        os.environ.pop('MUSICGEN_SKIP_CHECKSUM', None)
        self.addCleanup(self._env.stop)

    def _write(self, directory, payload):
        path = os.path.join(directory, worker.MODEL_WEIGHTS_FILE)
        with open(path, 'wb') as handle:
            handle.write(payload)
        return path

    def test_matching_checksum_is_accepted_and_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            self._write(directory, b'musicgen')
            with mock.patch.object(worker, 'MODEL_WEIGHTS_SIZE', 8), \
                    mock.patch.object(
                        worker, 'MODEL_WEIGHTS_SHA256', worker._sha256_file(
                            os.path.join(directory, worker.MODEL_WEIGHTS_FILE)
                        ),
                    ):
                first = worker._weights_integrity(directory)
                second = worker._weights_integrity(directory)

        self.assertTrue(first['ok'])
        self.assertTrue(first['checked'])
        self.assertFalse(first.get('cached'))
        self.assertTrue(second['ok'])
        self.assertTrue(second.get('cached'))

    def test_truncated_weights_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            self._write(directory, b'music')
            with mock.patch.object(worker, 'MODEL_WEIGHTS_SIZE', 4096):
                result = worker._weights_integrity(directory)

        self.assertFalse(result['ok'])
        self.assertIn('truncated', result['reason'])

    def test_corrupt_weights_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            self._write(directory, b'musicgen')
            with mock.patch.object(worker, 'MODEL_WEIGHTS_SIZE', 8), \
                    mock.patch.object(worker, 'MODEL_WEIGHTS_SHA256', '0' * 64):
                result = worker._weights_integrity(directory)

        self.assertFalse(result['ok'])
        self.assertIn('corrupt', result['reason'])

    def test_missing_weights_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            result = worker._weights_integrity(directory)

        self.assertFalse(result['ok'])
        self.assertIn('missing', result['reason'])

    def test_skip_checksum_override(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ, {'MUSICGEN_SKIP_CHECKSUM': '1'}, clear=False
            ):
                result = worker._weights_integrity(directory)

        self.assertTrue(result['ok'])
        self.assertFalse(result['checked'])
