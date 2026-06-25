# Feature 6.2 — Segment Count Guidance

| Field | Value |
|---|---|
| Feature ID | 6.2 |
| Title | Segment Count Guidance |
| Status | Planned |
| Priority | Medium |
| Complexity | Low |
| Estimated Effort | 1 day(s) |
| Dependencies | Project model migration system must be working |
| Dependencies (cont.) | Frontend project page must expose a live segment list with a count |
| Dependencies (cont.) | Existing PATCH project endpoint must be tested and stable |
| Output Files (NEW) | frontend/components/SegmentCountGuide.tsx |
| Output Files (NEW) (cont.) | frontend/constants/platformRecommendations.ts |
| Files Modified | backend/api/models.py |
| Files Modified (cont.) | backend/api/serializers.py |
| Files Modified (cont.) | frontend/app/projects/[id]/page.tsx |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow currently provides absolutely no structural guidance to creators about how many
segments their project should contain for the specific platform they are targeting, leaving
every structural decision entirely to guesswork at the start of each new project.

A creator building a sixty-second TikTok video has fundamentally different pacing requirements
than one building a twenty-minute long-form YouTube documentary, yet the StoryFlow project
editor treats both creators identically with no contextual information about what a
well-structured project looks like for their intended distribution channel.

Without any segment count recommendation system, creators regularly either over-segment their
content — producing videos that cut so rapidly they feel frantic and unwatchable — or
under-segment it, generating long static shots with minimal visual variation that causes
audiences to disengage on short-form platforms where pacing expectations are especially high.

This gap is most costly at the beginning of a project when restructuring is effortless, since
a creator who only discovers their segment count is dramatically wrong after recording all their
voiceovers must re-cut and re-time the entire project from scratch, wasting significant
production effort that a simple visible recommendation could have prevented entirely.

### 1.2 Proposed Solution

Add a project-level target_platform field with five predefined platform choices and drive a
visible, always-present guidance card in the project editor that compares the live segment count
to curated platform-specific recommendations stored in a typed frontend constants file.
The guidance card displays a colored status badge — green for on target, yellow for too few,
and red for too many — that updates in real time as segments are added or removed, giving
creators immediate feedback at every stage of the editing workflow.
All recommendation data lives entirely on the frontend in a typed constants file, so the entire
feature is zero-latency and requires no new API endpoints beyond the existing project PATCH
route used to save the platform selection itself.

- Add a target_platform CharField to the Project model with a PLATFORM_CHOICES list of five
  entries and a default of "youtube", so the field is immediately useful for all new projects
  without requiring creators to actively select a platform at project creation time.

- Expose target_platform in ProjectSerializer as both a readable and writable field by adding
  it to Meta.fields, enabling the frontend to display and update the platform through the same
  PATCH /api/projects/{id}/ endpoint already used for other project-level fields.

- Add a "Target Platform" dropdown to the project settings panel in the project page with
  the five human-readable platform choices, wired to dispatch a PATCH save request immediately
  on selection change since choosing from five named options is an explicit deliberate action.

- Create frontend/constants/platformRecommendations.ts as a new typed constants file that maps
  each platform key string to an object containing minSegments, maxSegments, targetDurationSeconds,
  and a description sentence, keeping all recommendation data co-located in one self-contained
  file so updating ranges requires changing a single file with no backend involvement.

- Create frontend/components/SegmentCountGuide.tsx as a new presentational component that
  accepts platform and segmentCount as props, looks up the recommendation from the constants
  file, computes whether the count is within range, and renders a card with the recommended
  range, current count, and a color-coded status badge element.

- Place the SegmentCountGuide component unconditionally in the project header area above the
  segment list so it is visible without any scrolling whenever a project is opened, ensuring
  creators see the structural guidance immediately rather than having to open a settings panel.

- Attach a title tooltip to the status badge containing the platform's description sentence
  from the constants file, so creators who see an unexpected badge color can hover the badge
  to read a brief human-readable explanation of why that segment range is recommended.

### 1.3 Scope

