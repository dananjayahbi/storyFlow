# Feature 1.6 — Image Style Consistency

| Field | Value |
|---|---|
| Feature ID | 1.6 |
| Title | Image Style Consistency |
| Status | Planned |
| Priority | High |
| Complexity | Low |
| Estimated Effort | 1 day(s) |
| Dependencies | Image generation flow must be operational |
| Dependencies (cont.) | Project model migration system must be working |
| Dependencies (cont.) | DRF serializers must be tested and stable |
| Output Files (NEW) | None |
| Files Modified | backend/api/models.py |
| Files Modified (cont.) | backend/api/serializers.py |
| Files Modified (cont.) | backend/api/views.py |
| Files Modified (cont.) | backend/core_engine/render_utils.py |
| Files Modified (cont.) | frontend/app/projects/[id]/page.tsx |

---

## 1. Document Overview

### 1.1 Problem Statement

In the current StoryFlow implementation, every segment's image_prompt field is authored
and stored in complete isolation, with no shared visual context linking any one segment's
generated image to those produced by neighboring segments in the same project.

This means a project can output a photorealistic first segment, a cartoon-style second
segment, and a watercolor third segment all within a single video, making the final result
look visually incoherent and unprofessional regardless of how strong the script narrative is.

There is no project-level concept of a "visual style" that is propagated uniformly into the
image generation pipeline, leaving creators solely responsible for manually typing the same
lengthy style suffix — such as "photorealistic, cinematic lighting, 4K" — into every single
segment prompt, which is both time-consuming and error-prone at scale.

For creators producing twenty or more segments per project, even a single forgotten style
descriptor immediately breaks visual continuity in the final video, destroying the consistent
aesthetic that makes AI-generated video content look professionally produced.

### 1.2 Proposed Solution

Introduce a single project-level image_style field on the Project model that stores a visual
style descriptor string, such as "photorealistic, cinematic lighting, 4K" or "anime style,
detailed, high quality". This string is automatically appended to every segment's image_prompt
at image generation time inside a centralized backend helper function, so all generated images
share a consistent aesthetic without requiring the creator to repeat anything manually.
The frontend exposes this field through a dropdown offering eight curated preset style strings
plus a "Custom" option that reveals a free-text input for bespoke style descriptors.
A live style preview indicator shows the creator exactly what suffix will be appended before
any generation is triggered, and a change-notification banner appears if the style is updated
after images have already been generated so the creator knows to re-run generation.

- Add image_style as a CharField on the Project model with max_length=200, blank=True,
  and default='' so the field is optional and the migration is non-destructive to existing data.
  An empty string value triggers no appending behavior in the prompt builder function.

- Expose image_style in ProjectSerializer as both a readable and writable field
  by adding it to the Meta.fields list, enabling the existing GET, PATCH, and PUT project
  endpoints to handle the new field without requiring any new URL routes or ViewSet methods.

- Present a styled dropdown in the project settings panel on frontend/app/projects/[id]/page.tsx
  containing a blank "None" option, eight preset style strings, and a "Custom..." option
  that dynamically reveals a text input field directly beneath the dropdown when selected.

- Bind the dropdown's current value to the local project state using the same state management
  pattern already established for other project settings fields on the page, then persist the
  value via a PATCH /api/projects/{id}/ request on blur or on a "Save Settings" button click.

- Create a function named build_effective_prompt in backend/core_engine/render_utils.py that
  accepts a base_prompt string and a style_suffix string, returns the concatenated prompt if
  style_suffix is non-empty after stripping whitespace, and returns base_prompt unchanged
  if style_suffix is empty, making this the single authoritative location for prompt logic.

- Render a "Style Preview" line directly beneath the dropdown or custom text input in the
  frontend settings panel, displaying bold italic text such as "Prompt will include:
  photorealistic, cinematic lighting, 4K" so the creator can confirm the exact suffix
  before triggering any generation action.

- Track a styleChangedAfterGeneration boolean in local React state that is set to true
  whenever image_style is updated and at least one segment already has a generated image_file
  attached, and render a dismissible yellow banner reading "Image style changed — regenerate
  segment images to apply the new style" so creators are never left with a silent style mismatch.

### 1.3 Scope

