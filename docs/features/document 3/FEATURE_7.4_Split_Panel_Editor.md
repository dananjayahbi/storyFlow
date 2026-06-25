# Feature 7.4 — Split-Panel Timeline Editor

| Field | Value |
|---|---|
| Feature ID | 7.4 |
| Title | Split-Panel Timeline Editor |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Medium |
| Estimated Effort | 2–3 days |
| Dependencies | `react-resizable-panels` npm package |
| Output Files (NEW) | `frontend/components/EditorCenterPanel.tsx`, `frontend/components/EditorRightPanel.tsx` |
| Files Modified | `frontend/app/projects/[id]/page.tsx`, `frontend/components/Timeline.tsx`, `frontend/app/projects/[id]/page.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

The current project editor layout uses a vertical scrolling segment list with a narrow right sidebar for controls. Segment images are displayed as small ~180px thumbnails inside each SegmentCard, which is far too small for a video creator to properly evaluate whether the image visually supports the narration text. Writers who care about visual-narrative alignment must mentally track the connection between the text they are editing in the card and the thumbnail far above or below it in the scroll position. On modern widescreen monitors used by video producers, the current layout wastes enormous horizontal space by running all content through a narrow center column. There is no immersive way to see the composition of a segment (image, text, voice, timing) in a unified view without scrolling between elements.

### 1.2 Proposed Solution

The project editor page is restructured into a horizontal three-panel layout using the `react-resizable-panels` library. A left panel hosts the segment list, a center panel provides a large image preview and video player, and a right panel hosts the per-segment and project controls. The layout is fluid and user-resizable, with sizes persisted per project in `localStorage`. Clicking a segment in the left panel focuses it and updates the center and right panels with that segment's content.

- Install `react-resizable-panels` via npm; wrap the project editor content in a `PanelGroup direction="horizontal"` with three `Panel` children and two `PanelResizeHandle` drag handles
- Left panel (default 25% width, minimum 18%): a scrollable column containing the existing `<Timeline>` component; clicking any segment card sets it as the global `focusedSegmentId` in local state
- Center panel (default 50% width, minimum 35%): displays the currently focused segment's image at full usable size using an `<img>` with `object-contain`; shows segment text preview in a read-only `<p>` below the image; contains a video preview player when the project has a completed render
- Right panel (default 25% width, minimum 18%): hosts all controls currently in the right sidebar — voice selector, subtitle style sliders, Ken Burns intensity slider, per-segment action buttons (generate audio, upload image)
- Drag handles between panels are rendered as thin vertical bars (4px wide) with a visual `cursor-col-resize` indicator and a subtle color on hover
- Panel width percentages are serialized and saved to `localStorage` using key `editor-panels-{projectId}` and restored on next page load for that project
- Create `EditorCenterPanel.tsx` to encapsulate the image preview and text preview logic; create `EditorRightPanel.tsx` to encapsulate voice, subtitle, and action controls
- Add a "Reset Layout" button in the project page toolbar that clears the saved panel sizes and reverts to the 25/50/25 defaults

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| Three-panel resizable layout for the project editor | Mobile editor layout (separate feature 7.2) |
| Per-project panel size persistence in localStorage | Server-side persistence of panel sizes |
| Focused segment state synchronizing all three panels | Animated transitions between panel configurations |
| "Reset Layout" toolbar button | Custom panel themes or color schemes |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `frontend/app/projects/[id]/page.tsx` | Project detail page; root of the editor | Vertical scroll + right sidebar layout; no panel group |
| `frontend/components/Timeline.tsx` | Scrollable list of all SegmentCards | Standalone vertical list component |
| `frontend/components/SegmentCard.tsx` | Single segment UI (image, text, audio, controls) | Self-contained; must accept `isFocused` prop |
| `frontend/components/EditorCenterPanel.tsx` | NEW — large image preview + video player | Does not exist yet |
| `frontend/components/EditorRightPanel.tsx` | NEW — voice selector, sliders, action buttons | Does not exist yet |

---

## 2. Flow Diagram

```
frontend/app/projects/[id]/page.tsx
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│  PanelGroup direction="horizontal"                          │
│                                                              │
│  ┌──────────────┐ ┤ ┌──────────────────────┐ ┤ ┌──────────┐ │
│  │ Left Panel   │   │   Center Panel       │   │  Right   │ │
│  │  (25%)       │   │   (50%)              │   │  Panel   │ │
│  │              │   │                      │   │  (25%)   │ │
│  │ <Timeline>   │   │  <img>               │   │ Voice    │ │
│  │  - Seg 1     │   │  (focused segment    │   │ Selector │ │
│  │  - Seg 2 ◄───┼───┼──image, full size)  │   │ Subtitle │ │
│  │  - Seg 3     │   │                      │   │ Sliders  │ │
│  │              │   │  <p> text preview    │   │ Actions  │ │
│  └──────────────┘   └──────────────────────┘   └──────────┘ │
│                  ▲                          ▲                │
│         PanelResizeHandle          PanelResizeHandle         │
└──────────────────────────────────────────────────────────────┘
        │
        ▼
