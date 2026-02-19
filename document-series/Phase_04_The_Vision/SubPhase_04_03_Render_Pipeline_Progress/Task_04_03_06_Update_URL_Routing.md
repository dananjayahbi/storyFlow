# Task 04.03.06 — Update URL Routing

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.03.06                                                             |
| **Task Name** | Update URL Routing                                                   |
| **Sub-Phase** | 04.03 — Render Pipeline & Progress API                               |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Low                                                                  |
| **Dependencies** | Tasks 04.03.01 and 04.03.02 (both endpoints must be implemented) |
| **Parent**    | [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md)           |

---

## Objective

Ensure that the render and status custom actions on ProjectViewSet are properly registered as URL routes and accessible via the expected API paths. DRF's DefaultRouter typically auto-registers custom actions defined with the action decorator, but this task verifies the registration, handles any edge cases, and confirms the final URL patterns are correct.

---

## Instructions

### Step 1 — Verify Auto-Registration

When using DRF's DefaultRouter with a ModelViewSet, methods decorated with @action(detail=True) are automatically registered as URL patterns. Verify that the router configuration in backend/api/urls.py uses DefaultRouter and that ProjectViewSet is registered with it. The render action should auto-generate POST /api/projects/{id}/render/ and the render_status action (with url_path='status') should auto-generate GET /api/projects/{id}/status/.

### Step 2 — Add Explicit Routes if Needed

If the auto-registration does not produce the correct URL patterns (which can depend on DRF version and router configuration), add explicit URL patterns in urls.py. Register the render action as a POST route and the render_status action as a GET route, both at the project detail level with the UUID path converter.

### Step 3 — Verify No Route Conflicts

Confirm that the new routes do not conflict with existing endpoints. Phase 03 already registers POST /api/projects/{id}/generate-all-audio/ and GET /api/tasks/{task_id}/status/ — these use different paths and should not collide. The project detail endpoint GET /api/projects/{id}/ is also distinct from the /render/ and /status/ sub-paths.

### Step 4 — Test Route Accessibility

Verify both endpoints are reachable by checking the DRF browsable API or using a manual HTTP request. Confirm POST /api/projects/{id}/render/ accepts POST and GET /api/projects/{id}/status/ accepts GET.

---

## Expected Output

Both render and status endpoints are accessible at their expected URLs. POST /api/projects/{id}/render/ triggers the render endpoint and GET /api/projects/{id}/status/ returns the status endpoint response.

---

## Validation

- [ ] POST /api/projects/{id}/render/ is accessible and routed to the render action.
- [ ] GET /api/projects/{id}/status/ is accessible and routed to the render_status action.
- [ ] No conflicts with existing Phase 03 routes.
- [ ] The UUID path converter handles project IDs correctly.
- [ ] Incorrect HTTP methods (e.g., GET on /render/) return 405 Method Not Allowed.

---

## Notes

- This is a low-complexity verification task. If DRF's DefaultRouter is configured correctly (which it should be from Phase 01/02), the routes are auto-registered and this task is primarily confirmation.
- The url_path='status' parameter on the render_status action is essential — without it, DRF would use the method name "render_status" as the URL segment, producing /api/projects/{id}/render_status/ instead of /api/projects/{id}/status/.
- No new URL patterns file is needed. All modifications go in the existing backend/api/urls.py.

---

> **Parent:** [SubPhase_04_03_Overview.md](./SubPhase_04_03_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
