# Feature 3.1 — Production Dashboard

| Field | Value |
|---|---|
| Feature ID | 3.1 |
| Title | Production Dashboard |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Medium |
| Estimated Effort | 3–4 days |
| Dependencies | Feature 1.1 (provides target_platform on Project); recharts npm package must be installed |
| Output Files (NEW) | frontend/components/dashboard/StatCard.tsx, frontend/components/dashboard/CategoryDonutChart.tsx, frontend/components/dashboard/WeeklyBarChart.tsx, frontend/components/dashboard/StatusBreakdown.tsx |
| Files Modified | backend/api/models.py, backend/api/serializers.py, backend/api/views.py, backend/api/urls.py, frontend/app/page.tsx |

---

## 1. Document Overview

### 1.1 Problem Statement

The current StoryFlow dashboard page presents only a basic list of existing projects without any aggregated production analytics, giving creators no insight into their content output patterns over time.
Creators who are building a consistent content pipeline have no way to understand how many videos they produce per week, how long each production cycle takes on average, whether their output volume is trending upward or downward, or how their completed content is distributed across topic categories.
Without aggregated production data, creators cannot make informed decisions about their workflow: they cannot identify bottlenecks, set realistic weekly production goals, or demonstrate to collaborators that their pipeline is consistently delivering results.
The absence of a high-level analytics view also reduces creator motivation — there is no vanity metric equivalent to a "you have produced N hours of content" counter, which research consistently shows drives productive creative behaviors in solo creators.

### 1.2 Proposed Solution

The Production Dashboard feature replaces the existing minimal dashboard page with a rich analytics surface that aggregates historical production data from the `Project` model and presents it through a combination of large numeric stat cards, interactive charts, and structured breakdowns. A new backend API endpoint performs all aggregation server-side so that the frontend remains free of complex data manipulation and the response is cacheable at the HTTP layer. The frontend implements the dashboard as a collection of focused subcomponents — each responsible for a single visualization type — rather than one monolithic page component, making each visualization independently testable and reusable. The entire dashboard data lifecycle uses a straightforward fetch-on-mount pattern with a sixty-second client-side cache, balancing freshness against unnecessary API calls during normal navigation.

- A `category` field is added to the `Project` model with a set of enumerated content category choices, enabling grouping of projects by topic.
- A new backend endpoint `GET /api/stats/production-summary/` performs all aggregation queries and returns a single structured JSON response with counts, averages, and per-group breakdowns.
- A row of large numeric `StatCard` components at the top of the dashboard displays total videos, videos this week, this month, and average production time.
- A `CategoryDonutChart` component renders a recharts `PieChart` showing the distribution of completed projects across content categories.
- A `WeeklyBarChart` component renders a recharts `BarChart` displaying the count of projects created in each of the last eight calendar weeks.
- A `StatusBreakdown` component renders a horizontal stacked-bar visualization comparing the count of projects in Draft, Rendering, and Complete status.
- A "Total Content Minutes" counter is shown prominently near the top of the dashboard as a large motivating vanity metric that updates whenever fresh data is fetched.

### 1.3 Scope

| Category | Item |
|---|---|
| In Scope | Adding the `category` CharField to the Project model and including it in the serializer |
| In Scope | Building the `GET /api/stats/production-summary/` aggregation endpoint |
| In Scope | Building the four dashboard subcomponents (StatCard, CategoryDonutChart, WeeklyBarChart, StatusBreakdown) |
| In Scope | Replacing the existing minimal frontend dashboard page with the new analytics layout |
| Out of Scope | Real-time WebSocket dashboard updates — polling or manual refresh is sufficient |
| Out of Scope | Per-user authentication or multi-user analytics isolation |
| Out of Scope | Exporting dashboard data to CSV or PDF |
| Out of Scope | Custom date-range filtering on any of the charts |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| backend/api/models.py | Defines the Project model including all database fields and choices | Exists; Project has status, created_at, render_settings but no category field |
| backend/api/views.py | DRF views for all existing API operations — new stats endpoint goes here | Exists; has project CRUD views but no aggregation or stats views |
| backend/api/urls.py | URL routing for all backend API endpoints | Exists; needs a new URL pattern for /api/stats/production-summary/ |
| backend/api/serializers.py | DRF serializers for Project and Segment models | Exists; needs category field added to ProjectSerializer |
| frontend/app/page.tsx | The main dashboard page component loaded at the application root | Exists; currently renders a minimal project list; needs to become the analytics dashboard |

