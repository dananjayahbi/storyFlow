# Feature 4.7 — Project Handoff Packages

| Field | Value |
|---|---|
| Feature ID | 4.7 |
| Title | Project Handoff Packages |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Medium |
| Estimated Effort | 3–5 days |
| Dependencies | Feature 1.1 (Project Model), Feature 1.2 (Segment Model), Feature 4.6 (Metadata Export) |
| Output Files (NEW) | backend/api/package_utils.py |
| Files Modified | backend/api/views.py, backend/api/urls.py, backend/api/models.py, frontend/app/projects/[id]/page.tsx, frontend/app/projects/page.tsx, frontend/components/ImportPackageZone.tsx |

---

## 1. Document Overview

### 1.1 Problem Statement

A StoryFlow project — which consists of a database record for the project itself, one database
record per segment, source PNG images attached to those segments, TTS-generated audio files
attached to those segments, and a rendered MP4 output file — exists entirely within a single
local installation of the application and cannot be transferred to another StoryFlow instance
without manually locating and copying every individual file along with the raw SQLite database
rows. If two creators want to collaborate on the same piece of content (for example, one
person handles the script writing and image generation while another handles TTS selection and
final rendering), they currently have no structured mechanism to hand off the project bundle
between their respective machines without deep knowledge of the internal directory layout and
database schema. There is also no safe way to archive a completed project as a self-contained
unit that can be restored identically on a fresh machine months or years later, which is a
significant risk for creators who rely on StoryFlow to produce their primary content library.

### 1.2 Proposed Solution

Implement a project export/import system — the "Handoff Package" — that bundles all database
metadata and all referenced media files for a given project into a single versioned ZIP archive
that is both human-readable and machine-importable. Any StoryFlow instance can consume the ZIP
and reconstruct the project's database records and media files in one step, making
collaboration and archival straightforward and safe.

- Create a new utility module `backend/api/package_utils.py` housing `build_package(project_id)`
  and `extract_package(zip_bytes)` functions that contain the ZIP construction and parsing
  logic separate from the view layer.
- Add a `POST /api/projects/{id}/export-package/` endpoint in `backend/api/views.py` that
  calls `build_package` and streams the resulting ZIP back to the client as a download with
  `Content-Type: application/zip`.
- The ZIP archive always contains exactly three artifacts: a `manifest.json` describing the
  package format version and file inventory, a `project.json` with all project and segment
  metadata using relative internal paths, and `images/` and `audio/` subfolders containing
  copies of all referenced media files.
- Add a `POST /api/projects/import-package/` endpoint in `backend/api/views.py` that accepts
  a multipart form upload of a ZIP file and calls `extract_package` to reconstruct the project.
- During import, create a new `Project` record and new `Segment` records with new primary keys
  rather than reusing the IDs from the package, appending "(imported)" to the project name
  if a project with the same original name already exists to prevent silent overwrites.
- Add an "Export Package (.zip)" button on the project detail page and an "Import Package"
  drag-and-drop zone on the project list page in the frontend.
- Store a package format version field in `manifest.json` so that future StoryFlow versions
  can detect and handle packages created by older versions with a compatibility shim.

### 1.3 Scope

#### In Scope

| Item | Description |
|---|---|
| ZIP package creation | Bundling project metadata and all referenced media files into a self-contained ZIP archive |
| ZIP package import | Parsing an uploaded ZIP, validating the manifest, and reconstructing all database records |
| Relative path rewriting | Replacing absolute media paths with relative paths inside the ZIP for portability |
| Versioned package format | Including a format version field in manifest.json for future compatibility handling |

#### Out of Scope

| Item | Description |
|---|---|
| Differential or incremental packages | Exporting only the changes since a previous package snapshot is not included |
| cloud-hosted package sharing | Uploading packages to a shared cloud repository for team discovery is out of scope |
| Re-render on import | Automatically re-triggering a render after importing a package is not included here |
| Merging two projects on import | Importing a package into an existing project rather than creating a new one is excluded |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| backend/api/package_utils.py | New utility module for ZIP construction and extraction logic | Does not exist; must be created |
| backend/api/views.py | DRF views; will receive export-package and import-package endpoints | Existing; contains project and segment views |
| backend/api/models.py | Project and Segment ORM models | Existing; may need an original_id field for import tracking |
| frontend/app/projects/[id]/page.tsx | Project detail page; will receive the Export Package button | Existing; render controls and settings panels present |
| frontend/components/ImportPackageZone.tsx | New drag-and-drop import component | Does not exist; must be created |