| Category | Item |
|---|---|
| In Scope | Adding target_platform CharField with PLATFORM_CHOICES to the Project model and running its migration |
| In Scope | Creating frontend/constants/platformRecommendations.ts with recommendation data for all five platforms |
| In Scope | Creating frontend/components/SegmentCountGuide.tsx with green/yellow/red status badge evaluation logic |
| In Scope | Adding the "Target Platform" dropdown to the project settings panel wired to the PATCH endpoint |
| Out of Scope | Automatically splitting, merging, or reordering segments to hit the recommended count range |
| Out of Scope | User-defined custom platform entries with arbitrary min/max segment ranges they define themselves |
| Out of Scope | Backend validation that rejects project saves when segment count falls outside the recommended range |
| Out of Scope | Per-segment duration tracking or automatic calculation of total estimated video runtime |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| backend/api/models.py | Defines the Project model and all database-backed fields | Has name, render_settings, updated_at; no target_platform field or PLATFORM_CHOICES list exists |
| backend/api/serializers.py | DRF serializer controlling which Project fields are exposed via the API | Serializes all existing Project fields; target_platform not yet in Meta.fields |
| frontend/app/projects/[id]/page.tsx | Per-project editor page rendered for a given project ID route | Shows segment list and project details; no platform dropdown or guidance card present |
| frontend/components/SegmentCountGuide.tsx | New presentational guidance card component with colored status badge | File does not exist; must be created as the primary UI deliverable of this feature |
| frontend/constants/platformRecommendations.ts | New typed constants file with platform recommendation data | File does not exist; must be created as the sole data source for all recommendation ranges |

---

## 2. Flow Diagram

```
Creator opens the project editor page
            |
            v
Project data loaded via GET /api/projects/{id}/
  project.target_platform = "tiktok" (or any of 5 values)
            |
            v
Segment list loaded from project state
  segments.length = N (current segment count)
            |
            v
SegmentCountGuide component mounts in project header area
            |
            v
Import PLATFORM_RECOMMENDATIONS from constants file
  Look up entry for "tiktok":
  { minSegments: 4, maxSegments: 6,
    targetDurationSeconds: 60,
    description: "TikTok under 60s..." }
            |
            v
Evaluate: is N within the range [minSegments, maxSegments]?
      _____|___________
     |        |         |
     v        v         v
  N < 4    4<=N<=6   N > 6
  too few  on target  too many
     |        |         |
     v        v         v
  Yellow    Green      Red
  badge     badge      badge
  "Too    "On target  "Too many
  few ⚠"     ✓"      segments ⚠"
     |        |         |
     v        v         v
title tooltip text set to description string:
  "TikTok under 60s performs best with
   4-6 segments of 10-15 seconds each."
            |
            v
Creator changes platform in the settings dropdown
            |
            v
Optimistic local state update applied immediately
            |
            v
PATCH /api/projects/{id}/ with new target_platform value
            |
            v
SegmentCountGuide re-evaluates against new platform data
  New range: minSegments=40, maxSegments=60 for youtube_long
            |
            v
Badge color and text update without any page reload
```

---

## 3. Step-by-Step Instructions

### Step 1 — Add target_platform to the Project Model

1. Open backend/api/models.py and locate the Project class definition; add a class-level
   list named PLATFORM_CHOICES before the field declarations containing five two-tuples:
   ("youtube", "YouTube"), ("tiktok", "TikTok"), ("instagram_reel", "Instagram Reel"),
   ("youtube_shorts", "YouTube Shorts"), and ("youtube_long", "YouTube (Long-Form)").

2. After the existing field declarations, add target_platform as a CharField with
   max_length=30, choices=PLATFORM_CHOICES, default="youtube", and blank=False, since
   a platform selection should always be present and "youtube" is a meaningful universal
   default that applies to the majority of video content creators using the platform.

3. The choices constraint ensures Django's built-in model validation and DRF's serializer
   validation will both reject any string that is not one of the five allowed keys,
   providing data integrity without requiring any custom field validator function.

4. Run python manage.py makemigrations from the backend/ directory to generate a new
   migration file in backend/api/migrations/ that adds the target_platform column to the
   api_project table with a database-level default value of "youtube" for all rows.

