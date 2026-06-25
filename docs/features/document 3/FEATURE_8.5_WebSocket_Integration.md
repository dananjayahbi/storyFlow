# Feature 8.5 — Real-Time Render Progress via WebSocket Integration

| Field | Value |
|---|---|
| Feature ID | 8.5 |
| Title | Real-Time Render Progress via WebSocket Integration |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | High |
| Estimated Effort | 5–7 days |
| Dependencies | Django Channels, Daphne ASGI server, channels-redis, Redis (dev: InMemoryChannelLayer) |
| Output Files (NEW) | `backend/api/consumers.py`, updated `backend/storyflow_backend/asgi.py` |
| Files Modified | `backend/api/tasks.py`, `backend/storyflow_backend/settings.py`,
`frontend/hooks/useRenderProgress.ts`, `frontend/app/projects/[id]/page.tsx`,
`frontend/components/ProgressBar.tsx`, `start-backend.sh`, `start-backend.bat` |

---

## 1. Document Overview

### 1.1 Problem Statement

The current render-status polling mechanism in StoryFlow sends a new HTTP GET request from
every connected browser tab every 2–3 seconds regardless of whether any real progress has
occurred on the backend since the last request. With five concurrent users each polling at a
2-second interval, the Django application server receives approximately 150 requests per
minute to a single endpoint — the vast majority of which return an unchanged progress value
and consume server resources without delivering new information to anyone. This constant
polling occupies Django worker threads, triggers redundant database reads or in-memory cache
lookups on every cycle, and scales linearly with the number of connected users rather than
with the amount of actual rendering work happening. The latency problem is equally
significant: a render that completes between two polling calls will not be reflected in the
UI for up to 2–3 seconds, making the application feel sluggish even when the backend
finishes work faster than the user expects.

### 1.2 Proposed Solution

Replace the HTTP polling loop with a Django Channels WebSocket channel layer so the backend
pushes progress data to connected clients only when real data changes. The server maintains
a persistent, low-overhead bidirectional connection per project session rather than
responding to a continuous stream of client-initiated GET requests. Each Celery task sends
exactly one channel layer message per meaningful progress increment, and the channel layer
fans that single message out to every client watching the same project simultaneously. This
means backend call volume scales with actual rendering activity rather than with the product
of users multiplied by polling frequency.

Key components of the solution:

- Install Django Channels and Daphne as the ASGI server entry point, and configure the
  project to serve both HTTP and WebSocket traffic through a single ProtocolTypeRouter ASGI
  application that dispatches connections by protocol before any Django middleware runs.

- Create a new AsyncWebsocketConsumer class named RenderProgressConsumer in the new file
  `backend/api/consumers.py`. This consumer subscribes to a named channel group derived
  from the project ID when a client connects, and unsubscribes when the client disconnects
  or the TCP connection drops, keeping group membership always accurate.

- Update `backend/storyflow_backend/asgi.py` to include a URLRouter that maps the path
  `ws/render/{project_id}/` to RenderProgressConsumer, giving each project an isolated
  channel group name that cannot collide with another project's broadcast stream.

- Modify the Celery tasks `render_project_task` and `generate_audio_task` in
  `backend/api/tasks.py` to call `channel_layer.group_send` with the current progress
  percentage and a human-readable status string each time the task advances to the next
  processing milestone, such as completing a segment encode or an audio batch.

- Update or create `frontend/hooks/useRenderProgress.ts` to open a native browser WebSocket
  within a useEffect, parse incoming JSON messages containing progress and status fields, and
  push updates into Zustand store or component state to drive the ProgressBar in real time.

- Implement a graceful fallback strategy inside the frontend hook: if the WebSocket
  connection fails (e.g., because Django Channels is not yet installed in a developer's
  environment), re-enable the original setInterval polling so the UI degrades gracefully
  and remains functional at the cost of latency rather than becoming fully broken.

- Configure InMemoryChannelLayer in `settings.py` for local development to avoid requiring
  a Redis server during early development, and document the required production switch to
  RedisChannelLayer prominently in the settings file comments and the project README.

### 1.3 Scope

