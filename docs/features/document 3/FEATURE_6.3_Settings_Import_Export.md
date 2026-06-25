# Feature 6.3 — Settings Import and Export

| Field | Value |
|---|---|
| Feature ID | 6.3 |
| Title | Settings Import and Export |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Low |
| Estimated Effort | 2 days |
| Dependencies | GlobalSettings model must exist; SettingsProfiles (Feature 6.1) should be completed first for profile export support |
| Output Files (NEW) | None — all logic added to existing files |
| Files Modified | `backend/api/views.py`, `backend/api/urls.py`, `frontend/app/settings/page.tsx`, `frontend/store/settingsStore.ts` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow currently stores all global settings exclusively inside the application database with no mechanism for exporting or importing them. When a creator reinstalls the operating system, migrates to a new machine, or sets up a secondary workstation, their carefully crafted subtitle styles, preferred TTS voice, zoom intensity, and render configuration must be reconstructed entirely from memory by manually re-entering every settings field. This problem compounds significantly for users who have invested significant time fine-tuning settings across multiple named profiles — all of that configuration work is permanently lost with a single database reset. There is also no way for a creator to share their production configuration with a collaborator, a client, or an online community.

### 1.2 Proposed Solution

Implement a lightweight JSON-based settings portability system that allows any GlobalSettings record (or a named SettingsProfile) to be downloaded as a structured JSON file and later re-imported on the same or any other StoryFlow installation, with frontend validation and a diff preview before applying.

- Add a Django view at `GET /api/settings/export/` that serializes the current `GlobalSettings` record into a flat JSON dictionary and returns it as an HTTP response with `Content-Disposition: attachment; filename=storyflow_settings.json` and `Content-Type: application/json` so the browser triggers a file download automatically.
- Extend the export endpoint to accept an optional query parameter `profile_id` so that `GET /api/settings/export/?profile_id=3` exports a specific SettingsProfile's `settings_data` field instead of the live GlobalSettings, enabling portable profile backups.
- Add a Django view at `POST /api/settings/import/` that receives a raw JSON body, validates the structure against a known required-field schema (fields: `subtitle_font`, `voice_id`, `zoom_intensity`, `transition_duration`, `subtitle_style`, and any other GlobalSettings fields), applies validated values to the GlobalSettings record, and returns either HTTP 200 with the updated settings or HTTP 400 with per-field validation errors.
- On the frontend, add an "Export Settings" button in the settings page toolbar that calls the export endpoint and programmatically triggers the browser download by creating a temporary anchor element pointing to the response blob URL.
- Add an "Import Settings" file input button that opens an OS file picker filtered to `.json` files; on file selection, read the file using the browser `FileReader` API, parse the JSON, and display a diff modal comparing current settings values versus the imported values before asking for confirmation.
- The diff modal shows a two-column table (Current Value vs Imported Value) with only the changed fields highlighted, allowing the creator to review exactly what will change before committing the import.

### 1.3 Scope

| Dimension | In Scope |
|---|---|
| GlobalSettings export | Download current GlobalSettings as a JSON file |
| SettingsProfile export | Download a named profile's data as a JSON file via profile_id param |
| Settings import with validation | Upload JSON, validate schema, preview diff, confirm write |
| Field-level import errors | Backend returns per-field errors for invalid imported values |

| Dimension | Out of Scope |
|---|---|
| Project render_settings export | Per-project render overrides are not included in this export |
| Bulk profile export | Exporting all profiles in a single archive is a future enhancement |
| Auto-import on startup | Auto-loading from a config file path is not included |
| Encrypted export | Security-hardened export for sensitive fields (API keys) is a separate concern |

### 1.4 Key Files Reference