5. Run python manage.py migrate to apply the migration; then verify in the Django shell
   that Project.objects.first().target_platform returns "youtube" for an existing project
   and that Project.objects.create(name='test').target_platform also returns "youtube".

### Step 2 — Expose target_platform in the ProjectSerializer

1. Open backend/api/serializers.py and find the ProjectSerializer class and its inner
   Meta class containing the fields declaration that controls API serialization behavior.

2. Add the string 'target_platform' to the fields sequence so the field is included in
   all serialized API responses and accepted in all deserializable request bodies for
   both POST creation requests and PATCH update requests.

3. No custom field type or SerializerMethodField is needed because DRF's default CharField
   serializer behavior handles the choices validation automatically, so submitting a value
   like "twitch" that is not in PLATFORM_CHOICES will produce a clean 400 validation error.

4. Issue a test GET /api/projects/{id}/ request and confirm that "target_platform" appears
   in the JSON response body with the correct current value, likely "youtube" for all
   existing projects that received the migration default.

5. Issue a test PATCH /api/projects/{id}/ request with target_platform set to "tiktok"
   and confirm the response reflects the updated value; then issue a follow-up PATCH with
   an invalid key and confirm the response is a 400 error with a descriptive validation message.

### Step 3 — Create the Platform Recommendations Constants File

1. Create the new file frontend/constants/platformRecommendations.ts and begin by defining
   a TypeScript interface named PlatformRecommendation with four typed properties:
   minSegments as number, maxSegments as number, targetDurationSeconds as number,
   and description as string.

2. Define and export a constant object named PLATFORM_RECOMMENDATIONS typed as
   Record<string, PlatformRecommendation> with five keys matching the backend's
   PLATFORM_CHOICES internal value strings exactly: "youtube", "tiktok", "instagram_reel",
   "youtube_shorts", and "youtube_long".

3. Populate the five entries with their respective data objects:
   "youtube" gets minSegments: 20, maxSegments: 30, targetDurationSeconds: 600,
   description: "YouTube standard videos of around 10 minutes perform best with 20 to 30
   segments of roughly 20 seconds each for consistent viewer pacing throughout.";
   "tiktok" gets minSegments: 4, maxSegments: 6, targetDurationSeconds: 60,
   description: "TikTok under 60 seconds performs best with 4 to 6 focused segments of
   10 to 15 seconds each to maintain high viewer attention through the full clip."

4. Continue populating: "instagram_reel" gets minSegments: 3, maxSegments: 4,
   targetDurationSeconds: 30, description: "Instagram Reels of 30 seconds work best with
   3 to 4 tight segments of 8 to 10 seconds each for high-energy visual impact on the feed.";
   "youtube_shorts" gets minSegments: 4, maxSegments: 6, targetDurationSeconds: 60,
   description: "YouTube Shorts under 60 seconds perform well with 4 to 6 segments that
   move quickly and keep the viewer engaged from the very first frame to the last."

5. Add the final entry: "youtube_long" gets minSegments: 40, maxSegments: 60,
   targetDurationSeconds: 1200, description: "Long-form YouTube videos of around 20 minutes
   achieve comfortable narrative pacing with 40 to 60 segments that allow depth without
   dragging."; also export a PLATFORM_DISPLAY_NAMES Record<string, string> constant that
   maps all five keys to their human-readable display name strings for use in the component.

### Step 4 — Create the SegmentCountGuide Component