| Category | Item |
|---|---|
| In Scope | Adding the image_style CharField to the Project model and generating and applying its Django migration |
| In Scope | Exposing image_style in ProjectSerializer for both read and write operations |
| In Scope | Building the preset dropdown and custom text input for image_style in the project settings panel |
| In Scope | Creating the build_effective_prompt helper and updating all prompt construction callsites |
| Out of Scope | Per-segment style overrides that allow individual segments to differ from the project-level style |
| Out of Scope | Automatic background re-generation of existing segment images when image_style is changed |
| Out of Scope | Storing or displaying a versioned history of previously saved image_style values per project |
| Out of Scope | AI-assisted suggestion of a style descriptor based on analysis of script content or images |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| backend/api/models.py | Defines the Project model class and all database-backed fields | Contains name, render_settings JSONField, updated_at; no image_style field exists |
| backend/api/serializers.py | DRF ModelSerializer controlling which Project fields are readable and writable | Serializes all existing Project fields; image_style not yet declared in Meta.fields |
| backend/api/views.py | DRF ViewSet handling all CRUD operations for the Project resource | ProjectViewSet has standard actions; no prompt-building helpers present anywhere |
| backend/core_engine/render_utils.py | Shared rendering and processing utility functions used across the engine | Contains rendering helpers; no build_effective_prompt function exists yet |
| frontend/app/projects/[id]/page.tsx | Main per-project editor page rendered for a given project ID | Shows segment list and project info; no image style control or preview indicator present |

---

## 2. Flow Diagram

```
Creator opens the project editor page
            |
            v
Project record loaded via GET /api/projects/{id}/
  project.image_style = "" or "some style string"
            |
            v
Project settings panel renders with "Visual Style" control
  Dropdown options: None / 8 presets / Custom...
            |
            v
Creator selects a preset option from the dropdown
            |
            v
Style Preview line updates immediately in real time
  Italic text: Prompt will include: [selected style string]
            |
            v
Creator saves the selection (blur or Save button)
            |
            v
PATCH /api/projects/{id}/ with { image_style: "selected value" }
            |
            v
Backend validates and stores image_style to the database
            |
            v
Was at least one segment image already generated?
      YES   |                    NO
            v                     v
styleChangedAfterGeneration    Await generation event
= true --> yellow banner         no banner shown yet
appears at top of segment list
            |
            v
Creator triggers image generation for a segment
            |
            v
Backend calls build_effective_prompt(
  segment.image_prompt,
  project.image_style
)
            |
            v
If image_style is non-empty after stripping:
  final_prompt = base_prompt + ", " + image_style
Else:
  final_prompt = base_prompt (returned unchanged)
            |
            v
Image generator receives the style-augmented prompt
```

---

## 3. Step-by-Step Instructions

### Step 1 — Add image_style to the Project Model

1. Open backend/api/models.py and locate the Project class definition near the top of the
   models file, above any Segment or related model definitions in the same file.

2. After the existing render_settings JSONField declaration, insert the new field image_style
   defined as a CharField with max_length=200, blank=True, and default='', placing it in the
   logical group of project-level configuration fields for readability.

3. The blank=True setting ensures both the Django admin interface and the DRF serializer
   accept an empty string as a valid value for projects where no visual style has been set,
   without triggering a validation error on any existing or new project record.

4. Run python manage.py makemigrations from the backend/ directory to generate a new
   migration file in backend/api/migrations/ that adds the image_style column to the
   api_project database table with an empty string as the column default value.

5. Run python manage.py migrate to apply the migration and confirm the command exits with
   no errors; then open the database via the Django shell and verify that all existing
   project rows have an empty string as their image_style value after migration completes.

### Step 2 — Expose image_style in the ProjectSerializer

1. Open backend/api/serializers.py and locate the ProjectSerializer class along with its
   inner Meta nested class that declares the serializer configuration for the Project model.

2. Find the fields declaration inside Meta — whether it is a list, a tuple, or the
   string '__all__' — and add the string 'image_style' to it so the field participates
   in both serialized API output and deserialized API input for all HTTP verbs.

3. No custom SerializerMethodField declaration or validate_image_style validation method
   is required, since Django's CharField with blank=True already communicates to DRF
   that empty strings are valid write values and should not raise a ValidationError.

4. Test serialization by sending a GET /api/projects/{id}/ request and confirming that
   the response JSON includes "image_style" as a key with either an empty string or the
   previously saved style value for that project record.

5. Test deserialization by sending a PATCH /api/projects/{id}/ request with the body
   containing image_style set to "photorealistic, cinematic lighting, 4K" and confirming
   the response reflects the saved value; then repeat with an empty string to confirm
   that blank values are also accepted without producing a 400 validation error response.

### Step 3 — Build the Centralized Prompt Helper in the Backend

1. Open backend/core_engine/render_utils.py and add a new standalone function named
   build_effective_prompt in a logical location within the file, such as immediately after
   any existing import declarations and before the first existing utility function body.

2. Define the function to accept exactly two string parameters: base_prompt representing
   the segment's own authored image_prompt value, and style_suffix representing the
   project's image_style field which may be an empty string or whitespace-only string.

