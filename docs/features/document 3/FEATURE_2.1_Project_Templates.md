# Feature 2.1 — Project Templates / Presets

| Field | Value |
|---|---|
| **Feature ID** | 2.1 |
| **Title** | Project Templates / Presets |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Medium |
| **Estimated Effort** | 5–8 days |
| **Dependencies** | Project model stable, Settings API (`GET /api/settings/`) functional, `CreateProjectDialog.tsx` rendering correctly |
| **Output Files (NEW)** | `backend/api/migrations/000X_add_project_template.py`, `frontend/components/TemplateGallery.tsx`, `frontend/components/SaveTemplateDialog.tsx`, `backend/api/management/commands/load_starter_templates.py`, `backend/api/fixtures/starter_templates.json` |
| **Files Modified** | `backend/api/models.py`, `backend/api/serializers.py`, `backend/api/views.py`, `backend/api/urls.py`, `frontend/components/CreateProjectDialog.tsx`, `frontend/app/settings/page.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

Every new StoryFlow project currently starts as a blank slate, inheriting only the global defaults defined in the settings store. For creators who produce recurring video series — such as a daily "History Facts" channel or a weekly "Business Explainer" series — this means manually re-entering the same voice ID, subtitle font and color, logo position, resolution, framerate, and music track for every single project. In practice, this reconfiguration process takes two to three minutes per project, and any inconsistency between episodes (a slightly different subtitle color, a forgotten logo toggle) breaks the visual coherence of the series. There is currently no mechanism to capture, name, and reuse a consistent configuration bundle across multiple projects, which is a significant friction point for professional and semi-professional creators using StoryFlow at scale.

### 1.2 Proposed Solution

Introduce a first-class "Project Template" concept, where a template is a named, reusable snapshot of a project's configuration settings — excluding its segments, audio, and media files. Templates can be created from any existing project in one click, stored persistently in the database, and selected during project creation to pre-fill all settings automatically. The implementation involves a new Django model, a small set of API endpoints, and incremental additions to the existing frontend dialogs.

Key components of the solution:

- Introduce a new `ProjectTemplate` Django model with a `settings_snapshot` JSONField that stores all configurable fields from the `Project` model (voice, subtitle, logo, resolution, music, transitions).
- Add a boolean `is_global` flag on the template model to distinguish built-in starter templates (visible to all users) from user-created private templates.
- Expose three new API endpoints: list all templates, create a template (by cloning an existing project's settings or from a raw settings dict), and delete a template by ID.
- Add a `POST /api/projects/{id}/apply-template/{template_id}/` endpoint that writes the template's snapshot fields onto an existing project without overwriting its segments.
- Add a "Save as Template" button in the project settings panel that opens a small modal where the user types a name and optional description, then submits to create the template.
- In `CreateProjectDialog.tsx`, add a "Start from Template" tab showing a `TemplateGallery` component with selectable template cards; selecting a card pre-fills all form fields before the user submits the new project.
- Ship five built-in starter templates (Documentary, TikTok Short, YouTube Educational, Horror Narration, Business Explainer) as a Django fixture loaded via a management command so fresh installations are immediately useful.

### 1.3 Scope

| Dimension | In Scope |
|---|---|
| Template creation from existing project | ✅ "Save as Template" from project settings panel |
| Template application at creation time | ✅ "From Template" tab inside `CreateProjectDialog` |
| Template application to existing project | ✅ `apply-template` endpoint overwrites settings only |
| Built-in starter templates | ✅ Five fixtures loaded via management command |
| Template listing and deletion in Settings | ✅ Dedicated section in `frontend/app/settings/page.tsx` |

| Dimension | Out of Scope |
|---|---|
| Template sharing between users / export-import | ❌ Not planned in this phase |
| Templates that include segment content or media files | ❌ Settings snapshot only, no media |
| Template versioning or change history | ❌ Out of scope for v1 |
| Per-template thumbnail or preview video generation | ❌ Text summary card only |
| Role-based permissions for global vs. private templates | ❌ Deferred to a later multi-user phase |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/api/models.py` | Defines all Django ORM models | Contains `Project`, `Segment` models; no `ProjectTemplate` yet |
| `backend/api/serializers.py` | DRF serializers for all models | `ProjectSerializer`, `SegmentSerializer` present; no template serializer |
| `backend/api/views.py` | API view logic (CBVs/FBVs) | Project CRUD views exist; no template views |
| `backend/api/urls.py` | URL routing for the API | Routes for projects and segments; template routes absent |
| `frontend/components/CreateProjectDialog.tsx` | Modal for creating new projects | Single-tab form; no template selection UI |
| `frontend/app/settings/page.tsx` | Global settings page | Renders voice/subtitle/render settings; no template management section |

---

## 2. Flow Diagram

