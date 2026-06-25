# Feature 6.4 — Font Browser

| Field | Value |
|---|---|
| Feature ID | 6.4 |
| Title | Font Browser |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Medium |
| Estimated Effort | 3 days |
| Dependencies | Subtitle preview infrastructure; `GlobalSettings.subtitle_font` field must exist; backend fonts directory must be accessible |
| Output Files (NEW) | `frontend/components/FontBrowser.tsx`; `backend/api/views.py` (fonts list endpoint); `backend/fonts/` (bundled .ttf files) |
| Files Modified | `backend/core_engine/subtitle_engine.py`, `backend/api/urls.py`, `frontend/app/settings/page.tsx`, `frontend/store/settingsStore.ts` |

---

## 1. Document Overview

### 1.1 Problem Statement

StoryFlow's current font workflow requires the creator to first locate a TrueType font file on their local disk, upload it through a file picker, wait for it to be stored, and then initiate a full video render before seeing whether the font suits their subtitle style. There is no visual comparison between fonts available at any point in the workflow — a creator cannot look at "Roboto Bold" next to "Montserrat ExtraBold" next to "Impact" and make an informed choice without rendering. This upload-and-render cycle significantly discourages font experimentation and results in creators defaulting to whichever font they already know from memory rather than selecting the best option for their brand. The process also assumes the creator has .ttf files readily available on their machine, which is not always the case for users who are not familiar with font management.

### 1.2 Proposed Solution

Replace the raw .ttf file upload input with a visual font browser modal that provides immediate access to 20 bundled popular fonts displayed as live preview tiles, plus an optional second tab for Google Fonts search — all within the StoryFlow settings page.

- Bundle 20 popular subtitle and display fonts as `.ttf` files in `backend/fonts/` (or serve statically from `frontend/public/fonts/`): the set should include Roboto Bold, Montserrat ExtraBold, Impact, Bebas Neue, Anton, Oswald Bold, Source Serif 4, Cinzel Decorative, Lato Black, Nunito ExtraBold, Raleway Bold, Playfair Display Bold, Ubuntu Mono Bold, PT Sans Bold, Exo 2 Bold, Rubik Bold, Caveat Bold, Dancing Script Bold, Pacifico, and Permanent Marker.
- Add a `BUNDLED_FONTS` constant list to `backend/core_engine/subtitle_engine.py` listing each font's filename and display name so the video renderer can resolve fonts by name at render time without filesystem scanning.
- Add a backend endpoint `GET /api/fonts/` that reads the `backend/fonts/` directory and returns a JSON array of font objects (filename, display_name, category) — this list is the source of truth for which fonts are available for both the FontBrowser component and the video renderer.
- Create `frontend/components/FontBrowser.tsx` as a ShadCN Dialog or Sheet component triggered by clicking the font field in the settings form. The browser renders a scrollable grid of preview tiles — each tile showing the text "The Quick Brown Fox" in that font at 18px using a dynamically loaded `@font-face` declaration and a visual label below.
- Google Fonts integration (second tab): a debounced search input calls a backend proxy endpoint `GET /api/fonts/google-search/?q=bebas` which in turn calls the Google Fonts API; results appear in a second tab; clicking a Google Font result downloads the `.ttf` file to `backend/fonts/` via a backend HTTP request and adds it to the available fonts list.
- Clicking "Use Font" inside the FontBrowser calls `settingsStore.setSubtitleFont(fontFilename)` and closes the modal; the live subtitle preview on the settings page updates immediately.

### 1.3 Scope

| Dimension | In Scope |
|---|---|
| Bundled fonts browser | 20 pre-installed fonts shown as visual preview tiles in a modal grid |
| Fonts API endpoint | GET /api/fonts/ returning font list from the backend fonts directory |
| Font selection | Clicking Use Font updates GlobalSettings.subtitle_font field |
| Google Fonts proxy tab | Optional tab for searching and downloading Google Fonts via backend proxy |

| Dimension | Out of Scope |
|---|---|
| Variable font support | OpenType variable font axes (weight, width sliders) not supported |
| System fonts | Scanning the OS system font directory is not included |
| Font deletion | Removing bundled fonts from the browser is not implemented |
| Font licensing display | Displaying license information for each bundled font is not included |

### 1.4 Key Files Reference

| File | Role in This Feature |
|---|---|
| `frontend/components/FontBrowser.tsx` | Modal grid of font preview tiles; Use Font action; Google Fonts search tab |
| `backend/fonts/` | Directory where all bundled and downloaded .ttf files are stored |
| `backend/core_engine/subtitle_engine.py` | Add BUNDLED_FONTS constant; update font resolution logic to use font display names |
| `backend/api/views.py` | Add FontListView and GoogleFontsProxyView endpoints |
| `frontend/app/settings/page.tsx` | Replace raw file upload input with a "Browse Fonts" button that opens FontBrowser |