---

## 2. Flow Diagram

    Creator clicks "Export Package (.zip)"
            |
            v
    POST /api/projects/{id}/export-package/
            |
            v
    package_utils.build_package(project_id)
      - Fetch Project + all Segments from DB
      - Open in-memory ZipFile (io.BytesIO)
      - Write manifest.json  (version, inventory)
      - Write project.json   (all metadata, relative paths)
      - Copy each segment image  → images/segment_NNN.png
      - Copy each segment audio  → audio/segment_NNN.mp3
            |
            v
    Stream ZIP as application/zip download
    filename: storyflow_project_{id}_YYYY-MM-DD.zip
            |   (shared with collaborator)
            v
    Collaborator drags ZIP into ImportPackageZone
            |
            v
    POST /api/projects/import-package/  (multipart)
            |
            v
    package_utils.extract_package(zip_bytes)
      - Open ZipFile, read manifest.json → validate version
      - Read project.json → build Project dict
      - Check name collision → append "(imported)" if needed
      - Create new Project record (new PK)
      - Extract images/ → MEDIA_ROOT/projects/{new_id}/images/
      - Extract audio/  → MEDIA_ROOT/projects/{new_id}/audio/
      - Create Segment records with updated file paths
            |
            v
    Returns { new_project_id, redirect URL }
    Frontend navigates to new project detail page

---

## 3. Step-by-Step Instructions

### Step 1 — Create the Package Utility Module

Create a new file at `backend/api/package_utils.py` and implement two public functions:
`build_package(project_id)` and `extract_package(zip_file_obj)`. The `build_package` function
starts by fetching the `Project` record and all related `Segment` records ordered by
`sequence_index`, then opens an `io.BytesIO` buffer and creates a `zipfile.ZipFile` object
writing to it in `"w"` mode with `ZIP_DEFLATED` compression. It writes a `manifest.json`
entry containing the package format version string (e.g., `"1.0"`), the StoryFlow version,
the project's original ID, the total number of segments, and a list of all files included in
the archive for inventory and integrity checking. It then writes a `project.json` entry using
`json.dumps` of a project dict that replaces all `image_file` and `audio_file` values with
relative paths of the form `images/segment_001.png` and `audio/segment_001.mp3`. Finally it
iterates over each segment, reads the actual media file bytes from the filesystem using the
`MEDIA_ROOT` setting, and writes them into the ZIP at the corresponding relative path. After
all files are written, it seeks the buffer to position zero and returns the buffer so the
calling view can stream it as a response.

### Step 2 — Implement the Extract Package Function

In the `extract_package` function within `backend/api/package_utils.py`, accept a file-like
object representing the uploaded ZIP archive and open it with `zipfile.ZipFile` in read mode.
Read and parse `manifest.json` first and raise a `ValueError` with a descriptive message if
the format version field is missing or contains an unrecognized version string, so the import
endpoint can return a meaningful 400 error to the frontend rather than a cryptic 500. Read and
parse `project.json` to extract the project-level metadata and the segments array, then check
whether a `Project` record with the same `name` already exists in the database and if so
append " (imported)" to the name before constructing the new record. Create the new `Project`
with `Project.objects.create(...)` receiving a fresh auto-assigned primary key, then determine
the destination media subdirectory under `MEDIA_ROOT` for this new project ID. For each segment
entry in the parsed segments array, extract the corresponding image and audio files from the
ZIP to the new project's media subdirectory, create a `Segment` record pointing to the new
file paths, and return the new project's primary key to the calling view.

### Step 3 — Add the Export and Import API Endpoints

