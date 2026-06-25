# Feature 8.3 — Health Check Dashboard

| Field | Value |
|---|---|
| Feature ID | 8.3 |
| Title | Health Check Dashboard |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Low |
| Estimated Effort | 2–3 days |
| Dependencies | Django backend running, existing settings.py configuration, DRF installed |
| Output Files (NEW) | frontend/components/HealthCheckPanel.tsx, backend/api/health_probes.py |
| Files Modified | backend/api/views.py, backend/api/urls.py, frontend/app/settings/page.tsx, frontend/components/NavBar.tsx, frontend/store/healthStore.ts |

---

## 1. Document Overview

### 1.1 Problem Statement

When StoryFlow is first installed on a new machine — whether a creator's workstation, a cloud VM, or a CI environment — there is currently no mechanism to verify that all required system dependencies are correctly installed and reachable before a render is attempted, meaning a user can invest significant time configuring a project and pressing Start Render only to have it fail immediately or mid-process due to a missing binary or absent model file.
The four most common silent failure categories are: FFmpeg not found in the system PATH (renders produce no output), the Kokoro TTS ONNX model file absent from the expected models/ directory (audio generation fails), the upscaler model file missing or corrupted (upscaling step crashes), and available disk space too low to hold intermediate render artifacts (FFmpeg terminates with a cryptic I/O error).
These failures all require technical knowledge to diagnose — a non-technical creator who sees "An error occurred during rendering" has no actionable next step and is likely to abandon the tool entirely rather than investigate Python stack traces or FFmpeg error codes.
A proactive, visible health status panel visible in the settings UI, combined with a persistent warning banner when critical dependencies are missing, would catch all four failure categories before any render is started and would provide human-readable guidance rather than raw error output.

### 1.2 Proposed Solution

Add a Health Check Dashboard that runs a suite of lightweight dependency probes whenever a user visits the settings page, displays each result as a color-coded status row (green for ready, yellow for degraded, red for missing), and surfaces a dismissable application-wide banner when any probe returns a critical error. The dashboard is entirely read-only and non-destructive — it observes and reports, never modifies system state.

- Create a GET /api/system/health/ backend endpoint in views.py that runs all probes synchronously in sequence, caches the combined result in a module-level dictionary for 60 seconds to prevent hammering subprocess and disk operations, and returns a structured JSON response containing a list of check objects with name, status, detail, and icon fields.
- Implement each probe as an isolated function in a new backend/api/health_probes.py helper module: an FFmpeg probe that calls ffmpeg -version via subprocess.run and parses the first line; a TTS model probe that checks file existence and size; an upscaler model probe; an NVENC probe that calls ffmpeg -encoders and searches the output; and a disk space probe using shutil.disk_usage().
- Define clear status thresholds for each probe: FFmpeg is ok if the process returns exit code 0, error if not found; TTS model is ok if file size exceeds 50 MB, warning if present but smaller, error if absent; disk space is ok above 10 GB free, warning between 2 and 10 GB, error below 2 GB; NVENC is ok if the encoder string is present in ffmpeg -encoders output, warning otherwise.
- Create the HealthCheckPanel.tsx React component as a vertical list of status rows, each row containing a colored indicator circle, the probe name, the detail string, and a timestamp label showing when the check was last run, with a Re-check button at the top that clears the cache and fetches fresh results.
- Embed HealthCheckPanel into the settings page in a dedicated "System Status" section and add a compact status indicator to the navigation bar footer showing a summary like "5 OK" or "1 Warning" as a dot plus label combination.
- When any probe returns error status, render a dismissable full-width banner at the top of every page in the app (above the navigation) using a React context or Zustand store that holds the last health check result, allowing any page to conditionally show the banner without re-fetching.
- Add a Performance Benchmark subsection below the core dependency checks displaying the last render duration in seconds per segment and the available system RAM, sourced from a separate lightweight GET /api/system/metrics/ endpoint that reads from the Project model's render metadata and Python's psutil library.