---

## 2. Flow Diagram

```
User is on Settings Page → font field shows current font name
         |
User clicks "Browse Fonts" button
         |
         v
FontBrowser Dialog opens
         |
         v
Component mounts → calls GET /api/fonts/
         |
         v
Backend reads backend/fonts/ directory → returns font list
         |
         v
FontBrowser renders scrollable grid (4 columns)
  [ Roboto Bold ]  [ Impact ]  [ Bebas Neue ]  [ Oswald ]
  "Quick Brown Fox" "Quick Brown Fox" ...
  (each tile loads @font-face dynamically)
         |
  User clicks Tab 2: "Google Fonts"
         |
         v
  Debounced search input → GET /api/fonts/google-search/?q=cinzel
         |
         v
  Backend calls Google Fonts API → returns matching fonts
  Results displayed as tiles with "Download & Use" button
         |
  User selects a font → clicks "Use Font"
         |
         v
settingsStore.setSubtitleFont("BebasNeue-Regular.ttf")
         |
         v
FontBrowser closes → font field in settings form updates
Live subtitle preview re-renders with new font
```

---

## 3. Step-by-Step Instructions

### Step 1 — Bundle fonts and add backend font list endpoint

File: `backend/fonts/` directory and `backend/api/views.py`

Place 20 `.ttf` font files into `backend/fonts/`. Create `FontListView` in `views.py` as a `GET` API view that lists all `.ttf` files in the `backend/fonts/` directory using `os.listdir`, filters by `.ttf` extension, and returns a JSON array where each item has `filename` (the raw .ttf filename), `display_name` (derived by removing the extension and replacing hyphens/underscores with spaces), and `category` (a hardcoded string — "sans-serif", "serif", "display", or "handwriting" — defined in a lookup dictionary keyed by filename). Register this view at `GET /api/fonts/` in `backend/api/urls.py`. Also add `BUNDLED_FONTS` as a list of font filename strings to `backend/core_engine/subtitle_engine.py` and update the font resolution function to look in the `backend/fonts/` directory when a matching filename is found in that list.

### Step 2 — Create FontBrowser.tsx modal component

File: `frontend/components/FontBrowser.tsx` (new file)

Build the component as a ShadCN Dialog that accepts an `onSelect(fontFilename: string)` callback prop and an `open` boolean prop with an `onOpenChange` handler. On mount (or when open becomes true), fetch `GET /api/fonts/` and store the result in local component state. Render a `Tabs` component with two tabs: "Bundled Fonts" and "Google Fonts". The Bundled Fonts tab renders a 4-column responsive CSS grid of font preview cards. Each card contains a `<p>` element styled with an inline `fontFamily` corresponding to the font's display name; a dynamically injected `<style>` tag in the card's parent declaring a `@font-face` with `src: url('/api/fonts/serve/?filename=<fontFilename>')` pointing to a backend static serve endpoint; the font display name as a caption label; and a "Use Font" button that calls `onSelect(fontFilename)` and closes the dialog.

### Step 3 — Add font serving and Google Fonts proxy endpoints

File: `backend/api/views.py` and `backend/api/urls.py`

Add `FontServeView` at `GET /api/fonts/serve/?filename=BebasNeue-Regular.ttf` that reads the requested `.ttf` file from `backend/fonts/`, validates that the filename exists in the directory (security check — prevent directory traversal by stripping any path separators from the filename parameter), and returns the file content as `HttpResponse` with `Content-Type: font/ttf`. Add `GoogleFontsProxyView` at `GET /api/fonts/google-search/?q=<query>` that calls the Google Fonts Web API using the `requests` library with the configured API key from Django settings, parses the JSON response, and returns a simplified list of font objects (family name, variants, a preview URL pointing to the font's CSS from Google's CDN). Register both endpoints in `urls.py`. Store the Google Fonts API key in `backend/storyflow_backend/settings.py` as `GOOGLE_FONTS_API_KEY` loaded from an environment variable.

### Step 4 — Replace file upload with Browse Fonts button in settings page

File: `frontend/app/settings/page.tsx`

Locate the existing subtitle font input field in the settings form. Replace the raw `<input type="file">` element with two side-by-side elements: a read-only text input displaying the current font display name (derived from the `subtitle_font` filename stored in `settingsStore`), and a "Browse Fonts" button (ShadCN Button, outlined variant) that sets local state `isFontBrowserOpen = true`. Render the `FontBrowser` component with `open={isFontBrowserOpen}` and `onOpenChange={setIsFontBrowserOpen}`. Wire the `onSelect` callback to call `settingsStore.setSubtitleFont(fontFilename)` and `setIsFontBrowserOpen(false)`. The existing `settingsStore.setSubtitleFont` action should also update the `subtitle_font` field in the Zustand store so the text input and subtitle preview both reflect the change immediately.

