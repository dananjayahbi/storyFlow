"""Segment narration download endpoint (WAV / MP3)."""

import os
import shutil
import tempfile

from django.core.files.base import ContentFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Account, GlobalSettings, Project, Segment

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class SegmentAudioDownloadTests(APITestCase):
    def setUp(self):
        GlobalSettings.load()
        self.account = Account.objects.create(
            name='Page One', section='facebook'
        )
        self.project = Project.objects.create(
            title='Beavers', section='facebook', account=self.account
        )
        self.segment = Segment.objects.create(
            project=self.project,
            sequence_index=0,
            text_content='Hello world',
            audio_duration=1.0,
            audio_engine='kokoro',
        )
        self.segment.audio_file.save(
            'narration.wav',
            ContentFile(b'RIFF' + b'\x00' * 64),
            save=True,
        )
        self.url = (
            f'/api/segments/{self.segment.id}/download-audio/'
            f'?section=facebook&account={self.account.id}'
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_wav_download_is_an_attachment_with_a_readable_name(self):
        response = self.client.get(self.url + '&audio_format=wav')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'audio/wav')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('Beavers - segment 1.wav', response['Content-Disposition'])
        self.assertTrue(b''.join(response.streaming_content).startswith(b'RIFF'))

    def test_mp3_download_uses_the_converter(self):
        def fake_convert(source_path, output_path, bitrate='192k'):
            self.assertTrue(os.path.isfile(source_path))
            with open(output_path, 'wb') as handle:
                handle.write(b'ID3fake-mp3')

        with __import__('unittest').mock.patch(
            'core_engine.audio_convert.convert_to_mp3',
            side_effect=fake_convert,
        ):
            response = self.client.get(self.url + '&audio_format=mp3')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'audio/mpeg')
        self.assertIn('Beavers - segment 1.mp3', response['Content-Disposition'])
        self.assertEqual(
            b''.join(response.streaming_content), b'ID3fake-mp3'
        )

    def test_defaults_to_wav(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'audio/wav')

    def test_rejects_unknown_format(self):
        response = self.client.get(self.url + '&audio_format=flac')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('wav', response.data['error'])

    def test_missing_audio_returns_404(self):
        self.segment.audio_file = None
        self.segment.save(update_fields=['audio_file'])
        response = self.client.get(self.url + '&audio_format=wav')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_account_cannot_download(self):
        other = Account.objects.create(name='Page Two', section='facebook')
        url = (
            f'/api/segments/{self.segment.id}/download-audio/'
            f'?section=facebook&account={other.id}'
        )
        response = self.client.get(url + '&audio_format=wav')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

