# Feature 4.6 — Export All Projects Metadata

| Field | Value |
|---|---|
| Feature ID | 4.6 |
| Title | Export All Projects Metadata |
| Status | 🟡 Planned |
| Priority | Low |
| Complexity | Low |
| Estimated Effort | 1–2 days |
| Dependencies | Feature 1.1 (Project Model), Feature 1.2 (Segment Model) |
| Output Files (NEW) | None — all changes are to existing files |
| Files Modified | backend/api/views.py, backend/api/urls.py, backend/api/serializers.py, frontend/app/projects/page.tsx, frontend/app/settings/page.tsx |

---

## 1. Document Overview

### 1.1 Problem Statement

Every piece of project metadata that a creator accumulates in StoryFlow — project titles,
production categories, target platforms, render settings, segment counts, creation and update
timestamps, completion statuses, and output file references — is stored exclusively inside a
local SQLite database file that is opaque to any external tool. Creators who want to analyze
their production output over time, generate a portfolio report, cross-reference their StoryFlow
output against their publishing calendar, or simply verify that a completed batch of videos
was all rendered successfully have no structured mechanism to access this data outside the
application itself. Migrating a project catalog to another machine or another StoryFlow
installation is not possible without manually copying the raw database file, which is a fragile
and error-prone process that also transfers unrelated internal state. The lack of a structured
metadata export means that StoryFlow is a closed silo that cannot participate in the broader
data workflows that professional content creators rely on.

### 1.2 Proposed Solution

Add a lightweight metadata export system to the StoryFlow backend that serializes all project
records — without any media files — to a downloadable JSON or CSV file via dedicated API
endpoints. The frontend surfaces these endpoints through clearly labeled export buttons in
the project list page and global settings, making the data accessible to any creator with a
single click and compatible with any downstream tool that reads standard data formats.

- Create a `GET /api/projects/export/` endpoint in `backend/api/views.py` that accepts a
  `format` query parameter supporting `"json"` and `"csv"` values and returns a file download
  response containing all project metadata records.
- For the JSON format, construct the response body as a structured envelope containing an
  `exported_at` timestamp, a `storyflow_version` field, a `total_projects` count, and a
  `projects` array with one object per project containing all metadata fields.
- For the CSV format, use Python's built-in `csv.DictWriter` to produce a flat one-row-per-
  project file with columns matching the metadata fields returned by the JSON format, with
  appropriate HTTP response headers to trigger a browser download.
- Add a `GET /api/projects/{id}/export/` endpoint that exports a single project as a detailed
  JSON document including all segment data: sequence index, text content, image prompt, audio
  file name, and image file name for each segment.
- Add a `Content-Disposition: attachment` response header to all export endpoints with a
  filename containing the current date, such as `storyflow_export_2026-03-11.json`, to ensure
  browsers treat the response as a download rather than opening it inline.
- Add an "Export All" button in the Data Management section of `frontend/app/settings/page.tsx`
  with a format dropdown (JSON / CSV) that opens the appropriate export URL in a new tab.
- Add a per-project "Export Data" option in the project list context menu in
  `frontend/app/projects/page.tsx` that downloads the single-project detailed JSON.

### 1.3 Scope

#### In Scope

| Item | Description |
|---|---|
| All-projects JSON export | A downloadable JSON file containing metadata for all projects in the database |
| All-projects CSV export | A downloadable CSV file with one row per project and all metadata columns |
| Single-project JSON export | A detailed JSON export of one project including all of its segment records |
| Frontend export controls | Download buttons in the settings page and project list context menu |

#### Out of Scope

| Item | Description |
|---|---|
| Media file export | Exporting actual image files, audio files, or MP4 files is not part of this feature |
| Import from exported file | Re-importing a JSON or CSV export to recreate projects is excluded from this feature |
| Scheduled automatic exports | Generating export files on a cron schedule or nightly basis is not included here |
| Filtering and partial exports | Exporting only projects matching a date range or status filter is out of this scope |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| backend/api/views.py | DRF views; will receive the two export endpoint handlers | Existing; contains project CRUD and render views |
| backend/api/serializers.py | DRF serializers for Project and Segment | Existing; used to provide the field structure for export |
| backend/api/urls.py | URL routing; will register the export endpoint paths | Existing; project URL patterns already defined |
| frontend/app/projects/page.tsx | Project list page; will receive per-project export context menu item | Existing; project list with context menus likely present |
| frontend/app/settings/page.tsx | Global settings page; will receive the Data Management export section | Existing; settings sections present |

---