---

## 4. Expected Outcome

- The settings page displays a "Browse Fonts" button next to the font name field; clicking it opens a visually rich modal showing 20 bundled fonts as live-rendered preview tiles.
- Each font tile correctly renders the sample text "The Quick Brown Fox" in the actual font via dynamic @font-face loading — fonts that fail to load fall back to a system monospace and show an error indicator.
- Clicking "Use Font" on any bundled tile closes the modal and immediately updates the font field in the settings form and the live subtitle preview with the selected font.
- The Google Fonts search tab returns results within 1 second for common font names and displays each result as a tile using Google's CDN font CSS for preview rendering.
- Selecting a Google Font and clicking "Download & Use" stores the font file in `backend/fonts/` and makes it available for both the FontBrowser and the video renderer without requiring a server restart.
- The Django subtitle engine correctly resolves font files from the `backend/fonts/` directory using the `BUNDLED_FONTS` constant, producing rendered subtitles in the selected font during video generation.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `FontListView` returns an array where each item contains `filename`, `display_name`, and `category` keys and every item corresponds to an actual `.ttf` file in `backend/fonts/`.
- [ ] `FontServeView` returns HTTP 403 or 404 when the `filename` parameter contains a directory traversal sequence such as `../manage.py`, verifying the security check is effective.
- [ ] `subtitle_engine.py` font resolution function returns the correct absolute path for a font filename that exists in `BUNDLED_FONTS` and raises a clear exception for a font filename that does not exist in the directory.
- [ ] `FontBrowser` component renders the correct number of font tiles matching the count returned by the mocked `GET /api/fonts/` response in a Jest render test.

### 5.2 Integration / Manual Tests

- [ ] Open the FontBrowser and verify all 20 bundled fonts display correctly rendered sample text — no tiles should show fallback fonts or blank text.
- [ ] Select "Bebas Neue" from the font browser, confirm the settings form font field updates to "Bebas Neue", confirm the subtitle preview in the page re-renders in Bebas Neue, and confirm that saving settings and re-rendering a video produces subtitles in Bebas Neue.
- [ ] Search for "Pacifico" in the Google Fonts tab, click "Download & Use", verify the file appears in `backend/fonts/`, and verify the font is available as a bundled tile the next time the FontBrowser is opened.
- [ ] Confirm that the Google Fonts proxy endpoint gracefully returns an empty list (not an error) when the `GOOGLE_FONTS_API_KEY` is not configured, and that the Google Fonts tab in the browser shows a clear "API key not configured" message rather than a broken UI.
- [ ] Verify that the font field in the settings form correctly displays the human-readable display name of the currently active font on page load rather than the raw filename with dashes and extension.

### 5.3 Regression Tests

- [ ] Existing subtitle preview component (`SubtitlePreview.tsx`) continues to render correctly using the `subtitle_font` value from the settingsStore after the font input change from file upload to FontBrowser selector.
- [ ] Video render tasks that use a font set prior to this feature (stored as a raw .ttf filename in GlobalSettings) still resolve correctly — the subtitle engine must remain backward-compatible with previously stored font filenames.
- [ ] The settings page loads without JavaScript errors when `GET /api/fonts/` returns an empty list (e.g., the fonts directory is empty or the endpoint is temporarily unavailable).

---

## 6. Notes for AI Agent

- The `FontServeView` directory traversal security check is critical: before opening any file from `backend/fonts/`, perform `os.path.basename(filename)` and verify the result matches the original parameter to ensure no path components were injected by the caller. Never construct the file path by naively joining the fonts directory with a user-supplied string without this normalization step.
- Font loading in the browser via dynamically injected `@font-face` style tags can be slow for the first tile render; mitigate this by using the CSS `font-display: swap` descriptor so the preview text appears immediately in a fallback font and swaps in once the `.ttf` file has downloaded, avoiding a blank tile during loading.
- The `BUNDLED_FONTS` constant in `subtitle_engine.py` should be a list of dictionaries rather than plain strings, where each entry has at minimum `filename` and `display_name` keys — this avoids having to reparse filenames at render time and makes the constant self-documenting.
- Google Fonts API calls from the backend proxy should be cached for at least 10 minutes using Django's cache framework (or a simple in-memory dict) to avoid hitting rate limits during rapid search interactions; the frontend debounce delay (300ms) alone is not sufficient protection against API quota exhaustion.