3. In the function body, strip leading and trailing whitespace from style_suffix; if the
   stripped result is a non-empty string, return the concatenation of base_prompt, the
   literal two-character separator ", ", and the stripped suffix value.

4. If the stripped style_suffix is empty or was already an empty string before stripping,
   return base_prompt exactly as received so no trailing comma, space, or other artifact
   is appended to the raw prompt that gets sent to the generating model.

5. Search the entire backend/ directory for every location where segment.image_prompt is
   passed as input to an image generation call, Celery task, or API handler, and update
   each callsite to instead call build_effective_prompt(segment.image_prompt, project.image_style)
   so the centralized logic is the only prompt-building path in the entire codebase.

### Step 4 — Add the Visual Style Control to the Project Settings UI

1. Open frontend/app/projects/[id]/page.tsx and find the project settings panel section,
   the JSX region containing labeled inputs for project-level fields such as the project
   name and any existing render configuration options already displayed.

2. Add a new labeled form group with the visible label text "Visual Style" containing a
   select HTML element whose value is bound to project.image_style in the component's
   local state and whose onChange handler updates that state variable immediately.

3. Populate the select element with nine option elements in this order: a blank option
   with value "" and label "None (no style suffix)", then the seven curated presets —
   "photorealistic, cinematic lighting, 4K", "digital art, vibrant colors, fantasy",
   "minimalist, clean, modern illustration", "anime style, detailed, high quality",
   "vintage film photography", "watercolor illustration, soft pastels",
   "dark neon cyberpunk aesthetic" — and finally a special option with label "Custom...".

4. Introduce a local boolean state variable isCustomStyle that is true when the current
   project.image_style value does not exactly match any of the seven presets and is not
   an empty string; when isCustomStyle is true, render a plain text input below the
   select that is bound to project.image_style for free-form user entry.

5. Below the dropdown or the visible custom input, render a small paragraph element with
   italic bold styling showing "Prompt will include: [current image_style]" when
   image_style is non-empty, and hide this paragraph entirely via a conditional render
   when image_style is empty to avoid a confusing empty-quoted preview line.

### Step 5 — Wire the Save Action and the Change-Notification Banner

1. In frontend/app/projects/[id]/page.tsx, connect the style control's save action to the
   existing API utility function used elsewhere on the page for PATCH requests, dispatching
   PATCH /api/projects/{id}/ with image_style as the payload body, matching the save
   pattern already established for other project fields on this page.

2. Add a local boolean state variable named styleChangedAfterGeneration to the component,
   initialized to false on mount; set it to true inside the image_style change handler only
   when at least one entry in the current segment list has a truthy image_file value,
   indicating that at least one image has already been produced for this project.

3. In the JSX body, conditionally render a div styled as a yellow informational banner,
   positioned above the segment list and below the settings panel, containing the text
   "Image style changed — regenerate segment images to apply the new style" along with
   a small dismiss button element labeled with an X character.

4. Wire the dismiss button's onClick handler to call the state setter with false, collapsing
   the banner and preventing it from reappearing until the next image_style change event
   occurs within the same browser session without requiring any page reload.

5. Perform a full manual round-trip test: select a style preset, confirm the preview line
   updates, save and verify the PATCH request appears in the browser network tab, generate
   one segment image, then change the style and confirm the yellow banner appears — then
   dismiss the banner and verify it disappears and stays gone.

---

## 4. Expected Outcome

1. The api_project database table gains a new image_style text column that holds an empty
   string by default on all new projects, and all existing project rows in the database
   receive this empty-string default automatically through the migration with zero data loss.

2. The GET /api/projects/{id}/ endpoint response JSON includes the "image_style" key with
   its current value for every project, and PATCH /api/projects/{id}/ correctly persists any
   valid style string including an empty string without producing a validation error response.

3. The project settings panel on the frontend displays a clearly labeled "Visual Style"
   dropdown offering eight curated presets and a "Custom" free-text entry, giving creators
   a fast and ergonomic way to set a consistent visual aesthetic for all images in a single
   interaction rather than duplicating the style string across every individual segment prompt.

4. The live style preview indicator beneath the dropdown updates in real time as the creator
   changes the selection or types in the custom field, showing the exact suffix string that
   will be appended to every image prompt so there is no ambiguity about what the model sees.

5. Every segment image generated after a non-empty image_style is saved will use the
   build_effective_prompt-augmented prompt, resulting in visually consistent aesthetic output
   across all segments that share the same project-level style descriptor string.

6. When image_style is changed on a project that already has at least one generated segment
   image, the yellow change-notification banner appears immediately in the editor without
   a page reload, ensuring the creator is never left with a silent style mismatch between
   old-style and new-style images within the same project timeline.

