# Feature 1.8 — Inline Image Search & Selection

| Field | Value |
|---|---|
| **Feature ID** | 1.8 |
| **Title** | Inline Image Search & Selection |
| **Status** | 🟡 Planned |
| **Priority** | Medium |
| **Complexity** | Medium |
| **Estimated Effort** | 3 days |
| **Dependencies** | Unsplash Developer Account (API key), Pexels API key |
| **Output Files (NEW)** | `backend/core_engine/stock_image_fetcher.py` |
| **Files Modified** | `frontend/components/ImageUploader.tsx`, `backend/api/views.py`, `backend/api/urls.py`, `backend/storyflow_backend/settings.py` |

---

## 1. Document Overview

### 1.1 Problem Statement

The current image workflow requires users to open an external browser tab, navigate to Unsplash or Pexels, search for a relevant image, download it to their machine, switch back to StoryFlow, and then upload the file through the existing uploader. For a project with 20 or more segments this context-switching adds up to dozens of interruptions and can easily consume more time than the editorial work itself. There is also a practical risk that downloaded files pile up in the user's downloads folder with no meaningful names, making cleanup tedious. The experience is fundamentally mismatched with StoryFlow's goal of keeping the entire production workflow inside a single interface.

### 1.2 Proposed Solution

Extend the existing `ImageUploader.tsx` component with a second tab that offers a stock image search experience entirely within the editor. Search results are fetched through a backend proxy endpoint that holds API credentials securely on the server side, preventing key exposure in the browser. Once the user selects a thumbnail, the backend downloads the full-resolution image, saves it using the same storage path used by conventional file uploads, and returns the segment image URL. The only difference the rest of the application sees is that the image arrived via a server-to-server download rather than a multipart upload.

Key implementation points:

- A tabbed layout in `ImageUploader.tsx` replaces the current single-mode uploader with two modes: "Upload File" (existing behaviour, unchanged) and "Search Images" (new).
- The "Search Images" tab contains a text input, a source selector (Unsplash or Pexels), a Search button, and a responsive thumbnail grid below.
- Results are loaded via `GET /api/stock-images/?q={query}&source={unsplash|pexels}&page={n}` — a new DRF endpoint backed by `StockImageSearchView`.
- The backend proxy calls the Unsplash or Pexels API using the `requests` library, normalises each result into a shared schema, and returns a JSON list.
- Clicking a thumbnail triggers a second backend call: `POST /api/stock-images/select/` with the chosen image metadata, prompting the server to download the full image and attach it to the segment.
- Unsplash attribution is stored as an `attribution_html` string in the segment's metadata (or a dedicated field) and rendered as a small linked credit beneath the image in the editor.
- Pexels requires a visible credit link — same approach.
- API keys are stored in Django settings and never exposed to the frontend.

### 1.3 Scope

| Category | Item |
|---|---|
| **In Scope** | Tabbed UI in `ImageUploader.tsx` with "Upload File" and "Search Images" modes |
| **In Scope** | Backend proxy endpoint for Unsplash and Pexels search results |
| **In Scope** | Server-side image download and storage on thumbnail selection |
| **In Scope** | Attribution HTML stored per segment and displayed in the editor |
| **Out of Scope** | Paid stock image services (Getty, Shutterstock) |
| **Out of Scope** | Self-hosted image crawling or caching beyond the current media storage |
| **Out of Scope** | AI-generated image integration (separate feature) |
| **Out of Scope** | Reverse image search or "find similar" functionality |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/components/ImageUploader.tsx` | Handles local file selection and FormData upload to the segment PATCH endpoint | Single-mode upload; no search tab |
| `backend/api/views.py` | DRF views for project and segment operations | No stock image endpoints exist |
| `backend/api/urls.py` | URL routing for all API endpoints | No stock image routes |
| `backend/core_engine/stock_image_fetcher.py` | NEW — helper module for stock API calls and image download | Does not exist yet |
| `backend/storyflow_backend/settings.py` | Django settings; env vars and media paths | No stock API key settings present |

---

## 2. Flow Diagram

```
User opens ImageUploader on a segment
         │
         ▼
Tabs rendered: [Upload File] | [Search Images]
         │
         ▼
User clicks "Search Images" tab
         │
         ▼
Types query, selects source (Unsplash / Pexels), clicks Search
         │
         ▼
Frontend: GET /api/stock-images/?q=...&source=...&page=1
         │
         ▼
StockImageSearchView (Django)
         │
         ├── source=unsplash → stock_image_fetcher.search_images(unsplash)
         │                         → Unsplash API call
         │
         └── source=pexels  → stock_image_fetcher.search_images(pexels)
                                 → Pexels API call
         │
         ▼
