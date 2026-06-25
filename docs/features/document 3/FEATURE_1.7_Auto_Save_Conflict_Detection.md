# Feature 1.7 — Auto-Save with Conflict Detection

| Field | Value |
|---|---|
| **Feature ID** | 1.7 |
| **Title** | Auto-Save with Conflict Detection |
| **Status** | 🟡 Planned |
| **Priority** | High |
| **Complexity** | Low |
| **Estimated Effort** | 2 days |
| **Dependencies** | Existing 500ms debounce auto-save mechanism |
| **Output Files (NEW)** | `frontend/components/SaveStatusBadge.tsx` |
| **Files Modified** | `frontend/app/projects/[id]/page.tsx`, `backend/api/views.py`, `backend/api/serializers.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

The current auto-save implementation fires a debounced PATCH request after edits but provides no visible feedback to the user — there is no indication whether the last change has been committed to the server, is still pending, or has failed silently. A second and more serious problem arises when the same project is open in two browser tabs simultaneously: each tab maintains its own in-memory state, and when both submit a save, the second write silently overwrites the first with no warning, causing data loss. Neither scenario is acceptable for a creative tool where segment text and ordering represent significant editorial effort.

### 1.2 Proposed Solution

Implement a three-state save status indicator that is always visible in the project page header and add a lightweight optimistic-concurrency check on every save request. The concurrency check uses the project's existing `updated_at` timestamp — already maintained by Django — as a version token. The frontend tracks the last timestamp it received from the server; on each save it sends that timestamp along with the PATCH request. The backend compares it to the current database value and rejects the request with HTTP 409 if they differ, prompting the user to resolve the conflict through a modal dialog.

Key implementation points:

- Three save states in the project page component: `idle` (all changes saved), `pending` (save in flight or debounce timer active), and `conflict` (409 received).
- A dedicated `SaveStatusBadge` component reads the save state and renders the appropriate visual: green checkmark for idle, animated spinner for pending, yellow dot for unsaved, red exclamation for conflict.
- Every PATCH request includes a `last_known_updated_at` field in the request body (or `If-Unmodified-Since` header — body field is simpler given the existing DRF setup).
- The backend `ProjectDetailView` or segment update view checks the incoming timestamp against `project.updated_at`. If they do not match, it returns 409 with a body explaining the conflict.
- On 409, a modal gives the user two explicit choices: reload the latest server version (discarding local unsaved changes) or force-save their version unconditionally (an override PATCH without the timestamp check).
- Optional: a 30-second polling loop that silently checks `updated_at` via a lightweight GET and surfaces a non-blocking banner if the project has been changed elsewhere.

### 1.3 Scope

| Category | Item |
|---|---|
| **In Scope** | Save status badge component with idle / pending / conflict states |
| **In Scope** | `last_known_updated_at` field sent on every auto-save PATCH |
| **In Scope** | Backend 409 response when timestamp mismatch is detected |
| **In Scope** | Conflict resolution modal with reload and force-save options |
| **Out of Scope** | Three-way merge of conflicting text content |
| **Out of Scope** | Operational history, diff viewer, or undo beyond the browser session |
| **Out of Scope** | Multi-user real-time collaboration (WebSockets, CRDTs) |
| **Out of Scope** | Conflict detection at the individual segment level (project level only) |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/app/projects/[id]/page.tsx` | Project detail page; owns segment state and auto-save logic | Has debounce save; no save status state; no conflict handling |
| `frontend/components/SaveStatusBadge.tsx` | NEW — renders the save state indicator in the project header | Does not exist yet |
| `backend/api/views.py` | DRF views for project and segment CRUD | PATCH logic exists; no timestamp comparison; no 409 response |
| `backend/api/serializers.py` | Serializes `Project` and `Segment` models | `updated_at` may not be included in current response fields |

---

## 2. Flow Diagram