### 1.3 Scope

**In Scope**

| Item | Description |
|---|---|
| Dependency probing | Subprocess and filesystem checks for FFmpeg, TTS model, upscaler model, NVENC, and disk space |
| Status dashboard UI | Color-coded HealthCheckPanel component embedded in the settings page |
| Global warning banner | Application-wide dismissable error banner when critical probes fail |
| 60-second server cache | Module-level result cache to prevent aggressive frontend polling from causing performance issues |

**Out of Scope**

| Item | Description |
|---|---|
| Auto-remediation | The dashboard only reports problems; it does not attempt to install missing dependencies |
| Network connectivity checks | No probing of external API endpoints, model download servers, or cloud storage |
| Real-time streaming probes | All probes run synchronously on request; no WebSocket-based live streaming of probe results |
| Multi-machine monitoring | Dashboard only monitors the local server machine; no distributed or multi-node health checks |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| backend/api/views.py | DRF API views for all project and system endpoints | Exists; health endpoint must be added as a new function-based view |
| backend/api/health_probes.py | New helper module housing each individual probe function | Does not exist; must be created from scratch with one function per probe |
| backend/storyflow_backend/settings.py | Django configuration including MEDIA_ROOT, BASE_DIR, and model paths | Exists; probe functions will read model paths from settings constants |
| frontend/app/settings/page.tsx | Settings page in the Next.js app directory | Exists; HealthCheckPanel must be imported and placed in a System Status section |
| frontend/components/HealthCheckPanel.tsx | New React component for the status row list | Does not exist; must be created with status rows, icons, and Re-check button |
| frontend/components/NavBar.tsx | Top navigation bar component | Exists; must be updated to display the compact health summary indicator |

---

## 2. Flow Diagram

    User visits Settings Page
              |
              v
    HealthCheckPanel mounts
    Calls GET /api/system/health/
              |
              v
    Backend checks module-level cache
    Cache fresh (< 60s)?
         /         \
       Yes          No
        |            |
        v            v
    Return cached   Run probes in sequence:
    result JSON     1. ffmpeg -version (subprocess)
                    2. TTS model file exists + size
                    3. Upscaler model exists
                    4. ffmpeg -encoders (NVENC check)
                    5. shutil.disk_usage (disk space)
                    6. Save result to cache
                         |
                         v
                    Return JSON {checks: [...]}
              |
              v
    Frontend renders status rows
    green / yellow / red circles
              |
         +----+----+
         |         |
         v         v
    All OK      Any error?
    "5 OK"      → Show global
    nav dot       warning banner
                  on all pages

---

## 3. Step-by-Step Instructions

### Step 1 — Create the health_probes.py helper module with all individual probe functions

Create the file backend/api/health_probes.py and import subprocess, os, shutil, and Django's settings module at the top of the file — these four imports cover every dependency needed by all probe functions without requiring any third-party packages beyond what is already in the project's requirements.txt.
Write a function called probe_ffmpeg that calls subprocess.run with the arguments list ["ffmpeg", "-version"], captures both stdout and stderr, sets a timeout of 5 seconds, catches FileNotFoundError and subprocess.TimeoutExpired, and returns a dictionary with keys name set to "FFmpeg", status set to "ok" if exit code is zero, "error" if not found, and detail set to the first line of stdout output (the version string) or an error message describing the problem.
Write a function called probe_tts_model that resolves the TTS model path by joining Django settings BASE_DIR with "models/kokoro-v0_19.onnx", checks whether the path exists using os.path.isfile, reads the file size with os.path.getsize if it exists, and returns "ok" with the size formatted as megabytes if the file exceeds 50 MB, "warning" with a truncation message if the file is present but smaller, or "error" with a not-found message if the file is absent.
Write a probe_disk_space function that calls shutil.disk_usage on the Django MEDIA_ROOT directory, computes free space in gigabytes by dividing the free bytes value by 1,073,741,824, and returns "ok" if free space exceeds 10 GB, "warning" with the exact free space value if it is between 2 and 10 GB, or "error" with an urgent message if free space falls below 2 GB; also write a probe_nvenc function that calls ffmpeg -encoders via subprocess and returns "ok" if "h264_nvenc" appears in the combined output, or "warning" with a message noting that CPU encoding will be used instead.
Write a top-level run_all_probes function that calls each individual probe function in order, assembles their return values into a list, adds log.debug calls using Django's standard logging framework to record each probe result, and assigns a suitable emoji icon field to each probe result based on its status before returning the complete list to be consumed by the view.