7. The build_effective_prompt function in backend/core_engine/render_utils.py is the single
   authoritative source of prompt augmentation logic in the entire codebase, meaning that
   future changes to how style strings are concatenated require editing exactly one function
   in one file rather than a multi-location search-and-replace operation across the project.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] Test that build_effective_prompt called with an empty string as style_suffix returns
  the base_prompt string completely unchanged without any trailing comma, space, or other
  artifact appended to it, verifying the empty-string guard works correctly.

- [ ] Test that build_effective_prompt called with "photorealistic, 4K" as style_suffix
  returns the base_prompt followed by ", " followed by the suffix with the separator
  inserted correctly and the suffix value appearing without duplication.

- [ ] Test that build_effective_prompt called with a style_suffix that contains leading and
  trailing whitespace strips that whitespace before appending, producing a clean result
  without leading or trailing spaces in the appended style portion.

- [ ] Test that ProjectSerializer includes and correctly round-trips the image_style field
  in serialized JSON output and that it accepts an empty string as a valid deserialized
  write value without raising a DRF ValidationError for blank content.

- [ ] Test that a freshly instantiated Project() object before any save operation has
  image_style equal to an empty string, confirming that the default='' argument on the
  model field is applied correctly at the Python object level before any database write.

### 5.2 Integration / Manual Tests

- [ ] Create a new project via POST /api/projects/ without including image_style in the
  request body, then verify the response JSON contains "image_style": "" as the field
  default applied automatically by the model layer.

- [ ] Send PATCH /api/projects/{id}/ with image_style set to "vintage film photography"
  and then verify the subsequent GET /api/projects/{id}/ response reflects the correctly
  saved value, confirming the full write-then-read round trip works end-to-end.

- [ ] Open a project in the browser, select the "anime style, detailed, high quality"
  preset from the Visual Style dropdown, and confirm the style preview paragraph appears
  beneath the dropdown showing the correct suffix text immediately without a page save.

- [ ] Select the "Custom..." dropdown option, type a custom style string in the revealed
  text input, trigger a save via the blur event, then refresh the page and confirm the
  custom style text re-populates correctly from the backend-stored value.

- [ ] Trigger image generation for a segment on a project where image_style is set to
  a non-empty value, then inspect the prompt passed to the generator and confirm the
  style suffix appears at the end of the prompt following the ", " separator.

- [ ] Change the image_style on a project that already has at least one segment with a
  non-null image_file value and confirm the yellow "Image style changed" banner appears
  without a page reload and contains the expected instructional message text.

### 5.3 Regression Tests

- [ ] Confirm that all projects where image_style is an empty string generate segment
  images using only the segment's own raw image_prompt with no trailing comma, no trailing
  whitespace, and no other artifacts appended to the prompt string passed to the generator.

- [ ] Confirm that the complete suite of existing project API endpoint tests for GET, POST,
  PATCH, and DELETE on /api/projects/ continue to pass after the image_style migration
  is applied, verifying no regressions in the existing API surface.

- [ ] Confirm that the project editor page loads in the browser without JavaScript console
  errors for all existing projects, verifying that the new image_style state variable
  initializes cleanly when the API returns the default empty string for older records.

---

## 6. Notes for AI Agent

- The image_style field on the Project model must use default='' and must NOT include
  null=True or default=None, because storing an empty string as the no-style sentinel
  allows build_effective_prompt to use a simple truthiness check after stripping whitespace
  without needing to handle None as a separate code branch anywhere in the pipeline.

- The build_effective_prompt function must be imported and called at every callsite in the
  backend where image prompts are constructed and forwarded for generation; run a global
  search for the string "image_prompt" within the backend/ directory tree to locate all
  relevant locations, and update each one without skipping any to avoid inconsistency.

- On the frontend, do not convert the dropdown's empty-string value to null or undefined
  before including it in the PATCH request body, because the backend CharField with blank=True
  correctly stores and retrieves empty strings and converting to null would require adding
  null=True to the model field which would complicate the backend prompt logic unnecessarily.

- The styleChangedAfterGeneration boolean is a pure local React state concern and does not
  need any corresponding backend field, database column, or API flag; it is initialized to
  false on every fresh page load and only ever set to true by user interaction within
  the current browser session, which is the correct behavior for an in-session nudge.

- When implementing the detection logic for whether to show the yellow style-change banner,
  use a check like segments.some(s => Boolean(s.image_file)) rather than simply checking
  segments.length > 0, because a project can have many segments with no generated images
  yet and showing the banner in that case would be confusing and unhelpful to the creator.