Open `backend/api/views.py` and add two new endpoints. The export endpoint handles
`POST /api/projects/{id}/export-package/`: it fetches the project by primary key, calls
`package_utils.build_package(project.id)` to obtain the in-memory BytesIO buffer, wraps it
in a `StreamingHttpResponse` (or a regular `HttpResponse` for smaller packages), sets the
`Content-Type` to `application/zip`, and adds a `Content-Disposition` header of the form
`attachment; filename="storyflow_project_{id}_{date}.zip"`. The import endpoint handles
`POST /api/projects/import-package/`: it reads the uploaded file from `request.FILES["package"]`,
validates that the filename ends with `.zip` or that the content type is `application/zip`,
calls `package_utils.extract_package(uploaded_file)`, catches `ValueError` to return a 400
response with the validation message, and on success returns a 201 response containing the
`new_project_id` and the frontend URL for the new project's detail page. Register both routes
in `backend/api/urls.py` taking care to place `projects/import-package/` before any wildcard
project ID patterns.

### Step 4 — Build the Export Package Button in the Project Detail Page

Open `frontend/app/projects/[id]/page.tsx` and add an "Export Package (.zip)" button to the
project actions area, adjacent to or below the existing render controls or settings panel.
The button should dispatch a POST fetch request to `/api/projects/{id}/export-package/` and
handle the response as a blob download: call `response.blob()` on the fetch response, create
an object URL from the blob with `URL.createObjectURL`, assign it to a temporary anchor
element with the `download` attribute set to a suggested filename, programmatically click it,
then revoke the object URL to free memory. Add a loading spinner state on the button during
the fetch to indicate that the server is assembling the ZIP, which may take several seconds
for large projects with many media files. Display an error toast notification if the fetch
returns a non-200 status code so the creator knows the export failed rather than receiving
a silent empty download.

### Step 5 — Build the Import Package Zone Component and Integrate It

Create a new React component at `frontend/components/ImportPackageZone.tsx` that renders a
drag-and-drop file upload zone styled with a dashed border and an upload icon, accepting only
`.zip` files as indicated by the `accept=".zip"` attribute on the underlying hidden file input.
The component should manage three states: idle (showing the drop prompt), uploading (showing
a progress indicator), and result (showing either a success message with a "Go to Project" link
or an error message from the API response). When a file is dropped or selected, construct a
`FormData` object with the file appended under the key `"package"` and POST it to
`/api/projects/import-package/`, then on a 201 response navigate the user to the returned
project URL using Next.js's `useRouter` hook. Import and render `ImportPackageZone` in
`frontend/app/projects/page.tsx` in a collapsible or always-visible panel at the top or bottom
of the project list, labeled "Import Project Package" with a short description explaining that
this accepts `.zip` packages created by the "Export Package" function.

---

## 4. Expected Outcome

1. Calling the export-package endpoint for a project with five segments produces a valid ZIP
   file containing `manifest.json`, `project.json`, five files in `images/`, and five files
   in `audio/` with all files present and uncorrupted.
2. The `project.json` inside the ZIP uses only relative paths (e.g., `images/segment_001.png`)
   for all media file references and contains no absolute filesystem paths or server-specific
   URLs.
3. Uploading the exported ZIP via the import endpoint on a fresh StoryFlow installation creates
   a new `Project` record and the correct number of `Segment` records with all text and prompt
   fields matching the original project's values.
4. Importing a package whose project name already exists in the target database creates the
   import as a copy with "(imported)" appended to the name rather than overwriting the existing
   project.
5. Uploading a file that is not a valid StoryFlow package ZIP (e.g., a random archive or a
   package with an unrecognized manifest version) returns a 400 response with a descriptive
   error message and does not create any partial database records.
6. The "Export Package (.zip)" button on the project detail page triggers a file download with
   a correctly named ZIP file and shows a loading state during the server-side assembly period.
7. The `ImportPackageZone` component navigates the creator to the newly created project's
   detail page immediately after a successful import without requiring a manual page refresh.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] A unit test for `build_package` confirms that the returned BytesIO buffer is a valid ZIP
      file containing `manifest.json`, `project.json`, and the expected number of image and
      audio files for a project with a known segment count.