### Step 2 — Implement the health check view, caching, and URL registration

Open backend/api/views.py and add a module-level dictionary called _health_cache with two keys: result (initially None) and last_checked (initially zero), which will serve as the 60-second cache without requiring Redis or any additional infrastructure.
Write a function-based view called system_health_view decorated with @api_view(["GET"]) that computes the elapsed time since last_checked using time.time(), returns the cached result directly if the elapsed time is less than 60 seconds, otherwise calls run_all_probes() from health_probes.py, updates both _health_cache keys with the new result and current timestamp, and returns the probe list wrapped in a JSON response with a 200 status code.
Add a second lightweight view called system_metrics_view that reads the most recently completed project from the database, retrieves its render_time_seconds and segment count if available to compute a per-segment average, attempts to import psutil and read psutil.virtual_memory().available converted to gigabytes, and returns these values in a simple JSON object — if psutil is not installed, the RAM field should gracefully return null rather than raising an ImportError.
Open backend/api/urls.py and add two new path entries under a "system/" prefix: one for "system/health/" pointing to system_health_view and one for "system/metrics/" pointing to system_metrics_view, ensuring both URL names are unique and follow the existing naming convention used by the project-scoped endpoints.
Manually test both endpoints by starting the Django development server and using curl or the browser to call GET /api/system/health/, confirming that the response is a valid JSON object with a checks array, that calling the endpoint twice within 60 seconds returns the same cached result (verifiable by checking that the timestamps or data are identical), and that the results update after the 60-second window expires.

### Step 3 — Build the HealthCheckPanel.tsx React component

Create the file frontend/components/HealthCheckPanel.tsx as a React functional component that stores the health check results in a local state array, a loading boolean, an error string, and a lastChecked timestamp, then immediately triggers a fetch to GET /api/system/health/ on mount using a useEffect hook that calls the fetch function and updates all four state values.
Render the check results as an unordered list where each list item contains a small circular div element whose background color is set to a green, yellow, or red Tailwind color class based on the probe's status field, a bold span containing the probe name, a muted span containing the detail string, and an icon character pulled from the probe's icon field displayed at the left edge of the row.
Add a "Re-check" button in the top-right corner of the panel that, when clicked, posts to a hypothetical cache-clear logic by calling the health endpoint with a cache-bust query parameter (or simply waiting for the natural 60-second expiry and calling again), sets the loading state to true to display a spinner, and re-populates the results when the response arrives.
Add an auto-refresh behavior by storing a setInterval reference in a useRef, starting a 30-second interval on component mount that calls the fetch function repeatedly, and clearing the interval in the useEffect cleanup function when the component unmounts to prevent memory leaks and unnecessary network requests.
Add a last-updated timestamp label below the Re-check button formatted as "Last checked: X seconds ago" using a secondary useEffect or derived state, updating every second with a setInterval so the creator always knows how stale the displayed results are without needing to manually inspect the network tab.

### Step 4 — Embed the panel in the settings page and add the navigation bar indicator

