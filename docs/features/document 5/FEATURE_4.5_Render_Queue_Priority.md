# Feature 4.5 — Render Queue Priority System

| Field | Value |
|---|---|
| Feature ID | 4.5 |
| Title | Render Queue Priority System |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Low |
| Estimated Effort | 2–3 days |
| Dependencies | Feature 1.1 (Project Model), Celery task runner, Redis or RabbitMQ broker |
| Output Files (NEW) | None — all changes are to existing files |
| Files Modified | backend/api/models.py, backend/api/views.py, backend/api/urls.py, backend/api/tasks.py, backend/api/serializers.py, backend/storyflow_backend/settings.py, frontend/app/projects/[id]/page.tsx, frontend/app/settings/page.tsx |

---

## 1. Document Overview

### 1.1 Problem Statement

All render requests submitted to StoryFlow are dispatched to a single Celery task queue and
processed in strict first-in, first-out order with no notion of urgency, deadline, or
background-fill priority. A creator who queues a large overnight batch of twenty low-priority
content shorts cannot distinguish those from a single video that must be rendered within the
next thirty minutes for an imminent social media upload deadline. Once the batch is in the
queue, the urgent video must wait behind all twenty items regardless of how small or simple
it is, and there is no mechanism in the current interface to reorder, promote, or deprioritize
any queued render. This rigidity creates a frustrating bottleneck for creators who manage mixed
urgency workloads, especially those who run StoryFlow on a shared or resource-constrained
machine where render throughput is a limiting factor. The absence of priority control also
means that idle overnight capacity cannot be leveraged intelligently — all tasks consume
compute resources with equal urgency regardless of whether the creator actually needs the
result immediately or is simply pre-rendering content for a future date.

### 1.2 Proposed Solution

Introduce a three-tier render priority system consisting of Rush, Normal, and Low tiers that
maps directly to Celery's named-queue routing mechanism, allowing workers to be configured
to drain higher-priority queues before processing lower-priority ones. Priority is stored as a
field on the Project model, selected by the creator before submitting a render, and reflected
visually throughout the queue display.

- Add a `render_priority` CharField with choices "rush", "normal", and "low" to the `Project`
  model in `backend/api/models.py` with "normal" as the default value, then generate and apply
  the corresponding database migration.
- Update `backend/api/serializers.py` to expose `render_priority` in the `ProjectSerializer`
  so the field is readable and writable through the REST API.
- Add a `PATCH /api/projects/{id}/set-priority/` endpoint in `backend/api/views.py` that
  accepts a priority value and updates the project record, enabling real-time priority changes
  even after a project has been created.
- Modify `backend/api/tasks.py` so that the render Celery task is dispatched to one of three
  named queues — `rush_renders`, `default`, or `low_renders` — based on the project's stored
  priority value at the time the render is triggered.
- Configure Celery queue routing in `backend/storyflow_backend/settings.py` so that the
  `rush_renders` queue is always consumed before `default`, and `default` before `low_renders`,
  using Celery's built-in queue priority or worker command-line arguments.
- Add a Priority selector widget (three-button toggle or dropdown) to the render controls
  section of `frontend/app/projects/[id]/page.tsx` with tooltips explaining each tier.
- Color-code the render queue display with red/orange badges for Rush, gray for Normal, and
  muted blue for Low, always sorting Rush items to the top of the visual list.

### 1.3 Scope

#### In Scope

| Item | Description |
|---|---|
| Three-tier priority model | Adding rush, normal, and low priority tiers to the Project model and Celery dispatch logic |
| Queue routing configuration | Routing Celery tasks to separate named queues and configuring worker consumption order |
| Priority selector UI | A frontend toggle or dropdown on the project detail page for selecting render priority |
| Per-project priority API endpoint | A PATCH endpoint that allows changing a project's priority value via the REST API |

#### Out of Scope

| Item | Description |
|---|---|
| Real-time queue reordering | Revoking already-running tasks and re-inserting them at a different position is not included |
| Dynamic worker scaling | Auto-scaling the number of Celery workers based on queue depth is excluded from this feature |
| Priority inheritance | Automatically escalating priority based on project age or deadline is not part of this scope |
| User role-based rush limits | Restricting how many rush renders a given user can submit per day is out of scope here |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| backend/api/models.py | Project ORM model; will receive the render_priority field | Existing; no priority field currently |
| backend/api/tasks.py | Celery render task dispatcher | Existing; dispatches to a single default queue |
| backend/storyflow_backend/settings.py | Django and Celery configuration | Existing; Celery queues not yet configured for priority |
| frontend/app/projects/[id]/page.tsx | Project detail editor; will receive priority selector | Existing; render controls section present |
| frontend/app/settings/page.tsx | Global settings page | Existing; will receive default priority preference setting |