## 2. Flow Diagram

    Creator clicks "Export All Projects" in Settings
            |
            v
    Selects format:  [ JSON  |  CSV ]
            |
            v
    Browser opens  GET /api/projects/export/?format=json
               or  GET /api/projects/export/?format=csv
            |
            v
    View queries all Project records from database
    annotates each with segment_count (Count aggregation)
            |
            v
    format == "json" ?
         /          \
        yes          no  (csv)
        |             |
        v             v
    Build JSON       DictWriter writes
    envelope dict    rows to StringIO buffer
        |             |
        v             v
    HttpResponse    HttpResponse
    (application/   (text/csv +
     json)           Content-Disposition)
        |             |
        v             v
    Browser receives file download
    with date-stamped filename

---

## 3. Step-by-Step Instructions

### Step 1 — Design the Export Data Structure

Before writing any code, define what fields will appear in both the JSON and CSV export
formats by reviewing the `Project` and `Segment` models in `backend/api/models.py` and
listing every field that carries meaningful metadata for a creator. The all-projects export
should include at minimum: `id`, `name`, `status`, `render_priority`, `segment_count`
(annotated via Django ORM), `created_at`, `updated_at`, and `output_file` as a relative path
string. The single-project detailed export should repeat those project-level fields and nest
a `segments` array containing each segment's `sequence_index`, `text_content`, `image_prompt`,
and the filenames (not full paths) of `audio_file` and `image_file`. The JSON envelope for
the all-projects export should wrap the `projects` array with a metadata object containing
`exported_at` (ISO 8601 timestamp), `storyflow_version` (a string constant such as `"1.0.0"`),
and `total_projects` (an integer count) at the top level of the response body.

### Step 2 — Implement the All-Projects Export Endpoint

Open `backend/api/views.py` and create a new view function `export_all_projects` that handles
`GET /api/projects/export/`. Read the `format` query parameter from `request.GET` and default
to `"json"` if it is absent or unrecognized. For the JSON path, use Django's ORM to fetch all
`Project` records with a `Count` annotation for segment count, construct each project's
dictionary by iterating over the queryset and building the field map described in Step 1, then
serialize the full envelope dict with `json.dumps` and return it as an `HttpResponse` with
`content_type="application/json"` and a `Content-Disposition` header of the form
`attachment; filename="storyflow_export_YYYY-MM-DD.json"`. For the CSV path, create an in-
memory `io.StringIO` buffer, initialize a `csv.DictWriter` with the list of column names, write
the header row, then iterate over the queryset writing one row per project, and return the
buffer's string value as an `HttpResponse` with `content_type="text/csv"` and the corresponding
`Content-Disposition` header. Register the route in `backend/api/urls.py` at the path
`projects/export/` before the `projects/<int:pk>/` pattern to avoid slug conflicts.

### Step 3 — Implement the Single-Project Export Endpoint

In `backend/api/views.py`, create a second view function `export_single_project` that handles
`GET /api/projects/{id}/export/`. Fetch the project by primary key, returning 404 if not found,
then fetch all related `Segment` records ordered by `sequence_index`. Build the project
dictionary with all metadata fields and add a `segments` list where each entry is a dictionary
containing `sequence_index`, `text_content`, `image_prompt`, and the base filenames extracted
from `audio_file.name` and `image_file.name` (using `os.path.basename` so absolute storage
paths are not leaked). Serialize the result with `json.dumps` using `default=str` to handle
any `DateTimeField` values, and return it as a JSON download response with the filename
`storyflow_project_{id}_export_YYYY-MM-DD.json`. Register this route in `backend/api/urls.py`
at `projects/<int:pk>/export/` alongside the existing project detail routes. The endpoint
should be read-only (GET only) and require no request body, making it safe to call from a
direct browser URL or a fetch-based download trigger in the frontend.

### Step 4 — Add Export Controls to the Settings Page

Open `frontend/app/settings/page.tsx` and add a new "Data Management" section below the
existing settings sections, containing a heading, a brief description explaining what the
export includes, and an export action area with a format selector and a download button. The
format selector should be a Shadcn/UI `Select` component with "JSON" and "CSV" options,
backed by a local state variable initialized to "json". The download button should be labeled
"Export All Projects" and on click should construct the export URL as
`/api/projects/export/?format={selectedFormat}` and navigate to it directly using
`window.open(url, "_blank")` or create a temporary anchor element with the `download` attribute
to trigger the browser's file download dialog. Wrap the entire Data Management section in a
card component consistent with the visual style of the rest of the settings page, and add a
note below the button saying the export includes project metadata only, not media files.

### Step 5 — Add Per-Project Export to the Project List Context Menu