---

## 2. Flow Diagram

    User navigates to frontend root route  "/"
                |
                v
    frontend/app/page.tsx mounts
    Checks client-side 60-second cache (SWR or useState + timestamp)
                |
          Cache stale or empty?
          /             \
        YES              NO
         |                |
         v                v
    fetch GET             Use cached data
    /api/stats/           |
    production-summary/   |
         |                |
         v                |
    Django receives request    <---------+
    runs aggregation queries:
      - Project.objects.count()
      - weekly buckets (last 8 weeks)
      - group by category
      - group by status
      - avg duration proxy
      - sum of estimated content minutes
                |
                v
    Returns JSON: { total, thisWeek, thisMonth,
                    avgProductionHours, byCategory,
                    byStatus, weeklyBuckets,
                    totalContentMinutes,
                    lastRefreshedAt }
                |
                v
    frontend/app/page.tsx receives JSON
    Sets dashboardData state
                |
                v
    Renders layout:
      [Total Content Minutes banner]
      [StatCard row: Total | This Week | This Month | Avg Time]
      [CategoryDonutChart]  [WeeklyBarChart]
      [StatusBreakdown horizontal bar]
      [Last refreshed: 14 seconds ago]

---

## 3. Step-by-Step Instructions

### Step 1 — Add Category Field to the Project Model

Open `backend/api/models.py` and locate the `Project` model class.
Immediately above the class body, define a module-level `CATEGORY_CHOICES` tuple of two-tuples covering the following category keys and labels: `("history", "History")`, `("science", "Science")`, `("horror", "Horror")`, `("educational", "Educational")`, `("entertainment", "Entertainment")`, and `("other", "Other")`.
Inside the Project class body, add a new field `category` defined as a `CharField` with `max_length=50`, `choices=CATEGORY_CHOICES`, `blank=True`, and `default=""` so that existing projects remain valid after migration and the field is entirely optional when creating new projects.
After saving the model file, run `python manage.py makemigrations api` from within the `backend/` directory to generate the migration, then run `python manage.py migrate` to apply the `category` column to the SQLite database without affecting any existing project rows.
Open `backend/api/serializers.py` and add the string `"category"` to the `fields` list in the `ProjectSerializer` Meta class so that the category value is returned in all project API responses and can be set in POST and PATCH request bodies.
Verify the change works correctly by creating or patching a test project using the DRF browsable API at `/api/projects/` and confirming that a category value is accepted and returned in the response.

### Step 2 — Build the Production Summary API Endpoint

Open `backend/api/views.py` and add a new view at the bottom of the file — this can be a plain Django REST Framework `APIView` subclass or a function-based view decorated with `@api_view(["GET"])`, whichever style is consistent with the rest of the project's view conventions.
Inside the view handler, import Django's `Count`, `Avg`, and `F` from `django.db.models` at the top of the file if not already present, then run the following aggregation queries against the `Project` model: total project count using `Project.objects.count()`; weekly counts for the last eight calendar weeks by iterating over date boundaries and counting projects whose `created_at` falls within each week; per-category counts using `Project.objects.values("category").annotate(count=Count("id"))`; per-status counts using the same `values` and `annotate` pattern on the `status` field; a simplified average production time proxy calculated as the average of `(updated_at - created_at)` converted to hours; and total estimated content minutes summed from segment count multiplied by an assumed average segment duration constant of ten seconds.
Assemble all aggregation results into a single Python dictionary containing the keys `total`, `thisWeek`, `thisMonth`, `avgProductionHours`, `byCategory` (list of dicts), `byStatus` (list of dicts), `weeklyBuckets` (list of week-label and count pairs), `totalContentMinutes` (integer), and `lastRefreshedAt` (ISO 8601 string of `datetime.now()`).
Return the assembled dictionary using `Response(data)` so DRF serializes it to JSON automatically.
Open `backend/api/urls.py` and add a new URL pattern routing `GET /api/stats/production-summary/` to the new view, using `path("stats/production-summary/", views.ProductionSummaryView.as_view(), name="production-summary")` or its function-view equivalent.

### Step 3 — Build the Dashboard Subcomponents