User clicks Seg 2 in Timeline
→ setFocusedSegmentId(seg2.id)
→ Center panel updates to Seg 2 image
→ Right panel updates to Seg 2 voice/settings
```

---

## 3. Step-by-Step Instructions

### Step 3.1 — Install react-resizable-panels and Update the Editor Page Structure

Run `npm install react-resizable-panels` in the `frontend/` directory to add the dependency. Open `frontend/app/projects/[id]/page.tsx`. Add a `focusedSegmentId` state variable initialized to the first segment's ID (or `null`). Import `PanelGroup`, `Panel`, and `PanelResizeHandle` from `react-resizable-panels`. Replace the existing content wrapper `<div>` with a `<PanelGroup direction="horizontal" className="h-full">` element. This is the root container for all three panels. Add an `onLayout` callback to the `PanelGroup` that receives the new size percentages array and saves them to `localStorage` under the key `editor-panels-{projectId}`.

### Step 3.2 — Configure the Three Panel Components

Inside the `PanelGroup`, add a `<Panel defaultSize={25} minSize={18}>` for the left panel and render `<Timeline segments={segments} focusedSegmentId={focusedSegmentId} onSegmentFocus={setFocusedSegmentId} />` inside it. Add a `<PanelResizeHandle className="w-1 bg-border hover:bg-primary/50 cursor-col-resize transition-colors" />` between the left and center panels. Add a `<Panel defaultSize={50} minSize={35}>` for the center panel and render `<EditorCenterPanel segment={focusedSegment} projectHasRender={!!project.output_url} />`. Add another `<PanelResizeHandle>`. Add the right `<Panel defaultSize={25} minSize={18}>` and render `<EditorRightPanel segment={focusedSegment} project={project} onSegmentUpdate={handleSegmentUpdate} />` inside it.

### Step 3.3 — Create EditorCenterPanel.tsx

Create `frontend/components/EditorCenterPanel.tsx`. The component accepts a `segment` prop (of type `Segment | null`) and a `projectHasRender` boolean. When `segment` is not null and has an `image_url`, render a `<div className="flex flex-col items-center h-full p-4">`. Inside it, render `<img src={segment.image_url} alt="Segment image" className="max-h-[60%] w-full object-contain rounded-lg" />`. Below the image, render a `<p className="mt-4 text-center text-muted-foreground text-sm max-w-xl">` containing `segment.text_content`. If `projectHasRender` is true, render a `<video controls src={project.output_url} className="mt-4 w-full max-h-[30%] rounded-lg" />` below the text. If `segment` is null, show a centered placeholder: "Select a segment to preview".

### Step 3.4 — Create EditorRightPanel.tsx

Create `frontend/components/EditorRightPanel.tsx`. The component accepts `segment`, `project`, and `onSegmentUpdate` as props. Inside it, render the controls that were previously in the right sidebar: a `<VoiceSelector>` component bound to `segment.voice_id`, a `<SubtitlePreview>` component, Ken Burns intensity and transition sliders as `<input type="range">` elements, and action buttons "Generate Audio", "Upload Image", and "Delete Segment". When any control value changes, call `onSegmentUpdate(segment.id, { changedField: newValue })` so the update propagates back to the page's state and triggers an API PATCH. Wrap the panel content in `<div className="overflow-y-auto h-full px-4 py-4 flex flex-col gap-6">`.

### Step 3.5 — Restore Saved Panel Sizes and Add Reset Button

In `frontend/app/projects/[id]/page.tsx`, add a `useEffect` that runs on mount and reads the saved sizes from `localStorage` under key `editor-panels-{projectId}`. If sizes are found, use the `PanelGroup`'s `ref` and the `setLayout` method from the `react-resizable-panels` API to restore the saved proportions programmatically. In the page's toolbar (the `<header>` or `<div>` above the `PanelGroup`), add a "Reset Layout" button. When clicked, it clears the `localStorage` key for this project and calls `setLayout([25, 50, 25])` on the panel group ref to snap back to the default proportions. Update `Timeline.tsx` to accept and use the `focusedSegmentId` and `onSegmentFocus` props — add a `ring-2 ring-primary` highlight class to the SegmentCard whose `id` matches `focusedSegmentId`.

---

## 4. Expected Outcome

1. The project editor page renders as a horizontal three-panel layout with visible resize handles between each panel.
2. Dragging any resize handle resizes the adjacent panels fluidly without page reloading.
3. Clicking a segment in the left panel updates both the center image preview and the right controls panel to show that segment's data.
4. The center panel displays the focused segment's image large enough to properly evaluate the visual content.
5. The right panel contains all voice, subtitle, and action controls previously accessed via the right sidebar — fully functional.
6. After resizing panels, refreshing the page restores the user's exact panel proportions for that project.
7. Clicking "Reset Layout" snaps all panels back to the default 25/50/25 proportion and clears the saved sizes.
8. The existing `Timeline.tsx` scroll and segment interactions continue to work correctly within the constrained left panel.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `EditorCenterPanel` renders a placeholder when `segment` prop is null
- [ ] `EditorCenterPanel` renders `<img>` with correct `src` when segment has an `image_url`
- [ ] `EditorRightPanel` calls `onSegmentUpdate` with the correct payload when the voice selector changes
- [ ] `focusedSegmentId` state updates correctly when `onSegmentFocus` is called from `Timeline`
- [ ] Panel sizes are correctly serialized and stored in `localStorage` on `onLayout` callback

### 5.2 Integration / Manual Tests

- [ ] Open the project editor — three panels render side by side without layout overflow
- [ ] Drag the left-center resize handle — both panels resize fluidly and content reflows
- [ ] Click different segments in the left panel — center and right panels update to correct segment data
- [ ] Change voice in the right panel — the change saves via API PATCH without errors
- [ ] Reload the page after resizing — panels restore to the user's last saved proportions
- [ ] Click "Reset Layout" — panels snap to 25/50/25 and `localStorage` entry is cleared

### 5.3 Regression Tests

- [ ] All existing segment editing functions (audio generation, image upload, text editing) work correctly in the new panel structure
- [ ] The render button and project-level actions in the toolbar remain accessible and functional
- [ ] TypeScript compilation reports zero new errors after the refactor

---

## 6. Notes for AI Agent

- The `react-resizable-panels` library requires a `PanelGroup` to have an explicit `id` prop for programmatic layout control via `useRef` and `setLayout`. Add `id="editor-panels"` to the `PanelGroup` element and create a `panelGroupRef` using `useRef`.
- The `Panel` components do not render scroll bars natively — wrap the content inside each `Panel` in a `<div className="h-full overflow-y-auto">` to enable independent scrolling within each pane.
- Focused segment state should live in the project page (`[id]/page.tsx`) as a single source of truth, passed down as props to `Timeline`, `EditorCenterPanel`, and `EditorRightPanel`. Do not duplicate this state in child components.
- The `EditorRightPanel` reuses existing components (`VoiceSelector`, `SubtitlePreview`, sliders) — extract them from the current right sidebar implementation rather than writing new ones. This reduces the risk of behavioral regression.
- Test the layout at three viewport widths: 1280px (standard laptop), 1920px (widescreen desktop), and 1024px (small laptop). The minimum panel sizes (18%, 35%, 18%) should prevent either side panel from becoming unusably narrow on 1024px screens.
