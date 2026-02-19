# Task 05.03.04 — Build SubtitlePreview

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.04                                                                                       |
| **Task Name**          | Build SubtitlePreview                                                                          |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Medium                                                                                       |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | Task 05.03.03 (SubtitleSettingsForm provides font and color data)                              |
| **Output Files**       | `frontend/components/SubtitlePreview.tsx` (NEW)                                                |

---

## Objective

Build a live preview box that shows sample subtitle text styled with the current font and color settings, updating in real-time as the user adjusts subtitle settings. This gives the user immediate visual feedback about how their subtitles will appear in the rendered video.

---

## Instructions

### Step 1 — Create the SubtitlePreview Component

Create `frontend/components/SubtitlePreview.tsx` as a client component. The component accepts `font` (current font path string) and `color` (current hex color string) as props.

### Step 2 — Render the Preview Box

Render a dark gray container (approximately 200 pixels wide by 120 pixels tall) styled to simulate a video background. Use a dark color like `bg-zinc-900` or `bg-gray-800` with rounded corners. This represents the video frame where subtitles appear.

### Step 3 — Render Sample Subtitle Text

Inside the preview box, render sample text at the bottom-center position (mirroring actual subtitle placement in the video). Use the text "The quick brown fox jumps over" as the sample string. Apply the following styles to approximate the actual subtitle rendering:

- **Font:** Use a generic bold sans-serif font family as an approximation (e.g., Arial Black, Helvetica Neue, or the system sans-serif in bold weight). Loading the actual `.ttf` file via CSS `@font-face` is overly complex for a preview — the approximation is sufficient for v1.0.
- **Color:** Apply the `subtitle_color` hex value directly to the text color.
- **Text shadow:** Apply a multi-directional shadow to simulate the stroke/outline effect used in the actual video subtitles. Use shadows in all four diagonal directions with a dark color to create a border effect around the text.
- **Font size:** Scale proportionally to the preview box size — smaller than actual subtitle size but readable.
- **Text alignment:** Center-aligned horizontally, positioned at the bottom of the preview box with some padding.

### Step 4 — Real-Time Updates

The preview should re-render automatically whenever the `font` or `color` props change. Since React re-renders on prop changes by default, no special handling is needed — just ensure the styles are derived from the props.

### Step 5 — Add a Label

Add a small "Preview" label above or inside the preview box to clarify its purpose. Style the label in muted text to avoid competing with the preview content.

---

## Expected Output

A `SubtitlePreview.tsx` component rendering a compact dark preview box with sample subtitle text that updates in real-time to reflect the current font and color settings from the SubtitleSettingsForm.

---

## Validation

- [ ] Preview box renders with a dark background simulating a video frame.
- [ ] Sample subtitle text is positioned at the bottom-center of the preview box.
- [ ] Text color updates in real-time when `subtitle_color` changes.
- [ ] Text has a stroke/shadow effect mimicking actual subtitle rendering.
- [ ] Preview is compact (approximately 200×120 pixels).
- [ ] The preview uses a generic bold font as an approximation.
- [ ] A "Preview" label is visible.

---

## Notes

- The preview is intentionally an approximation, not a pixel-perfect reproduction of the MoviePy TextClip rendering. Loading custom `.ttf` fonts via CSS `@font-face` from the server would require a font-serving endpoint and dynamic style injection — this is disproportionate complexity for a preview. Users can see the exact subtitle rendering in the rendered video output.
- The text shadow CSS technique (multiple shadows in four directions) creates a visual effect similar to the MoviePy TextClip stroke parameter, though not identical. It is close enough for preview purposes.
- The preview box should maintain its aspect ratio and not stretch based on content.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
