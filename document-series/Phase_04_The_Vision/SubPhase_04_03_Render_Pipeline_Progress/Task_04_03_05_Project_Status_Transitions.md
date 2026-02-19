# Task 04.03.05 — Project Status Transitions

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.03.05                                                             |
| **Task Name** | Project Status Transitions                                           |
| **Sub-Phase** | 04.03 — Render Pipeline & Progress API                               |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Medium                                                               |
| **Dependencies** | None (standalone logic, used by Tasks 04.03.01 and 04.03.04)     |
| **Parent**    | [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md)           |

---

## Objective

Define and implement the complete lifecycle of Project.status transitions during the render pipeline. The status field acts as a simple state machine governing what actions are allowed on a project: DRAFT is the initial state, PROCESSING means rendering is in progress, COMPLETED means the video is ready, and FAILED means an error occurred. This task ensures that transitions are validated and applied consistently across the render endpoint and the background task function.

---

## Instructions

### Step 1 — Define Valid Transitions

Document the five valid status transitions for the render pipeline:

1. DRAFT to PROCESSING — triggered when the render endpoint starts a new render.
2. PROCESSING to COMPLETED — triggered when the background task finishes successfully.
3. PROCESSING to FAILED — triggered when the background task encounters an error.
4. COMPLETED to PROCESSING — triggered when the user requests a re-render of an already-completed project.
5. FAILED to PROCESSING — triggered when the user retries a failed render.

The one invalid transition is PROCESSING to PROCESSING — a project that is already rendering cannot start another render simultaneously. This is blocked with a 409 Conflict response.

### Step 2 — Implement Status Guard in the Render Endpoint

In the render endpoint (Task 04.03.01), before setting the status to PROCESSING, check the current status. Create a utility function or inline check that determines whether rendering can start from the current status. The allowed source states are DRAFT, COMPLETED, and FAILED. The blocked state is PROCESSING. This can be expressed as a simple membership check against a set of allowed values.

### Step 3 — Implement Success Transition in the Task Function

In the background render task (Task 04.03.04), when rendering completes successfully, set Project.status to COMPLETED and Project.output_path to the rendered file's URL-relative path. Use save with update_fields to perform a targeted database update without overwriting other fields.

### Step 4 — Implement Failure Transition in the Task Function

In the background render task, when rendering fails with an exception, set Project.status to FAILED. Optionally clear Project.output_path (or leave the previous value if a prior successful render exists, allowing the user to still access the old video). Save with update_fields.

### Step 5 — Define Status Constants

The status values (DRAFT, PROCESSING, COMPLETED, FAILED) should be referenced consistently across all files. Since models are frozen from Phase 01, use string literals that match the Phase 01 model definition. Optionally define module-level constants in a shared location to avoid typos, but do not modify the model itself.

---

## Expected Output

The project status transitions are implemented consistently across the render endpoint and background task function. The state machine DRAFT → PROCESSING → COMPLETED/FAILED is enforced, with re-render and retry paths supported.

---

## Validation

- [ ] DRAFT → PROCESSING transition works (render triggered).
- [ ] PROCESSING → COMPLETED transition works (render succeeded).
- [ ] PROCESSING → FAILED transition works (render error).
- [ ] COMPLETED → PROCESSING transition works (re-render).
- [ ] FAILED → PROCESSING transition works (retry).
- [ ] PROCESSING → PROCESSING is blocked with 409 Conflict.
- [ ] update_fields is used for all status saves to avoid overwriting other fields.
- [ ] Status values match the Phase 01 model definition exactly.

---

## Notes

- The status field defaults to DRAFT (defined in Phase 01). New projects always start in DRAFT state.
- The FAILED state is recoverable — clicking "Export Video" again transitions back to PROCESSING for a fresh render attempt.
- The COMPLETED state allows re-rendering — the old final.mp4 is overwritten by the new render. The output_path remains the same URL.
- There is no CANCELLED state in Phase 04. Python threads cannot be forcefully killed, so cancel is best-effort only and is out of scope for this phase.

---

> **Parent:** [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
