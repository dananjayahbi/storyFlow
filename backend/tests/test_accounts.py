"""Account layer tests (Feature update #1).

Each workspace section can hold many accounts.  Projects always belong to one
account, API access is scoped by ``?section=&account=``, and project assets live
under ``Storage/<Section>/<account-id>/<project-id>``.
"""

import os
import shutil
import tempfile
from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Account, GlobalSettings, Project, Segment
from api.storage_paths import project_dir, project_relpath

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class AccountTests(APITestCase):
    def setUp(self):
        GlobalSettings.load()
        self.fb = Account.objects.create(name='Page One', section='facebook')
        self.fb_second = Account.objects.create(
            name='Page Two', section='facebook'
        )
        self.yt = Account.objects.create(name='Channel One', section='youtube')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    # ── Models / storage ────────────────────────────────────────────────

    def test_project_auto_assigns_default_account(self):
        project = Project.objects.create(title='No account', section='youtube')
        self.assertIsNotNone(project.account_id)
        self.assertEqual(project.account.section, 'youtube')
        self.assertEqual(project.account.name, 'Default Account')

    def test_default_account_reused_per_section(self):
        a = Account.default_for_section('facebook')
        b = Account.default_for_section('facebook')
        c = Account.default_for_section('youtube')
        self.assertEqual(a.pk, b.pk)
        self.assertNotEqual(a.pk, c.pk)
        self.assertEqual(a.section, 'facebook')
        self.assertEqual(c.section, 'youtube')

    def test_storage_paths_include_account_folder(self):
        project = Project.objects.create(
            title='Scoped', section='facebook', account=self.fb
        )
        expected = os.path.join(
            TEMP_MEDIA_ROOT, 'Facebook', str(self.fb.id), str(project.id)
        )
        self.assertEqual(
            os.path.normpath(str(project_dir('facebook', project.id))),
            os.path.normpath(expected),
        )
        self.assertEqual(
            project_relpath('facebook', project.id, 'images', 'x.png'),
            f'Facebook/{self.fb.id}/{project.id}/images/x.png',
        )

    # ── Accounts API ────────────────────────────────────────────────────

    def test_list_accounts_is_section_scoped(self):
        response = self.client.get('/api/accounts/?section=facebook')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {str(item['id']) for item in response.data['results']}
        self.assertTrue({str(self.fb.id), str(self.fb_second.id)} <= ids)
        self.assertNotIn(str(self.yt.id), ids)
        self.assertTrue(all(
            item['section'] == 'facebook'
            for item in response.data['results']
        ))

        response = self.client.get('/api/accounts/?section=youtube')
        ids = {str(item['id']) for item in response.data['results']}
        self.assertIn(str(self.yt.id), ids)
        self.assertTrue(all(
            item['section'] == 'youtube'
            for item in response.data['results']
        ))

    def test_create_account_uses_requested_section(self):
        response = self.client.post(
            '/api/accounts/?section=youtube',
            {'name': 'Channel Two', 'section': 'youtube', 'description': 'Docs'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['section'], 'youtube')
        self.assertEqual(response.data['project_count'], 0)

    def test_create_account_rejects_cross_section(self):
        response = self.client.post(
            '/api/accounts/?section=facebook',
            {'name': 'Wrong side', 'section': 'youtube'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Account.objects.filter(name='Wrong side').exists())

    def test_duplicate_name_in_same_section_rejected(self):
        response = self.client.post(
            '/api/accounts/?section=facebook',
            {'name': 'Page One', 'section': 'facebook'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rename_account(self):
        response = self.client.patch(
            f'/api/accounts/{self.fb.id}/?section=facebook',
            {'name': 'Renamed Page'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.fb.refresh_from_db()
        self.assertEqual(self.fb.name, 'Renamed Page')

    def test_account_cannot_move_between_sections(self):
        response = self.client.patch(
            f'/api/accounts/{self.fb.id}/?section=facebook',
            {'section': 'youtube'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_account_from_other_section_returns_404(self):
        response = self.client.get(f'/api/accounts/{self.fb.id}/?section=youtube')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ── Project scoping ─────────────────────────────────────────────────

    def test_create_project_inside_account(self):
        response = self.client.post(
            f'/api/projects/?section=facebook&account={self.fb.id}',
            {'title': 'Account project', 'section': 'facebook'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(str(response.data['account']), str(self.fb.id))
        project = Project.objects.get(pk=response.data['id'])
        self.assertEqual(project.account_id, self.fb.id)

    def test_project_list_is_account_scoped(self):
        Project.objects.create(title='A', section='facebook', account=self.fb)
        Project.objects.create(
            title='B', section='facebook', account=self.fb_second
        )

        response = self.client.get(
            f'/api/projects/?section=facebook&account={self.fb.id}'
        )
        self.assertEqual(
            [item['title'] for item in response.data['results']], ['A']
        )

    def test_project_detail_hidden_from_other_account(self):
        project = Project.objects.create(
            title='Private', section='facebook', account=self.fb
        )
        response = self.client.get(
            f'/api/projects/{project.id}/?section=facebook'
            f'&account={self.fb_second.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_section_account_parameter_rejected(self):
        response = self.client.get(
            f'/api/projects/?section=facebook&account={self.yt.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_import_project_inside_account(self):
        response = self.client.post(
            f'/api/projects/import/?section=youtube&account={self.yt.id}',
            {
                'format': 'json',
                'title': 'Imported to channel',
                'section': 'youtube',
                'segments': [{'text_content': 'Hello', 'image_prompt': ''}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(pk=response.data['id'])
        self.assertEqual(project.account_id, self.yt.id)

    def test_gallery_is_account_scoped(self):
        a = Project.objects.create(
            title='A', section='facebook', account=self.fb,
            status='COMPLETED',
        )
        Project.objects.create(
            title='B', section='facebook', account=self.fb_second,
            status='COMPLETED',
        )
        dummy = os.path.join(TEMP_MEDIA_ROOT, 'dummy.mp4')
        with open(dummy, 'wb') as f:
            f.write(b'video')

        with patch('api.views._resolve_video_path', return_value=dummy):
            response = self.client.get(
                f'/api/gallery/?section=facebook&account={self.fb.id}'
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in response.data], [str(a.id)])

    def test_segments_are_account_scoped(self):
        a = Project.objects.create(
            title='A', section='facebook', account=self.fb
        )
        b = Project.objects.create(
            title='B', section='facebook', account=self.fb_second
        )
        seg_a = Segment.objects.create(
            project=a, sequence_index=0, text_content='a'
        )
        seg_b = Segment.objects.create(
            project=b, sequence_index=0, text_content='b'
        )

        response = self.client.get(
            f'/api/segments/?project={a.id}&section=facebook'
            f'&account={self.fb.id}'
        )
        self.assertEqual([s['id'] for s in response.data['results']], [str(seg_a.id)])

        cross = self.client.get(
            f'/api/segments/{seg_b.id}/?section=facebook'
            f'&account={self.fb.id}'
        )
        self.assertEqual(cross.status_code, status.HTTP_404_NOT_FOUND)

    # ── Deletion ────────────────────────────────────────────────────────

    def test_delete_account_removes_projects_and_folder(self):
        project = Project.objects.create(
            title='Doomed', section='facebook', account=self.fb
        )
        folder = project_dir('facebook', project.id)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, 'keep.txt'), 'w') as f:
            f.write('x')

        response = self.client.delete(
            f'/api/accounts/{self.fb.id}/?section=facebook'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Account.objects.filter(pk=self.fb.pk).exists())
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())
        self.assertFalse(os.path.isdir(folder))
