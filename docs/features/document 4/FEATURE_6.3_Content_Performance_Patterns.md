# Feature 6.3 — Content Performance Patterns

| Field | Value |
|---|---|
| Feature ID | 6.3 |
| Title | Content Performance Patterns |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Medium |
| Estimated Effort | 3–4 days |
| Dependencies | Each project must reach "render complete" status before a metric record is created; Feature 6.2 (`target_platform` field on `Project`) recommended |
| Output Files (NEW) | `backend/api/models.py:ProductionMetrics`, `frontend/app/analytics/page.tsx`, `frontend/components/ProductionInsightCard.tsx` |
| Files Modified | `backend/core_engine/video_renderer.py`, `backend/api/views.py`, `backend/api/urls.py`, `frontend/components/Sidebar.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

A creator using StoryFlow who has produced fifty or more videos has no way to examine their own production habits or identify workflow inefficiencies. They do not know whether their shorter videos take less time per segment to produce, which voice they use most frequently, or whether their Monday evening sessions consistently result in more retakes than their weekend morning sessions. All of this information is implicitly present in the system — timestamps, segment counts, voice selections, and render durations are already stored — but it is never aggregated or surfaced in any meaningful way. Without a structured analytics layer, creators cannot make data-informed decisions about how to schedule their work, which content formats suit their workflow, or whether switching voices or platforms would improve their throughput.

### 1.2 Proposed Solution

Automatically capture a lightweight metrics record whenever a video render completes, then expose an analytics dashboard in the frontend that summarizes production patterns over time in simple visual displays. The data collection is invisible to the creator and requires no manual input — it simply logs the facts of what was produced and how long it took. The frontend dashboard translates this raw data into actionable insights presented as plain-language statements.

- Add a `ProductionMetrics` model to `backend/api/models.py` with a one-to-one relationship to `Project`, capturing segment count, total duration, voice identifier, platform, render duration in seconds, and the datetime of render completion
- In `backend/core_engine/video_renderer.py`, at the point where the output video file is finalized and saved, create or update the `ProductionMetrics` record for the associated project in a single `update_or_create` call
- Add a backend API endpoint `GET /api/analytics/production-patterns/` that aggregates `ProductionMetrics` records and returns summary statistics including per-platform averages, per-weekday production counts, duration bucket efficiency, and a computed list of natural-language insight strings
- Create a new frontend page `frontend/app/analytics/page.tsx` that fetches the patterns endpoint on load and renders bar charts, a frequency table, and insight cards
- Add an "Analytics" navigation entry to `frontend/components/Sidebar.tsx` pointing to `/analytics` so creators can reach the dashboard from any page in the application
- Define duration buckets (0–5 min, 5–10 min, 10–20 min, 20+ min) as constants in the backend analytics view to bucket projects by approximate video length for efficiency comparison
- Show an empty state gracefully when fewer than five projects have been rendered — display a motivational message: "Produce at least 5 videos to see your production patterns" and a progress bar toward that threshold

### 1.3 Scope

| Category | In Scope |
|---|---|
| In Scope | Automatic capture of render metrics (segment count, duration, voice, platform, render time) on every completed render |
| In Scope | Backend aggregation endpoint returning weekday counts, platform averages, duration-bucket efficiency, and plain-language insights |
| In Scope | Frontend analytics page with bar charts, frequency display, and insight callout cards |
| In Scope | Link to the analytics page in the left navigation sidebar |

| Category | Out of Scope |
|---|---|
| Out of Scope | Exporting analytics data to external systems (Google Analytics, Mixpanel, CSV download) |
| Out of Scope | Real-time or streaming analytics — the dashboard reflects data from completed renders only |
| Out of Scope | Multi-user comparison or team-level analytics — all metrics are per-installation |
| Out of Scope | Predictive suggestions ("you should produce on Tuesday") — only historical pattern display is in scope |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/api/models.py` | Django ORM models including Project, Segment, GlobalSettings | Exists; add `ProductionMetrics` model here |
| `backend/core_engine/video_renderer.py` | Renders final video from project assets; writes output file | Exists; add metric capture at render completion |
| `backend/api/views.py` | DRF views and API endpoints | Exists; add `ProductionPatternsView` aggregation endpoint |
| `backend/api/urls.py` | API URL routing | Exists; register the new analytics endpoint path |
| `frontend/app/analytics/page.tsx` | Analytics dashboard page | Does not exist; must be created |
| `frontend/components/Sidebar.tsx` | Left navigation sidebar | Exists; add "Analytics" link entry |