Open frontend/app/settings/page.tsx and import HealthCheckPanel at the top of the file, then add a new section between the existing settings sections with a heading of "System Status" and render the HealthCheckPanel component inside it, ensuring the section has appropriate vertical padding consistent with the visual spacing of adjacent settings sections.
Create a second smaller component called HealthStatusBadge that accepts a checks prop (an array of check objects), computes the summary counts of "ok", "warning", and "error" statuses, renders a small colored dot whose color reflects the most severe status present, and displays a short label such as "5 OK" or "1 Warning, 4 OK" in the navigation sidebar or footer.
Open frontend/components/NavBar.tsx, import HealthStatusBadge, and place it in the footer section of the sidebar or at the bottom of the navigation menu — the health badge should be visually unobtrusive in the normal "all OK" state but visually prominent (using a yellow or red dot) when a warning or error is present, without obstructing other navigation elements.
Wire the HealthStatusBadge's checks data to a shared Zustand store or React context (frontend/store/healthStore.ts) so that both the badge in the navbar and the full HealthCheckPanel in the settings page read from the same cached data without making duplicate API requests; the store fetches on app initialization and updates on every Re-check action.
Test the integration by artificially renaming the FFmpeg executable on your test machine (or pointing the probe at a non-existent path), reloading the StoryFlow application, and confirming that the HealthCheckPanel shows a red row for FFmpeg, the HealthStatusBadge in the navigation shows a red dot, and the global warning banner appears at the top of the page.

### Step 5 — Implement the global warning banner and the Performance Benchmark subsection

Create a global warning banner component in frontend/components/SystemWarningBanner.tsx that reads from the health Zustand store, renders only when the store contains at least one check with status "error", displays a full-width red or amber banner with the text of the first critical error and a link labeled "View Details" that navigates to /settings, and includes a close button that sets a dismissed flag in local component state hiding the banner for the remainder of the session.
Mount the SystemWarningBanner component in the root layout file (frontend/app/layout.tsx or the equivalent root layout) so that it is rendered above all page content on every route without requiring individual pages to import it, ensuring new pages added to the application in the future automatically inherit the banner behavior.
Add a "Performance Benchmark" card below the main HealthCheckPanel in the settings page that fetches from GET /api/system/metrics/, displays the average seconds-per-segment for the most recent completed render, and displays available RAM in gigabytes, with each metric in its own labeled row using the same visual style as the health check rows.
If psutil is not yet in the project's requirements.txt, add it there and update the backend virtualenv by running pip install -r requirements.txt, then document in the README that psutil is required for the RAM metric and is installed automatically with the standard dependency installation command.
Conduct end-to-end verification of the full Health Check Dashboard by running the backend and frontend together, visiting the settings page, confirming all five probes return results, confirming the Re-check button triggers a fresh probe cycle, confirming the navigation badge updates, and reviewing the Django DEBUG logs to verify that probe results are correctly logged at the DEBUG level as specified.

---

## 4. Expected Outcome

1. Any developer or creator who installs StoryFlow on a new machine can visit the Settings page and immediately see a color-coded status panel confirming whether FFmpeg, the TTS model, the upscaler model, NVENC encoding, and disk space are all correctly configured before attempting a single render.
2. The health endpoint returns a structured JSON response within 500 milliseconds under normal conditions because all probes are lightweight synchronous operations (subprocess calls and filesystem stat operations), with results cached for 60 seconds to prevent any performance impact from frequent frontend polling.
3. When FFmpeg is missing or the TTS model file is absent, a full-width dismissable warning banner appears at the top of every page in the application, giving creators immediate visibility into the critical issue without requiring them to navigate to the settings page first.
4. The HealthCheckPanel auto-refreshes every 30 seconds while visible, so a creator who installs a missing dependency (such as downloading FFmpeg and adding it to PATH in a separate terminal) will see the relevant status row turn green without requiring a page reload.
5. The navigation bar displays a compact health summary badge that turns yellow or red when any probe is in a degraded or failed state, providing persistent ambient awareness of system health without occupying significant screen real estate.
6. The Performance Benchmark section surfaces practical machine-level data (last render speed and available RAM) that helps creators diagnose whether slow renders are caused by system constraints rather than application bugs.
7. All probe functions are cleanly isolated in health_probes.py with no side effects and no dependency on global state beyond Django settings constants, making them individually testable in unit tests without requiring a running web server or database connection.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] probe_ffmpeg returns status "ok" and a non-empty detail string when FFmpeg is installed, and returns status "error" with a descriptive message when the executable path is patched to a non-existent binary using unittest.mock.patch
- [ ] probe_tts_model returns status "ok" when the model file exists and has a size greater than 50 MB, returns "warning" when the file exists but is smaller, and returns "error" when the path does not exist
- [ ] probe_disk_space returns "ok" for a mocked disk usage with 15 GB free, "warning" for 5 GB free, and "error" for 1 GB free when shutil.disk_usage is patched with mock return values
- [ ] run_all_probes returns a list of exactly five dictionaries, each containing the keys name, status, detail, and icon, and does not raise any exceptions under normal operating conditions
- [ ] The 60-second caching logic in system_health_view returns the cached result without re-running probes when called twice within the cache window, verifiable by asserting that run_all_probes was called exactly once across two view invocations