| File | Role in This Feature |
|---|---|
| `backend/api/views.py` | Add `ExportSettingsView` and `ImportSettingsView` function-based or class-based views |
| `backend/api/urls.py` | Register `/api/settings/export/` and `/api/settings/import/` URL patterns |
| `backend/api/serializers.py` | Reuse or extend `GlobalSettingsSerializer` for import validation |
| `frontend/app/settings/page.tsx` | Add Export button, Import file input, and import diff modal component |
| `frontend/store/settingsStore.ts` | Add `importSettings` async action that calls the import endpoint and refreshes state |

---

## 2. Flow Diagram

```
EXPORT FLOW:
User clicks "Export Settings" button
         |
         v
Frontend calls GET /api/settings/export/
(optional: ?profile_id=3 for a named profile)
         |
         v
Backend serializes GlobalSettings (or profile.settings_data)
         |
         v
Response: Content-Disposition: attachment
         |
         v
Browser downloads storyflow_settings.json

IMPORT FLOW:
User clicks "Import Settings" → OS file picker opens
         |
         v
User selects storyflow_settings.json
         |
         v
FileReader parses JSON → validates required keys
         |
    Invalid? → Show field error list, abort
         |
    Valid? → Show diff modal
         |
         v
Two-column diff table: Current vs Imported
User reviews → clicks "Apply Import"
         |
         v
POST /api/settings/import/  (JSON body)
         |
    Backend validation fails? → return 400 + errors
         |
    Success → GlobalSettings updated
         |
         v
settingsStore refreshed → form fields update
```

---

## 3. Step-by-Step Instructions

### Step 1 — Add export and import views in backend/api/views.py

File: `backend/api/views.py`

Create `ExportSettingsView` as a class-based `APIView` with a `get` method. The method retrieves the singleton `GlobalSettings` record; if a `profile_id` query parameter is present, it fetches the matching `SettingsProfile` and uses its `settings_data` instead. Serialize the data using `GlobalSettingsSerializer` and return it as a `JsonResponse` with the `Content-Disposition` header set to `attachment; filename=storyflow_settings.json`. Create `ImportSettingsView` as a second `APIView` with a `post` method that reads the raw request body as JSON, passes it through `GlobalSettingsSerializer(instance=settings, data=request.data, partial=False)`, and on valid saves calls `serializer.save()` and returns the updated settings; on invalid returns `serializer.errors` with HTTP 400.

### Step 2 — Register new URL patterns in backend/api/urls.py

File: `backend/api/urls.py`

Add two explicit path entries in the urlpatterns list: `path('settings/export/', ExportSettingsView.as_view(), name='settings-export')` and `path('settings/import/', ImportSettingsView.as_view(), name='settings-import')`. Both paths sit alongside the existing settings endpoints and are prefixed by the parent `api/` router prefix. Verify there are no naming conflicts with existing GlobalSettings CRUD endpoints. Import both new view classes at the top of the file.

### Step 3 — Add Export button and Import file input to the settings page

File: `frontend/app/settings/page.tsx`

Add a small action toolbar row at the top of the settings page card, below the Profile selector (if Feature 6.1 is implemented) and above the first settings section. The toolbar contains two buttons: "Export Settings" (outlined secondary style) and "Import Settings" (outlined secondary style). The Export button fires an async function that calls `fetch('/api/settings/export/')`, converts the response to a blob, creates a temporary `<a>` element with an object URL, programmatically clicks it to trigger the browser download, and then revokes the object URL. The Import button is backed by a hidden `<input type="file" accept=".json">` element; clicking the visible button programmatically clicks the hidden input to open the OS file picker.

### Step 4 — Implement FileReader parsing, diff modal, and import action

File: `frontend/app/settings/page.tsx` and `frontend/store/settingsStore.ts`