Open `frontend/app/projects/page.tsx` and locate the three-dot context menu or action menu
component that appears on each project card or row in the project list. Add a new menu item
labeled "Export Project Data" with a download icon below any existing items such as "Edit",
"Duplicate", or "Delete". When clicked, this item should construct the URL
`/api/projects/{project.id}/export/` and trigger a download by creating and clicking a
temporary anchor element in JavaScript, passing the project's name as a hint for the filename.
This gives the creator a quick way to snapshot a single project's metadata and segment
information as a JSON backup without navigating away from the project list. Ensure the menu
item is always available regardless of the project's current status, since the export is a
read-only operation that does not modify any data and is safe to call on any project at any
time.

---

## 4. Expected Outcome

1. A GET request to `/api/projects/export/?format=json` returns a valid JSON file download
   with a `Content-Disposition` header, an `exported_at` timestamp, and a `projects` array
   containing one object per project with all required metadata fields.
2. A GET request to `/api/projects/export/?format=csv` returns a valid CSV file download with
   a header row matching the defined column set and one data row per project in the database.
3. The segment_count column in both export formats accurately reflects the number of Segment
   records associated with each project as annotated by the ORM query.
4. A GET request to `/api/projects/{id}/export/` returns a detailed JSON download for the
   specified project including a `segments` array with all segment fields present.
5. The exported JSON and CSV filenames include the current date in YYYY-MM-DD format so that
   exports from different dates do not overwrite each other on the creator's local filesystem.
6. The "Export All Projects" button in the settings page triggers a browser file download of
   the correct format matching the creator's selection without navigating away from the page.
7. The "Export Project Data" context menu item on the project list downloads a complete single-
   project JSON file with all segment data when clicked for any project regardless of status.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] A unit test with a seeded database of five projects confirms that the JSON export
      response body includes exactly five objects in the `projects` array with correct field values.
- [ ] A unit test confirms that the CSV export response has a `Content-Type` of `text/csv`
      and a `Content-Disposition` header containing the word "attachment" and a `.csv` filename.
- [ ] A unit test confirms that the single-project export for a project with three segments
      returns a `segments` array of length three with correct `sequence_index` values.
- [ ] A unit test confirms that the all-projects export endpoint returns 200 with an empty
      `projects` array rather than an error when no projects exist in the database.
- [ ] A unit test confirms that the `storyflow_version` field and `exported_at` field are
      present in the JSON export envelope with the correct types.

### 5.2 Integration / Manual Tests

- [ ] Open the settings page, select JSON format, click "Export All Projects", and verify the
      downloaded file opens correctly in a text editor and contains valid JSON with the expected
      structure and field values matching the projects in the database.
- [ ] Repeat the above test with the CSV format and open the downloaded file in a spreadsheet
      application to confirm all columns are correctly populated and separated.
- [ ] Right-click or open the context menu on a project in the project list, click "Export
      Project Data", and verify the downloaded JSON file contains the correct project metadata
      and a segments array matching the project's actual segment count and content.
- [ ] Create a project with five segments of known text content values, export it via the
      single-project endpoint, and confirm all five segments appear in the correct order with
      matching text_content values in the download.
- [ ] Verify that the export endpoints do not include any absolute filesystem paths, internal
      database IDs for file storage references, or sensitive configuration values in their output.
- [ ] Test the export endpoints with an empty database and confirm both the JSON and CSV
      formats return valid, parseable empty responses rather than server errors.

### 5.3 Regression Tests

- [ ] Confirm that all existing project CRUD endpoints continue to function correctly after the
      new export route is registered in `backend/api/urls.py`.
- [ ] Verify that the project list page renders correctly and all existing context menu items
      continue to function after the "Export Project Data" item is added.
- [ ] Ensure the settings page loads without JavaScript errors and all existing settings
      sections are still visible and functional after the Data Management section is added.

---

## 6. Notes for AI Agent

- Register the `projects/export/` URL pattern in `backend/api/urls.py` before the
  `projects/<int:pk>/` pattern to prevent the router from interpreting the literal string
  "export" as a primary key integer, which would cause a 404 or a 500 error.
- Use `json.dumps(..., default=str)` when serializing the export data to ensure that Django
  `DateTimeField` values, `FieldFile` objects, and any other non-JSON-serializable fields
  are converted to strings without requiring a custom encoder class.
- The CSV export should use `io.StringIO` rather than `io.BytesIO` as the buffer and return
  the buffer's `getvalue()` as the response content with `content_type="text/csv; charset=utf-8"`
  to ensure correct encoding on Windows systems where Excel may open the file.
- When constructing segment file name fields for the single-project export, always use
  `os.path.basename(field.name)` rather than `field.url` to avoid exposing absolute server
  paths or signed URL tokens that would break portability of the exported document.
- Avoid importing the export serializer or view into the regular project API serializer to
  prevent circular dependencies — keep the export logic entirely self-contained within the
  export view function using direct ORM queries and plain Python dict construction.

