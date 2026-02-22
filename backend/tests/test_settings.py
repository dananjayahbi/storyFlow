"""
Task 05.03.15 — Write Settings Tests

Comprehensive Django REST Framework API tests covering all GlobalSettings
endpoints: settings retrieval, partial updates, validation enforcement,
voice listing, and font file upload.
"""

import os
import shutil
import tempfile

from django.conf import settings as django_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import GlobalSettings

# ── URL constants ──
SETTINGS_URL = '/api/settings/'
VOICES_URL = '/api/settings/voices/'
FONT_UPLOAD_URL = '/api/settings/font/upload/'

# Temporary media root for font upload tests
TEMP_MEDIA_ROOT = tempfile.mkdtemp()


class GlobalSettingsAPITests(APITestCase):
    """Tests for settings retrieval, updates, and response structure."""

    def setUp(self):
        GlobalSettings.objects.all().delete()

    # ── Step 2 — Settings Retrieval ──

    def test_auto_creation_on_first_access(self):
        """GET creates a singleton when none exists and returns defaults."""
        self.assertEqual(GlobalSettings.objects.count(), 0)

        response = self.client.get(SETTINGS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(GlobalSettings.objects.count(), 1)

        data = response.json()
        self.assertEqual(data['default_voice_id'], 'af_bella')
        self.assertEqual(data['subtitle_font_family'], 'Arial')
        self.assertEqual(data['subtitle_font_size'], 48)
        self.assertEqual(data['subtitle_font_color'], '#FFFFFF')
        self.assertEqual(data['subtitle_position'], 'bottom')
        self.assertEqual(data['render_width'], 1920)
        self.assertEqual(data['render_height'], 1080)
        self.assertEqual(data['render_fps'], 30)
        self.assertAlmostEqual(data['ken_burns_zoom'], 1.2)
        self.assertAlmostEqual(data['transition_duration'], 0.5)

    def test_retrieving_existing_settings(self):
        """GET returns custom values when a record already exists."""
        GlobalSettings.objects.create(
            pk=1,
            default_voice_id='am_adam',
            subtitle_font_family='Roboto',
            subtitle_font_size=64,
            subtitle_font_color='#FF0000',
            subtitle_position='top',
            render_width=1280,
            render_height=720,
            render_fps=24,
            ken_burns_zoom=1.5,
            transition_duration=1.0,
        )

        response = self.client.get(SETTINGS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['default_voice_id'], 'am_adam')
        self.assertEqual(data['subtitle_font_family'], 'Roboto')
        self.assertEqual(data['subtitle_font_size'], 64)
        self.assertEqual(data['subtitle_font_color'], '#FF0000')
        self.assertEqual(data['subtitle_position'], 'top')
        self.assertEqual(data['render_width'], 1280)
        self.assertEqual(data['render_height'], 720)
        self.assertEqual(data['render_fps'], 24)
        self.assertAlmostEqual(data['ken_burns_zoom'], 1.5)
        self.assertAlmostEqual(data['transition_duration'], 1.0)

    def test_response_structure(self):
        """GET response contains all expected fields."""
        response = self.client.get(SETTINGS_URL)
        data = response.json()

        expected_fields = {
            'default_voice_id', 'tts_speed',
            'subtitle_font_family', 'subtitle_font_size',
            'subtitle_font_color', 'subtitle_position',
            'subtitle_font', 'subtitle_color',
            'render_width', 'render_height', 'render_fps',
            'ken_burns_zoom', 'transition_duration', 'zoom_intensity',
            'custom_font_file',
            'created_at', 'updated_at',
        }
        self.assertEqual(set(data.keys()), expected_fields)

    # ── Step 3 — Settings Updates ──

    def test_partial_update_single_field(self):
        """PATCH changing only default_voice_id preserves other fields."""
        self.client.get(SETTINGS_URL)  # ensure record exists

        response = self.client.patch(
            SETTINGS_URL,
            {'default_voice_id': 'bf_emma'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['default_voice_id'], 'bf_emma')
        # Other fields remain at defaults
        self.assertEqual(data['subtitle_font_family'], 'Arial')
        self.assertEqual(data['subtitle_font_size'], 48)
        self.assertEqual(data['render_fps'], 30)

    def test_partial_update_multiple_fields(self):
        """PATCH can update several fields at once."""
        self.client.get(SETTINGS_URL)

        response = self.client.patch(
            SETTINGS_URL,
            {
                'subtitle_font_size': 72,
                'subtitle_font_color': '#00FF00',
                'subtitle_position': 'center',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['subtitle_font_size'], 72)
        self.assertEqual(data['subtitle_font_color'], '#00FF00')
        self.assertEqual(data['subtitle_position'], 'center')
        # Unchanged fields
        self.assertEqual(data['default_voice_id'], 'af_bella')
        self.assertEqual(data['render_width'], 1920)

    def test_update_persistence(self):
        """Changes from PATCH are persisted across requests."""
        self.client.get(SETTINGS_URL)

        self.client.patch(
            SETTINGS_URL,
            {'subtitle_font_family': 'Courier New'},
            format='json',
        )

        response = self.client.get(SETTINGS_URL)
        self.assertEqual(
            response.json()['subtitle_font_family'], 'Courier New'
        )

    def test_noop_update(self):
        """PATCH with empty body returns 200 with unchanged settings."""
        self.client.get(SETTINGS_URL)

        response = self.client.patch(SETTINGS_URL, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['default_voice_id'], 'af_bella')
        self.assertEqual(data['subtitle_font_size'], 48)

    # ── Step 4 — Validation ──

    def test_font_size_below_minimum(self):
        """subtitle_font_size < 12 is rejected."""
        self.client.get(SETTINGS_URL)
        response = self.client.patch(
            SETTINGS_URL, {'subtitle_font_size': 5}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_font_size_above_maximum(self):
        """subtitle_font_size > 120 is rejected."""
        self.client.get(SETTINGS_URL)
        response = self.client.patch(
            SETTINGS_URL, {'subtitle_font_size': 200}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_hex_color_word(self):
        """subtitle_font_color = 'red' (non-hex) is rejected."""
        self.client.get(SETTINGS_URL)
        response = self.client.patch(
            SETTINGS_URL, {'subtitle_font_color': 'red'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_hex_color_bad_chars(self):
        """subtitle_font_color = '#GGG' (invalid hex chars) is rejected."""
        self.client.get(SETTINGS_URL)
        response = self.client.patch(
            SETTINGS_URL, {'subtitle_font_color': '#GGG'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_hex_color_too_short(self):
        """subtitle_font_color = '#FF' (too short) is rejected."""
        self.client.get(SETTINGS_URL)
        response = self.client.patch(
            SETTINGS_URL, {'subtitle_font_color': '#FF'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_subtitle_position(self):
        """subtitle_position = 'left' is rejected."""
        self.client.get(SETTINGS_URL)
        response = self.client.patch(
            SETTINGS_URL, {'subtitle_position': 'left'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zoom_below_range(self):
        """ken_burns_zoom = 0.5 is rejected."""
        self.client.get(SETTINGS_URL)
        response = self.client.patch(
            SETTINGS_URL, {'ken_burns_zoom': 0.5}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zoom_above_range(self):
        """ken_burns_zoom = 3.0 is rejected."""
        self.client.get(SETTINGS_URL)
        response = self.client.patch(
            SETTINGS_URL, {'ken_burns_zoom': 3.0}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_transition_duration_negative(self):
        """transition_duration = -1.0 is rejected."""
        self.client.get(SETTINGS_URL)
        response = self.client.patch(
            SETTINGS_URL, {'transition_duration': -1.0}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_transition_duration_above_range(self):
        """transition_duration = 5.0 is rejected."""
        self.client.get(SETTINGS_URL)
        response = self.client.patch(
            SETTINGS_URL, {'transition_duration': 5.0}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_fps_value(self):
        """render_fps = 45 (not 24/30/60) is rejected."""
        self.client.get(SETTINGS_URL)
        response = self.client.patch(
            SETTINGS_URL, {'render_fps': 45}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_resolution(self):
        """Non-preset resolution is rejected."""
        self.client.get(SETTINGS_URL)
        response = self.client.patch(
            SETTINGS_URL,
            {'render_width': 800, 'render_height': 600},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_boundary_values(self):
        """Exact min/max boundaries are accepted."""
        self.client.get(SETTINGS_URL)

        boundaries = [
            {'subtitle_font_size': 12},
            {'subtitle_font_size': 120},
            {'ken_burns_zoom': 1.0},
            {'ken_burns_zoom': 2.0},
            {'transition_duration': 0.0},
            {'transition_duration': 2.0},
            {'render_fps': 24},
            {'render_fps': 60},
            {'subtitle_font_color': '#FFF'},   # 3-char shorthand
            {'subtitle_font_color': '#000000'},  # 6-char full
        ]

        for payload in boundaries:
            response = self.client.patch(
                SETTINGS_URL, payload, format='json'
            )
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                msg=f'Boundary value rejected: {payload}',
            )


class VoiceListingTests(APITestCase):
    """Tests for the GET /api/settings/voices/ endpoint."""

    def test_voices_list_returned(self):
        """GET returns 200 with a non-empty list."""
        response = self.client.get(VOICES_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_voice_object_structure(self):
        """Each voice has at least id, name, and language fields."""
        response = self.client.get(VOICES_URL)
        data = response.json()

        for voice in data:
            self.assertIn('id', voice)
            self.assertIn('name', voice)
            self.assertIn('language', voice, msg=f'Missing language for {voice}')

    def test_voice_count(self):
        """Number of voices matches expected Kokoro voice count (26)."""
        response = self.client.get(VOICES_URL)
        data = response.json()
        self.assertEqual(len(data), 26)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class FontUploadTests(APITestCase):
    """Tests for the POST /api/settings/font/upload/ endpoint."""

    def setUp(self):
        GlobalSettings.objects.all().delete()
        # Ensure a fresh singleton for every test
        GlobalSettings.load()
        # Clean temp fonts directory
        fonts_dir = os.path.join(TEMP_MEDIA_ROOT, 'fonts')
        if os.path.isdir(fonts_dir):
            shutil.rmtree(fonts_dir)

    @classmethod
    def tearDownClass(cls):
        # Remove entire temp media root when done
        if os.path.isdir(TEMP_MEDIA_ROOT):
            shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_successful_font_upload(self):
        """Uploading a valid .ttf file returns 200 with updated settings."""
        font_data = b'\x00\x01\x00\x00' + b'\x00' * 100  # minimal bytes
        font_file = SimpleUploadedFile(
            'TestFont.ttf', font_data, content_type='font/ttf'
        )

        response = self.client.post(
            FONT_UPLOAD_URL, {'font': font_file}, format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('fonts/TestFont.ttf', data['custom_font_file'])
        self.assertEqual(data['subtitle_font_family'], 'TestFont')

    def test_invalid_file_extension(self):
        """Uploading a .txt file is rejected with 400."""
        bad_file = SimpleUploadedFile(
            'readme.txt', b'hello world', content_type='text/plain'
        )

        response = self.client.post(
            FONT_UPLOAD_URL, {'font': bad_file}, format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_oversized_file(self):
        """Uploading a file > 10 MB is rejected with 400."""
        big_data = b'\x00' * (10 * 1024 * 1024 + 1)  # 10 MB + 1 byte
        big_file = SimpleUploadedFile(
            'Huge.ttf', big_data, content_type='font/ttf'
        )

        response = self.client.post(
            FONT_UPLOAD_URL, {'font': big_file}, format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_font_replacement(self):
        """Second upload replaces the first; settings reflect the new font."""
        font_a = SimpleUploadedFile(
            'FontA.ttf', b'\x00' * 64, content_type='font/ttf'
        )
        font_b = SimpleUploadedFile(
            'FontB.ttf', b'\x00' * 64, content_type='font/ttf'
        )

        self.client.post(FONT_UPLOAD_URL, {'font': font_a}, format='multipart')
        response = self.client.post(
            FONT_UPLOAD_URL, {'font': font_b}, format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('FontB.ttf', data['custom_font_file'])
        self.assertEqual(data['subtitle_font_family'], 'FontB')

        # Old file should no longer exist on disk
        old_path = os.path.join(TEMP_MEDIA_ROOT, 'fonts', 'FontA.ttf')
        self.assertFalse(
            os.path.isfile(old_path),
            'Previous font file should be removed after replacement.',
        )

    def test_no_font_file_provided(self):
        """POST without a font file returns 400."""
        response = self.client.post(
            FONT_UPLOAD_URL, {}, format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