---

## 2. Flow Diagram

    Creator opens project detail page
            |
            v
    Selects Priority:  [ Rush | Normal | Low ]
            |
            v
    PATCH /api/projects/{id}/set-priority/
    Updates render_priority on Project record
            |
            v
    Creator clicks "Start Render"
            |
            v
    View calls tasks.dispatch_render(project_id)
            |
     priority == ?
      /      |      \
   rush   normal    low
    |        |        |
    v        v        v
  rush_   default  low_renders
  renders  queue    queue
    |        |        |
    v        v        v
         Celery Worker
    (drains rush first, then default, then low)
            |
            v
    Render task executes, project status updated

---

## 3. Step-by-Step Instructions

### Step 1 — Add the render_priority Field to the Project Model

Open `backend/api/models.py` and add a `render_priority` CharField to the `Project` model
with a `choices` attribute listing the three allowed values as a tuple of two-tuples:
`("rush", "Rush")`, `("normal", "Normal")`, and `("low", "Low")`. Set the `default` parameter
to `"normal"` so that all existing and new projects start at the standard processing tier
without any migration-time data change. After saving the model file, run Django's `makemigrations`
command to auto-generate a migration file in `backend/api/migrations/` with an `AlterField`
or `AddField` operation for `render_priority`. Apply the migration with `migrate` and verify
the new column appears in the database schema by inspecting the `api_project` table. Update
`backend/api/serializers.py` to include `render_priority` in the `fields` list of
`ProjectSerializer` so the value is returned in all project GET responses and can be written
in full-project PATCH requests.

### Step 2 — Modify the Celery Task Dispatch Logic

Open `backend/api/tasks.py` and locate the function or method that submits the render task
to Celery, typically a call to `render_project.delay(project_id)` or similar. Before
dispatching, query the `Project` record by `project_id` and read its `render_priority` value
to determine which named queue to target. Replace the unconditional `.delay()` call with an
`.apply_async()` call that passes a `queue` keyword argument: `"rush_renders"` if priority is
`"rush"`, `"default"` if priority is `"normal"`, and `"low_renders"` if priority is `"low"`.
This change ensures that the routing decision happens at submission time and is immutable once
the task is enqueued, which is the simplest and most reliable approach given Celery's
queue-based priority model. Add a log statement at the INFO level recording the project ID,
its priority, and the target queue name so that queue routing decisions are visible in the
worker logs for debugging purposes.

### Step 3 — Configure Celery Queue Routing in Settings

Open `backend/storyflow_backend/settings.py` and add Celery configuration entries that define
the three named queues and their consumption order for the render worker. Add a `CELERY_QUEUES`
entry using Celery's `Queue` objects (imported from `kombu`) that declares `rush_renders`,
`default`, and `low_renders` with explicit routing keys. Set `CELERY_DEFAULT_QUEUE` to
`"default"` so any tasks that do not specify a queue land in the standard tier. Document in
a comment block adjacent to these settings that the render worker should be started with the
command-line argument `--queues rush_renders,default,low_renders` to ensure it polls queues
in that priority order from left to right, consuming all items from `rush_renders` before
moving to `default`. Add an additional note explaining that a dedicated low-priority worker
can be started with `--queues low_renders` only, listening solely to the background tier for
overnight batch workloads. Ensure the `CELERY_TASK_ROUTES` dictionary maps the render task
to the `"default"` queue as a fallback so existing deployments without priority configuration
continue to function without errors.

### Step 4 — Add the Set-Priority API Endpoint

Open `backend/api/views.py` and create a new view function or class-based view that handles
`PATCH /api/projects/{id}/set-priority/`. The view should read the `priority` key from the
request body, validate that its value is one of the three allowed strings ("rush", "normal",
"low"), return a descriptive 400 error if the value is not in the allowed set, then update
the `Project` record's `render_priority` field and save it to the database. Register this URL
pattern in `backend/api/urls.py` under the path `projects/<int:pk>/set-priority/` with the
name `project-set-priority`. Consider adding a check that prevents changing the priority of a
project currently in an "in_progress" render status, since the task has already been dispatched
to a queue and changing the field would have no practical effect on the running task — return
a 400 with a message explaining that priority cannot be changed while a render is active.

### Step 5 — Build the Priority Selector in the Frontend