| Category | Item |
|---|---|
| In Scope | WebSocket consumer for render and audio generation progress |
| In Scope | Channel group broadcast from Celery tasks on progress increment |
| In Scope | Frontend hook replacement of setInterval polling with WebSocket |
| In Scope | Graceful polling fallback if WebSocket is unavailable |
| Out of Scope | User authentication or authorization of WebSocket connections |
| Out of Scope | WebSocket support for any endpoint other than render progress |
| Out of Scope | Production Redis deployment, SSL/TLS WebSocket (wss://) setup |
| Out of Scope | Real-time collaborative editing or multi-user conflict resolution |

### 1.4 Key Files Reference

| File | Role |
|---|---|
| `backend/storyflow_backend/asgi.py` | ASGI entry point; add ProtocolTypeRouter and WebSocket URLRouter |
| `backend/api/consumers.py` | NEW — AsyncWebsocketConsumer: connect, disconnect, progress_update |
| `backend/api/tasks.py` | Celery tasks; add channel_layer.group_send on every progress write |
| `backend/storyflow_backend/settings.py` | Add daphne+channels to INSTALLED_APPS; add CHANNEL_LAYERS dict |
| `frontend/hooks/useRenderProgress.ts` | Replace setInterval polling with WebSocket; fallback on error |
| `frontend/app/projects/[id]/page.tsx` | Consume updated hook; remove legacy polling useEffect |

---

### 1.5 Architectural Considerations

Switching from a WSGI to an ASGI serving model is a cross-cutting infrastructure change
that affects how the entire backend application boots, handles connections, and is deployed.
The following considerations must be evaluated before beginning implementation:

- Django Channels adds a new in-process event loop layer managed by Daphne. Any existing
  synchronous Django middleware, authentication backends, and ORM calls continue to work
  unchanged because Channels routes HTTP traffic to the standard Django ASGI application
  internally. There is no need to convert existing views to async.

- The InMemoryChannelLayer used during development is per-process: if the backend is
  started with multiple Daphne workers (such as via gunicorn or a process manager), channel
  messages from a Celery task in one process will not reach WebSocket connections handled
  by a different process. This is the primary reason production use requires Redis.

- The `async_to_sync` wrapper from `asgiref.sync` allows the synchronous Celery task to
  call async channel layer methods. This wrapper creates a temporary event loop for the
  duration of the call and is the officially supported pattern for bridging sync Celery
  workers with the async Channels layer.

- The `start-backend.sh` and `start-backend.bat` scripts must be updated as part of this
  feature to launch Daphne on the correct ASGI application path. Running `manage.py
  runserver` after adding Django Channels to INSTALLED_APPS will not raise an error but
  will silently refuse all WebSocket upgrade requests.

---

## 2. Flow Diagram

```
Client Browser                  Django / Channels               Celery Worker
     |                                 |                               |
     |--- HTTP GET /api/projects/{id} ->|                               |
     |<-- 200 Project Data ------------|                               |
     |                                 |                               |
     |--- WS CONNECT ws/render/{id}/ ->|                               |
     |                   adds to group render_{id}                     |
     |<-- WS OPEN --------------------|                               |
     |                                 |                               |
     |   (user starts render)          |<-- render_project_task ------ |
     |                                 |       progress = 10%          |
     |                   group_send(render_{id}, progress=10)          |
     |<-- WS MSG {progress:10} --------|                               |
     |   [ProgressBar updates to 10%]  |       progress = 45%          |
     |<-- WS MSG {progress:45} --------|                               |
     |   [ProgressBar updates to 45%]  |       progress = 100%         |
     |<-- WS MSG {status:"done"} ------|                               |
     |   [UI shows complete]           |                               |
     |--- WS CLOSE ------------------->|                               |
     |                   removes from group render_{id}                |
```

---

## 3. Step-by-Step Instructions

### Step 1 — Install Dependencies and Configure Django Settings

Files: `backend/requirements.txt` and `backend/storyflow_backend/settings.py`

Add three new package lines to `requirements.txt`: `channels`, `daphne`, and
`channels-redis`. Pin each to a known compatible version range and add a comment grouping
them as "WebSocket / Channels dependencies" so future developers understand why they are
present. Run pip install on the updated file to confirm all three packages resolve without
conflict against the existing Django and Celery versions already pinned in the file.

In `settings.py`, make the following changes in order:

First, insert the string `"daphne"` as the very first item in the `INSTALLED_APPS` list.
Daphne must appear before `django.contrib.staticfiles` in the list because it installs
a custom static files handler; placing it in any other position causes a startup warning
or, in some Django versions, silently disables the static files serving override.

Second, add the string `"channels"` anywhere in `INSTALLED_APPS` after daphne. Position
does not matter for channels itself as long as it is present before the app is started.

Third, set `ASGI_APPLICATION` to the string `"storyflow_backend.asgi.application"`. This
tells Django to use your new ASGI router (defined in Step 2) as the application entry
point when served by Daphne, rather than the default wsgi.py application object.

Fourth, add a `CHANNEL_LAYERS` dictionary. For development, set the backend to
`channels.layers.InMemoryChannelLayer` with an empty `CONFIG` dict. Add a multi-line
comment above this block warning that InMemoryChannelLayer is process-local and must be
replaced with `channels_redis.core.RedisChannelLayer` and a `hosts` entry before any
multi-process or production deployment of the application.

### Step 2 — Update the ASGI Entry Point

File: `backend/storyflow_backend/asgi.py`

The existing `asgi.py` exports a single standard Django ASGI callable named `application`.
This needs to be replaced with a `ProtocolTypeRouter` that examines each incoming connection
before deciding where to send it.

The `"http"` key of the router must point to `get_asgi_application()` — the same callable
that was previously assigned directly to `application`. This preserves the full Django
request/response cycle for all REST API calls, authentication endpoints, and admin routes
exactly as they work today, with no changes to any view code.

The `"websocket"` key must point to an `AuthMiddlewareStack` wrapping a `URLRouter`. The
`AuthMiddlewareStack` populates `scope["user"]` from the session cookie so that the
WebSocket consumer can access the authenticated user if authorization checks are added
later. The `URLRouter` must contain one route: the path `ws/render/<uuid:project_id>/`
mapping to `RenderProgressConsumer` imported from `api.consumers`.

Using the `<uuid:project_id>` path converter rather than a generic string pattern is
important for two reasons: it rejects requests with non-UUID identifiers before they reach
the consumer code, and it ensures the project ID extracted in the consumer is always a
well-formed UUID string that can be safely embedded in the channel group name without
risk of whitespace, slashes, or other characters that would corrupt the group identifier.

### Step 3 — Create the WebSocket Consumer

File: `backend/api/consumers.py` (NEW FILE)

Create `backend/api/consumers.py` from scratch. This file contains the single consumer
class that manages the lifecycle of each WebSocket connection and delivers progress
messages to the browser.

Define a class `RenderProgressConsumer` that inherits from
`channels.generic.websocket.AsyncWebsocketConsumer`. Store the group name as an instance
attribute inside `connect` so it can be referenced again in `disconnect` and in tests
without re-computing it.

The `connect` method should: extract `project_id` from `self.scope["url_route"]["kwargs"]`,
construct the group name by concatenating the literal prefix `"render_"` with the project
ID string, call `await self.channel_layer.group_add(self.group_name, self.channel_name)`
to register this connection in the group, and finally call `await self.accept()` to
complete the WebSocket handshake. If `accept()` is never called, the browser's WebSocket
constructor will fire the `onerror` event instead of `onopen`.

The `disconnect` method should call `await self.channel_layer.group_discard(self.group_name,
self.channel_name)`. This must run even on abnormal closure to prevent stale channel names
from accumulating in the group and consuming memory in the channel layer.

The `progress_update` method receives the event dictionary dispatched by `group_send`.
It should extract the `progress` and `status` keys from the event, build a JSON-serializable
dictionary, serialize it to a string, and send it with `await self.send(text_data=...)`. The
method name uses an underscore rather than the dot in the type string `"progress.update"`
because Channels converts dots to underscores when routing events to handler methods.

### Step 4 — Broadcast Progress from Celery Tasks

File: `backend/api/tasks.py`

Both `render_project_task` and `generate_audio_task` currently update a progress value
(stored either in the Django database on the Project model or in a shared cache key) at
various points during their execution. This step adds a channel layer broadcast call at
each of those same points so connected WebSocket clients are notified immediately.

At the top of `tasks.py`, add two imports: `get_channel_layer` from `channels.layers` and
`async_to_sync` from `asgiref.sync`.

Inside each task function, after every line that writes the progress percentage,
add a call to `async_to_sync(channel_layer.group_send)(group_name, message_dict)`. The
`group_name` is constructed by concatenating `"render_"` with the `project_id` argument
that was passed into the Celery task. The `message_dict` must contain three keys: `"type"`
set to the string `"progress.update"` (the dot maps to the `progress_update` handler method
in the consumer), `"progress"` set to the current integer or float percentage, and
`"status"` set to a human-readable string such as `"rendering"`, `"generating_audio"`,
`"assembling"`, or `"complete"`.

The `async_to_sync` wrapper is necessary because Celery workers run as synchronous Python
processes and cannot await coroutines directly. Each call to `async_to_sync` creates a
short-lived event loop for the duration of the group_send, which is acceptable for
low-frequency progress updates. If profiling shows this overhead is a concern for
high-frequency updates, consider batching progress updates to fire at most once per second
using a timestamp guard variable at the top of the task loop.

### Step 5 — Replace Frontend Polling with WebSocket Hook

Files: `frontend/hooks/useRenderProgress.ts` and `frontend/app/projects/[id]/page.tsx`

This step replaces the polling implementation inside the custom hook with a WebSocket
connection while retaining polling as a silent fallback path.

Construct the WebSocket URL at the top of the useEffect using the environment variable
`NEXT_PUBLIC_WS_BASE_URL` (which should default to `ws://localhost:8000` in the local
`.env.local` file) concatenated with `/ws/render/${projectId}/`. Assign the result to a
local `ws` variable created with `new WebSocket(url)` inside the effect body.

Assign three event handlers to the WebSocket instance:

The `onopen` handler should set a local `isConnected` state flag to true and optionally
log a debug message. This flag is used to prevent the fallback polling interval from
firing unnecessarily while the WebSocket connection is healthy.

The `onmessage` handler should parse `event.data` as JSON, extract the `progress` and
`status` fields, and call the same state setter or Zustand action that was previously
called inside the polling fetch callback. The ProgressBar and any other UI consumers do
not need to change — only the data delivery mechanism changes from pull to push.

The `onerror` handler should call `console.warn` with a descriptive message, set the
`isConnected` flag to false, and set a `useFallbackPolling` flag to true in local state.
When `useFallbackPolling` is true, a second useEffect should activate the original
setInterval polling loop so the UI continues to function at reduced responsiveness.

The useEffect cleanup function must call `ws.close()` and clear any active polling
interval. Both the WebSocket cleanup and the interval cleanup must run when the component
unmounts and also when `projectId` changes, to prevent one project's connection from
delivering progress updates to a different project's UI after navigation.

In `page.tsx`, search for and remove any `setInterval` or `fetch` calls targeting the
render-status REST endpoint that are now handled inside the updated hook.

---

## 4. Expected Outcome

- The browser establishes a single persistent WebSocket connection per project page load.
  During an active render the backend receives zero HTTP polling requests to the
  render-status endpoint, eliminating the 150-requests-per-minute baseline with 5 users.

- The ProgressBar component updates within milliseconds of a Celery task emitting a progress
  increment, with no polling interval gap introducing artificial display latency between the
  moment work completes and the moment the user sees the progress bar advance.

- Five concurrent users watching the same project receive updates via their own WebSocket
  connections. The backend emits exactly one `group_send` broadcast per progress event and
  the channel layer fans it to all connected clients, rather than responding to N×polling
  requests per minute.

- When a render or audio generation task completes or fails, the status payload `"complete"`
  or `"error"` arrives over the WebSocket immediately and the UI transitions to the final
  state without requiring a user-initiated action or waiting for a polling cycle.

- If Django Channels is not configured or the WebSocket handshake is refused, the hook
  silently activates the original polling fallback so the feature degrades gracefully and
  the UI remains functional at the cost of higher latency and server load.

- The existing REST endpoint `GET /api/projects/{id}/render-status/` remains in place and
  is not removed, preserving backward compatibility for external scripts, CI pipelines, and
  any integration tests that currently call it directly.

- The InMemoryChannelLayer configuration in local development requires no Redis installation;
  the CHANNEL_LAYERS settings block is well-commented so developers know exactly what to
  change when preparing the application for a multi-process production environment.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] Test that `RenderProgressConsumer.connect` calls `group_add` with the group name
  `render_{project_id}` derived from the URL route kwargs and then calls `accept()`.