```
User types in SegmentCard
         │
         ▼
Debounce timer resets (500ms)
         │
         ▼
Timer fires → SaveState = "pending"
         │
         ▼
PATCH request sent with last_known_updated_at
         │
         ├── 200 OK ──────────────────────────────────────────────┐
         │    │                                                    │
         │    ▼                                                    │
         │  Store new updated_at from response                     │
         │  SaveState = "idle" → Badge shows green ✓              │
         │                                                         │
         └── 409 Conflict ─────────────────────────────────────┐  │
              │                                                 │  │
              ▼                                                 │  │
         SaveState = "conflict"                                 │  │
         Badge shows red !                                      │  │
              │                                                 │  │
         Conflict Modal appears                                 │  │
              │                                                 │  │
              ├── "Reload latest" → GET project, replace state  │  │
              │                                                 │  │
              └── "Keep mine"    → Force PATCH (no timestamp)   ┘  │
                                                                    │
Optional 30s polling: GET ?fields=updated_at ───────────────────────┘
If mismatch → non-blocking banner "Updated elsewhere — reload?"
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Expose updated_at in the Project serializer

File: `backend/api/serializers.py`

Locate the `ProjectSerializer` class. Find the `fields` list or tuple inside the `Meta` inner class. Add `"updated_at"` to that list if it is not already present. Because `updated_at` is a read-only auto-managed field, ensure it appears only in the serializer output and is not writable — mark it as `read_only=True` in explicit field declarations if the serializer uses them, or rely on the model's own `auto_now` behaviour to prevent writes. Verify that the endpoint response for `GET /api/projects/{id}/` now includes `updated_at` as an ISO 8601 string.

### Step 3.2 — Add 409 Conflict handling to the backend PATCH view

File: `backend/api/views.py`

Locate the view that handles PATCH requests for a project (likely `ProjectDetailView` or a method inside a `ProjectViewSet`). At the beginning of the update handler — before any field validation — read `last_known_updated_at` from `request.data`. If the field is present and non-empty, compare it to the project's current `updated_at` value after converting both to comparable datetime objects. If they do not match, immediately return a `Response` with HTTP status 409, including a JSON body with a `detail` key explaining the conflict and a `server_updated_at` key containing the current server value. If `last_known_updated_at` is absent from the request body, treat the save as unconditional and proceed normally — this covers the "force save" path from the conflict modal.

### Step 3.3 — Create the SaveStatusBadge component

File: `frontend/components/SaveStatusBadge.tsx` (new file)

Create a React functional component that accepts a single prop representing the save state — a string union of `"idle"`, `"pending"`, and `"conflict"`. For the `"idle"` state, render a small green checkmark icon with the text "All changes saved". For `"pending"`, render an animated spinner icon with "Saving...". For `"conflict"`, render a red exclamation icon with "Conflict detected". Use Tailwind utility classes for colour and sizing. Keep the component narrow so it fits comfortably in a project header bar alongside existing controls. Export the component as a named export.

### Step 3.4 — Integrate save state and conflict detection into the project page

File: `frontend/app/projects/[id]/page.tsx`

Locate where `useState` hooks are declared. Add a `saveState` state variable initialised to `"idle"`, and a `lastKnownUpdatedAt` state variable initialised from the project data loaded on mount. Find the auto-save function (the debounced PATCH call). Before dispatching the request, set `saveState` to `"pending"`. In the success callback, extract `updated_at` from the response body, update `lastKnownUpdatedAt`, and set `saveState` to `"idle"`. In the error callback, check the response status code: if it is 409, set `saveState` to `"conflict"` and store the `server_updated_at` value from the error response body for use in the conflict modal. For non-409 errors, set `saveState` back to `"idle"` (or to a separate `"error"` state if a more granular distinction is desired). Modify the PATCH request body construction to include `last_known_updated_at: lastKnownUpdatedAt`. Place `SaveStatusBadge` in the project header JSX and pass the `saveState` value as its prop.

### Step 3.5 — Implement the conflict resolution modal

File: `frontend/app/projects/[id]/page.tsx`

When `saveState` is `"conflict"`, render a modal dialog (use the ShadCN `Dialog` component). The modal title should read something like "Project modified in another tab". The body should explain in plain language that the server version is newer than the local version. Provide two action buttons: "Reload latest version" and "Keep my version and overwrite". For "Reload latest version", call the project fetch function to retrieve fresh data from the server, replace the local segment state with the server data, update `lastKnownUpdatedAt`, and set `saveState` to `"idle"`. For "Keep my version", dispatch the same PATCH request but omit `last_known_updated_at` from the body so the backend treats it as an unconditional write; on success, update `lastKnownUpdatedAt` and set `saveState` to `"idle"`.

---

## 4. Expected Outcome

1. The project header always displays one of three clearly distinguishable save indicators, giving users constant awareness of persistence state.
2. After any edit the indicator transitions to "Saving..." within 500ms, and back to "All changes saved" once the server confirms the write.
3. When the same project is open in two tabs and both tabs have made edits, the second save results in a 409 response and the conflict modal appears rather than silently overwriting data.
4. The "Reload latest version" path fully replaces local state with the server version, restoring data integrity.
5. The "Keep my version" path forces the save unconditionally, giving the user full agency to override the conflict if they are confident their version is correct.
6. The optional 30-second polling banner appears when an external change is detected, allowing proactive reload before edits are made.
7. Projects that are never opened in multiple tabs are completely unaffected — the timestamp check passes on every save and no new UX appears beyond the status badge.
8. The backend changes are minimal and backward-compatible: omitting `last_known_updated_at` from a PATCH body continues to work as before.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `SaveStatusBadge` renders a green checkmark element when `saveState` is `"idle"`.
- [ ] `SaveStatusBadge` renders a spinner element when `saveState` is `"pending"`.
- [ ] `SaveStatusBadge` renders a red exclamation element when `saveState` is `"conflict"`.
- [ ] Backend view returns HTTP 200 when `last_known_updated_at` matches the current `updated_at`.
- [ ] Backend view returns HTTP 409 with a `detail` key when `last_known_updated_at` does not match.
- [ ] Backend view returns HTTP 200 (unconditional) when `last_known_updated_at` is absent from the request body.

### 5.2 Integration / Manual Tests

- [ ] Edit a segment in one browser tab; verify the badge shows "Saving..." during the debounce window and "All changes saved" after the response.
- [ ] Open the same project in two tabs. Make an edit in tab A and wait for it to save. Then make a different edit in tab B and save. Verify the conflict modal appears in tab B.
- [ ] Click "Reload latest version" in the conflict modal; verify the page reloads the server state and the badge returns to "All changes saved".
- [ ] Click "Keep my version" in the conflict modal; verify the force-save succeeds and the badge returns to "All changes saved".
- [ ] Confirm that `GET /api/projects/{id}/` response body now includes an `updated_at` ISO 8601 field.
- [ ] Verify no conflict modal appears during normal single-tab editing sessions.

### 5.3 Regression Tests

- [ ] Existing auto-save still works end-to-end when `last_known_updated_at` is included and matches.
- [ ] Confirm existing segment-level PATCH endpoints are unaffected by the project-level timestamp check.
- [ ] Confirm that loading the project page still works when `updated_at` is added to the serializer.

---

## 6. Notes for AI Agent

- Django's `updated_at = models.DateTimeField(auto_now=True)` updates on every `save()` call including those triggered by segment changes if the project is saved in the same transaction; confirm the exact update path before relying on `updated_at` as a version token.
- The comparison between `last_known_updated_at` (a string from the HTTP body) and `project.updated_at` (a Python datetime) requires careful timezone-aware parsing; use `django.utils.dateparse.parse_datetime` and ensure both sides are UTC before comparing.
- The "force save" path that omits the timestamp check should still be guarded at the Django layer against truly malicious concurrent writes — this feature is intended to protect against accidental tab duplication, not adversarial actors.
- The optional 30-second polling is a stretch goal; implement only after the core badge and conflict modal are working and tested, since the polling adds a background network request that must be cleanly cancelled on component unmount.
- If the project page already uses React Query or SWR for data fetching, the conflict detection and reload logic should be implemented within that layer rather than as custom `useState` logic, to avoid cache inconsistencies.