```
User clicks "New Project"
        │
        ▼
CreateProjectDialog opens
        │
   ┌────┴────────────────┐
   │                     │
"Blank Project"    "From Template"
   tab                  tab
   │                     │
   │              TemplateGallery
   │              renders cards
   │                     │
   │          User selects template card
   │                     │
   │              API: GET /api/project-templates/
   │              returns settings_snapshot JSON
   │                     │
   │              Form fields pre-filled
   │                     │
   └────────┬────────────┘
            │
    User edits / confirms
            │
            ▼
   POST /api/projects/  (settings baked in)
            │
            ▼
      New Project created
            │
            ▼
  Navigate to /projects/{id}/editor
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Add the ProjectTemplate Django Model

File: `backend/api/models.py`

Locate the end of the existing model definitions (after the `Segment` model class). Add a new `ProjectTemplate` class. Give it a `name` CharField with a max length of 150 and a `blank=False` constraint. Add a `description` TextField that is blank-able and nullable. Add a `settings_snapshot` JSONField with `default=dict` to store the serialized project configuration. Add a `created_at` DateTimeField with `auto_now_add=True`. Add an `is_global` BooleanField defaulting to False — when True, the template is a built-in starter visible in the gallery without any ownership filter. Finally, add a `__str__` method returning the name. Run `makemigrations` and `migrate` after adding the model. The migration file will be auto-generated and does not need manual editing.

### Step 3.2 — Add the Template Serializer and API Views

File: `backend/api/serializers.py` and `backend/api/views.py`

In `serializers.py`, locate the block where `ProjectSerializer` is defined and add a new `ProjectTemplateSerializer` class. It should expose all fields on the model. Add a read-only `settings_fields_summary` SerializerMethodField that returns a short human-readable string (e.g., "Voice: af_sky · 1080p · Subtitles ON") computed from the snapshot — this drives the card summary in the frontend UI.

In `views.py`, add a `ProjectTemplateListCreateView` (ListCreateAPIView subclass) that handles `GET` (return all templates) and `POST` (accept either a `project_id` in the request body to clone settings from, or a raw `settings_snapshot` dict). Add a `ProjectTemplateDestroyView` for `DELETE /api/project-templates/{id}/`. Add an `ApplyTemplateView` function-based view at `POST /api/projects/{id}/apply-template/{template_id}/` that loads the template's snapshot and calls `Project.objects.filter(pk=id).update(**snapshot_fields)` then returns the updated project serialization.

### Step 3.3 — Register the New URL Routes

File: `backend/api/urls.py`

Locate the existing `urlpatterns` list. Append three new path entries: one for `project-templates/` pointing to `ProjectTemplateListCreateView`, one for `project-templates/<int:pk>/` pointing to `ProjectTemplateDestroyView`, and one for `projects/<int:pk>/apply-template/<int:template_id>/` pointing to `ApplyTemplateView`. Keep the naming convention consistent with the existing project and segment route names already in the file.

### Step 3.4 — Create the TemplateGallery and SaveTemplateDialog Frontend Components

File (new): `frontend/components/TemplateGallery.tsx`
File (new): `frontend/components/SaveTemplateDialog.tsx`

`TemplateGallery` is a component that accepts an `onSelect(template)` callback prop. It fetches `GET /api/project-templates/` on mount and renders a responsive grid of cards. Each card displays the template name, description (truncated at two lines), and the `settings_fields_summary` string from the API. A selected card gets a highlighted border using a Tailwind ring class. The component also shows a loading skeleton (using the ShadCN Skeleton component) while the fetch is in-flight, and an empty-state message if no templates exist.

`SaveTemplateDialog` is a modal containing a name input and an optional description textarea. It accepts a `projectId` prop. On submit, it calls `POST /api/project-templates/` with the `project_id` and the user-entered name/description. On success it shows a brief success toast and closes. On error it shows a destructive toast. This dialog is opened from a "Save as Template" button in the project settings panel.

### Step 3.5 — Extend CreateProjectDialog with a Template Tab

File: `frontend/components/CreateProjectDialog.tsx`

Locate the form rendering inside the dialog. Wrap the existing form fields in a ShadCN `Tabs` component with two tabs: "Blank Project" (the existing form, unchanged) and "From Template". In the "From Template" tab, render the `TemplateGallery` component. When the user selects a template, write all settings from the `settings_snapshot` into local component state (using `useState` already in the file or additional state variables) so that when the user clicks "Create Project", the POST body includes the template's settings in addition to the project name. Keep the existing form validation logic intact — only populate the pre-fillable fields; the project name still requires user input.

### Step 3.6 — Add Built-in Starter Templates as Fixtures

File (new): `backend/api/fixtures/starter_templates.json`
File (new): `backend/api/management/commands/load_starter_templates.py`

Create a JSON fixture file defining five template records with `is_global: true`. The five starters are: Documentary (deep voice, 1080p, black subtitles on white background, no music), TikTok Short (fast speech, 1080x1920 portrait, large bold subtitles, upbeat music track), YouTube Educational (neutral voice, 1080p, clean subtitle style, logo enabled), Horror Narration (slow deep voice, dark subtitle color, cinematic framerate), and Business Explainer (professional voice, 720p, minimal subtitle style, light background music). The management command loads this fixture by calling Django's built-in `loaddata` internally and prints a confirmation message. Document the command name as `load_starter_templates` so it can be run during deployment setup.

---

## 4. Expected Outcome

1. A `ProjectTemplate` database table exists with the correct schema after running migrations.
2. `GET /api/project-templates/` returns a list of all templates, including the five built-in starters after the management command is run.
3. `POST /api/project-templates/` successfully creates a template when called with a valid `project_id`, cloning all settings fields from that project into the snapshot.
4. `DELETE /api/project-templates/{id}/` removes the template and returns HTTP 204; attempts to delete a global template with `is_global=True` should return HTTP 403.
5. The "New Project" dialog displays a "From Template" tab that renders the template gallery with card summaries.
6. Selecting a template card in the gallery and clicking "Create Project" results in a new project whose settings exactly match the template snapshot.
7. `POST /api/projects/{id}/apply-template/{template_id}/` updates an existing project's settings and returns the full updated project object without touching any segment data.
8. The "Save as Template" button in the project settings panel opens the `SaveTemplateDialog`, and submitting it with a unique name creates a new user template visible in the gallery on next load.
9. All five built-in starter templates appear in the template gallery after running the `load_starter_templates` management command on a fresh database.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `ProjectTemplateSerializer` correctly serializes all fields and computes the `settings_fields_summary` string with a known snapshot input.
- [ ] `ProjectTemplateListCreateView` POST with a valid `project_id` returns HTTP 201 and a template whose snapshot matches the source project's fields.
- [ ] `ProjectTemplateListCreateView` POST with an invalid `project_id` returns HTTP 400 with a descriptive error message.
- [ ] `ProjectTemplateDestroyView` DELETE on a non-global template returns HTTP 204 and removes the record from the database.
- [ ] `ProjectTemplateDestroyView` DELETE on a template with `is_global=True` returns HTTP 403 without deleting the record.
- [ ] `ApplyTemplateView` correctly updates only the settings fields on an existing project and does not modify any related `Segment` records.
- [ ] The `load_starter_templates` management command creates exactly five records with `is_global=True` on a clean database and is idempotent on re-run (no duplicates).

### 5.2 Integration / Manual Tests

- [ ] Open the "New Project" dialog; verify both tabs are visible and switching between them does not reset the project name input.
- [ ] Select a template in the gallery, confirm all form fields reflect the template snapshot values before submission.
- [ ] Create a project from a template; open the project settings panel and confirm that every setting matches the template exactly.
- [ ] Navigate to Settings → Templates; verify all user-created templates are listed and can be deleted; verify built-in templates cannot be deleted (delete button is disabled or absent).
- [ ] Open a project's settings, click "Save as Template", enter a name, submit; verify the new template appears in the creation gallery immediately (or after a refresh).
- [ ] Apply a template to an existing project that already has segments; confirm segments are completely unaffected after applying.
- [ ] Observe the template gallery cards: verify each card shows the name, description, and settings summary string in the expected layout without UI overflow.

### 5.3 Regression Tests

- [ ] Creating a blank project (without selecting any template) still works correctly with all default values intact.
- [ ] The existing `ProjectSerializer` and project CRUD endpoints are unaffected by the new model and URL additions.
- [ ] The global settings API (`GET /api/settings/`) continues to return the correct schema and values without errors.
- [ ] The `CreateProjectDialog` still closes and resets its form state when the user dismisses it without creating a project.

---

## 6. Notes for AI Agent

- Begin implementation with the backend (model → serializer → view → URL) before touching any frontend files; the frontend components depend on the API shape being stable.
- The `settings_snapshot` JSONField should be populated by iterating over a fixed whitelist of field names from the `Project` model — do not use `model_to_dict` blindly, as it will include fields like `id`, `name`, `description`, `created_at`, and `segments` that must be excluded from the snapshot.
- The `apply-template` endpoint must use `update()` rather than overwriting the entire project object; fetching and re-saving the full instance risks triggering unwanted side effects such as clearing cached fields or resetting auto-generated values.
- When implementing the "From Template" tab in `CreateProjectDialog`, be careful to preserve all existing `useState` declarations and not duplicate the form submission handler — simply merge the template snapshot values into the existing state before calling the create function.
- The `is_global` guard in the `ProjectTemplateDestroyView` is a simple check and does not require a permissions framework; a conditional returning a `Response(status=403)` is sufficient for this phase.
- Load starter templates as the very last step during development, after verifying the model migration and serializer work correctly with manually created templates; this avoids fixture format mismatch errors during early iteration.
