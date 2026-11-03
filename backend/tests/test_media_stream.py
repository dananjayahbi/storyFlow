"""Tests for the Range-capable media view used by the audio/video players."""

import os

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from api.media_views import parse_range_header


class RangeParserTests(SimpleTestCase):
    def test_standard_ranges(self):
        self.assertEqual(parse_range_header('bytes=0-3', 100), (0, 3))
        self.assertEqual(parse_range_header('bytes=10-', 100), (10, 99))
        self.assertEqual(parse_range_header('bytes=-10', 100), (90, 99))
        self.assertEqual(parse_range_header('bytes=90-200', 100), (90, 99))

    def test_unsatisfiable_and_malformed(self):
        self.assertEqual(parse_range_header('bytes=100-', 100), (100, 99))
        self.assertEqual(parse_range_header('bytes=9-4', 100), (100, 99))
        self.assertIsNone(parse_range_header('items=0-1', 100))
        self.assertIsNone(parse_range_header('bytes=-', 100))


class MediaRangeResponseTests(TestCase):
    def setUp(self):
        self.relative_path = 'test-media/range-test.wav'
        self.path = os.path.join(str(settings.MEDIA_ROOT), self.relative_path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'wb') as handle:
            handle.write(b'0123456789abcdef')

    def tearDown(self):
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_full_response_advertises_range_support(self):
        response = self.client.get(f'/media/{self.relative_path}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Accept-Ranges'], 'bytes')
        self.assertEqual(response['Content-Length'], '16')
        self.assertEqual(b''.join(response.streaming_content), b'0123456789abcdef')

    def test_range_request_returns_partial_content(self):
        response = self.client.get(
            f'/media/{self.relative_path}', HTTP_RANGE='bytes=4-7'
        )
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response['Content-Range'], 'bytes 4-7/16')
        self.assertEqual(response['Content-Length'], '4')
        self.assertEqual(b''.join(response.streaming_content), b'4567')

    def test_suffix_range(self):
        response = self.client.get(
            f'/media/{self.relative_path}', HTTP_RANGE='bytes=-4'
        )
        self.assertEqual(response.status_code, 206)
        self.assertEqual(b''.join(response.streaming_content), b'cdef')

    def test_unsatisfiable_range_returns_416(self):
        response = self.client.get(
            f'/media/{self.relative_path}', HTTP_RANGE='bytes=99-'
        )
        self.assertEqual(response.status_code, 416)
        self.assertEqual(response['Content-Range'], 'bytes */16')

    def test_missing_and_traversal_paths_are_404(self):
        self.assertEqual(
            self.client.get('/media/test-media/missing.wav').status_code, 404
        )
        self.assertEqual(
            self.client.get('/media/../manage.py').status_code, 404
        )
