# Task 05.03.12 — Update Zustand, API, and Types

## Layer 3 Task Document

---

| **Field**              | **Value**                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| **Task ID**            | 05.03.12                                                                                       |
| **Task Name**          | Update Zustand, API, and Types                                                                 |
| **Sub-Phase**          | 05.03 — Final UI Polish & Testing                                                              |
| **Phase**              | Phase 05 — The Polish                                                                          |
| **Layer**              | Layer 3 (Task Document)                                                                        |
| **Status**             | Not Started                                                                                    |
| **Estimated Complexity** | Medium                                                                                       |
| **Parent Document**    | [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)                           |
| **Dependencies**       | Task 05.03.14 (GlobalSettings Backend API must exist for API layer to call)                    |
| **Output Files**       | `frontend/types/settings.ts` (NEW), `frontend/api/settingsApi.ts` (NEW), `frontend/store/settingsStore.ts` (NEW) |

---

## Objective

Create the TypeScript type definitions, Axios API service layer, and Zustand state store needed to power the GlobalSettings UI components (Tasks 05.03.01–05.03.05) by connecting them to the backend GlobalSettings API (Task 05.03.14).

---

## Instructions

### Step 1 — Define TypeScript Interfaces

Create `frontend/types/settings.ts` containing the TypeScript interfaces for settings data. Define a `GlobalSettings` interface with fields for: default voice identifier (string), subtitle font family (string), subtitle font size (number), subtitle font color (string — hex format), subtitle position (string — "bottom", "center", or "top"), render resolution as a width/height pair (object with width and height numbers), render FPS (number), default Ken Burns zoom level (number), and default transition duration (number). Define a `Voice` interface with fields for: voice identifier (string), display name (string), language (string), and optional sample audio URL (string or null). All interfaces should use TypeScript strict mode conventions — no `any` types, all fields explicitly typed.

### Step 2 — Build the Settings API Service

Create `frontend/api/settingsApi.ts` as an Axios-based service module that mirrors the pattern used by the existing project and segment API services. Implement the following functions:

- `getSettings()` — Sends a GET request to the settings endpoint and returns the current GlobalSettings object. This fetches the singleton settings record from the backend.
- `updateSettings(data: Partial<GlobalSettings>)` — Sends a PATCH request to the settings endpoint with the partial settings object. Returns the updated full GlobalSettings object. Partial updates are used so that the frontend can send only the fields that changed.
- `getVoices()` — Sends a GET request to the voices endpoint and returns an array of available Voice objects. This is a read-only endpoint that lists the Kokoro TTS voices available in the system.
- `uploadFont(file: File)` — Sends a POST request with a multipart form data payload containing the font file. Returns the updated settings object with the new font family name. The file should be sent as a `FormData` object with the field name "font_file".

All functions should follow the existing error handling pattern: let Axios throw on HTTP errors, and let the calling component or store handle the error via try/catch.

### Step 3 — Build the Settings Zustand Store

Create `frontend/store/settingsStore.ts` as a Zustand store that manages the global settings state. The store should hold: the current `GlobalSettings` object (or null if not yet fetched), the list of available `Voice` objects, a loading boolean, and an error string (or null). Implement the following actions:

- `fetchSettings()` — Calls `settingsApi.getSettings()`, sets the settings state on success, and sets the error state on failure. Sets loading to true before the call and false after.
- `saveSettings(data: Partial<GlobalSettings>)` — Calls `settingsApi.updateSettings(data)`, updates the local settings state with the response on success, and sets the error on failure.
- `fetchVoices()` — Calls `settingsApi.getVoices()`, populates the voices array on success, and sets the error on failure.
- `uploadFont(file: File)` — Calls `settingsApi.uploadFont(file)`, updates the settings state with the response (which includes the new font family), and sets the error on failure.

Follow the same Zustand `create` pattern used by the existing project store and segment store in the codebase. Use the `set` function for state updates and keep all async logic inside the action functions.

---

## Expected Output

Three new files: a `settings.ts` types file defining `GlobalSettings` and `Voice` interfaces, a `settingsApi.ts` service with four API functions (get, update, voices, font upload), and a `settingsStore.ts` Zustand store with state management and async actions for settings data.

---

## Validation

- [ ] `GlobalSettings` interface covers all settings fields with proper TypeScript types (no `any`).
- [ ] `Voice` interface covers identifier, display name, language, and optional sample URL.
- [ ] `getSettings()` sends a GET request and returns a `GlobalSettings` object.
- [ ] `updateSettings()` sends a PATCH request with partial data and returns the updated settings.
- [ ] `getVoices()` sends a GET request and returns a `Voice[]` array.
- [ ] `uploadFont()` sends a POST request with `FormData` and returns updated settings.
- [ ] Zustand store holds settings, voices, loading, and error state.
- [ ] `fetchSettings()` action fetches and stores settings with proper loading/error handling.
- [ ] `saveSettings()` action sends partial updates and refreshes local state.
- [ ] `fetchVoices()` action populates the voices list.
- [ ] `uploadFont()` action uploads a font file and updates settings state.
- [ ] All patterns are consistent with the existing Zustand stores in the codebase.

---

## Notes

- This task creates the data layer that all GlobalSettings UI components depend on. While the dependencies technically flow from the UI tasks to this task, this task also depends on the backend API (Task 05.03.14) existing to test against. During development, the API layer can be built against the expected API contract and tested once the backend is ready.
- The settings store follows the singleton pattern — there is only one GlobalSettings record in the entire application, not one per project. This simplifies the store design (no array management, no ID-based lookups).
- Font upload is a special case because it uses `multipart/form-data` instead of `application/json`. The Axios call must construct a `FormData` object rather than sending a plain JSON body. The existing API service pattern may need a slight adaptation for this one endpoint.

---

> **Parent:** [SubPhase_05_03_Overview.md](./SubPhase_05_03_Overview.md) (Layer 2)
> **Phase:** [Phase_05_Overview.md](../Phase_05_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