Normalised list returned to frontend
{ id, thumbnail_url, full_url, photographer,
  photographer_url, width, height, attribution_html }
         │
         ▼
Thumbnail grid rendered in UI
         │
         ▼
User clicks a thumbnail
         │
         ▼
Frontend: POST /api/stock-images/select/
  { segment_id, full_url, attribution_html, source }
         │
         ▼
Backend: stock_image_fetcher.download_image(full_url, temp_path)
         │
         ▼
Saved to segment.image_file (same path as normal upload)
attribution_html stored on segment
         │
         ▼
Response: { image_url, attribution_html }
         │
         ▼
Frontend updates segment image preview
Attribution credit rendered below image in editor
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Create the stock_image_fetcher helper module

File: `backend/core_engine/stock_image_fetcher.py` (new file)

Create a new Python module in the `core_engine` package. Define a function called `search_images` that accepts three parameters: `query` (string), `source` (string, either "unsplash" or "pexels"), and `page` (integer, defaults to 1). Inside, read the appropriate API key from Django settings using `django.conf.settings` — `UNSPLASH_ACCESS_KEY` for Unsplash and `PEXELS_API_KEY` for Pexels. Construct the correct API request URL and headers for each service, call it using `requests.get` with a reasonable timeout (10 seconds), and parse the JSON response. Map each result into a dictionary with keys: `id`, `thumbnail_url`, `full_url`, `photographer`, `photographer_url`, `width`, `height`, and `attribution_html`. For Unsplash, `attribution_html` should be a formatted anchor tag linking to the photographer's Unsplash profile with the required UTM parameters. For Pexels it should link to the photographer's Pexels page. Return the normalised list. Also define a separate function called `download_image` that accepts a `url` string and an `output_path` string, streams the GET response using `requests.get` with `stream=True`, and writes the content to `output_path` in binary mode. Raise a descriptive exception if the response status is not 200.

### Step 3.2 — Add API keys to Django settings

File: `backend/storyflow_backend/settings.py`

Near the bottom of the settings file, where other third-party service configurations are grouped, add two new constants: `UNSPLASH_ACCESS_KEY` and `PEXELS_API_KEY`. Both should read their values from environment variables using `os.environ.get(...)` with an empty-string default, rather than being hardcoded. Add a comment above each one indicating which environment variable to set. Also note in a comment that free-tier rate limits apply (Unsplash: 50 requests per hour in demo mode; Pexels: 200 requests per hour for the free tier) so that developers are aware when testing.

### Step 3.3 — Create the StockImageSearchView and select endpoint in views.py

File: `backend/api/views.py`

At the end of the views file, define a new class-based view called `StockImageSearchView` inheriting from DRF's `APIView`. Implement the `get` method to read `q`, `source`, and `page` from `request.query_params`. Validate that `q` is non-empty and that `source` is one of the allowed values; return HTTP 400 with a descriptive message if either check fails. Call `stock_image_fetcher.search_images(q, source, page)` and return the result list wrapped in a `Response`. Catch `requests.exceptions.RequestException` and any key-related errors; return HTTP 502 with a plain-language error message rather than exposing a stack trace. In the same file, define a second class-based view called `StockImageSelectView` with a `post` method. It reads `segment_id`, `full_url`, `attribution_html`, and `source` from `request.data`. It retrieves the target segment object by `segment_id`, constructs a unique file path under the project's media directory, calls `stock_image_fetcher.download_image(full_url, temp_path)`, then assigns the downloaded file to `segment.image_file` using Django's `FileField` mechanics, stores `attribution_html` in a suitable segment field, saves the segment, and returns the final image URL along with the attribution HTML.

### Step 3.4 — Register the new routes in urls.py

File: `backend/api/urls.py`

Locate the `urlpatterns` list. Add two new path entries: one for `stock-images/` mapped to `StockImageSearchView.as_view()` with the name `"stock-image-search"`, and one for `stock-images/select/` mapped to `StockImageSelectView.as_view()` with the name `"stock-image-select"`. Place them with the other non-nested API routes so they are accessible at `/api/stock-images/` and `/api/stock-images/select/` respectively.

### Step 3.5 — Extend ImageUploader.tsx with the search tab

File: `frontend/components/ImageUploader.tsx`