Create the directory `frontend/components/dashboard/` and add four new TypeScript React component files inside it.
Create `StatCard.tsx` — a simple presentational component that accepts `label` (string), `value` (string or number), `subtext` (optional string), and `highlight` (optional boolean) props, and renders them inside a white card div with a large bold value, a smaller label below it, and an optional subtext line; when `highlight` is true, apply a colored left border or top accent to visually distinguish the most important cards from the others.
Create `CategoryDonutChart.tsx` — a component that accepts a `data` prop typed as `Array<{ category: string; count: number }>` and renders a recharts `PieChart` with an inner-radius `Pie` to produce the donut shape; include a `Tooltip` and a `Legend` configured to show the category label and item count; use a hand-picked set of accessible chart colors defined in an inline constant array rather than relying on recharts defaults.
Create `WeeklyBarChart.tsx` — a component that accepts `data` typed as `Array<{ weekLabel: string; count: number }>` and renders a recharts `BarChart` with a single `Bar`, an `XAxis` using `weekLabel`, a `YAxis`, a `Tooltip`, and `CartesianGrid` with light stroke color; keep the chart height fixed at 240 pixels and ensure labels are readable without rotation.
Create `StatusBreakdown.tsx` — a component that accepts `data` typed as `Array<{ status: string; count: number; color: string }>` and renders a horizontally-stacked bar built entirely from CSS flex divs rather than a charting library, with each segment proportionally sized by count; the simplicity of this approach makes the component lightweight and easy to style with Tailwind.

### Step 4 — Rebuild the Frontend Dashboard Page

Open `frontend/app/page.tsx` and read the current structure — it likely renders a heading and a project list component.
Add a `dashboardData` state variable (initialized to `null`) and a `lastFetchedAt` timestamp state variable (initialized to zero), then inside a `useEffect` hook, implement a simple cache check: if `Date.now() - lastFetchedAt > 60000` (sixty seconds), fetch `GET /api/stats/production-summary/`, update `dashboardData` with the JSON response, and update `lastFetchedAt` to `Date.now()`.
Below the existing project list or as a separate tab, add the full analytics layout: a large `Total Content Minutes` banner at the top styled with a prominent font size and a motivating label such as "Total minutes of content produced"; a horizontal row of four `StatCard` instances using `total`, `thisWeek`, `thisMonth`, and `avgProductionHours` from `dashboardData`; a two-column grid row containing the `CategoryDonutChart` on the left and the `WeeklyBarChart` on the right; and the `StatusBreakdown` component spanning the full width below the charts.
Add a "Last refreshed" text element at the bottom of the dashboard section that displays a human-readable relative time string such as "Last refreshed 42 seconds ago", computed from `Date.now() - lastFetchedAt` at render time.
Add a "Refresh" icon button next to the "Last refreshed" label that, when clicked, resets `lastFetchedAt` to zero and re-triggers the `useEffect` fetch logic so the creator can manually force a data refresh without waiting for the sixty-second window to expire.

### Step 5 — Add Duration Estimate to Project List Entries

Open `frontend/app/page.tsx` (or the project list subcomponent it uses) and locate the JSX that renders each project row or card in the project list.
Import the render estimate utility function from `frontend/lib/renderEstimates.ts` (created in Feature 1.1 or as a new file if Feature 1.1 was not yet implemented) — the function should accept a segment count and a bitrate in Kbps and return a formatted duration string.
For each project in the list, add a small subtitle text element beneath or alongside the project title that displays the estimated video duration formatted as "~N min M sec", computed from the project's current segment count multiplied by the assumed average segment duration of ten seconds.
Style this estimated duration label using a muted text color (e.g., `text-gray-400` in Tailwind) and a smaller font size so it is clearly supplementary information and does not compete visually with the project title or status badge.
This per-project duration estimate feeds into the `totalContentMinutes` vanity metric on the dashboard, and making it visible inline on the project list helps creators cross-reference the dashboard total with their individual projects to build intuition about the numbers.

---

## 4. Expected Outcome

