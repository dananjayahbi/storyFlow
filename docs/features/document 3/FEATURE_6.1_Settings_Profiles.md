# Feature 6.1 — Settings Profiles

| Field | Value |
|---|---|
| Feature ID | 6.1 |
| Title | Settings Profiles |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Low |
| Estimated Effort | 2 days |
| Dependencies | GlobalSettings model must exist; DRF endpoint infrastructure operational |
| Output Files (NEW) | `backend/api/models.py` (SettingsProfile model); `frontend/components/ProfileSelector.tsx` |
| Files Modified | `backend/api/serializers.py`, `backend/api/views.py`, `backend/api/urls.py`, `frontend/app/settings/page.tsx`, `frontend/store/settingsStore.ts` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow currently provides a single global settings object that applies to all projects on the system, supplemented only by per-project render overrides. When a creator operates two or more YouTube channels with entirely distinct visual identities — for example, a bold-text, high-zoom horror channel versus a clean-text, slow-pan educational channel — they must manually revisit and adjust eight or more individual settings fields every time they switch context. This is not only tedious but error-prone, as forgetting to change a single subtitle font or zoom intensity produces videos that look mismatched with the target brand. There is no mechanism to save, name, or recall a complete visual configuration as a single reusable unit.

### 1.2 Proposed Solution

Introduce a named Settings Profiles system that allows creators to save any complete snapshot of their current GlobalSettings under a custom label, then restore that entire configuration in a single dropdown selection. Profiles act as bookmarked configurations rather than separate databases — they store the same fields as GlobalSettings but independently per profile record.

- Introduce a new `SettingsProfile` model with fields: `name` (CharField), `settings_data` (JSONField storing a full copy of all GlobalSettings fields), `is_default` (BooleanField), and `created_at` (DateTimeField auto-populated).
- Add three REST endpoints: `GET/POST /api/settings-profiles/` for listing and creating profiles; `PUT/DELETE /api/settings-profiles/{id}/` for updating and removing a profile; and `POST /api/settings-profiles/{id}/activate/` which writes the profile's stored data into the live GlobalSettings record.
- Add a "Profiles" section at the top of the settings page in the frontend, containing a dropdown listing all saved profiles by name, an "Active Profile" badge showing which profile is currently applied, and a "Save as New Profile" button that captures the current settings state.
- When the user selects a profile from the dropdown, its settings_data is loaded into the Zustand settingsStore immediately for a live UI preview — the settings fields update visually without a backend write — and a "Confirm and Apply" button commits the change to the backend by calling the activate endpoint.
- Each profile row in a separate profile management table includes a rename action (inline text edit), a "Set as Default" toggle, and a delete button with a confirmation dialog.
- On initial StoryFlow load, if a profile is marked `is_default = true`, its data is automatically loaded into GlobalSettings on the backend (handled in the get-or-create logic for GlobalSettings).

### 1.3 Scope

| Dimension | In Scope |
|---|---|
| Profile creation | Save current GlobalSettings snapshot as a named profile |
| Profile activation | Apply profile data to live GlobalSettings via activate endpoint |
| Profile management | Rename, delete, set-default actions on existing profiles |
| Profile dropdown | Frontend dropdown with live preview on selection |

| Dimension | Out of Scope |
|---|---|
| Per-project profile assignment | Assigning a profile directly to a project (separate feature) |
| Profile versioning | Tracking the history of changes made to a profile over time |
| Profile sharing via cloud | Cloud sync or team sharing of profiles (separate feature) |
| Import/Export of profiles | Handled in Feature 6.3 (Settings Import/Export) |

### 1.4 Key Files Reference

| File | Role in This Feature |
|---|---|
| `backend/api/models.py` | Add `SettingsProfile` model with `name`, `settings_data`, `is_default`, `created_at` |
| `backend/api/serializers.py` | Add `SettingsProfileSerializer` with full validation of `settings_data` structure |
| `backend/api/views.py` | Add `SettingsProfileViewSet` and `activate` action method |
| `frontend/app/settings/page.tsx` | Add profile dropdown, active badge, Save as Profile, and Confirm Apply button |
| `frontend/store/settingsStore.ts` | Add `loadProfilePreview` and `activeProfileId` state to the store |

---

## 2. Flow Diagram

```
User opens Settings Page
         |
         v
Frontend requests GET /api/settings-profiles/
         |
         v
Profiles dropdown rendered at page top
[ YouTube Series A ] [ TikTok Horror ] [ + Save as New ]
         |
  User selects profile
         |
         v
settingsStore.loadProfilePreview(profile.settings_data)
         |
         v
All settings fields update visually (live preview)
         |
         v
User sees preview → clicks "Confirm and Apply"
         |
         v
POST /api/settings-profiles/{id}/activate/
         |
         v
Backend writes profile.settings_data → GlobalSettings
         |
         v
Frontend re-fetches GlobalSettings → confirms sync
         |
         v
Active Profile badge updates to selected profile name
```

---

## 3. Step-by-Step Instructions

### Step 1 — Add SettingsProfile model to backend/api/models.py

File: `backend/api/models.py`