---

## 2. Flow Diagram

```
Video render completes in video_renderer.py
          │
          ▼
Capture render metadata:
  - segment_count: Segment.objects.filter(project=project).count()
  - total_duration_seconds: sum of segment audio durations
  - voice_id: most-used voice in project render_settings
  - platform: project.target_platform
  - render_duration_seconds: (now - render_start_time).total_seconds()
  - rendered_at: datetime.now()
          │
          ▼
ProductionMetrics.objects.update_or_create(project=project, defaults={...})
          │
──────────┼────────────── (collection complete, async safe) ───────────
          │
          ▼
Creator navigates to /analytics in frontend sidebar
          │
          ▼
GET /api/analytics/production-patterns/
          │
          ▼
ProductionPatternsView.get() — runs aggregation queries:
  ├── Count renders per weekday (Monday–Sunday)
  ├── Average render time per duration bucket
  ├── Most-used voice (mode of voice_id)
  ├── Average segment count per platform
  └── Compute insight strings: top weekday, fastest bucket, etc.
          │
          ▼
Return JSON: { weekday_counts, duration_efficiency,
               platform_stats, top_voice, insights[] }
          │
          ▼
frontend/app/analytics/page.tsx fetches data on mount
          │
          ├── Weekday bar chart (recharts BarChart)
          ├── Duration efficiency bar chart
          ├── Platform breakdown table
          └── Insight cards (ProductionInsightCard × N)
```

---

## 3. Step-by-Step Instructions

### Step 1 — Add the ProductionMetrics model and run migration

In `backend/api/models.py`, define a new model `ProductionMetrics` below the existing `Segment` model. It has the following fields: `project` as a `OneToOneField` to `Project` with `on_delete=CASCADE` and `related_name="production_metrics"`; `segment_count` as a `PositiveIntegerField`; `total_duration_seconds` as a `FloatField(default=0.0)` representing the total audio duration in seconds; `voice_id` as a `CharField(max_length=100, blank=True, default="")` holding the voice identifier string from the render settings; `target_platform` as a `CharField(max_length=50, blank=True, default="youtube")` mirroring the platform the project was produced for; `render_duration_seconds` as a `FloatField(default=0.0)` representing how many seconds the rendering process itself took from start to finish; `retake_count` as a `PositiveIntegerField(default=0)` recording how many audio regenerations occurred before final render; and `rendered_at` as a `DateTimeField` storing the exact moment render was declared complete. Add a `__str__` method returning `f"Metrics for {self.project.name}"`. After saving the model, run `python manage.py makemigrations` and `python manage.py migrate` to create the corresponding database table. Register `ProductionMetrics` in `backend/api/admin.py` for visibility in the Django admin panel.

### Step 2 — Capture metrics at render completion in video_renderer.py

In `backend/core_engine/video_renderer.py`, identify the function or code block that runs after the output video file has been successfully written to disk (approximately after the final `ffmpeg` subprocess call and file existence check). At that point, import `datetime` and import `ProductionMetrics` from `backend.api.models` at the top of the file (use a deferred import inside the function body to avoid circular imports if needed). Record `render_end_time = datetime.datetime.now()` and compute `render_duration = (render_end_time - render_start_time).total_seconds()` where `render_start_time` should be captured at the beginning of the render function. Compute `total_duration_seconds` by summing the audio file durations for all segments in the project. Extract `voice_id` from `project.render_settings.get("voice_id", "")`. Extract `target_platform` from `project.target_platform` if that field exists, or from `project.render_settings.get("target_platform", "youtube")`. Call `ProductionMetrics.objects.update_or_create(project=project, defaults={"segment_count": segment_count, "total_duration_seconds": total_duration_seconds, "voice_id": voice_id, "target_platform": target_platform, "render_duration_seconds": render_duration, "rendered_at": render_end_time})` to persist the record. Wrap this in a broad `try/except Exception` so that any metrics capture failure never interrupts the render result being returned to the caller.