- [ ] A unit test for `extract_package` confirms that calling it with a valid package ZIP
      creates the correct number of Project and Segment records in the test database.
- [ ] A unit test confirms that `extract_package` raises a `ValueError` when given a ZIP that
      does not contain `manifest.json` or contains a manifest with an unrecognized version.
- [ ] A unit test confirms that importing a package whose project name matches an existing
      project results in the new project being named with "(imported)" suffix rather than
      overwriting the original.
- [ ] A unit test confirms that the export endpoint returns `Content-Type: application/zip`
      and a `Content-Disposition: attachment` header in its response.

### 5.2 Integration / Manual Tests

- [ ] Export a real project from a running StoryFlow instance, open the resulting ZIP manually,
      and verify that all listed files are present and that `project.json` is valid JSON with
      the correct field values and only relative file paths.
- [ ] Import the exported ZIP on the same StoryFlow instance and navigate to the newly created
      project to verify that all segment text content, image prompts, image previews, and audio
      playback work identically to the original.
- [ ] Import the exported ZIP on a separate StoryFlow instance (different machine or fresh
      database) and verify that the project is reconstructed correctly without any file-not-found
      errors in the segment media fields.
- [ ] Attempt to import a corrupt or incomplete ZIP and confirm that the import endpoint
      returns a 400 error and the import zone component displays the error message to the user.
- [ ] Export a project while another render is in progress for a different project and verify
      neither the export nor the running render is interrupted or corrupted by the concurrent
      operation.
- [ ] Verify that the drag-and-drop zone accepts a ZIP file dropped directly onto it and that
      the upload progress state is visible during the upload before the navigation event fires.

### 5.3 Regression Tests

- [ ] Confirm that all existing project detail page functionality (render controls, segment
      editor, settings panel) continues to work correctly after the Export Package button is
      added to the layout.
- [ ] Verify that the project list page renders correctly and existing project cards function
      normally after the ImportPackageZone component is inserted into the page.
- [ ] Ensure that the backend `/api/projects/` list and detail endpoints remain unaffected by
      the new package utility module and that no circular imports are introduced by its addition.

---

## 6. Notes for AI Agent

- Use `zipfile.ZipFile` in combination with `io.BytesIO` for the in-memory ZIP construction
  in `build_package` rather than writing to a temporary file on disk, to avoid leaving orphan
  temp files if the request is interrupted and to keep the implementation stateless.
- When reading media file bytes for the ZIP archive inside `build_package`, always resolve the
  absolute path using `os.path.join(settings.MEDIA_ROOT, segment.image_file.name)` rather than
  `segment.image_file.url` to access the raw file system path without URL encoding or signing.
- The import endpoint should wrap the entire project and segment creation in a database
  transaction using `transaction.atomic()` so that if any step fails (e.g., a file extraction
  error midway through), no partial Project or Segment records are left in the database.
- Name segment files inside the ZIP using zero-padded sequence indices (e.g., `segment_001`,
  `segment_042`) rather than the original filenames to make the archive human-readable and
  to avoid filename collisions when the original names contain spaces or special characters.
- Test the package format version check with both a missing version field and a version string
  that is not in the supported list to ensure the validation raises ValueError in both cases
  and that the message is descriptive enough for the frontend to surface it usefully.

---

## 7. Implementation Risks and Mitigations

- **Risk: Large projects producing ZIP files that exhaust server memory.** A project with
  forty high-resolution PNG images at 5 MB each and forty WAV audio files at 3 MB each could
  produce a ZIP that exceeds 300 MB in the BytesIO buffer before any compression is applied,
  and this may exceed the memory available on the host server or cause the Gunicorn worker
  handling the request to be terminated by the OS out-of-memory manager mid-response.
  Mitigation: for projects exceeding a configurable size threshold (e.g., 50 MB total media),
  dispatch the ZIP creation to a Celery task with a dedicated result URL and have the frontend
  poll for completion, so that large exports do not block a synchronous HTTP worker. For small
  projects under the threshold, the in-memory BytesIO approach remains acceptable and simpler.