1. Create the new file frontend/components/SegmentCountGuide.tsx and define a TypeScript
   interface named SegmentCountGuideProps with two required properties: platform as a string
   (the current project's target_platform value) and segmentCount as a number (the current
   length of the project's segment array in the local component state).

2. Inside the component function, import both PLATFORM_RECOMMENDATIONS and
   PLATFORM_DISPLAY_NAMES from the constants file, then resolve the recommendation by
   looking up PLATFORM_RECOMMENDATIONS[platform] and falling back to
   PLATFORM_RECOMMENDATIONS["youtube"] if the key is not found in the object.

3. Compute a local status variable by comparing segmentCount to the resolved minSegments
   and maxSegments values: assign "few" if segmentCount is less than minSegments, assign
   "many" if segmentCount is greater than maxSegments, and assign "target" in all other
   cases including when segmentCount equals exactly minSegments or exactly maxSegments.

4. Derive badgeText from status as: "On target ✓" for "target", "Too few segments ⚠️"
   for "few", and "Too many segments ⚠️" for "many"; also derive badgeColorClass as a
   Tailwind CSS string: "bg-green-500 text-white" for "target", "bg-yellow-400 text-black"
   for "few", and "bg-red-500 text-white" for "many".

5. Render a div container styled as a compact card with a visible border and rounded corners
   containing: a heading "Segment Count Guide", a paragraph showing the recommended range
   "Recommended for [displayName]: [min]–[max] segments", a paragraph showing "Current:
   [segmentCount] segments", and a span badge with badgeColorClass applied, badgeText as
   content, and the description string set as the title attribute for the native tooltip.

### Step 5 — Integrate the Platform Dropdown and Guidance Card into the Project Page

1. Open frontend/app/projects/[id]/page.tsx and locate the project settings panel section;
   add a new labeled form group titled "Target Platform" immediately adjacent to existing
   project settings fields such as the project name input for visual consistency.

2. Render a select element inside this group whose options map the five platform keys to
   their human-readable display names using PLATFORM_DISPLAY_NAMES from the constants file,
   and bind the select element's value to project.target_platform in the local project state.

3. In the select element's onChange handler, immediately apply an optimistic local state
   update with the new platform key, then dispatch a PATCH /api/projects/{id}/ API call
   sending target_platform with the new value — autosave on selection is appropriate here
   because choosing from a short dropdown list is an explicit and unambiguous action.

4. In the project header area of the page JSX — specifically the region rendered above the
   segment list but below the project title — unconditionally render SegmentCountGuide once
   the project data is loaded, passing project.target_platform as the platform prop and
   segments.length as the segmentCount prop.

5. Wrap SegmentCountGuide in a fixed-height outer container so that changes to segmentCount
   as segments are added or deleted do not cause the page layout to shift and displace the
   segment list content below it, preventing a disorienting visual jump for the creator.

---

## 4. Expected Outcome

1. The api_project database table gains a target_platform text column with a database-level
   default of "youtube", and all pre-existing project rows automatically receive this default
   with no data loss and no manual SQL intervention required during the migration.

2. The GET /api/projects/{id}/ endpoint response JSON includes "target_platform" with
   its current value for every project, and PATCH /api/projects/{id}/ correctly saves any of
   the five valid platform keys while returning a 400 error for any unrecognized invalid value.

3. The project settings panel displays a "Target Platform" dropdown with five clearly labeled
   options that persists the selection to the backend immediately on change, giving creators
   a quick and ergonomic way to declare their distribution target at any point in the workflow.

4. The frontend/constants/platformRecommendations.ts file exists as a clean, fully typed,
   self-contained data source for all five platforms with no runtime API calls required,
   making the guidance card completely instant in all user interactions on the page.

5. The frontend/components/SegmentCountGuide.tsx component renders correctly in three distinct
   visual states — green, yellow, and red — based purely on the live segment count comparison
   and updates its badge color and text immediately when segments are added or removed.

6. The guidance card is visible above the fold in the project header area on first page load
   without any scrolling required, so creators see their structural alignment status the moment
   they open any project regardless of the current segment count or platform selection.

7. When the creator hovers over the status badge, a browser tooltip appears displaying the
   plain-English description sentence for the current platform from the constants file, giving
   enough context to understand the recommendation and make an informed structural decision.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] Test that SegmentCountGuide renders a badge with the text "On target ✓" and a green
  background class when segmentCount equals exactly the minSegments boundary value,
  confirming the lower boundary is treated as on-target and not as too-few.

- [ ] Test that SegmentCountGuide renders a badge with the text "Too few segments ⚠️" and a
  yellow background class when segmentCount is strictly less than minSegments for the platform,
  verifying the yellow state is not triggered at or above the minimum boundary value.

