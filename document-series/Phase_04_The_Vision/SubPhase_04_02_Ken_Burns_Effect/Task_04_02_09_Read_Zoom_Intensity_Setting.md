# Task 04.02.09 — Read Zoom Intensity Setting

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.02.09                                                             |
| **Task Name** | Read Zoom Intensity Setting                                          |
| **Sub-Phase** | 04.02 — Ken Burns Effect Implementation                              |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Low                                                                  |
| **Dependencies** | None (independent Django ORM read, though logically feeds into Task 04.02.08) |
| **Parent**    | [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md)           |

---

## Objective

Implement the logic to read the zoom_intensity value from the GlobalSettings singleton model and make it available to the Ken Burns rendering pipeline. The zoom_intensity setting controls how much the Ken Burns effect zooms into the source image — a value of 1.0 means no zoom, 1.3 (the default) means 30 percent zoom, and 2.0 means 100 percent zoom. This task defines the data flow from the database model to the rendering function, including validation and fallback behavior for missing or invalid data.

---

## Instructions

### Step 1 — Locate the Reading Point

The zoom_intensity value is read inside the render_project function in backend/core_engine/video_renderer.py, at the beginning of the function after the Project and its Segments are loaded from the database. This placement ensures the value is available before the per-segment rendering loop begins, where it is passed to apply_ken_burns for each segment.

### Step 2 — Import GlobalSettings

Import the GlobalSettings model from api.models at the top of video_renderer.py (or within the render_project function if preferred for encapsulation). GlobalSettings is a singleton model — only one row exists in the database, containing application-wide configuration values including zoom_intensity.

### Step 3 — Query the GlobalSettings Instance

Use GlobalSettings.objects.first() to retrieve the single GlobalSettings row. This returns the first (and only) instance if it exists, or None if the table is empty. The table may be empty if the database was freshly created without seeding, or if the initial migration has not been run.

### Step 4 — Extract and Validate zoom_intensity

If a GlobalSettings instance is found, extract its zoom_intensity attribute. This field was defined in the Phase 01 model with a default value of 1.3.

Validate the extracted value:

- If zoom_intensity is None (which should not happen given the model definition but could occur with manual database edits), fall back to 1.3.
- If zoom_intensity is less than or equal to zero, fall back to 1.3 and log a WARNING-level message indicating that an invalid zoom_intensity value was found in the database.
- If zoom_intensity is within a normal range (typically 1.0 to 2.0), accept it as-is. Values outside this range (for example, 0.5 or 3.0) are unusual but technically valid and should be accepted with a DEBUG-level log noting the atypical value.

### Step 5 — Handle Missing GlobalSettings

If GlobalSettings.objects.first() returns None, set zoom_intensity to the default value of 1.3. Log a WARNING-level message explaining that no GlobalSettings row was found and the default zoom_intensity is being used. This situation is expected during initial development or testing when the database may not have been seeded with configuration data.

### Step 6 — Log the Active Value

Log the zoom_intensity value being used at INFO level. This log entry serves as an audit trail for debugging rendering issues — if a video has unexpected zoom behavior, the log shows exactly what zoom_intensity was applied.

### Step 7 — Pass to apply_ken_burns

The zoom_intensity variable is then passed as an argument to apply_ken_burns in the per-segment loop (handled in Task 04.02.08). This task focuses on the reading and validation logic; the passing happens as part of the integration.

---

## Expected Output

After completing this task, the render_project function in video_renderer.py reads zoom_intensity from GlobalSettings with proper fallback and validation:

- If GlobalSettings exists with zoom_intensity equals 1.3, the value 1.3 is used.
- If GlobalSettings exists with zoom_intensity equals 1.0, the value 1.0 is used (no zoom, but Ken Burns pipeline still runs).
- If GlobalSettings exists with zoom_intensity equals 0.0, the value falls back to 1.3 with a warning log.
- If GlobalSettings does not exist (None), the value falls back to 1.3 with a warning log.

---

## Validation

- [ ] GlobalSettings is imported from api.models in video_renderer.py.
- [ ] GlobalSettings.objects.first() is called to retrieve the singleton instance.
- [ ] zoom_intensity is extracted from the instance if it exists.
- [ ] A default of 1.3 is used when GlobalSettings is missing (None).
- [ ] A default of 1.3 is used when zoom_intensity is invalid (less than or equal to zero).
- [ ] A WARNING log is emitted when falling back to the default value.
- [ ] An INFO log is emitted showing the zoom_intensity value being used.
- [ ] The zoom_intensity value is available for passing to apply_ken_burns.

---

## Notes

- The GlobalSettings model is a singleton pattern — only one row should exist. The objects.first() query is the standard Django pattern for retrieving singleton instances. Using objects.get() would raise DoesNotExist if the row is missing, which is less graceful than the first/None pattern.
- The zoom_intensity field was defined in Phase 01 (model definition) but is used for the first time in Phase 04. There is no UI for editing this field until Phase 05. During Phase 04, developers can change the value using Django admin, the Django shell (python manage.py shell), or direct database manipulation.
- The typical zoom_intensity range is 1.0 to 2.0. A value of 1.0 means no zoom — the crop box equals the output resolution, so make_frame simply resizes the image to the output size without any zoom-in effect. Values above 2.0 are technically possible but produce very aggressive zoom with limited source image utilization.
- This task has no dependencies on other SubPhase 04.02 tasks because it deals purely with Django ORM reading, which is orthogonal to the Ken Burns mathematical algorithm. However, it logically feeds into Task 04.02.08 (renderer integration) where the value is actually consumed.

---

> **Parent:** [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