- **Risk: Partial import leaving orphaned media files on disk.** If the import process extracts
  all media files to the new project's media directory successfully but then fails partway
  through creating Segment database records, those extracted files will remain on disk without
  any database references, consuming storage and making it impossible to clean them up through
  the normal storage management interface. Mitigation: wrap the entire import operation in a
  database transaction using transaction.atomic(), and add a rollback handler using a try/except
  block that calls shutil.rmtree on the newly created media directory if the transaction is
  rolled back, ensuring the database and filesystem stay in a consistent state after any failure.

- **Risk: Package schema changes breaking imports of older packages.** If a new required field
  is added to the Project model between StoryFlow versions, a package created with the older
  version will be missing that field and the extract_package function will fail when trying to
  create the Project record with incomplete data. Mitigation: implement a forward-compatibility
  shim in extract_package that inspects the manifest version and applies default values for any
  fields present in the current model but absent in the package's project.json, so that packages
  from older versions can still be imported with sensible defaults rather than an error that
  forces the user to manually edit the ZIP contents to repair the missing field.

- **Risk: Filename collisions in the ZIP archive for segments with duplicate source filenames.**
  If two segments share the same source image filename (possible when images are manually copied
  into the media directory without the application's naming scheme), the ZIP will contain
  duplicate path entries and Python's zipfile extractor will silently overwrite the earlier file
  with the later one during extraction, causing incorrect image-to-segment assignments.
  Mitigation: always use the zero-padded segment sequence index as the definitive filename
  inside the ZIP archive (e.g., images/segment_001.png, images/segment_042.png) rather than
  preserving original filenames, which guarantees uniqueness regardless of source naming.

- **Risk: Import creating an unusable project if source media files were already deleted.**
  If a project's image or audio files were deleted from disk before the export is triggered,
  build_package will encounter FileNotFoundError when reading those files, and either skip them
  silently or raise an unhandled exception depending on how the file read is implemented.
  Mitigation: wrap each file read in build_package in a try/except FileNotFoundError block,
  add the missing file's relative path to a missing_files list in manifest.json rather than
  aborting, and include a warning message in the export response so the frontend can alert the
  user that the package is incomplete before they share it with a collaborator.

---

## 8. Rollout and Phasing

### 8.1 Phase One — Build Package Function and Export Endpoint

The first phase delivers the package_utils.py module with the build_package function and the
POST /api/projects/{id}/export-package/ endpoint. Testing in this phase should be performed
entirely through direct HTTP requests using a REST client or curl, saving the response as a
.zip file and manually inspecting its contents to verify that manifest.json, project.json, all
image files, and all audio files are present with correct contents and relative path references.
The manifest version string and project.json schema must be explicitly defined and frozen in
this phase because they establish the contract that the import logic implemented in phase two
will depend on — any changes after phase two begins will require a backward-compatibility shim.

### 8.2 Phase Two — Extract Package Function, Import Endpoint, and Frontend

The second phase implements the extract_package function in package_utils.py, the
POST /api/projects/import-package/ endpoint, the Export Package button on the project detail
page, and the ImportPackageZone component on the project list page. The critical acceptance
test for this phase is a complete round-trip: export a known project, import the resulting ZIP
on the same or a different StoryFlow instance, navigate to the new project, and verify that
all segments have the correct text content, image prompts, and functional media file links.
The name collision handling (appending "(imported)" to duplicate names) and the transaction
rollback on failure must both be explicitly tested during this phase before the feature is
considered ready for phase three.

### 8.3 Phase Three — Async Large-Package Export and Format Specification

The third phase addresses the production-readiness concerns in the risk register: implement the
Celery-based asynchronous export path for large projects, add the streaming extraction approach
for large imports, and write a formal Package Format Specification document in the docs/
directory describing the exact JSON schemas for manifest.json and project.json, the required
directory structure inside the ZIP, and the version negotiation protocol for handling packages
from older StoryFlow installations. This specification document will serve as the foundation
for any future collaborative features built on top of the handoff package system, and publishing
it alongside the feature enables third-party tool developers to build compatible package
generators and importers without needing access to the StoryFlow source code.
