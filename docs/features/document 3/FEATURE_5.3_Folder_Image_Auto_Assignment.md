# Feature 5.3 — Folder Image Auto-Assignment

| Field | Value |
|---|---|
| Feature ID | 5.3 |
| Title | Folder Image Auto-Assignment (Index Order, Filename Match, AI CLIP) |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Medium (Modes A & B) / High (Mode C) |
| Estimated Effort | 5–8 days |
| Dependencies | Existing single-image upload endpoint per segment, `Segment` model with `image_file` and `image_prompt` fields, `model_loader.py` caching infrastructure (Mode C only), `transformers` Python library installable via pip (Mode C only) |
| Output Files (NEW) | `frontend/components/segments/BulkImageUploadModal.tsx`, `frontend/components/segments/AssignmentPreviewTable.tsx`, `backend/api/clip_views.py` |
| Files Modified | `backend/api/views.py`, `backend/api/urls.py`, `backend/core_engine/model_loader.py`, `frontend/app/projects/[id]/page.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow currently provides no mechanism to upload images to a project's segments in bulk: every segment requires the creator to navigate to its row in the project detail view, locate and click the upload control embedded in that row, open a native file picker, navigate their filesystem to find the correct image file, select it, and wait for the individual upload confirmation before repeating the entire process for the next segment, with no shortcut available for selecting multiple files across segments simultaneously.

A creator who generates fifteen images with Midjourney or Stable Diffusion for a fifteen-segment short-form video project must repeat this per-segment upload cycle fifteen times over, a process that takes between five and twelve minutes depending on filesystem navigation speed, and it is critically error-prone because the only visual cue connecting a script segment to the right image is the creator's memory of which generation prompt they used for each line of the script — a connection that breaks down rapidly when working with batches of similarly styled images.

The mismatch problem is compounded by the fact that there is currently no recovery workflow: if a creator realizes after uploading all fifteen images that two adjacent segments were accidentally swapped, the only remedy is to re-upload the correct file to each affected segment row individually, visiting each row, removing the wrong image, and uploading the correct replacement.

For creators working in a high-volume production mode — generating and uploading images for ten or more projects per day — this per-segment manual process becomes the single most time-consuming touchpoint in the entire StoryFlow pipeline, easily exceeding the time spent on scriptwriting, audio generation, and rendering combined.

The need for a bulk image assignment solution covering at minimum the simple index-order case (where image filenames already reflect their intended segment position) and ideally also an AI-assisted matching mode (for unstructured filename cases) has been identified as one of the top three workflow pain points in the StoryFlow ideas documentation and must be resolved to make the project detail workflow practical at any meaningful production scale.

### 1.2 Proposed Solution

Introduce a "Bulk Upload Images" modal accessible from the project detail page at `frontend/app/projects/[id]/page.tsx` that offers three clearly differentiated assignment modes selected via a radio control at the top of the modal. The three modes serve distinct creator workflows and skill levels, from the simplest possible interaction (sorted files assigned left-to-right) up to a sophisticated AI semantic matching mode that can assign structurally named or totally unnamed image files to their correct segments based on visual and textual similarity. All three modes share a unified preview step before any permanent change is written to the database, ensuring the creator retains full control to inspect and override individual assignments.

Key implementation aspects:

- A "Bulk Upload Images" floating modal built with the ShadCN `Dialog` component is triggered by a new button added to the project detail page toolbar. The modal header shows the project name and the current segment count so the creator immediately knows how many segments they need to fill. The modal presents a three-option radio group at the top with clearly labeled modes, a shared file input area below the radio group, and the preview table area below the file input. A step-by-step progress indicator inside the modal footer transitions from "Select Files" to "Preview Assignments" to "Uploading" as the user advances.

- Mode A (Index Order, the default selection) requires zero configuration from the user beyond selecting files. The creator selects multiple image files via a standard `input[type="file"][multiple][accept="image/*"]`. The frontend code calls `Array.from(fileList).sort((a, b) => a.name.localeCompare(b.name, undefined, {numeric: true, sensitivity: 'base'}))` to produce a stable alphanumeric sort, then pairs the sorted file at position zero with the segment having `sequence_index` of one, the file at position one with segment two, and so on. This is a pure frontend computation with no new backend endpoint; the sorted files are simply passed to `AssignmentPreviewTable` as the proposed assignment mapping.

- Mode B (Filename Matching) allows more flexible filename conventions. The creator uploads files named with leading or embedded integers such as `segment_1.jpg`, `segment_2.jpg`, or `1_hero.jpg`, `2_hero.jpg`. The frontend runs each filename through a JavaScript regex extraction function that pulls the first integer sequence from the filename string using the pattern `/(\d+)/` and casts the match to an integer. The extracted integer is then looked up against the segments array by matching on `sequence_index`. Files that produce no numeric match (filenames like `hero_landscape.jpg`) are not silently dropped but are instead collected into a visible "Unmatched Files" list below the preview table so the creator knows which files need manual assignment. Files whose extracted number does not correspond to any segment index (for example a file named `99.jpg` in a ten-segment project) are also listed as warnings.

- Mode C (AI CLIP Matching, marked as advanced) uses a CLIP vision-language model running in the backend to compute semantic similarity between the uploaded images and the text of each segment's `image_prompt` field, assigning each image to the segment whose prompt most closely describes its visual content. When Mode C is selected, a prominent notice is displayed inside the modal warning the creator to expect a processing delay of thirty to ninety seconds depending on the number of images and server hardware. The creator clicks "Run AI Analysis" which sends all image files as a multipart POST to `POST /api/projects/{id}/images/auto-assign-ai/`. The backend returns a JSON mapping with similarity scores before any database write occurs, allowing the creator to review and override AI decisions in the preview table.

- The preview table shown before confirmation is identical in structure across all three modes and is implemented as a standalone `AssignmentPreviewTable` component. The table has three columns: the first shows the segment sequence number and the first sixty characters of its `text_content` as a subtitle; the second shows the proposed assigned filename as text (or a "No match — unassigned" indicator in red if the slot is empty); the third shows a small inline thumbnail generated from `URL.createObjectURL(file)`. Every row contains a hidden file input element in the thumbnail cell that activates on click, enabling the creator to override the proposed assignment for any individual row without cancelling the entire modal session and starting over.

- For Modes A and B, the confirmation action iterates through the finalized `AssignmentEntry[]` array returned from the preview table and calls the existing single-segment image upload endpoint for each entry in sequence, using `await fetch()` calls chained so that each upload waits for the previous one to complete before sending the next. A `completedCount` state variable increments after each successful upload response and drives a linear ShadCN `Progress` bar in the modal footer, so the creator sees real progress through the upload sequence.

- For Mode C, the images were already sent to the backend during the AI analysis step. After the creator reviews and optionally adjusts the AI-proposed mapping in the preview table, clicking "Confirm" sends a follow-up request per segment using the same existing upload endpoint — either re-sending the files that were sent for analysis or confirming the AI mapping and triggering the backend to finalize the assignment. The backend `AutoAssignAIView` is stateless and returns only a suggested mapping, leaving all persistence to the standard upload endpoint.

### 1.3 Scope

| Category | Item |
|---|---|
| In Scope | Mode A — Index-order bulk assignment using alphanumeric filename sort, entirely frontend logic, no new backend endpoint |
| In Scope | Mode B — Filename-pattern matching using JavaScript regex extraction of leading integers, with unmatched file warnings displayed to the user |
| In Scope | Mode C — AI CLIP-based semantic matching via a new `POST /api/projects/{id}/images/auto-assign-ai/` endpoint returning a preview mapping before any database write |
| In Scope | Unified `AssignmentPreviewTable` component shared by all three modes: three-column layout with segment text, filename, thumbnail, per-row override file picker, Confirm/Cancel controls, and unmatched-file warning section |
| In Scope | Sequential upload with ShadCN Progress bar for Modes A and B; individual upload failure flagging with red error badge per row while remaining uploads continue |
| Out of Scope | Bulk image replacement across multiple projects simultaneously — the batch-level image assignment is a separate concern handled in Feature 5.1 |
| Out of Scope | Training, fine-tuning, or customizing the CLIP model on StoryFlow-specific data; the pre-trained `openai/clip-vit-base-patch32` checkpoint is used as-is |
| Out of Scope | Drag-and-drop reordering of assignment table rows; per-row file picker override is the supported manual correction path and is sufficient for the initial release |
| Out of Scope | Video file or animated GIF bulk assignment; only still image formats (JPEG, PNG, WebP) are in scope for this feature |
| Out of Scope | Bulk undo or redo after assignments are confirmed; the existing per-row single image re-upload on the project detail page is the supported correction path once confirmation has been submitted |

### 1.4 Key Files Reference

| File | Role in This Feature |
|---|---|
| `frontend/app/projects/[id]/page.tsx` | Add "Bulk Upload Images" button to the project toolbar that sets `bulkUploadOpen` state to true; render `BulkImageUploadModal` with `open`, `onOpenChange`, `segments`, and `projectId` props |
| `frontend/components/segments/BulkImageUploadModal.tsx` | Modal shell: ShadCN `Dialog` wrapper containing the mode radio group, shared file input, invocation of the correct mode-specific logic, and rendering of `AssignmentPreviewTable` with the computed mapping |
| `frontend/components/segments/AssignmentPreviewTable.tsx` | Preview component: three-column `Table` with segment index and text, proposed filename, and clickable thumbnail with per-row override file picker; Confirm/Cancel button pair; unmatched-file warning list below table |
| `backend/api/clip_views.py` | New file: `AutoAssignAIView` — loads CLIP via `model_loader.py`, accepts multipart image upload, embeds images and segment prompts, computes cosine similarity matrix, returns ranked mapping JSON without writing to database |
| `backend/core_engine/model_loader.py` | Add `get_clip_model()` function with module-level dict cache; add `embed_images()` and `embed_texts()` helper functions operating on PIL Image objects and string lists respectively |
| `backend/api/views.py` | Add a helper query or method used by `clip_views.py` to retrieve all segments for a given project ID ordered by `sequence_index`, returning their `id`, `sequence_index`, and `image_prompt` fields |
| `backend/api/urls.py` | Register `POST /api/projects/<int:pk>/images/auto-assign-ai/` pointing to `AutoAssignAIView.as_view()` |

---

## 2. Flow Diagram

    User on /projects/[id] clicks "Bulk Upload Images" button
                        |
                        v
            [BulkImageUploadModal opens]
            Header: "Bulk Upload Images — ProjectName (N segments)"
            Mode selector radio group:
              (A) Index Order — default, recommended
              (B) Filename Match
              (C) AI Semantic Match — slow, advanced
                        |
            ┌───────────┼──────────────────────┐
            v           v                      v
        [Mode A]    [Mode B]              [Mode C]
        User selects  User selects         User selects
        multiple     multiple files        multiple files
        files        with numeric          + clicks
                     filenames             "Run AI Analysis"
            |           |                      |
        Sort by     Extract integer        POST /api/projects/
        filename    via regex /(\d+)/      {id}/images/
        alphanumeric map to segment        auto-assign-ai/
                    by sequence_index           |
            |           |              Backend: load CLIP
            |           |              embed images + prompts
            |           |              cosine similarity matrix
            |           |              return mapping JSON
            |           |                      |
            |     Unmatched files         similarity scores
            |     → warning list         visible in preview
            |           |                      |
            └───────────┴──────────────────────┘
                        |
                        v
            [AssignmentPreviewTable renders]
            Column 1: Segment #  | text_content preview (60 chars)
            Column 2: Assigned filename  (or "No match" in red)
            Column 3: Thumbnail (URL.createObjectURL) — click to override
            Below table: Unmatched files warning list (Modes B & C)
                        |
                  [Confirm All] ← disabled if required rows have null file
                       OR
                    [Cancel] → modal closes, no uploads sent
                        |
                        v
            Sequential upload loop (Modes A & B):
            for each entry: POST to existing segment upload endpoint
            Progress bar: completedCount / totalCount × 100
            Failed rows → red error badge, loop continues
                        |
                        v
            Modal closes on success → project detail page
            React Query cache invalidated → thumbnails refresh

---

## 3. Step-by-Step Instructions

### Step 1 — Add CLIP Model Loader Functions

File: `backend/core_engine/model_loader.py`

Open the existing `model_loader.py` file and add a module-level dict at the top of the file named `_model_cache` initialized as an empty dictionary. Define a new function `get_clip_model(model_name="openai/clip-vit-base-patch32")` that first checks whether `model_name` exists as a key in `_model_cache`; if the key is present, return the cached tuple `(model, processor)` immediately to avoid reloading. If the key is absent, import `CLIPModel` and `CLIPProcessor` from `transformers`, call `CLIPProcessor.from_pretrained(model_name)` and `CLIPModel.from_pretrained(model_name)`, store both in `_model_cache[model_name]`, and return the tuple. Define companion functions `embed_texts(texts: list[str], model, processor)` that tokenizes the text list, runs the CLIP text encoder, normalizes the output embeddings using numpy, and returns a float32 numpy array of shape `(len(texts), embedding_dim)`; and `embed_images(pil_images: list, model, processor)` that processes a list of PIL Image objects through the CLIP image encoder, normalizes, and returns a matching numpy array. These helpers must contain no DRF or request-handling code.

### Step 2 — Create the AI Auto-Assign Backend View

Files: `backend/api/clip_views.py` (new), `backend/api/urls.py`

Create `backend/api/clip_views.py` and define `AutoAssignAIView` as a DRF `APIView` handling only POST requests. The view receives a multipart form body with image files under the key `images`. For each uploaded file, open it in memory as a PIL Image object using `PIL.Image.open(io.BytesIO(file.read()))` — do not write to disk. Fetch all segments for the project identified by the `pk` URL argument, ordered by `sequence_index`, and collect their `id`, `sequence_index`, and `image_prompt` text values into parallel lists (fall back to `text_content` for any segment where `image_prompt` is blank). Call `embed_images()` and `embed_texts()` from `model_loader.py`. Compute the cosine similarity matrix as the dot product of the two normalized arrays, producing a matrix of shape `(n_images, n_segments)`. For each image row, find the column index with the highest score. Build and return a JSON response: a list of objects each containing `image_index`, `original_filename`, `segment_id`, `segment_index`, and `similarity_score`. Do not perform any database writes in this view. Register the view in `backend/api/urls.py` under `projects/<int:pk>/images/auto-assign-ai/` using `.as_view()`.

### Step 3 — Build the Bulk Upload Modal Component

File: `frontend/components/segments/BulkImageUploadModal.tsx`

Create this component accepting props `open: boolean`, `onOpenChange: (open: boolean) => void`, `projectId: number`, and `segments: Segment[]`. Wrap the entire UI in a ShadCN `Dialog` controlled by the `open` and `onOpenChange` props. Inside `DialogContent`, render `DialogHeader` with the project name and segment count. Below the header, render a `RadioGroup` with three `RadioGroupItem` options labeled "Index Order (Recommended)", "Filename Match", and "AI Semantic Match (slow — may take 60s)". Below the radio group, render a file `input` with `multiple` and `accept="image/*"` attributes. When `onChange` fires on the input, branch by the selected mode: for Mode A, apply the alphanumeric sort and build an `AssignmentEntry[]`; for Mode B, run each filename through a regex extraction helper and match to segments by index, collecting unmatched files in a separate array; for Mode C, disable the preview render and instead show an "Analyze with AI" button that fires the CLIP endpoint POST. Store `entries: AssignmentEntry[]`, `unmatched: File[]`, and `step: 'select' | 'preview' | 'uploading'` in component state. Render `AssignmentPreviewTable` when `step === 'preview'`.

### Step 4 — Build the Assignment Preview Table Component

File: `frontend/components/segments/AssignmentPreviewTable.tsx`

Create a component accepting `entries: AssignmentEntry[]`, `segments: Segment[]`, `unmatched: File[]`, and `onConfirm: (finalEntries: AssignmentEntry[]) => void` as props. The `AssignmentEntry` type should be defined in a shared types file as `{ segmentId: number; segmentIndex: number; file: File | null; filename: string; similarityScore?: number; error?: string }`. Render a ShadCN `Table` with three columns: "Segment" (showing the sequence number as a badge and the first sixty characters of `text_content` as muted small text below), "File" (showing `entry.filename` or a red-colored "No match — unassigned" span when `file` is null, with the similarity score as muted text below for Mode C entries), and "Preview" (an `img` tag with `src={entry.file ? URL.createObjectURL(entry.file) : '/placeholder.png'}` constrained to 64×64 pixels, wrapped in a `label` that activates a hidden `input[type="file"][accept="image/*"]` on click so the creator can override the assignment for that row). Below the table, if `unmatched.length > 0`, render a yellow warning callout listing the unmatched filenames. The `DialogFooter` renders a "Confirm All" `Button` disabled when any segment with a `null` file is required, and a "Cancel" `Button` with `variant="ghost"`.

### Step 5 — Implement the Confirm Upload Handler

File: `frontend/components/segments/BulkImageUploadModal.tsx`

In the parent modal component, define the `handleConfirm` async function that is passed as the `onConfirm` prop to `AssignmentPreviewTable`. This function sets `step` to `'uploading'` and initializes a `completedCount` counter at zero. It then iterates through the confirmed `AssignmentEntry[]` in sequence using a standard for-of loop with `await` on each iteration. For each non-null entry, it constructs a `FormData` object with the file appended under the key `image`, then calls the existing segment image upload endpoint: `PATCH /api/projects/${projectId}/segments/${entry.segmentId}/` (or the equivalent endpoint for image update, matching whatever route already exists in `views.py`). On a successful response, it increments `completedCount` and updates a `progress` state variable to `(completedCount / totalCount) * 100`. On a non-2xx response, it marks that specific entry's `error` field in the entries state with the response status text and continues the loop without stopping. After the loop finishes, if all entries completed without error, call `onOpenChange(false)` to close the modal and invoke a passed-in `onRefresh` callback so the parent page re-fetches segment data.

### Step 6 — Wire the Modal into the Project Detail Page

File: `frontend/app/projects/[id]/page.tsx`

Open the project detail page and add a `bulkUploadOpen` boolean state variable initialized to `false`. Import `BulkImageUploadModal` from the components folder. In the project toolbar JSX area — which should already contain action buttons such as "Generate Audio" and "Render" — add a new button labeled "Bulk Upload Images" with an `Upload` icon from `lucide-react`. Set its `onClick` handler to `() => setBulkUploadOpen(true)`. Below the page's root container JSX, render `BulkImageUploadModal` with four props: `open={bulkUploadOpen}`, `onOpenChange={setBulkUploadOpen}`, `projectId={project.id}`, and `segments={segments}`. Pass an `onRefresh` prop that calls the existing function used to refetch segment data — either a React Query `refetch()` call or a manual `fetch` to reload the segments array and update state. Confirm the modal opens correctly by running the dev server and clicking the new button on a project detail page containing at least three segments.

---

## 4. Expected Outcome

1. A "Bulk Upload Images" button appears in the project detail page toolbar for every project and opens the modal without any console errors, broken layout, or TypeScript compile warnings in either development or production build mode.

2. Selecting five alphabetically sorted image files (named `01.jpg` through `05.jpg`) in Mode A produces a preview table where the thumbnail in row 1 corresponds to `01.jpg`, row 2 to `02.jpg`, and so on through row 5, with no files listed in the unmatched warnings section.

3. Selecting five image files with numeric filenames uploaded out of selection order (for example selecting `segment_3.jpg` before `segment_1.jpg`) in Mode B produces a preview table where each file appears in the row matching its extracted segment number regardless of the order in which the creator clicked the file picker selection, confirming that filename-based matching is order-independent.

4. Uploading three files named `hero.jpg`, `landscape.jpg`, and `portrait.jpg` in Mode B — where no integer can be extracted from any filename — results in all three files appearing in the unmatched warnings section below the preview table rather than being silently dropped or incorrectly assigned to segments.

5. Clicking any thumbnail cell in the preview table opens a native file picker; selecting a replacement file for that row updates the thumbnail and filename in that specific row without affecting any other row's assignment, confirming per-row override works correctly.

6. Clicking "Confirm All" on a five-entry preview table (Modes A or B) triggers five sequential upload calls and the progress bar in the modal footer advances smoothly from 0% to 100% as each upload completes, with the modal closing automatically after the final upload succeeds.

7. After confirmation and modal close, the project detail page's segment thumbnails refresh to show the newly uploaded images within one React Query cache invalidation cycle (or manual refetch), confirming the parent page's data is updated without a full browser reload.

8. In Mode C, posting a batch of five images to the CLIP endpoint returns a JSON array of five objects each containing a `similarity_score` value between 0.0 and 1.0, and the preview table renders these scores as muted text under each filename to help the creator identify low-confidence AI assignments before confirming.

9. If one upload fails during the confirmation sequence (simulated by temporarily returning a 500 error from the backend), that row's file cell turns red and displays the error status text while the remaining uploads continue and the progress bar advances past that row, confirming per-entry failure isolation works correctly.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] Mode A sort function: given a simulated FileList of five File objects with unsorted names `["03.jpg","01.jpg","05.jpg","02.jpg","04.jpg"]`, the function returns them in the order `01`, `02`, `03`, `04`, `05`
- [ ] Mode B regex extraction helper: given the input string `"segment_7_hero.jpg"` the function returns the integer `7`; given `"hero_landscape.jpg"` it returns `null`; given `"42.jpg"` it returns `42`
- [ ] `get_clip_model()` in `model_loader.py` returns the same object reference on a second call without calling `CLIPModel.from_pretrained` again, verified by mocking `from_pretrained` and asserting it is called exactly once across two `get_clip_model()` invocations
- [ ] `AutoAssignAIView` returns HTTP 400 when the POST body contains no files under the `images` key, with an error message indicating that at least one image is required
- [ ] `AutoAssignAIView` returns a JSON array whose length equals the number of images uploaded when called with two valid JPEG files for a project that has at least two segments with non-empty `image_prompt` values
- [ ] `AssignmentPreviewTable` renders a red "No match — unassigned" text in the File column for any entry whose `file` property is `null` rather than rendering an empty cell or crashing

### 5.2 Integration / Manual Tests

- [ ] Upload five sequentially named files via Mode A on a five-segment project; after clicking Confirm All, verify in the Django admin that all five segment `image_file` fields are non-null and correspond to the expected filenames in the correct order
- [ ] Upload five files with numeric filenames out of selection order via Mode B; confirm after Confirm All that each segment's `image_file` matches the file whose extracted number equals that segment's `sequence_index`, not the upload order
- [ ] Upload three files for a five-segment project via Mode A; confirm that the three matched segments are updated correctly and that the two unmatched segments still have their original `image_file` values (null or previously uploaded) without being overwritten
- [ ] Mode C: upload five image files to a project with five segments all having non-empty `image_prompt` text; confirm the endpoint responds in under ninety seconds with five mapping objects each containing a `similarity_score` between 0.0 and 1.0
- [ ] Override one preview table row's assignment by clicking the thumbnail and selecting a different file; click Confirm All; verify in the admin that the overridden segment received the replacement file rather than the originally proposed one
- [ ] Cancel the modal after the preview table has loaded (without clicking Confirm All); confirm no database changes occurred by verifying all segment `image_file` fields are unchanged from their pre-modal state in the Django admin
- [ ] Test the standard file input fallback by accessing the modal in Firefox (which does not support the File System Access API); verify the `input[type="file"][multiple]` element is visible and functional and that selecting files produces the expected Mode A preview table

### 5.3 Regression Tests

- [ ] The existing per-row individual image upload control on the project detail page still works correctly for a single segment after the new modal code is added; clicking the per-row upload, selecting one file, and confirming still updates only that one segment's `image_file` field without affecting any other segment
- [ ] Changes to `model_loader.py` for the new `get_clip_model` function and `_model_cache` dict do not interfere with any existing model-loading functions already defined in the file; the existing upscaler or TTS model loading (if present) still returns correct models after the CLIP cache dict is added
- [ ] Opening and immediately cancelling the `BulkImageUploadModal` three times in succession does not produce console errors about memory leaks or `URL.revokeObjectURL` failures, confirming that object URL cleanup in the component's unmount logic is executed correctly on each close

---

## 6. Notes for AI Agent

- Mode A and Mode B are entirely frontend logic until the confirmation step executes the upload loop. Do not create any new backend endpoint for these two modes; use the existing per-segment image upload endpoint (whatever route `views.py` already exposes for updating a segment's `image_file` field) called in a sequential loop from the frontend. Adding new backend endpoints only for sorting or pattern matching would introduce unnecessary complexity and a maintenance burden without any functional benefit.

- In the Mode B regex extraction helper, use `/(\d+)/` and always take only the first regex match result. Document in a JSDoc comment that the function matches the first integer sequence found in the filename from left to right, so future maintainers understand the priority order: `"15_image.jpg"` maps to segment 15, `"frame_3_scene.jpg"` maps to segment 3, and `"image_3_backup_2.jpg"` maps to segment 3 (not segment 2). Include a suite of example assertions in the unit test file to lock in this behavior as a contract.

- The CLIP model checkpoint `openai/clip-vit-base-patch32` is approximately 600 MB on disk. Do not trigger a download of this model at Django startup time or on the first web request. Instead, add a dedicated Django management command named `download_clip_model` so that production deployments can pre-fetch the model during the container build or deployment setup step. The `get_clip_model()` function should assume the model is already available locally and raise a clear `FileNotFoundError` with a helpful message directing the operator to run the management command if the model files are absent.

- In `AssignmentPreviewTable`, call `URL.createObjectURL(file)` for each entry when the component first renders the preview, and store the created URLs in a local ref. In the component's cleanup (either via `useEffect` cleanup or `onDestroy` equivalent), call `URL.revokeObjectURL` for every stored URL to release the browser's memory reference to the file data. Failing to revoke object URLs when the modal closes will cause memory to accumulate across modal open-close cycles, which is noticeable when the creator opens the modal many times during a session with large high-resolution image files.

- The `AutoAssignAIView` endpoint must be stateless: it receives images, computes embeddings, returns a mapping, and exits without touching the database. Only the subsequent per-segment upload calls — the same calls used by Modes A and B — should write `image_file` values to the database. Keeping the AI endpoint read-only means it can be called multiple times with different file sets (as the creator experiments with different image batches) without producing orphaned or incorrect database state between the analysis call and the eventual confirmation.

- When the sequential upload loop in `handleConfirm` encounters a failed upload for one entry, set that entry's `error` field in local state and render a red error icon in its table row, but do not call `break` or throw an exception — the loop must continue with `continue` to process the remaining entries. After the loop finishes, if `errorCount > 0`, keep the modal open and show a summary message such as "3 of 5 uploads succeeded. Please retry the failed rows." rather than closing the modal, so the creator can address failures without losing the confirmed entries that already succeeded.