---

## 7. Implementation Risks and Mitigations

- **Risk: URL routing collision between export path and integer primary key pattern.** If the
  projects/export/ URL pattern is registered after the projects/int:pk/ pattern in urls.py,
  Django's resolver will attempt to coerce the literal string "export" to an integer and raise
  an uncaught ValueError before the export view is reached, resulting in a confusing 500 error.
  Mitigation: always register projects/export/ and any other literal-suffix routes above the
  projects/int:pk/ pattern in urls.py, and place an ordering comment in the URL file explaining
  the requirement so future contributors do not accidentally insert a wildcard pattern above the
  export path during subsequent feature additions.

- **Risk: Memory exhaustion when exporting thousands of projects.** The all-projects export
  endpoint loads every Project record into a Python list before serializing the entire collection
  to JSON, and for a database with several thousand projects each having a large render_settings
  JSONField blob, this could exhaust the Gunicorn worker's memory allocation and cause the
  worker to be killed. Mitigation: use Django's queryset iterator() method with a chunk_size
  parameter to stream database rows in batches, write each batch to the response body using a
  StreamingHttpResponse with a generator function, and set a reasonable default upper limit for
  the non-streaming version (e.g., 2000 projects) while the streaming path is developed.

- **Risk: Non-serializable field values crashing the export with a 500 error.** Fields such
  as output_file (a FileField object), render_settings (a JSONField that may contain nested
  non-standard types), and DateTimeField values are not natively serializable by plain json.dumps
  without a custom handler, and a single project with an unusual stored value could cause the
  entire export response to fail for every user. Mitigation: always pass default=str to
  json.dumps as a universal fallback, write a unit test that exports a seeded project with all
  fields fully populated, and add an explicit str() conversion for FileField values so paths
  are exported as strings rather than FieldFile objects.

- **Risk: Leaking absolute server filesystem paths in the export file.** If output_file.path
  or audio_file.path is used instead of .name when building the export dict, the resulting
  JSON or CSV file will contain absolute paths like /home/user/storyflow/media/projects/42/
  output.mp4, which expose server directory structure information and break portability when
  the export is opened on a different machine. Mitigation: always use field.name (the relative
  path stored in the database) or os.path.basename(field.name) as appropriate, and add a unit
  test that asserts no value in the export output begins with the MEDIA_ROOT prefix.

- **Risk: CSV encoding issues when project names contain non-ASCII characters.** The csv module
  in Python 3 writes unicode text correctly, but if the HTTP response content type does not
  specify charset=utf-8, some browsers and spreadsheet applications (notably Excel on Windows)
  may interpret the file as Latin-1 and display garbled characters for projects with non-English
  names or prompts. Mitigation: set content_type="text/csv; charset=utf-8" on the response and
  prepend a UTF-8 BOM (the byte sequence EF BB BF) to the CSV output when the format is csv so
  that Excel correctly detects the encoding on all platforms without requiring manual import
  configuration from the creator.

---

## 8. Rollout and Phasing

### 8.1 Phase One — JSON Export Endpoint (Backend Only)

The first phase delivers only the GET /api/projects/export/?format=json endpoint and its URL
registration, without any frontend changes. This enables developers to test the endpoint by
visiting it directly in a browser and saving the response, and to verify that the JSON envelope
structure — including exported_at, storyflow_version, total_projects, and the projects array
with correctly populated fields — matches the specification documented in Step one. The
storyflow_version constant should be defined in this phase and linked to the application's
canonical version source so it does not need to be manually updated on each release. Finalizing
and peer-reviewing the JSON schema in this phase is important because it establishes the format
contract that external tools will consume.

### 8.2 Phase Two — CSV Format, Single-Project Export, and Frontend Buttons

The second phase adds the CSV format variant, the single-project detailed export endpoint, and
both frontend entry points: the Export All button in settings and the per-project context menu
item in the project list. End-to-end testing should include opening the JSON export in a code
editor to verify structure, opening the CSV in a spreadsheet application to verify column
alignment and encoding, and downloading the single-project JSON for a project with multiple
segments to confirm the segments array is correctly structured and ordered by sequence index.

### 8.3 Phase Three — Performance Hardening and Format Documentation

The third phase implements the streaming export approach for large databases, adds the UTF-8
BOM to CSV output for cross-platform compatibility, writes the complete unit test suite from
the verification checklist, and creates a formal Export Format Specification document in the
docs/ directory describing the JSON and CSV schemas with field definitions and example values.
This documentation will serve as the reference for any future import feature or third-party
integration that consumes StoryFlow export files, and freezing the format with a version tag
in this phase prevents unnecessary breaking changes as the application evolves.