- [ ] Test that `RenderProgressConsumer.disconnect` calls `group_discard` with the same
  group name and raises no exception when the group was never added.

- [ ] Test that `progress_update` sends a JSON string over the WebSocket that can be
  parsed back into a dict containing the original `progress` and `status` values.

- [ ] Test that the Celery task broadcast helper correctly wraps `group_send` with
  `async_to_sync` and does not raise a RuntimeError in a fully synchronous test context.

- [ ] Test the frontend hook's fallback logic by mocking the WebSocket constructor to
  immediately call `onerror`, then asserting that after one tick a polling interval
  has been set and fetch is being called at the expected interval.

### 5.2 Integration / Manual Tests

- [ ] Start the dev server with Daphne pointing to the new ASGI application and confirm
  that all existing REST API endpoints still respond with the correct status codes.

- [ ] Open a project detail page, start a render, and verify in the browser DevTools
  Network tab that exactly one WebSocket connection opens and zero additional requests
  appear for the render-status endpoint for the duration of the render.

- [ ] Open the same project in two browser tabs simultaneously, trigger a render, and
  confirm both ProgressBar components advance in sync with each other.

- [ ] Terminate the Daphne process mid-render to simulate a WebSocket drop and confirm
  the frontend falls back to polling within 3 seconds and progress continues updating.