### Step 3 — Add the aggregation endpoint in views.py

In `backend/api/views.py`, create a new class `ProductionPatternsView(APIView)`. The `get(self, request)` method fetches all `ProductionMetrics` records via `ProductionMetrics.objects.select_related("project").all()`. If fewer than five records exist, return an early response `{insufficient_data: true, recorded_renders: count, required_renders: 5}` so the frontend can show the empty state. Otherwise, compute the following aggregations using Python: `weekday_counts` is a dictionary mapping weekday names ("Monday" through "Sunday") to the count of `rendered_at` records falling on that day; `duration_efficiency` is a list of `{bucket, avg_render_duration_seconds, count}` objects where buckets are "0–5 min", "5–10 min", "10–20 min", "20+ min" based on `total_duration_seconds`; `platform_stats` is a dictionary of `{platform: {count, avg_segments, avg_duration_seconds}}` aggregated by `target_platform`; `top_voice` is the most frequent `voice_id` value across all records; and `insights` is a list of plain-language strings generated from the aggregated data (e.g., `"You produce most content on Tuesdays (12 videos)"`, `"Your fastest content bucket is 5–10 min (avg 18 min render time)"`, `"af_bella is your most-used voice with 34 productions"`). Return all of this in a single JSON response. In `backend/api/urls.py`, register `path("analytics/production-patterns/", ProductionPatternsView.as_view())`.

### Step 4 — Create the analytics page in the frontend

Create `frontend/app/analytics/page.tsx` as a new Next.js page component. At mount, use `useEffect` plus `fetch` (or the existing API client) to call `GET /api/analytics/production-patterns/`. Store the response in a `data` state variable. If `data.insufficient_data` is `true`, render a centered empty-state card with the message "Produce at least 5 videos to begin seeing your production patterns" and a subtle progress bar showing `data.recorded_renders / 5`. When data is available, render four sections: a "Production by Day of Week" horizontal bar chart using `recharts BarChart` where each bar represents the weekday count; a "Render Efficiency by Duration" grouped bar chart comparing average render duration per duration bucket; a "Platform Breakdown" simple HTML table showing count, average segments, and average duration per platform; and an "Insights" section at the page bottom where each string in `data.insights` is rendered as a `<ProductionInsightCard>` component (described in Step 5). Use TailwindCSS grid and card patterns consistent with the rest of the frontend, and include a page title "Your Production Patterns" with a brief subtitle "Based on your completed video renders in StoryFlow."

### Step 5 — Create ProductionInsightCard and update the Sidebar

Create `frontend/components/ProductionInsightCard.tsx` as a simple presentational card component. It accepts a single `insight: string` prop. Render it as a rounded card with a light background and a left accent border. Prefix each insight with a lightbulb emoji rendered as an icon or a Unicode symbol. The card text is the raw insight string; no truncation or parsing is needed since insights are pre-formatted plain language from the backend. Ensure the card has appropriate padding and a subtle drop shadow to distinguish it from the surrounding page background. In `frontend/components/Sidebar.tsx`, add a new navigation entry for "Analytics" pointing to `/analytics`. Position it below "Projects" in the navigation order. If the total render count is available from a global store or can be obtained via a lightweight API call, show a small dark badge next to the "Analytics" label displaying the total number of projects rendered — this serves as a subtle engagement incentive for users who have not yet visited the analytics page.

---

## 4. Expected Outcome