### 5.2 Integration / Manual Tests

- [ ] Visit /settings in the browser with all dependencies installed and verify that all five health check rows display green circles and informative detail strings reflecting actual installed versions and file sizes
- [ ] Remove the kokoro ONNX model file temporarily, reload the settings page, and confirm that the TTS model row shows a red circle and a message stating the file path that was expected but not found
- [ ] Confirm the Re-check button triggers a visible loading state (spinner or dimmed rows) while the fetch is in progress, and updates the rows approximately one second later with the fresh results
- [ ] Verify the navigation bar health badge changes from "5 OK" to "1 Error, 4 OK" and changes color to red when a critical probe fails, using the same renamed-FFmpeg simulation described in Step 4
- [ ] Confirm that the global warning banner appears on the project list page (not just the settings page) when a critical probe shows an error, and disappears after clicking the close button for the remainder of the browser session
- [ ] Check the Django development server console and verify that DEBUG-level log entries appear for each probe result when the health endpoint is called, confirming that the logging integration is working

### 5.3 Regression Tests

- [ ] Confirm that the existing project create, list, update, and render-start API endpoints continue to respond correctly after adding the health check and metrics endpoints to urls.py, with no URL routing conflicts
- [ ] Confirm that the settings page renders without React errors or TypeScript type errors after adding the HealthCheckPanel import and render, both when the health endpoint returns all-OK results and when it returns a mix of statuses
- [ ] Confirm that the application root layout renders without errors when the health store contains null data (before the first health fetch completes), ensuring the banner component handles the uninitialized state gracefully rather than crashing all pages

---

## 6. Notes for AI Agent

- All subprocess calls in the probe functions must use a timeout argument (5 seconds is sufficient) and must catch both FileNotFoundError and subprocess.TimeoutExpired to handle machines where FFmpeg exists but hangs on the version query, preventing the health endpoint from timing out and blocking the web worker thread.
- The 60-second module-level cache is intentionally simple and is appropriate for a single-process Django development server; if the backend is ever run with a multi-process production server (Gunicorn with multiple workers), each worker process will maintain its own independent cache, which is acceptable since each will still maintain the 60-second rate limit per worker.
- When reading the TTS model file size in probe_tts_model, avoid opening or reading the file contents — only use os.path.getsize to prevent loading a large ONNX model binary into memory during a lightweight health check operation.
- The HealthStatusBadge and SystemWarningBanner both read from the same Zustand health store, so the store's fetch function must be called once at app initialization (in the root layout or a top-level provider component) to ensure both components have data without triggering duplicate API requests on mount.
- When testing the NVENC probe, be aware that "h264_nvenc" may appear in the ffmpeg -encoders output even on machines without an NVIDIA GPU if NVIDIA drivers were previously installed and later removed, so the "ok" status for NVENC should be treated as an informational indicator rather than a guarantee that GPU encoding will succeed at render time.