In the page component, wire the file input's `onChange` handler to read the selected file using `new FileReader()`, parse the resulting string as JSON in the `onload` callback, and validate that all required fields are present in the parsed object. If any required field is missing, display an inline error banner listing the missing fields. If valid, compute a diff array by comparing each field in the parsed JSON against the current `settingsStore` values and open a modal (ShadCN Dialog) that renders a table with "Field", "Current Value", and "Imported Value" columns — showing only rows where the values differ. A "Apply Import" button in the modal footer calls `settingsStore.importSettings(parsedData)`. In settingsStore, the `importSettings` action sends `POST /api/settings/import/` with the parsed data, handles 400 validation errors by setting a store-level `importErrors` field, and on success calls the existing settings refresh action.

---

## 4. Expected Outcome

- Clicking "Export Settings" downloads a file named `storyflow_settings.json` containing a human-readable flat JSON object of all current GlobalSettings field values.
- Exporting with `?profile_id=N` downloads a JSON file representing the named profile, with the same structure as the GlobalSettings export for interoperability.
- Importing a valid JSON file shows a clean diff modal displaying only the fields that will change, with clear before-and-after values.
- Importing an invalid JSON file (missing required fields or incorrect types) shows per-field error messages without making any changes to the database.
- After a successful import, all settings form fields on the page update immediately to reflect the imported values without requiring a page refresh.
- The exported JSON file is forward-compatible — unused fields are silently ignored by the import endpoint so that exports from older versions can still be partially applied.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `ExportSettingsView` returns HTTP 200 with `Content-Disposition: attachment` header and a JSON body containing all GlobalSettings fields when called without query params.
- [ ] `ExportSettingsView` with `?profile_id=3` returns the `settings_data` of the matching `SettingsProfile`, not the live GlobalSettings data.
- [ ] `ImportSettingsView` with a payload missing the `subtitle_font` field returns HTTP 400 with a `subtitle_font` key in the error response body.
- [ ] `ImportSettingsView` with a fully valid payload updates the GlobalSettings record and returns HTTP 200 with the updated serialized data.

### 5.2 Integration / Manual Tests

- [ ] Export current settings, manually modify two field values in the JSON file using a text editor, re-import the file, confirm the diff modal shows exactly two changed rows, apply the import, and verify the form fields reflect the two changed values.
- [ ] Export a SettingsProfile (not the live GlobalSettings) and verify the downloaded JSON contains the profile's stored data rather than the current active settings.
- [ ] Upload a syntactically invalid JSON file (malformed JSON string) and verify the frontend shows a parse error message and does not open the diff modal.
- [ ] Import a settings file from a different StoryFlow instance that contains an unrecognized extra field and verify the import succeeds while the extra field is silently ignored.
- [ ] Confirm that clicking "Cancel" in the diff modal makes no backend call and leaves all settings unchanged.

### 5.3 Regression Tests

- [ ] Existing `GET /api/settings/` and `PATCH /api/settings/` endpoints return correct data and are not broken by the addition of the new export/import endpoints.
- [ ] The settings page profile selector (from Feature 6.1) and the export/import toolbar can coexist in the same layout without visual overlap or functional interference.
- [ ] The settingsStore refresh action triggered after a successful import produces the same result as the refresh triggered on initial page load.

---

## 6. Notes for AI Agent

- The `Content-Disposition: attachment` header is what triggers the browser download; the `Content-Type` must be `application/json` (not `application/octet-stream`) so that the file opens correctly in a text editor when inspected. Both headers must be set together on the response object in Django.
- The required-field schema for import validation should be defined as a Python constant list in `backend/api/views.py` (or a shared constants module) rather than duplicated in both the view and serializer — this single list is the authoritative schema for determining whether an imported file is complete enough to apply.
- The frontend diff computation must handle the case where an imported field value and the current store value are both numerically equal but differ in type (e.g., integer `1` vs float `1.0`) — treat these as equal and do not show them as diffs.
- If Feature 6.1 (Settings Profiles) has not yet been implemented, the `profile_id` query parameter support on the export endpoint should still be stubbed — return HTTP 404 with a message indicating profiles are not yet enabled — so the URL contract is established even if the functionality is deferred.
