"""Resolution-aware subtitle positioning for project settings."""

from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Account, AccountSettings, GlobalSettings, Project

SCOPE = '?section=facebook'


class SubtitlePositionTests(APITestCase):
    def setUp(self):
        GlobalSettings.objects.all().delete()
        GlobalSettings.load()
        self.account = Account.objects.create(name='Page', section='facebook')

    def url(self, project_id):
        return f'/api/projects/{project_id}/{SCOPE}&account={self.account.id}'

    def settings_url(self):
        return f'/api/settings/{SCOPE}&account={self.account.id}'

    def test_choosing_a_preset_clears_the_manual_override(self):
        project = Project.objects.create(
            title='Story',
            section='facebook',
            account=self.account,
            resolution_width=1080,
            resolution_height=1920,
            subtitle_font_size=48,
            subtitle_position='bottom',
            subtitle_y_position=1600,
        )

        response = self.client.patch(
            self.url(project.id),
            {'subtitle_position': 'top'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.subtitle_position, 'top')
        self.assertIsNone(project.subtitle_y_position)

    def test_account_fallback_y_rescales_on_creation_and_resolution_change(self):
        settings_obj = AccountSettings.load(self.account)
        settings_obj.render_width = 1920
        settings_obj.render_height = 1080
        settings_obj.subtitle_font_size = 48
        settings_obj.subtitle_y_position = 900
        settings_obj.save()

        created = self.client.post(
            f'/api/projects/{SCOPE}&account={self.account.id}',
            {
                'title': 'Portrait',
                'section': 'facebook',
                'resolution_width': 1080,
                'resolution_height': 1920,
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(pk=created.data['id'])
        # 900 px at 1080p keeps the same relative position at 1920 px.
        self.assertEqual(project.subtitle_y_position, 1600)

        response = self.client.patch(
            self.url(project.id),
            {'resolution_width': 1920, 'resolution_height': 1080},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.subtitle_y_position, 900)

    def test_custom_resolution_profile_y_wins_over_old_manual_value(self):
        self.client.patch(
            f'/api/settings/project-defaults/1080x1920/'
            f'{SCOPE}&account={self.account.id}',
            {'subtitle_font_size': 48, 'subtitle_y_position': 1200},
            format='json',
        )
        project = Project.objects.create(
            title='Story',
            section='facebook',
            account=self.account,
            resolution_width=1920,
            resolution_height=1080,
            subtitle_font_size=48,
            subtitle_y_position=500,
        )

        response = self.client.patch(
            self.url(project.id),
            {'resolution_width': 1080, 'resolution_height': 1920},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.subtitle_y_position, 1200)

    def test_direct_manual_y_is_clamped_inside_the_frame(self):
        project = Project.objects.create(
            title='Story',
            section='facebook',
            account=self.account,
            resolution_width=1080,
            resolution_height=1920,
            subtitle_font_size=48,
        )

        response = self.client.patch(
            self.url(project.id),
            {'subtitle_y_position': 5000},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        # 48 px font + 2 × 12 px padding = 72 px block; max top edge = 1848.
        self.assertEqual(project.subtitle_y_position, 1848)

    def test_project_defaults_list_scales_account_y(self):
        settings_obj = AccountSettings.load(self.account)
        settings_obj.render_height = 1080
        settings_obj.subtitle_font_size = 48
        settings_obj.subtitle_y_position = 900
        settings_obj.save()

        response = self.client.get(
            f'/api/settings/project-defaults/{SCOPE}&account={self.account.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        portrait = next(
            item for item in response.data['results']
            if (item['resolution_width'], item['resolution_height']) == (1080, 1920)
        )
        self.assertEqual(portrait['subtitle_y_position'], 1600)
