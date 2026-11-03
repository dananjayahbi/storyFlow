"""BGM Library tests: upload conversion, sharing and account isolation."""

import os
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Account, BGMClip, GlobalSettings

BGM_URL = '/api/bgm/'


def fake_convert(source_path, output_path, bitrate='192k'):
    with open(output_path, 'wb') as handle:
        handle.write(b'ID3fake-mp3-bytes')


class BGMUploadTests(APITestCase):
    def setUp(self):
        GlobalSettings.load()
        self.account = Account.objects.create(name='Page One', section='facebook')
        self.other = Account.objects.create(name='Page Two', section='facebook')
        self.youtube = Account.objects.create(name='Channel', section='youtube')
        self.url = f'{BGM_URL}?section=facebook&account={self.account.id}'

    def _upload(self, *, account=None, name='Track', shared=False, filename='song.wav'):
        account = account or self.account
        upload = SimpleUploadedFile(
            filename, b'RIFFfake-audio', content_type='audio/wav'
        )
        return self.client.post(
            f'{BGM_URL}?section={account.section}&account={account.id}',
            {'file': upload, 'name': name, 'is_shared': 'true' if shared else 'false'},
            format='multipart',
        )

    def test_upload_is_converted_to_mp3_and_stored(self):
        with patch('core_engine.audio_convert.convert_to_mp3', side_effect=fake_convert) as mocked, \
                patch('core_engine.audio_convert.probe_duration', return_value=123.4):
            response = self._upload(name='Epic ocean')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Epic ocean')
        self.assertTrue(response.data['file_url'].endswith('.mp3'))
        self.assertEqual(response.data['duration'], 123.4)
        self.assertEqual(response.data['original_format'], 'wav')
        self.assertTrue(response.data['can_edit'])
        mocked.assert_called_once()
        clip = BGMClip.objects.get(pk=response.data['id'])
        self.assertEqual(clip.account, self.account)
        self.assertEqual(clip.section, 'facebook')
        self.assertTrue(os.path.isfile(clip.file.path))

    def test_requires_account_and_file(self):
        no_account = self.client.post(
            f'{BGM_URL}?section=facebook', {'name': 'x'}, format='multipart'
        )
        self.assertEqual(no_account.status_code, status.HTTP_400_BAD_REQUEST)

        no_file = self.client.post(self.url, {'name': 'x'}, format='multipart')
        self.assertEqual(no_file.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_non_audio_extension(self):
        upload = SimpleUploadedFile('notes.txt', b'hello', content_type='text/plain')
        response = self.client.post(
            self.url, {'file': upload}, format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('audio', str(response.data).lower())

    def test_conversion_errors_are_returned(self):
        from core_engine.audio_convert import AudioConversionError

        with patch(
            'core_engine.audio_convert.convert_to_mp3',
            side_effect=AudioConversionError('ffmpeg missing'),
        ):
            response = self._upload()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('ffmpeg missing', response.data['error'])


class BGMSharingTests(APITestCase):
    def setUp(self):
        GlobalSettings.load()
        self.account = Account.objects.create(name='Page One', section='facebook')
        self.other = Account.objects.create(name='Page Two', section='facebook')
        self.youtube = Account.objects.create(name='Channel', section='youtube')

        self.own = BGMClip.objects.create(
            account=self.account, section='facebook', name='Mine'
        )
        self.shared = BGMClip.objects.create(
            account=self.other, section='facebook', name='Shared', is_shared=True
        )
        self.private = BGMClip.objects.create(
            account=self.other, section='facebook', name='Private'
        )

    def _url(self, account, suffix=''):
        return (
            f'{BGM_URL}{suffix}?section={account.section}&account={account.id}'
        )

    def test_list_includes_own_and_shared_clips_only(self):
        response = self.client.get(self._url(self.account))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {item['name'] for item in response.data['results']}
        self.assertEqual(names, {'Mine', 'Shared'})

        by_name = {item['name']: item for item in response.data['results']}
        self.assertTrue(by_name['Mine']['can_edit'])
        self.assertFalse(by_name['Shared']['can_edit'])
        self.assertEqual(by_name['Shared']['account_name'], 'Page Two')

    def test_shared_clips_do_not_cross_sections(self):
        response = self.client.get(self._url(self.youtube))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], [])

    def test_owner_can_share_and_rename(self):
        response = self.client.patch(
            self._url(self.account, f'{self.own.id}/'),
            {'is_shared': True, 'name': 'Mine shared'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.own.refresh_from_db()
        self.assertTrue(self.own.is_shared)
        self.assertEqual(self.own.name, 'Mine shared')

    def test_non_owner_cannot_edit_or_delete_a_shared_clip(self):
        edit = self.client.patch(
            self._url(self.account, f'{self.shared.id}/'),
            {'name': 'Hijacked'},
            format='json',
        )
        self.assertEqual(edit.status_code, status.HTTP_403_FORBIDDEN)

        delete = self.client.delete(self._url(self.account, f'{self.shared.id}/'))
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(BGMClip.objects.filter(pk=self.shared.pk).exists())

    def test_owner_can_delete_and_file_is_removed(self):
        clip = BGMClip.objects.create(
            account=self.account,
            section='facebook',
            name='Delete me',
            file='bgm/facebook/x/delete.mp3',
        )
        storage_path = clip.file.path
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        with open(storage_path, 'wb') as handle:
            handle.write(b'audio')
        response = self.client.delete(self._url(self.account, f'{clip.id}/'))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(BGMClip.objects.filter(pk=clip.pk).exists())
        self.assertFalse(os.path.exists(storage_path))