Locate the top-level JSX returned by the component. Wrap the existing uploader content in a tab structure using the ShadCN `Tabs`, `TabsList`, `TabsTrigger`, and `TabsContent` components. Label the first tab "Upload File" and place all current uploader content inside it unchanged. Add a second tab labelled "Search Images". Inside that tab, render a horizontal row containing a text input bound to a `searchQuery` state variable, a dropdown or toggle allowing the user to choose between "Unsplash" and "Pexels" (bound to a `source` state variable, defaulting to "unsplash"), and a "Search" button. Below the row, render a loading spinner while a request is in flight, an error message if the request failed, or a responsive grid of thumbnail images when results are available. Each thumbnail should be rendered as an image element with `object-fit: cover`, a fixed aspect ratio, and a hover overlay showing the photographer name. On click, dispatch a fetch call to `POST /api/stock-images/select/` with the required fields, show a brief loading state on the selected thumbnail, and on success call the parent's existing image-update callback with the returned image URL so the segment preview updates. Display the `attribution_html` string returned by the server directly below the image preview in the uploader (use `dangerouslySetInnerHTML` since the attribution is server-constructed and not user-provided). Pagination controls (Previous / Next) should update the `page` state variable and re-run the search.

---

## 4. Expected Outcome

1. The image upload area in every `SegmentCard` displays two tabs; users can switch between local file upload and stock image search without leaving the segment.
2. A search for any keyword returns a thumbnail grid populated from the selected stock image provider within a few seconds.
3. Clicking a thumbnail immediately triggers the server-side download and attaches the image to the segment — the preview updates in the editor within the normal network round-trip time.
4. No API keys are ever visible in the browser's network traffic, developer tools, or JavaScript bundle.
5. Attribution credits for Unsplash and Pexels images are stored with the segment and rendered in the editor, satisfying the terms of service for both free-tier APIs.
6. The existing "Upload File" tab is completely unchanged; users who prefer local uploads are unaffected.
7. Pagination allows browsing beyond the first page of results without needing to modify the search query.
8. Clear error messages appear if the API keys are missing, the external service is unavailable, or the search returns no results.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `search_images("sunset", "unsplash", 1)` returns a list of dicts each containing the required seven keys when the API key is valid.
- [ ] `search_images` raises a descriptive exception (not an unhandled `KeyError`) when the API key is missing from settings.
- [ ] `download_image` writes a non-empty file to the specified path when given a valid image URL.
- [ ] `StockImageSearchView` returns HTTP 400 when `q` is empty.
- [ ] `StockImageSearchView` returns HTTP 400 when `source` is not "unsplash" or "pexels".
- [ ] `StockImageSelectView` returns HTTP 404 when `segment_id` does not exist.

### 5.2 Integration / Manual Tests

- [ ] Open a project, navigate to a segment's image area, click the "Search Images" tab, and verify the tab renders without errors.
- [ ] Enter a search term, select "Unsplash", and click Search; verify that thumbnails appear in the grid.
- [ ] Click a thumbnail; verify the segment's image preview updates and the attribution credit appears below it.
- [ ] Switch to "Pexels" source and repeat the search; verify results appear with a Pexels attribution link.
- [ ] Click "Next" on the pagination controls; verify page 2 results are loaded.
- [ ] Upload a local file using the "Upload File" tab after having used the search tab; verify the local upload still works correctly.

### 5.3 Regression Tests

- [ ] Confirm the existing local file upload path is completely unaffected; a file selected through "Upload File" still reaches the segment PATCH endpoint as before.
- [ ] Verify that segments using stock images are rendered correctly in the video export pipeline — the image file is stored in the same location regardless of how it arrived.
- [ ] Confirm that removing a stock image from a segment (replacing it with a new upload or clearing it) also removes the stored attribution HTML.

---

## 6. Notes for AI Agent

- Unsplash's API terms require that each search request include a `utm_source` parameter linking back to the application; the application name should be "StoryFlow" — confirm the exact UTM parameters required in Unsplash's developer documentation before deploying.
- The `download_image` function should save to a temporary path first and only move the file to the final segment media path after the download completes successfully; this prevents partially downloaded files from being stored as segment images.
- The Segment model may not currently have an `attribution_html` field; check `backend/api/models.py` and add a `TextField` with `blank=True, default=""` if the field is absent, generating and applying the corresponding migration before implementing the view logic.
- Rate-limiting is a real concern during development: use a mock or cached response fixture in tests rather than hitting the live Unsplash or Pexels API on every test run, to avoid exhausting the demo-tier quota.
- The thumbnail grid in the frontend should use `loading="lazy"` on image elements to avoid fetching all thumbnails simultaneously on a slow connection; stagger or virtualise the grid if more than 30 results are displayed per page.