Open `frontend/app/projects/[id]/page.tsx` and locate the render controls section above or
around the existing "Start Render" button. Add a three-button toggle group using Shadcn/UI's
`ToggleGroup` component, with buttons labeled "Rush", "Normal", and "Low" and distinct visual
styles: Rush uses a red/orange variant, Normal uses the default variant, and Low uses a muted
blue variant. The selected value should be stored in component state initialized from the
project's `render_priority` field fetched from the API, and any change should immediately
dispatch a `PATCH` request to `/api/projects/{id}/set-priority/` to persist the change. Add
tooltip text to each button explaining the behavior of that tier to users who may be unfamiliar
with the priority system. In `frontend/app/settings/page.tsx`, add a "Default Render Priority"
setting using a Shadcn/UI `Select` component that writes the chosen default to the Zustand
global settings store, so that newly created projects pre-populate their priority selector with
the creator's preferred tier without requiring manual selection on each project.

---

## 4. Expected Outcome

1. The `Project` model has a `render_priority` field that accepts "rush", "normal", and "low"
   values, defaults to "normal", and is included in all API responses for project objects.
2. Submitting a render for a project with priority "rush" dispatches the Celery task to the
   `rush_renders` queue, "normal" to `default`, and "low" to `low_renders` as verified by
   Celery's task inspection tools.
3. A Celery worker started with `--queues rush_renders,default,low_renders` consistently
   processes all pending Rush tasks before consuming any Normal tasks and all Normal tasks
   before consuming any Low tasks.
4. The `PATCH /api/projects/{id}/set-priority/` endpoint returns 200 on valid input, 400 on
   an unrecognized priority value, and 400 with an explanatory message if the project is
   currently rendering.
5. The priority toggle widget on the project detail page displays the correct active state
   reflecting the project's stored priority and updates the backend record immediately on
   change without requiring the form to be saved separately.
6. The render queue display (wherever rendered in the frontend) shows color-coded badges for
   each project and sorts Rush items above Normal and Normal above Low items visually.
7. The default priority preference set in the global settings page is applied to all new
   project detail pages when they first load, pre-selecting the creator's configured default
   in the priority toggle.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] A unit test confirms that calling the render dispatch function with a project whose
      `render_priority` is "rush" results in `apply_async` being called with `queue="rush_renders"`.
- [ ] A unit test confirms that the set-priority endpoint returns 400 when given an invalid
      priority string such as "urgent" or an empty value.
- [ ] A unit test confirms that the set-priority endpoint returns 400 when called on a project
      whose status is "in_progress" and does not modify the priority field.
- [ ] A unit test validates that the `ProjectSerializer` includes `render_priority` in its
      output for both serialization and deserialization of project data.
- [ ] A unit test confirms that the `Project` model's default value for `render_priority` is
      "normal" when no explicit value is provided at creation time.

### 5.2 Integration / Manual Tests

- [ ] Create three projects, set one to Rush, one to Normal, one to Low, trigger all three
      renders in rapid succession, and observe via Celery Flower or worker logs that they are
      consumed in Rush-first order.
- [ ] Open the project detail page for an existing project and verify the priority toggle
      renders with the correct button highlighted based on the stored priority value from the API.
- [ ] Change the priority toggle from Normal to Rush, observe the PATCH request in browser
      devtools, then reload the page and confirm the Rush state persists.
- [ ] Set the default priority preference to "low" in settings, create a new project, and
      confirm its detail page opens with the Low button pre-selected in the priority toggle.
- [ ] Attempt to call the set-priority endpoint on a project that is currently in the
      in_progress state and confirm it returns 400 with the expected error message.
- [ ] Verify that the worker logs contain INFO-level entries recording the queue routing
      decision (project ID, priority, and queue name) for each dispatched render task.

### 5.3 Regression Tests

- [ ] Verify that projects created before this feature was added (without a priority field)
      render correctly after the migration, defaulting to "normal" queue dispatch.
- [ ] Confirm that the project detail page renders without JavaScript errors after the priority
      toggle is added to the render controls section.
- [ ] Ensure that all existing project list, create, update, and delete API endpoints continue
      to return correct responses after the `render_priority` field is added to the serializer.

---

## 6. Notes for AI Agent

- When configuring Celery queue priority in settings, prefer using the worker `--queues`
  argument ordering approach over Celery's numerical `priority` parameter on queues, because
  the ordering approach is universally supported across all Celery brokers (Redis, RabbitMQ)
  while numerical priority requires broker-specific configuration that may not be available.
- The set-priority endpoint should use a dedicated serializer or simple input validation
  rather than a full project serializer update to avoid accidentally overwriting other project
  fields with a partial PATCH payload from the priority-change action.
- In the frontend, the priority toggle state should be managed as a local component state
  variable synced to the server via the PATCH endpoint on change, rather than going through
  the full project update form form, to make priority changes feel instantaneous.
- When adding tooltips to the priority buttons in the frontend, use Shadcn/UI's `Tooltip`
  component wrapping each button so the tooltip behavior is consistent with the rest of the
  application's UI patterns.