Add a new `SettingsProfile` class below the existing `GlobalSettings` model. The model requires four fields: a `name` CharField with max_length 100 and unique constraint, a `settings_data` JSONField that stores the complete dictionary of GlobalSettings field values, an `is_default` BooleanField defaulting to False, and a `created_at` DateTimeField with auto_now_add=True. Add a `__str__` method returning the profile name. Run `makemigrations` and `migrate` after adding the model.

### Step 2 — Add serializer and viewset to backend API layer

File: `backend/api/serializers.py` and `backend/api/views.py`

In serializers.py, create `SettingsProfileSerializer` with all four model fields included and a `validate_settings_data` method that checks for the presence of the mandatory keys expected from GlobalSettings. In views.py, create `SettingsProfileViewSet` extending `ModelViewSet` with an extra `@action(detail=True, methods=['post'])` named `activate` that reads `settings_data` from the profile and updates every field on the singleton `GlobalSettings` record using `update_or_create`. Register the viewset in `backend/api/urls.py` under the `api/settings-profiles/` path using a `DefaultRouter`.

### Step 3 — Add ProfileSelector component to frontend

File: `frontend/components/ProfileSelector.tsx` (new file) and `frontend/app/settings/page.tsx`

Create `ProfileSelector.tsx` as a self-contained component that fetches the profile list on mount, renders a ShadCN Select dropdown, and exposes `onSelect` and `onSaveNew` callbacks. The component also displays an "Active" badge next to the currently applied profile name. Import and place `ProfileSelector` at the very top of the settings page form, above all settings sections. Wire `onSelect` to call `settingsStore.loadProfilePreview` which hydrates all form fields with the profile's settings_data values without yet persisting to the backend.

### Step 4 — Update settingsStore with profile preview state

File: `frontend/store/settingsStore.ts`

Add two new state fields: `activeProfileId` (number or null) and `isProfilePreviewActive` (boolean). Add a `loadProfilePreview` action that receives a settings_data object and calls setters for every individual settings field in the store. Add a `confirmApplyProfile` async action that calls `POST /api/settings-profiles/{id}/activate/` and on success sets `isProfilePreviewActive` to false and `activeProfileId` to the confirmed ID. Add a `cancelProfilePreview` action that re-fetches the current GlobalSettings from the backend to restore the pre-preview state.

---

## 4. Expected Outcome

- The settings page displays a profile dropdown at the top with all saved profiles listed by name and an "Active Profile" badge.
- Selecting a profile from the dropdown immediately updates all settings fields in the UI for instant visual comparison without saving to the backend.
- Clicking "Confirm and Apply" writes the profile data to GlobalSettings on the backend and the Active Profile badge updates to reflect the newly applied profile.
- The "Save as New Profile" button opens a name input dialog, captures all current settings field values, and creates a new profile record via POST.
- Profiles can be renamed inline, deleted with a confirmation prompt, and one profile can be designated as the default that loads on startup.
- The system gracefully handles the case where no profiles exist, showing only the "Save as New Profile" button with an empty dropdown state.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `SettingsProfileSerializer` rejects a `settings_data` payload missing required GlobalSettings keys and returns meaningful field-level errors.
- [ ] `activate` action on the viewset correctly overwrites all GlobalSettings fields with the values stored in `settings_data` and returns HTTP 200 with the updated GlobalSettings.
- [ ] `SettingsProfile` model enforces the `is_default` uniqueness constraint so that no two profiles can both have `is_default=True` simultaneously.
- [ ] `settingsStore.loadProfilePreview` correctly populates all individual settings fields without triggering a backend call or modifying `activeProfileId` prematurely.

### 5.2 Integration / Manual Tests

- [ ] Create three profiles with distinct subtitle fonts and zoom values; switch between them and verify all settings fields in the UI update correctly on each selection.
- [ ] Confirm that selecting a profile and then clicking "Cancel" (or refreshing) reverts the settings fields back to what was last saved in GlobalSettings.
- [ ] Set a profile as default; simulate a fresh backend restart and verify that GlobalSettings is seeded with the default profile's data.
- [ ] Delete a profile that is currently the active profile; verify the active badge clears and GlobalSettings retains the last applied values.
- [ ] Rename a profile from the management interface and verify the dropdown label updates immediately without a page refresh.

### 5.3 Regression Tests

- [ ] Existing GlobalSettings GET and PATCH endpoints return correct data and are unaffected by the addition of the SettingsProfile model.
- [ ] Per-project `render_settings` overrides continue to function independently of any profile activation.
- [ ] The settings page loads correctly when zero profiles exist in the database — no JS errors or layout breakage.

---

## 6. Notes for AI Agent

- The `SettingsProfile.settings_data` JSONField should store a flat dictionary mirroring the exact field names used in `GlobalSettings` — this ensures the `activate` action can use `**profile.settings_data` dict unpacking when updating GlobalSettings without any field mapping logic.
- The `is_default` constraint should be enforced at the model level using a custom `save()` override that sets all other profiles' `is_default` to False when a profile is saved with `is_default=True` — do not rely solely on frontend logic for this.
- The frontend `loadProfilePreview` action must not call any backend endpoints — it is a purely local state operation. Only `confirmApplyProfile` makes the network call. This separation prevents accidental partial saves.
- When the user clicks "Save as New Profile", capture the current Zustand store state (not the last-fetched backend state) so that any unsaved field changes are included in the new profile snapshot.