- [ ] Test that SegmentCountGuide renders a badge with the text "Too many segments ⚠️" and a
  red background class when segmentCount is strictly greater than maxSegments for the platform,
  confirming the red state is not triggered at or below the maximum boundary value.

- [ ] Test that SegmentCountGuide falls back gracefully to the "youtube" recommendation entry
  when an unrecognized string is passed as the platform prop, verifying that no runtime
  exception or component crash occurs due to a missing key in the constants lookup object.

- [ ] Test that ProjectSerializer returns a 400 validation error with a human-readable message
  when a PATCH request contains a target_platform value not in the PLATFORM_CHOICES list,
  confirming the choices constraint defined on the model field is enforced at the API level.

### 5.2 Integration / Manual Tests

- [ ] Create a new project via POST /api/projects/ without including target_platform in the
  request body, then verify the response JSON contains "target_platform": "youtube" as the
  field default value applied automatically by the model during creation.

- [ ] Open a project in the browser that has zero segments and confirm the SegmentCountGuide
  component renders with "Current: 0 segments" and a yellow "Too few" badge for the YouTube
  default platform, verifying the component initializes correctly at zero count.

- [ ] Change the platform dropdown selection from "YouTube" to "TikTok" in the project settings
  panel and confirm the guidance card immediately updates to show the TikTok range of 4–6
  segments with no page reload, verifying the optimistic state update is wired correctly.

- [ ] Add enough segments to bring the project's count within the recommended range for the
  currently selected platform and confirm the badge transitions from yellow to green as the
  count crosses the minSegments boundary, verifying live count propagation works.

- [ ] Hover over the status badge on the SegmentCountGuide for any platform and confirm that
  the native browser tooltip displays the correct description sentence from the constants file,
  verifying the title attribute is set correctly on the rendered badge element.

- [ ] Submit a PATCH /api/projects/{id}/ request via HTTP client with an invalid target_platform
  value and confirm the response status is 400 with a body containing a DRF validation error
  message that lists or references the accepted choices.

### 5.3 Regression Tests

- [ ] Confirm that all existing projects open correctly in the project editor after the
  target_platform migration has run, with the guidance card displaying the "youtube" default
  recommendation and no JavaScript exceptions in the browser console.

- [ ] Confirm that all existing segment creation, editing, deletion, and reordering workflows
  are unaffected by the addition of the guidance card in the project header area, verifying
  that no existing event handlers or layout calculations are disrupted.

- [ ] Confirm that the full backend API test suite for project CRUD endpoints passes after
  target_platform is added to ProjectSerializer, with no regressions in existing behavior
  caused by the new field appearing in serialized API response payloads.

---

## 6. Notes for AI Agent

- The platform key strings used in PLATFORM_RECOMMENDATIONS and PLATFORM_DISPLAY_NAMES in
  the frontend constants file must be byte-for-byte identical to the internal value strings
  in the backend PLATFORM_CHOICES list — specifically "youtube", "tiktok", "instagram_reel",
  "youtube_shorts", and "youtube_long" — because the API returns the internal value string
  directly and the frontend uses it as the lookup key without any transformation.

- The SegmentCountGuide component should receive segmentCount as a plain number prop rather
  than computing it from any internal state or context subscription, so the component is a
  pure function of its props and is straightforward to unit test with any arbitrary segment
  count value in complete isolation from the project page state.

- When wiring the platform dropdown's onChange handler in the project page, apply the state
  update optimistically before the PATCH response arrives so SegmentCountGuide evaluates the
  new platform range immediately, providing an instant user experience rather than a visible
  delay between dropdown selection and badge update that would feel laggy.

- Use a fixed-height outer wrapper div around SegmentCountGuide in the project page header
  so that the badge text change between "On target ✓" and the longer "Too few segments ⚠️"
  text does not shift the page layout and reposition the segment list content below it,
  preventing the disorienting visual jump that occurs when header elements change height.

- Do not add any new Django view, URL route, or API endpoint for the recommendation ranges;
  all five sets of recommendation numbers must live exclusively in
  frontend/constants/platformRecommendations.ts so the feature remains zero-latency and the
  backend stays focused solely on persisting and returning the target_platform field value.
