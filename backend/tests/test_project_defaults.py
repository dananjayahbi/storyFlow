"""Resolution-specific project defaults and per-project settings isolation."""

from rest_framework import status
from rest_framework.test import APITestCase

from api.models import (
    Account,
    AccountSettings,
    DefaultProjectSettings,
    GlobalSettings,
    Project,
)

DEFAULTS_URL = '/api/settings/project-defaults/'
SETTINGS_URL = '/api/settings/'


class ProjectDefaultsAPITests(APITestCase):
    def setUp(self):
        GlobalSettings.objects.all().delete()
        GlobalSettings.load()
        self.account = Account.objects.create(name='Page', section='facebook')
        self.other = Account.objects.create(name='Other Page', section='facebook')
        self.scope = f'?section=facebook&account={self.account.id}'

    def defaults_url(self, width=1280, height=720):
        return f'{DEFAULTS_URL}{width}x{height}/{self.scope}'

    # ── Profile CRUD ──────────────────────────────────────────────────────

    def test_list_reports_every_preset_with_fallback_values(self):
        response = self.client.get(f'{DEFAULTS_URL}{self.scope}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertGreaterEqual(len(results), 11)
        self.assertFalse(any(item['is_customized'] for item in results))
        self.assertTrue(all(item['resolution_width'] for item in results))

    def test_saving_defaults_is_scoped_to_account_and_resolution(self):
        response = self.client.patch(
            self.defaults_url(),
            {
                'subtitle_font_size': 72,
                'subtitle_font_color': '#00FF00',
                'default_voice_id': 'am_liam',
                'tts_speed': 1.3,
                'framerate': 60,
                'inter_segment_silence': 0.8,
                'logo_enabled': True,
                'bgm_gain_db': -24,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_customized'])
        self.assertEqual(response.data['subtitle_font_size'], 72)
        self.assertTrue(
            DefaultProjectSettings.objects.filter(
                account=self.account,
                resolution_width=1280,
                resolution_height=720,
            ).exists()
        )

        # Another resolution keeps the account fallback.
        other_resolution = self.client.get(self.defaults_url(1920, 1080))
        self.assertFalse(other_resolution.data['is_customized'])
        self.assertEqual(other_resolution.data['subtitle_font_size'], 48)

        # Another account never sees this profile.
        other_account = self.client.get(
            f'{DEFAULTS_URL}1280x720/?section=facebook&account={self.other.id}'
        )
        self.assertFalse(other_account.data['is_customized'])

    def test_invalid_resolution_is_rejected(self):
        response = self.client.patch(
            self.defaults_url(1000, 1000),
            {'subtitle_font_size': 50},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_reverts_to_account_defaults(self):
        self.client.patch(
            self.defaults_url(), {'subtitle_font_size': 66}, format='json'
        )
        response = self.client.delete(self.defaults_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_customized'])
        self.assertEqual(response.data['subtitle_font_size'], 48)
        self.assertFalse(
            DefaultProjectSettings.objects.filter(account=self.account).exists()
        )

    # ── Project creation ─────────────────────────────────────────────────

    def test_project_created_with_resolution_uses_matching_defaults(self):
        self.client.patch(
            self.defaults_url(1080, 1920),
            {
                'subtitle_font_size': 80,
                'default_voice_id': 'bf_emma',
                'tts_speed': 1.4,
                'framerate': 24,
                'subtitles_enabled': False,
            },
            format='json',
        )

        response = self.client.post(
            f'/api/projects/{self.scope}',
            {
                'title': 'Portrait project',
                'section': 'facebook',
                'resolution_width': 1080,
                'resolution_height': 1920,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(pk=response.data['id'])
        self.assertEqual(project.resolution_width, 1080)
        self.assertEqual(project.resolution_height, 1920)
        self.assertEqual(project.subtitle_font_size, 80)
        self.assertEqual(project.default_voice_id, 'bf_emma')
        self.assertEqual(project.tts_speed, 1.4)
        self.assertEqual(project.framerate, 24)
        self.assertFalse(project.subtitles_enabled)

    def test_different_resolutions_get_different_defaults(self):
        self.client.patch(
            self.defaults_url(1280, 720),
            {'subtitle_font_size': 40},
            format='json',
        )
        self.client.patch(
            self.defaults_url(1080, 1920),
            {'subtitle_font_size': 90},
            format='json',
        )

        landscape = self.client.post(
            f'/api/projects/{self.scope}',
            {
                'title': 'Landscape',
                'section': 'facebook',
                'resolution_width': 1280,
                'resolution_height': 720,
            },
            format='json',
        )
        portrait = self.client.post(
            f'/api/projects/{self.scope}',
            {
                'title': 'Portrait',
                'section': 'facebook',
                'resolution_width': 1080,
                'resolution_height': 1920,
            },
            format='json',
        )

        self.assertEqual(
            Project.objects.get(pk=landscape.data['id']).subtitle_font_size, 40
        )
        self.assertEqual(
            Project.objects.get(pk=portrait.data['id']).subtitle_font_size, 90
        )

    def test_project_creation_without_resolution_keeps_account_resolution(self):
        AccountSettings.objects.filter(account=self.account).delete()
        settings_obj = AccountSettings.load(self.account)
        settings_obj.render_width = 1280
        settings_obj.render_height = 720
        settings_obj.subtitle_font_size = 55
        settings_obj.save()

        response = self.client.post(
            f'/api/projects/{self.scope}',
            {'title': 'Default size', 'section': 'facebook'},
            format='json',
        )

        project = Project.objects.get(pk=response.data['id'])
        self.assertEqual(project.resolution_width, 1280)
        self.assertEqual(project.resolution_height, 720)
        self.assertEqual(project.subtitle_font_size, 55)

    # ── Isolation ─────────────────────────────────────────────────────────

    def test_editing_one_project_does_not_change_defaults_or_other_projects(self):
        self.client.patch(
            self.defaults_url(1280, 720),
            {'subtitle_font_size': 60},
            format='json',
        )
        first = self.client.post(
            f'/api/projects/{self.scope}',
            {
                'title': 'First',
                'section': 'facebook',
                'resolution_width': 1280,
                'resolution_height': 720,
            },
            format='json',
        ).data['id']
        second = self.client.post(
            f'/api/projects/{self.scope}',
            {
                'title': 'Second',
                'section': 'facebook',
                'resolution_width': 1280,
                'resolution_height': 720,
            },
            format='json',
        ).data['id']

        response = self.client.patch(
            f'/api/projects/{first}/{self.scope}',
            {'subtitle_font_size': 99},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(
            Project.objects.get(pk=first).subtitle_font_size, 99
        )
        self.assertEqual(
            Project.objects.get(pk=second).subtitle_font_size, 60
        )
        self.assertEqual(
            DefaultProjectSettings.objects.get(
                account=self.account,
                resolution_width=1280,
                resolution_height=720,
            ).subtitle_font_size,
            60,
        )

    def test_render_pipeline_setting_is_per_project(self):
        first = Project.objects.create(
            title='Fast pipeline',
            section='facebook',
            account=self.account,
        )
        second = Project.objects.create(
            title='Stable pipeline',
            section='facebook',
            account=self.account,
        )
        self.assertEqual(first.render_pipeline, 'v1')

        response = self.client.patch(
            f'/api/projects/{first.id}/{self.scope}',
            {'render_pipeline': 'v2'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['render_pipeline'], 'v2')
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.render_pipeline, 'v2')
        self.assertEqual(second.render_pipeline, 'v1')

    def test_account_settings_update_does_not_rewrite_existing_projects(self):
        project = Project.objects.create(
            title='Existing',
            section='facebook',
            account=self.account,
            subtitle_font_size=48,
        )
        response = self.client.patch(
            f'{SETTINGS_URL}{self.scope}',
            {'subtitle_font_size': 88},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        project.refresh_from_db()
        self.assertEqual(project.subtitle_font_size, 48)

    def test_changing_resolution_pulls_that_resolutions_defaults(self):
        self.client.patch(
            self.defaults_url(1080, 1920),
            {'subtitle_font_size': 82, 'framerate': 24},
            format='json',
        )
        project = Project.objects.create(
            title='Resize me',
            section='facebook',
            account=self.account,
            resolution_width=1280,
            resolution_height=720,
            subtitle_font_size=40,
            framerate=30,
        )

        response = self.client.patch(
            f'/api/projects/{project.id}/{self.scope}',
            {'resolution_width': 1080, 'resolution_height': 1920},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.resolution_width, 1080)
        self.assertEqual(project.resolution_height, 1920)
        self.assertEqual(project.subtitle_font_size, 82)
        self.assertEqual(project.framerate, 24)

    def test_reset_settings_reapplies_defaults_to_one_project(self):
        self.client.patch(
            self.defaults_url(1280, 720),
            {'subtitle_font_size': 58},
            format='json',
        )
        customized = Project.objects.create(
            title='Custom',
            section='facebook',
            account=self.account,
            resolution_width=1280,
            resolution_height=720,
            subtitle_font_size=91,
        )
        untouched = Project.objects.create(
            title='Untouched',
            section='facebook',
            account=self.account,
            resolution_width=1280,
            resolution_height=720,
            subtitle_font_size=72,
        )

        response = self.client.post(
            f'/api/projects/{customized.id}/reset-settings/{self.scope}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        customized.refresh_from_db()
        untouched.refresh_from_db()
        self.assertEqual(customized.subtitle_font_size, 58)
        self.assertEqual(untouched.subtitle_font_size, 72)