- [ ] Navigate away from the project page and confirm in DevTools that the WebSocket
  connection reaches the CLOSED state (code 1000) upon component unmount.

### 5.3 Regression Tests

- [ ] Confirm that the full DRF REST API test suite passes without modification after
  switching ASGI_APPLICATION to the new ProtocolTypeRouter entry point.

- [ ] Confirm that the existing Celery task unit tests pass after adding the group_send
  calls, verifying the channel layer is correctly mocked in the test fixtures.

- [ ] Confirm that the ProgressBar renders at 0% on first mount with no WebSocket message
  received and no prior polling response in state.

---

## 6. Notes for AI Agent

- The `start-backend.sh` and `start-backend.bat` scripts currently invoke `python manage.py
  runserver`. After adding Django Channels, WebSocket connections will be silently refused
  unless both scripts are updated to run Daphne pointing at the `storyflow_backend.asgi:
  application` entry point. Update both scripts as part of this feature implementation;
  do not leave them invoking `manage.py runserver` as that will cause silent WebSocket
  failures that are hard to diagnose.

- The channel group name `render_{project_id}` must be absolutely identical between the
  consumer (which constructs it in `connect`) and the Celery task (which constructs it
  before calling `group_send`). Extract this string formatting logic into a dedicated helper
  function in a shared module (e.g., `backend/api/channel_utils.py`) so both sites import
  and call the same function, eliminating the possibility of a silent mismatch that causes
  messages to be broadcast to an empty group with no error raised anywhere.

