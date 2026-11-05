"""YouTube metadata management: thumbnail prompts and active covers."""

import json
import os
import shutil
import tempfile
from io import BytesIO
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import (
    Account,
    GlobalSettings,
    Project,
    ProjectThumbnail,
    Segment,
)
from core_engine import metadata_prompts

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


def png_upload(name, colour=(20, 120, 90)):
    buffer = BytesIO()
    Image.new('RGB', (8, 8), colour).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class MetadataManagementTests(APITestCase):
    def setUp(self):
        self.account = Account.objects.create(
            name='Metadata Channel', section='youtube'
        )
        self.project = Project.objects.create(
            title='Deep Sea Documentary',
            section='youtube',
            account=self.account,
        )
        self.scope = f'?section=youtube&account={self.account.id}'
        settings_obj = GlobalSettings.load()
        settings_obj.ai_default_model = 'test-vision-model'
        settings_obj.save()

        self.segments = []
        for index in range(4):
            self.segments.append(
                Segment.objects.create(
                    project=self.project,
                    sequence_index=index,
                    text_content=f'Block {index + 1} narration about the abyss.',
                    image_prompt=f'Cinematic abyss frame {index + 1}.',
                    image_file=(
                        png_upload(f'block-{index}.png')
                        if index < 2
                        else None
                    ),
                )
            )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def _detail(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/{self.scope}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    # ── Readiness and isolation ──────────────────────────────────────

    def test_readiness_requires_script_and_half_the_blocks_with_images(self):
        payload = self._detail()
        readiness = payload['thumbnail_readiness']
        self.assertTrue(readiness['script_ready'])
        self.assertTrue(readiness['images_ready'])
        self.assertTrue(readiness['ready'])
        self.assertEqual(readiness['image_count'], 2)
        self.assertEqual(readiness['required_images'], 2)

        # Remove one image: 1/4 is below half.
        self.segments[0].image_file = None
        self.segments[0].save(update_fields=['image_file'])
        readiness = self._detail()['thumbnail_readiness']
        self.assertFalse(readiness['images_ready'])
        self.assertFalse(readiness['ready'])
        self.assertEqual(readiness['required_images'], 2)

    def test_readiness_rounds_up_for_odd_block_counts(self):
        project = Project.objects.create(
            title='Odd story', section='youtube', account=self.account
        )
        for index in range(5):
            Segment.objects.create(
                project=project,
                sequence_index=index,
                text_content='text',
                image_file=png_upload(f'odd-{index}.png') if index < 2 else None,
            )
        readiness = metadata_prompts.thumbnail_readiness(project)
        self.assertEqual(readiness['required_images'], 3)
        self.assertFalse(readiness['ready'])

    def test_metadata_endpoints_are_youtube_only(self):
        facebook_account = Account.objects.create(
            name='Facebook Only', section='facebook'
        )
        facebook_project = Project.objects.create(
            title='Facebook story',
            section='facebook',
            account=facebook_account,
        )
        response = self.client.get(
            f'/api/projects/{facebook_project.id}/metadata/thumbnails/'
            f'?section=facebook&account={facebook_account.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('only available for YouTube', response.data['error'])

    def test_system_prompt_can_be_saved_per_project(self):
        response = self.client.patch(
            f'/api/projects/{self.project.id}/{self.scope}',
            {'thumbnail_system_prompt': 'My custom art direction.'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['thumbnail_system_prompt'],
            'My custom art direction.',
        )
        self.project.refresh_from_db()
        self.assertEqual(
            self.project.thumbnail_system_prompt, 'My custom art direction.'
        )

    # ── Prompt generation ────────────────────────────────────────────

    def test_prompt_endpoint_sends_script_images_and_documents(self):
        selected = [self.segments[0].id, self.segments[1].id]
        with mock.patch(
            'core_engine.ai_client.chat_completion',
            return_value='"Dramatic abyss reveal prompt"',
        ) as completion:
            response = self.client.post(
                f'/api/projects/{self.project.id}/metadata/thumbnail-prompt/'
                f'{self.scope}',
                {
                    'system_prompt': 'Custom thumbnail system prompt.',
                    'message': 'Mimic the reference thumbnails.',
                    'segment_ids': json.dumps([str(item) for item in selected]),
                    'reference_images': [png_upload('style.png')],
                    'reference_docs': [
                        SimpleUploadedFile(
                            'notes.txt',
                            b'Contrast: bright subject, dark water.',
                            content_type='text/plain',
                        )
                    ],
                },
                format='multipart',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['prompt'], 'Dramatic abyss reveal prompt')
        self.assertEqual(response.data['model'], 'test-vision-model')
        self.assertEqual(
            response.data['used_segment_ids'],
            [str(item) for item in selected],
        )

        messages = completion.call_args.kwargs['messages']
        self.assertEqual(messages[0]['content'], 'Custom thumbnail system prompt.')
        parts = messages[1]['content']
        text = ' '.join(
            part['text'] for part in parts if part.get('type') == 'text'
        )
        self.assertIn('Deep Sea Documentary', text)
        self.assertIn('Block 1 narration about the abyss', text)
        self.assertIn('Mimic the reference thumbnails.', text)
        self.assertIn('Contrast: bright subject, dark water.', text)
        image_parts = [
            part for part in parts if part.get('type') == 'image_url'
        ]
        self.assertEqual(len(image_parts), 3)  # 2 blocks + 1 external
        self.assertTrue(
            image_parts[0]['image_url']['url'].startswith(
                'data:image/jpeg;base64,'
            )
        )

    def test_prompt_endpoint_uses_saved_system_prompt_and_default_refs(self):
        self.project.thumbnail_system_prompt = 'Saved project prompt.'
        self.project.save(update_fields=['thumbnail_system_prompt'])
        with mock.patch(
            'core_engine.ai_client.chat_completion',
            return_value='A prompt.',
        ) as completion:
            response = self.client.post(
                f'/api/projects/{self.project.id}/metadata/thumbnail-prompt/'
                f'{self.scope}',
                {},
                format='multipart',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['used_segment_ids'], [
            str(self.segments[0].id), str(self.segments[1].id)
        ])
        messages = completion.call_args.kwargs['messages']
        self.assertEqual(messages[0]['content'], 'Saved project prompt.')

    def test_prompt_endpoint_requires_readiness_and_two_references(self):
        # Not ready: only one block has an image.
        self.segments[1].image_file = None
        self.segments[1].save(update_fields=['image_file'])
        response = self.client.post(
            f'/api/projects/{self.project.id}/metadata/thumbnail-prompt/'
            f'{self.scope}',
            {},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Add images', response.data['error'])

        # Ready again but only one selected reference.
        self.segments[1].image_file = png_upload('block-1b.png')
        self.segments[1].save(update_fields=['image_file'])
        response = self.client.post(
            f'/api/projects/{self.project.id}/metadata/thumbnail-prompt/'
            f'{self.scope}',
            {'segment_ids': json.dumps([str(self.segments[0].id)])},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('at least 2', response.data['error'])

    def test_build_messages_include_external_images_and_pdf_text(self):
        all_segments = list(self.project.segments.all().order_by('sequence_index'))
        messages = metadata_prompts.build_thumbnail_messages(
            project=self.project,
            segments=all_segments,
            selected_segments=all_segments[:2],
            system_prompt='',
            user_message='',
            external_images=[png_upload('reference.png')],
            documents=[
                SimpleUploadedFile(
                    'brief.md',
                    b'Use a cold teal palette.',
                    content_type='text/markdown',
                )
            ],
        )
        self.assertEqual(
            messages[0]['content'],
            metadata_prompts.DEFAULT_THUMBNAIL_SYSTEM_PROMPT,
        )
        text = ' '.join(
            part['text']
            for part in messages[1]['content']
            if part.get('type') == 'text'
        )
        self.assertIn('Use a cold teal palette.', text)
        self.assertEqual(
            len([
                part
                for part in messages[1]['content']
                if part.get('type') == 'image_url'
            ]),
            3,
        )

    # ── Thumbnail gallery and active cover ───────────────────────────

    def _upload_thumbnail(self, name, prompt='', is_active='true'):
        return self.client.post(
            f'/api/projects/{self.project.id}/metadata/thumbnails/'
            f'{self.scope}',
            {
                'image': png_upload(name),
                'prompt': prompt,
                'is_active': is_active,
            },
            format='multipart',
        )

    def test_upload_list_activate_and_delete_thumbnails(self):
        first = self._upload_thumbnail('first.png', prompt='First prompt')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        self.assertTrue(first.data['is_active'])
        self.assertIn('/thumbnails/', first.data['url'])

        second = self._upload_thumbnail(
            'second.png', prompt='Second prompt', is_active='false'
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertFalse(second.data['is_active'])

        listing = self.client.get(
            f'/api/projects/{self.project.id}/metadata/thumbnails/'
            f'{self.scope}'
        )
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listing.data), 2)

        detail = self._detail()
        self.assertEqual(detail['thumbnail_source'], 'active')
        self.assertTrue(detail['has_active_thumbnail'])
        self.assertIn('/thumbnails/', detail['thumbnail_url'])
        self.assertEqual(len(detail['thumbnails']), 2)

        activated = self.client.patch(
            f'/api/projects/{self.project.id}/metadata/thumbnails/'
            f'{second.data["id"]}/{self.scope}',
            {'is_active': True},
            format='json',
        )
        self.assertEqual(activated.status_code, status.HTTP_200_OK)
        self.assertTrue(activated.data['is_active'])
        self.assertFalse(
            ProjectThumbnail.objects.get(pk=first.data['id']).is_active
        )
        self.project.refresh_from_db()
        self.assertEqual(
            self._detail()['active_thumbnail_url'],
            activated.data['url'],
        )

        deleted = self.client.delete(
            f'/api/projects/{self.project.id}/metadata/thumbnails/'
            f'{second.data["id"]}/{self.scope}'
        )
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        # The remaining candidate is promoted so the project keeps a cover.
        self.assertTrue(
            ProjectThumbnail.objects.get(pk=first.data['id']).is_active
        )

    def test_active_thumbnail_wins_over_manual_and_segment_cover(self):
        # Manual cover first.
        patched = self.client.patch(
            f'/api/projects/{self.project.id}/{self.scope}',
            {'thumbnail': png_upload('manual.png')},
            format='multipart',
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(patched.data['thumbnail_source'], 'manual')

        uploaded = self._upload_thumbnail('active.png')
        detail = self._detail()
        self.assertEqual(detail['thumbnail_source'], 'active')
        self.assertEqual(detail['active_thumbnail_url'], uploaded.data['url'])

        # Removing the active candidate falls back to the manual cover.
        self.client.delete(
            f'/api/projects/{self.project.id}/metadata/thumbnails/'
            f'{uploaded.data["id"]}/{self.scope}'
        )
        detail = self._detail()
        self.assertEqual(detail['thumbnail_source'], 'manual')
        self.assertIn('thumbnail.png', detail['thumbnail_url'])

    def test_project_list_uses_active_thumbnail_for_tiles(self):
        uploaded = self._upload_thumbnail('tile.png')
        listing = self.client.get(f'/api/projects/{self.scope}')
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        tile = next(
            item
            for item in listing.data['results']
            if item['id'] == str(self.project.id)
        )
        self.assertEqual(tile['thumbnail_source'], 'active')
        self.assertEqual(tile['thumbnail_url'], uploaded.data['url'])

    def test_thumbnail_upload_rejects_non_images(self):
        response = self.client.post(
            f'/api/projects/{self.project.id}/metadata/thumbnails/'
            f'{self.scope}',
            {
                'image': SimpleUploadedFile(
                    'not-an-image.txt', b'hello', content_type='text/plain'
                )
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