- The Low priority queue is most useful when combined with a separate Celery worker process
  dedicated to that queue, so consider documenting the recommended multi-worker startup
  commands in the project README or start scripts alongside this feature's implementation.

---

## 7. Implementation Risks and Mitigations

- **Risk: Tasks already queued before deployment cannot be re-routed.** When this feature is
  first deployed, any render tasks that were submitted before the render_priority field existed
  will already be sitting in the default queue with no priority metadata attached. If the
  worker configuration is changed at the same time as the code deployment, those existing tasks
  may end up stranded in a queue the newly configured worker is not consuming. Mitigation:
  deploy the code change (new model field and updated task dispatch logic) strictly before
  the Celery worker configuration change, ensuring all in-flight tasks drain from the old
  queue before the worker is reconfigured to poll named priority queues.

- **Risk: Rush tier overuse degrading system throughput for all other renders.** If there is
  no limit on how many projects a creator can simultaneously mark as Rush priority, a creator
  could mark every project as Rush and effectively bypass the intent of the queuing system,
  causing all Normal and Low projects to wait indefinitely behind a flood of Rush tasks. A
  Mitigation for this early implementation: add a soft validation in the set-priority endpoint
  that counts currently queued Rush renders and returns a 400 error with an explanatory message
  if the creator already has three or more Rush renders waiting, and add a tooltip note in the
  UI reminding users that Rush is intended for genuinely time-sensitive content only.

- **Risk: Priority database value out of sync with dispatched queue.** If the project's
  render_priority field is updated via the set-priority endpoint after the render task has
  already been dispatched to a Celery queue, the stored value in the database will no longer
  match the queue to which the task was actually submitted, causing the UI to display an
  incorrect priority badge for an in-progress render. Mitigation: once a render task has been
  dispatched, record the actual queue name it was submitted to in a separate read-only field
  on the Project model so the frontend can show the effective queue priority rather than the
  current preference value, and disable the priority toggle while a render is active.

- **Risk: Celery worker not reloaded after settings change.** Changes to the CELERY_QUEUES
  or routing configuration in settings.py require the Celery worker process to be fully
  restarted to take effect, but the Django development server hot-reload will not automatically
  restart running workers, making the priority routing appear broken during development.
  Mitigation: add a prominent comment in settings.py near the Celery queue configuration
  reminding developers to restart all worker processes after changing queue routing settings,
  and include this reminder in the feature's testing checklist to prevent confusion.

- **Risk: Monitoring tools not reflecting named queues until first use.** Some versions of
  Celery Flower and other monitoring dashboards do not display custom named queues in their
  overview until at least one task has been dispatched to that specific queue, making the queue
  setup appear broken or incomplete immediately after deployment when no Rush or Low tasks have
  yet been submitted. Mitigation: document this expected behavior in the developer setup guide
  and provide a one-liner command using the Celery CLI to inspect queue state directly so
  developers can verify routing is working correctly without relying on the Flower UI alone.

---

## 8. Rollout and Phasing

### 8.1 Phase One — Model Migration and Task Dispatch Routing

The first phase covers adding the render_priority field to the Project model, generating and
applying the database migration, updating the serializer to expose the field, and modifying
the task dispatch in tasks.py to use apply_async with the queue keyword argument. Deploy and
verify this phase in isolation before any frontend changes: create three test projects with
different priority values directly via the Django admin or shell, trigger renders for each,
and inspect the Celery worker logs to confirm the correct queue name appears for each task.
The Celery queue configuration in settings.py and the worker startup documentation should also
be finalized and committed in this phase so the routing infrastructure is in place.

### 8.2 Phase Two — Set-Priority Endpoint and UI Widget

The second phase implements the PATCH /api/projects/{id}/set-priority/ endpoint and adds the
three-button priority toggle to the project detail page with tooltips and immediate PATCH-on-
change behavior. End-to-end testing in this phase should cover the full interactive flow: a
developer selects a priority in the UI, observes the PATCH request in browser devtools, then
triggers a render and verifies the task lands in the correct Celery queue. The color-coded
queue badge display should also ship in this phase to make the priority system visible in the
render queue monitoring section of the frontend.

### 8.3 Phase Three — Default Priority Setting and Idle-Worker Documentation

The third phase adds the global default priority preference to the settings page and documents
the recommended multi-worker startup configuration for operating Rush, Normal, and Low queues
on separate worker processes. This phase is primarily documentation and configuration work
rather than new code, but it is important for making the Low priority tier useful as an idle-
time background fill system. Update the start-backend.sh and start-backend.bat scripts in the
project root to include commented-out examples of the multi-worker startup pattern so creators
running StoryFlow locally can enable the full priority system with minimal configuration effort.