- In any production environment, `InMemoryChannelLayer` must be replaced with
  `channels_redis.core.RedisChannelLayer` configured with the correct Redis host and port.
  Store the Redis URL in an environment variable and read it in settings.py using
  `os.environ.get()` so the same settings file works in both environments.

- The WebSocket base URL in the frontend hook must be read from `NEXT_PUBLIC_WS_BASE_URL`
  rather than hardcoded. Add this variable to `.env.local` with the value
  `ws://localhost:8000` and document it in the project README so developers know to set
  it when pointing the frontend at a remote backend.

- When the WebSocket `onerror` handler activates the polling fallback, apply a brief
  exponential backoff before each re-connect attempt (starting at 1 second, doubling up
  to a ceiling of 30 seconds). This prevents a large number of simultaneous browser tabs
  from flooding the server with reconnect requests the moment a brief network interruption
  or Daphne restart occurs.

---

## 7. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| InMemoryChannelLayer left in production | Medium | High | Settings audit in deploy checklist; CI env var assertion |
| Daphne not started; WebSocket silently refused | Medium | High | Update start scripts; add startup health check log line |
| group_send in Celery raises in sync context | Low | Medium | Wrap in async_to_sync; add unit test for sync-context call |
| Frontend WebSocket URL hardcoded | Medium | Medium | Enforce NEXT_PUBLIC_WS_BASE_URL via env variable linting |
| Stale channel names accumulate in layer | Low | Low | Ensure disconnect always calls group_discard; test cleanup |