1. Every time a render completes successfully, a `ProductionMetrics` record is automatically created or updated for that project — creators never need to manually log anything.
2. After at least five projects have been rendered, the analytics dashboard at `/analytics` populates with meaningful visualizations showing weekday production frequency, video duration efficiency, and platform breakdown.
3. The "Insights" section surfaces two to four plain-language pattern observations (e.g., most productive day, fastest content length, most-used voice) derived from the creator's actual production history.
4. The empty state for fewer than five renders is clean and motivating — it shows a progress indicator so creators understand exactly how close they are to unlocking the insights.
5. The analytics dashboard renders on the client without any perceptible loading jitter — the endpoint response is fast because `ProductionMetrics` is a single small table with no expensive joins.
6. If a render fails mid-way and never reaches the completion callback, no `ProductionMetrics` record is written for that render — the analytics only reflect successfully produced content.
7. The feature is entirely additive and non-invasive — existing render behavior, project management, and segment editing are completely unaffected by the presence of the new model and endpoint.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `ProductionPatternsView.get()` returns `{insufficient_data: true}` when fewer than five `ProductionMetrics` records exist
- [ ] `weekday_counts` correctly maps each production record's `rendered_at` weekday to the count bucket — verify with a set of mock records spanning multiple weekdays
- [ ] The duration bucket assignment logic places a record with `total_duration_seconds = 420` (7 min) into the "5–10 min" bucket, not "0–5 min"
- [ ] The `insights` list contains at least one string and all strings are non-empty when five or more records exist
- [ ] The `update_or_create` call in `video_renderer.py` does not raise an exception when called twice for the same project (idempotency check)

### 5.2 Integration / Manual Tests

- [ ] Render three complete projects, then visit `/analytics` — verify the empty state card appears with a progress bar showing `3/5`
- [ ] Render two additional projects (reaching 5 total), then reload `/analytics` — verify the charts and insights section appear with data
- [ ] Verify the "Production by Day of Week" bar chart shows the correct count for the day of the week on which the test renders were performed
- [ ] Change the voice setting on a project before rendering and confirm the `ProductionMetrics.voice_id` field reflects the updated voice
- [ ] Deliberately abort a render (kill the process mid-render) and confirm that no `ProductionMetrics` record is created or updated for the aborted project
- [ ] Click the "Analytics" sidebar link from the Projects page and confirm the route navigates to `/analytics` without a full page reload

### 5.3 Regression Tests

- [ ] Existing render pipeline (`POST /api/projects/{id}/render/`) continues to produce correctly formatted output video files with no change in behavior after the `ProductionMetrics.update_or_create` call is added to the completion callback
- [ ] The `Project` and `Segment` list endpoints (`GET /api/projects/`, `GET /api/segments/`) return the same schema as before — the new `ProductionMetrics` model does not inject any unexpected fields into existing serializer responses
- [ ] The Django admin panel loads without errors and displays the `ProductionMetrics` table correctly after the new migration has been applied

---

## 6. Notes for AI Agent

- The `ProductionMetrics` record must be created inside a `try/except` block in `video_renderer.py` because the render completion path is a critical section — any unhandled exception from analytics capture would silently swallow the render result or crash a Celery worker, which is a far more serious failure than missing one data point
- When computing `total_duration_seconds` for the metrics record, prefer reading the duration from the audio files' actual length rather than from the render settings target duration, because creators often adjust individual segment timings and the actual audio track length is the ground truth for analytics purposes
- Recharts is likely already installed in the frontend as a dependency (check `frontend/package.json`) — if it is not, add it rather than using a heavier charting library that would increase bundle size; the charts here are simple enough that Recharts' `BarChart` and `PieChart` components are fully sufficient
- The `insights` list computed in the backend view should always be bounded to at most six strings to prevent the frontend insight section from becoming overwhelming — if more patterns are detected, surface only the six most statistically significant ones based on the highest deviation from the average
- Do not attempt to infer semantic patterns from prompt text content (e.g., "you mostly produce cooking content") — the analytics are strictly behavioral and quantitative (counts, durations, timing) to avoid any need for text processing or AI inference that would slow down the aggregation endpoint
