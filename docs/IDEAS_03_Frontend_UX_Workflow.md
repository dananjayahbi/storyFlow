# StoryFlow Ideas — Document 3: Frontend, UX & Workflow

> **Category:** User Interface, User Experience, Workflow Efficiency, Editor Features  
> **Last Updated:** March 1, 2026  
> **Purpose:** Ideas to make the editing experience faster, more intuitive, and optimized for high-volume video production

---

## Table of Contents

- [1. Editor UX Improvements](#1-editor-ux-improvements)
- [2. Workflow Efficiency](#2-workflow-efficiency)
- [3. Visual Preview & Feedback](#3-visual-preview--feedback)
- [4. Gallery & Media Management](#4-gallery--media-management)
- [5. Bulk Operations & Batch Production](#5-bulk-operations--batch-production)
- [6. Settings & Configuration UX](#6-settings--configuration-ux)
- [7. Navigation & Layout](#7-navigation--layout)
- [8. Code Quality & Frontend Architecture](#8-code-quality--frontend-architecture)

---

## 1. Editor UX Improvements

### 1.1 Drag-and-Drop Segment Reordering
- **Current:** `reorderSegments` API exists but no drag-and-drop UI.
- **Idea:** Add DnD reordering to the Timeline using `@dnd-kit/core` — drag handles on segment cards.
- **Impact:** Intuitive visual reordering instead of manual index editing.
- **Complexity:** Medium — DnD library integration, optimistic state updates.

### 1.2 Undo/Redo System
- **Current:** All edits are fire-and-forget — no undo capability.
- **Idea:** Implement a command-based undo/redo stack (Ctrl+Z / Ctrl+Shift+Z):
  - Text edits, segment reorder, image changes, settings changes
  - Stack size: last 50 operations
- **Impact:** Confidence to experiment — creators can freely try changes knowing they can revert.
- **Complexity:** Medium — command pattern with state snapshots.

### 1.3 Multi-Select Segments
- **Current:** Single-segment operations only.
- **Idea:** Shift+Click / Ctrl+Click to select multiple segments for bulk actions:
  - Delete multiple segments
  - Lock/unlock multiple segments
  - Regenerate audio for selected segments
  - Move selection up/down
- **Impact:** Massive time savings when editing long video scripts (20+ segments).
- **Complexity:** Medium — selection state, bulk action UI toolbar.

### 1.4 Segment Split & Merge
- **Current:** Can only add or delete whole segments.
- **Idea:**
  - **Split:** Click at a cursor position in text → splits into two segments
  - **Merge:** Select two adjacent segments → merge text, keep first image
- **Impact:** Flexibility in editing — break long narration into punchier segments.
- **Complexity:** Medium — text split logic, sequence index recomputation.

### 1.5 Rich Text Segment Editor
- **Current:** Plain textarea for segment text.
- **Idea:** Upgrade to a lightweight rich text editor with:
  - Character count display
  - Word count display
  - Estimated audio duration (based on words/speed)
  - TTS markup highlighting (if SSML is implemented)
- **Impact:** Better editing experience, real-time feedback on segment characteristics.
- **Complexity:** Low–Medium — can use a simple overlay on textarea without full rich text.

### 1.6 Segment Duration Display
- **Current:** Audio duration shown after generation, no pre-generation estimate.
- **Idea:** Show estimated audio duration based on word count and TTS speed setting (avg ~150 words/minute at 1.0× speed).
- **Impact:** Users can gauge video length before generating any audio.
- **Complexity:** Low — simple math.

### 1.7 Auto-Save with Conflict Detection
- **Current:** Auto-save with 500ms debounce but no conflict detection.
- **Idea:** Add a "saved" / "unsaved changes" indicator, and detect if the server version has changed (e.g., from a parallel browser tab).
- **Impact:** Peace of mind that changes are persisted.
- **Complexity:** Low — timestamp/version check on save.

### 1.8 Inline Image Search & Selection
- **Current:** Must upload images from local filesystem.
- **Idea:** Add Unsplash/Pexels free stock image search directly in the image uploader — search by keyword, click to use.
- **Impact:** No need to leave the app to find images. Huge workflow speedup.
- **Complexity:** Medium — API integration, attribution handling.

---

## 2. Workflow Efficiency

### 2.1 Project Templates / Presets
- **Current:** Each project starts from scratch (inheriting GlobalSettings).
- **Idea:** Save and load project templates that include:
  - Voice + speed
  - Subtitle style (font, color, size, position)
  - Logo + position
  - Resolution/FPS
  - Music track + volume
  - Transition style
- **Impact:** Consistent branding across video series. One-click setup for new projects.
- **Complexity:** Medium — template model, save/load UI.

### 2.2 Project Duplication
- **Current:** No way to clone a project.
- **Idea:** "Duplicate Project" button → copies all settings, segments, and images to a new project.
- **Impact:** Perfect for A/B testing, content variations, or series episodes with same structure.
- **Complexity:** Low — deep copy of project + segments + media files.

### 2.3 Batch Import (Multiple Stories)
- **Current:** Import one story JSON at a time.
- **Idea:** Upload a folder or multiple JSON files → create one project per file automatically.
- **Impact:** With 1000+ scripts ready, importing them one-by-one is painful. Batch import is essential.
- **Complexity:** Low — loop over files, call existing import logic.

### 2.4 Quick Actions Toolbar
- **Current:** Actions scattered across buttons and menus.
- **Idea:** Floating action bar (like VS Code command palette) with keyboard-searchable commands:
  - Ctrl+K → open command palette
  - "Generate all audio", "Start render", "Import story", "Duplicate project"
- **Impact:** Power user efficiency — never touch the mouse for common actions.
- **Complexity:** Medium — command palette UI, action registry.

### 2.5 Estimated Total Video Duration
- **Current:** No pre-render duration estimate.
- **Idea:** Show real-time total estimated duration: `Σ(segment audio durations) + Σ(transition durations) + inter-segment silences + outro duration`.
- **Impact:** Users know video length before rendering. Useful for TikTok (60s/3min limits) and YouTube Shorts (60s).
- **Complexity:** Low — simple arithmetic from available data.

### 2.6 Production Pipeline View
- **Current:** Each project is managed individually.
- **Idea:** A Kanban-style board showing projects across stages:
  - **Draft** → **Images Ready** → **Audio Generated** → **Rendered** → **Published**
- **Impact:** Bird's-eye view of content production pipeline. Essential for high-volume production.
- **Complexity:** Medium — new page, project status tracking.

### 2.7 Project Tags / Categories
- **Current:** Projects are just a flat list sorted by date.
- **Idea:** Add tags/categories to projects: "History", "Science", "Horror", "Motivational", "Funny", etc.
- **Impact:** Organize 1000+ projects logically. Filter and search by category.
- **Complexity:** Low — add tags field, filter UI.

### 2.8 Project Search & Filter
- **Current:** Basic name search on projects list.
- **Idea:** Advanced filtering: by status, by date range, by tag, by number of segments, by has-output.
- **Impact:** Find specific projects quickly in a large library.
- **Complexity:** Low — filter UI, backend query params.

### 2.9 Keyboard Shortcut Enhancement
- **Current:** 5 keyboard shortcuts.
- **Idea:** Expand to cover all common actions:
  - `N` — new segment
  - `D` — duplicate selected segment
  - `Del` — delete segment (with confirmation)
  - `↑/↓` — navigate between segments
  - `Space` — play/pause audio
  - `L` — lock/unlock segment
  - `1–9` — jump to segment by index
- **Impact:** Mouse-free editing for power users.
- **Complexity:** Low.

---

## 3. Visual Preview & Feedback

### 3.1 Storyboard Preview Mode
- **Current:** No preview before rendering.
- **Idea:** "Storyboard" view: a horizontal timeline showing image thumbnails, audio waveforms, and subtitle text — like a film storyboard.
- **Impact:** Visual overview of the entire video composition before rendering.
- **Complexity:** Medium — new layout component, image thumbnails, audio visual.

### 3.2 Quick Preview (Pre-Render)
- **Current:** Must do full render to see any output.
- **Idea:** "Quick Preview" plays images in sequence timed to audio durations in the browser — no server-side rendering needed.
  - HTML5 canvas or `<img>` slideshow
  - Ken Burns approximated with CSS transforms
  - Audio segments played in sequence
  - Subtitle text overlaid
- **Impact:** Near-instant preview of the video concept — iterate in seconds instead of minutes.
- **Complexity:** Medium–High — client-side video preview engine.

### 3.3 Audio Waveform Visualization
- **Current:** Basic play/pause button for audio.
- **Idea:** Show audio waveform per segment (using WaveSurfer.js). Visualize where speech occurs and where silence is.
- **Impact:** Quickly spot silent gaps, pacing issues, or audio problems.
- **Complexity:** Medium — WaveSurfer.js integration.

### 3.4 Image Fit Preview
- **Current:** Image shown as uploaded, no indication of how it will look in the video.
- **Idea:** Show image with render-resolution crop overlay — highlight which area will be visible at each Ken Burns position.
- **Impact:** Users can verify their images look good before rendering.
- **Complexity:** Medium — CSS overlay showing crop boundaries.

### 3.5 Thumbnail Generator
- **Current:** No thumbnail generation.
- **Idea:** Auto-generate a video thumbnail from:
  - First segment image with title overlaid
  - Custom frame selection from rendered video
  - Template-based thumbnails (bold text, bright colors, face highlight)
- **Impact:** Every YouTube/TikTok video needs a thumbnail. This saves external tool usage.
- **Complexity:** Medium — server-side image composition, thumbnail template system.

### 3.6 Real-Time Subtitle Preview on Image
- **Current:** Subtitle preview shows text on a dark preview box.
- **Idea:** Overlay the subtitle preview on the actual segment image — see exactly how it looks in the final video.
- **Impact:** Catch readability issues before rendering (white text on bright images).
- **Complexity:** Low — overlay subtitle on image canvas in browser.

---

## 4. Gallery & Media Management

### 4.1 Video Thumbnails in Gallery
- **Current:** Gallery items shown as cards without thumbnail previews.
- **Idea:** Generate a thumbnail from the rendered video (first frame or a frame at 10% duration) and display in gallery cards.
- **Impact:** Visual gallery browsing instead of text-based.
- **Complexity:** Low — FFmpeg frame extraction.

### 4.2 Video Comparison View
- **Current:** View one video at a time.
- **Idea:** Side-by-side comparison of two rendered versions of the same project (e.g., different voice, different subtitle style).
- **Impact:** A/B testing of production choices.
- **Complexity:** Medium — dual video player sync.

### 4.3 Render History Per Project
- **Current:** Only the latest render output is kept.
- **Idea:** Keep last N renders (e.g., 3–5) with timestamp and settings snapshot.
- **Impact:** Compare different render configurations without losing previous work.
- **Complexity:** Medium — versioned output storage, settings snapshot on render.

### 4.4 Asset Library (Images, Audio, Music)
- **Current:** Images and audio tied to specific projects.
- **Idea:** Global asset library:
  - **Image Library** — drag images from library to segments across projects
  - **Music Library** — reusable background music tracks
  - **SFX Library** — reusable sound effects
- **Impact:** Reuse assets across projects — huge efficiency for series production.
- **Complexity:** Medium — new models, upload UI, drag-to-project.

### 4.5 Media Usage Tracking
- **Current:** No visibility into disk usage.
- **Idea:** Dashboard showing total disk usage: images, audio, rendered videos — with cleanup suggestions for old renders.
- **Impact:** Manage storage when producing at scale (1000+ videos).
- **Complexity:** Low — directory size calculation, dashboard widget.

---

## 5. Bulk Operations & Batch Production

### 5.1 Bulk Import with Auto-Queue
- **Current:** Import → manually upload images → manually generate audio → manually render (per project).
- **Idea:** "Batch Pipeline" mode:
  1. Import 10–50 stories at once
  2. Auto-assign images from a folder (match by segment index or filename)
  3. Auto-generate all audio
  4. Auto-render all
  5. Show progress dashboard for the entire batch
- **Impact:** Produce 50 videos overnight with a single click. Game-changer for scale.
- **Complexity:** High — orchestration pipeline, image matching, queue management.

### 5.2 CSV/Spreadsheet Import
- **Current:** JSON and plain text import only.
- **Idea:** Import from CSV/Excel: `title | segment_text | image_prompt | image_file_path`.
- **Impact:** Easy mass content creation from spreadsheet-managed content calendars.
- **Complexity:** Low — CSV parser, map columns to fields.

### 5.3 Folder-Based Image Auto-Assignment
- **Current:** Images uploaded one-by-one per segment.
- **Idea:** Upload a folder of images → auto-assign to segments by:
  - Filename order (01.jpg, 02.jpg, ...)
  - Matching: `segment_1.jpg` → segment 1
  - AI matching: compare image to `image_prompt` using CLIP similarity
- **Impact:** Massive time savings when images are pre-prepared (e.g., AI-generated batch).
- **Complexity:** Low–Medium (filename based), High (AI matching).

### 5.4 Bulk Settings Apply
- **Current:** Settings per project, changed individually.
- **Idea:** Select multiple projects → "Apply Settings From..." → copies all settings from a template or another project.
- **Impact:** Standardize branding across 100+ projects instantly.
- **Complexity:** Low — API endpoint to bulk-copy settings.

### 5.5 Production Queue with Scheduling
- **Current:** Bulk render runs immediately.
- **Idea:** Schedule renders: "Render these 20 projects starting at midnight" (when PC is idle).
- **Impact:** Render overnight, discover finished videos in the morning.
- **Complexity:** Medium — scheduling system, background daemon.

---

## 6. Settings & Configuration UX

### 6.1 Settings Profiles
- **Current:** One global settings + per-project overrides.
- **Idea:** Named settings profiles: "YouTube Series A", "TikTok Horror", "Instagram Facts".
- **Impact:** Quick-switch between different video styles.
- **Complexity:** Low — profile model, dropdown selector.

### 6.2 Live Preview for All Settings
- **Current:** Subtitle preview exists; logo preview exists.
- **Idea:** Extend live preview to all visual settings — Ken Burns intensity, transition duration, font changes — show a 3-second animated preview.
- **Impact:** Instant visual feedback for settings changes.
- **Complexity:** Medium — client-side preview rendering for each setting.

### 6.3 Settings Import/Export
- **Current:** Settings only in database.
- **Idea:** Export settings as JSON, import on another machine. Useful for backup or sharing setups.
- **Impact:** Portable workflow — share your video production config with friends.
- **Complexity:** Low — JSON serialization of settings.

### 6.4 Font Browser
- **Current:** Upload custom font file manually.
- **Idea:** Built-in browser of bundled fonts (20 popular fonts) + Google Fonts integration.
- **Impact:** Font selection without leaving the app.
- **Complexity:** Medium — font bundling, Google Fonts API, font preview.

---

## 7. Navigation & Layout

### 7.1 Dark/Light Mode Toggle
- **Current:** Hardcoded dark mode.
- **Idea:** Wire up the already-installed `next-themes` package for a toggle button.
- **Impact:** Accessibility and personal preference.
- **Complexity:** Low — already half-implemented.

### 7.2 Responsive/Mobile Layout
- **Current:** Desktop-only sidebar layout.
- **Idea:** Responsive breakpoints for tablet/mobile: collapsible sidebar → bottom nav, stacked segment cards.
- **Impact:** Edit on iPad or check progress on phone.
- **Complexity:** Medium — Tailwind responsive classes, layout restructure.

### 7.3 Breadcrumb Navigation
- **Current:** Sidebar nav with page links.
- **Idea:** Add breadcrumbs: `Dashboard > Projects > "The Lost City" > Timeline Editor`.
- **Impact:** Clear location awareness, easy back-navigation.
- **Complexity:** Low.

### 7.4 Split-Panel Timeline Editor
- **Current:** Vertical scrolling segment list + right sidebar.
- **Idea:** Split pane layout:
  - Left: segment list (narrative)
  - Center: large image preview / video preview
  - Right: settings panel
- **Impact:** See the full image while editing text — more immersive editing.
- **Complexity:** Medium — resizable split panes.

---

## 8. Code Quality & Frontend Architecture

### 8.1 Consolidate Duplicate Stores
- **Current:** Two `useSettingsStore` implementations in `lib/stores.ts` and `store/settingsStore.ts`.
- **Idea:** Merge into a single store, remove the duplicate.
- **Impact:** Eliminates import confusion and potential state desync.
- **Complexity:** Low.

### 8.2 Consolidate Duplicate Types
- **Current:** `types/settings.ts` and `lib/types.ts` define overlapping types with different field names.
- **Idea:** Single type definition source in `lib/types.ts`.
- **Impact:** Type safety, no field name mismatches.
- **Complexity:** Low.

### 8.3 Environment-Based API URL
- **Current:** Hardcoded `http://localhost:8000` in two Axios instances.
- **Idea:** Use `process.env.NEXT_PUBLIC_API_URL` with fallback.
- **Impact:** Portable configuration, easier testing.
- **Complexity:** Low.

### 8.4 Extract Duplicate Utilities
- **Current:** `formatRelativeTime` duplicated in 3 files.
- **Idea:** Extract shared utilities to `lib/utils.ts`.
- **Impact:** DRY code, single source of truth.
- **Complexity:** Low.

### 8.5 WebSocket Integration
- **Current:** HTTP polling every 2–3 seconds for progress.
- **Idea:** Django Channels + WebSocket for real-time render/audio progress push.
- **Impact:** Lower server load, instant progress updates, better UX.
- **Complexity:** High — Django Channels setup, WebSocket client.

### 8.6 Error Boundary Enhancement
- **Current:** Basic error boundary wrapper.
- **Idea:** Enhanced error boundary with:
  - Retry button
  - Error reporting (copy error details)
  - Fallback to last known good state
- **Impact:** Better error recovery UX.
- **Complexity:** Low.

---

## Priority Matrix

| Idea | Impact | Effort | Recommended Priority |
|------|--------|--------|---------------------|
| 2.3 Batch Import | CRITICAL | LOW | 🔴 Do First |
| 5.3 Folder Image Assignment | HIGH | LOW | 🔴 Do First |
| 1.1 DnD Segment Reordering | HIGH | MEDIUM | 🔴 Do First |
| 2.5 Estimated Video Duration | MEDIUM | LOW | 🔴 Do First |
| 3.2 Quick Preview | HIGH | MEDIUM | 🔴 Do First |
| 8.1 Consolidate Stores | LOW | LOW | 🟡 Do Soon |
| 8.3 Env-Based API URL | LOW | LOW | 🟡 Do Soon |
| 7.1 Dark/Light Toggle | LOW | LOW | 🟡 Do Soon |
| 2.2 Project Duplication | MEDIUM | LOW | 🟡 Do Soon |
| 2.7 Project Tags | MEDIUM | LOW | 🟡 Do Soon |
| 1.2 Undo/Redo | HIGH | MEDIUM | 🟠 Plan Ahead |
| 2.1 Project Templates | HIGH | MEDIUM | 🟠 Plan Ahead |
| 3.5 Thumbnail Generator | HIGH | MEDIUM | 🟠 Plan Ahead |
| 5.1 Bulk Auto-Pipeline | CRITICAL | HIGH | 🟠 Plan Ahead |
| 4.4 Asset Library | HIGH | MEDIUM | 🟠 Plan Ahead |
| 2.6 Kanban Pipeline View | MEDIUM | MEDIUM | 🔵 Future |
| 8.5 WebSocket Integration | MEDIUM | HIGH | 🔵 Future |
| 7.4 Split-Panel Editor | MEDIUM | MEDIUM | 🔵 Future |
