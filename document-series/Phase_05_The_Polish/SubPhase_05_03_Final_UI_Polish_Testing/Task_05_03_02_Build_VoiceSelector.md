# Task 05.03.02 — Build VoiceSelector

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.02                                                                                       |
| **Task Name**          | Build VoiceSelector                                                                            |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Medium                                                                                       |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | Task 05.03.12 (Zustand store and API types must include Voice interface and fetchVoices)        |
| **Output Files**       | `frontend/components/VoiceSelector.tsx` (NEW)                                                  |

---

## Objective

Build a dropdown component that displays all available Kokoro TTS voice IDs, allows the user to select a default voice for audio generation, and shows a warning toast when the voice is changed reminding the user to re-generate audio.

---

## Instructions

### Step 1 — Create the VoiceSelector Component

Create `frontend/components/VoiceSelector.tsx` as a client component. The component accepts props for the current `value` (the selected voice ID string), and an `onChange` callback for persisting changes.

### Step 2 — Fetch Available Voices

On mount, call `fetchVoices()` from the Zustand settings store to populate the `availableVoices` list from `GET /api/settings/voices/`. While voices are loading (`isVoicesLoading` is true), render the Shadcn/UI `Select` component in a disabled state with placeholder text "Loading voices...".

### Step 3 — Render the Voice Dropdown

Use the Shadcn/UI `Select` component to render the dropdown. Each option should display the voice name in a user-friendly format: for example "Bella (Female)" or "Adam (Male)", constructed from the voice object's `name` and `gender` fields. The `value` of each option is the voice's `id` string (e.g., "af_bella"). Highlight the currently selected voice.

### Step 4 — Handle Voice Selection Change

When the user selects a different voice, call the `onChange` callback with `{ default_voice_id: selectedVoiceId }`. After the change is persisted, show a **warning** toast with the message: "Voice changed. Re-generate audio to hear the new voice." This warning is critical because changing the voice setting does not automatically re-generate existing audio segments — the user must manually trigger audio regeneration.

### Step 5 — Implement Fallback Voice List

If the `GET /api/settings/voices/` API call fails (network error, backend down), fall back to the hardcoded `AVAILABLE_VOICES` list from `lib/constants.ts`. Show the dropdown with the fallback voices and log a console warning about the API failure. The user can still select voices even if the API-fetched list is unavailable.

### Step 6 — Add Section Label

Add a section header above the dropdown: a label with a microphone or speaker icon and the text "Voice". This helps visually organize the settings panel.

---

## Expected Output

A `VoiceSelector.tsx` component that renders a Shadcn/UI Select dropdown populated with available Kokoro voices, fires a warning toast on voice change, and falls back to a hardcoded voice list if the API is unavailable.

---

## Validation

- [ ] Voice dropdown renders with all available Kokoro voice IDs.
- [ ] Voice names display in user-friendly format (e.g., "Bella (Female)").
- [ ] Currently selected voice is highlighted in the dropdown.
- [ ] Changing the voice calls `onChange` with the new voice ID.
- [ ] Warning toast appears: "Voice changed. Re-generate audio to hear the new voice."
- [ ] Loading state shows a disabled dropdown with placeholder text.
- [ ] Fallback to `AVAILABLE_VOICES` from constants works when the API fails.

---

## Notes

- The `default_voice_id` is stored as a string in `GlobalSettings` (e.g., "af_bella"). This maps to a Kokoro voice configuration file.
- The warning toast is essential UX — without it, users may assume the voice change takes effect immediately on existing audio, leading to confusion when they hear the old voice.
- The voice list endpoint scans available Kokoro voice files on the backend. If new voices are added to the Kokoro model directory, they automatically appear in this dropdown on the next fetch.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