1. When a user navigates to the StoryFlow root URL, the page displays a full analytics dashboard featuring a prominent "Total Content Minutes" banner, four stat cards, two charts, and a status breakdown — replacing the previous minimal project list view.
2. The four stat cards clearly show total projects ever created, projects created in the current calendar week, projects created in the current calendar month, and average production time in hours, all with human-readable labels.
3. The category donut chart shows a proportional breakdown of projects by their content category, displaying both the chart and a legend, with a graceful "No data" empty state if no projects have a category set.
4. The weekly bar chart shows the project creation count for each of the last eight calendar weeks on a labeled axis, making production trend patterns immediately visible without requiring any data literacy from the creator.
5. The status breakdown section shows how many projects are in each status — Draft, Rendering, and Complete — as a proportional horizontal bar, helping creators understand what stage most of their work is currently at.
6. The dashboard data is fetched once on page load and cached for sixty seconds; navigating away and returning within the cache window shows the same data instantly without a loading spinner.
7. Each project row in the project list now displays an estimated video duration beneath its title, so creators can see at a glance how much content each project will produce before clicking into it.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] Test that the `ProductionSummaryView` returns a 200 response with a JSON body containing all expected top-level keys (`total`, `thisWeek`, `thisMonth`, `avgProductionHours`, `byCategory`, `byStatus`, `weeklyBuckets`, `totalContentMinutes`, `lastRefreshedAt`).
- [ ] Test that `byCategory` in the production summary response correctly counts projects grouped by category when test projects with known categories are seeded into the database.
- [ ] Test that `weeklyBuckets` returns exactly eight entries even when some weeks have zero projects, confirming that empty weeks are not simply omitted from the response.
- [ ] Test that the `ProjectSerializer` correctly accepts and returns the `category` field for all defined choice values and rejects values not in the choices list.
- [ ] Test that `StatCard` renders its `value` and `label` props as visible text elements in the DOM and applies the highlighted border style when the `highlight` prop is true.

### 5.2 Integration / Manual Tests

- [ ] Load the dashboard page with several projects in the database across different categories and statuses, and visually confirm that all four visualization components render data that matches the known project counts.
- [ ] Create a new project, assign it a category, then return to the dashboard and manually click the refresh button — confirm that the new project's category appears in the donut chart data.
- [ ] Navigate away from the dashboard to the project editor and then navigate back within thirty seconds — confirm that the dashboard re-renders immediately using cached data with no loading spinner shown.
- [ ] Wait more than sixty seconds after the initial page load, then return to the dashboard — confirm that a fresh fetch fires and the "Last refreshed" timestamp updates to reflect the new fetch time.
- [ ] Open Django admin or the DRF browsable API and verify that the production summary endpoint is accessible at the correct URL path and returns sensible data without authentication errors in the current development configuration.
- [ ] Verify that the estimated duration label on each project list row shows a plausible duration string based on the actual segment count of that project and updates correctly if a project is edited to add or remove segments.

### 5.3 Regression Tests

- [ ] Confirm that all existing project CRUD API endpoints continue to return their expected response shapes after `category` is added to the Project model and serializer, with no previously-present fields removed or renamed.
- [ ] Confirm that the project list view still renders correctly and the individual project editor page still loads without errors after the root dashboard page layout is replaced with the new analytics layout.
- [ ] Confirm that the Django migration generated for the `category` field applies cleanly against a database that has existing project rows, converting existing blank `category` values to empty strings without raising an IntegrityError.

---

## 6. Notes for AI Agent

- When computing the `weeklyBuckets` list in the backend view, do not rely on the database engine's date-truncation functions if the project is using SQLite, since SQLite has limited native date-arithmetic support compared to PostgreSQL; instead, fetch all projects' `created_at` values in a single query and perform the weekly bucketing in pure Python using `datetime.timedelta` comparisons, which is more portable and equally performant for the expected data volumes.
- The recharts library must be installed in the frontend before creating the chart components — run `npm install recharts` from the `frontend/` directory; recharts ships its own TypeScript type definitions since version 2.1 so no separate `@types/recharts` package is needed.
- The sixty-second client-side cache can be implemented with a simple `useState` storing the last fetch timestamp and a `useEffect` dependency on that timestamp, or with a lightweight SWR-style hook already present in the project; avoid importing a full external SWR library just for this one feature unless the project already uses one.
- When building the `CategoryDonutChart`, always render a graceful empty state (a centered "No categories assigned yet" message) when the `data` prop is an empty array or all counts are zero — recharts `PieChart` does not handle empty data gracefully by default and will throw a runtime warning in the browser console if a `Pie` element receives zero-length data without a guard.
- The `totalContentMinutes` calculation on the backend uses segment count multiplied by a ten-second constant as an approximation; add a comment in the view code explaining this assumption so future developers do not treat the value as an exact measurement, and note that once actual TTS audio file durations are stored on the Segment model, the calculation should be updated to use real audio durations instead.
