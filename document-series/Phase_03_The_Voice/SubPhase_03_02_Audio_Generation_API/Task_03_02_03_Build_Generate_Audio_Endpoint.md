# Task 03.02.03 — Build Generate Audio Endpoint

> **Sub-Phase:** 03.02 — Audio Generation API
> **Phase:** Phase 03 — The Voice
> **Complexity:** High
> **Dependencies:** Task 03.02.01 (TaskManager), Task 03.02.02 (ThreadPool)
> **Parent Document:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md)

---

## Objective

Implement the `POST /api/segments/{id}/generate-audio/` DRF action on `SegmentViewSet` that validates the segment, reads global TTS settings, and spawns a background task to generate audio for a single segment.

---

## Instructions

### Step 1 — Add imports to views.py

Import `get_task_manager` from `api.tasks`, `KokoroModelLoader` from `core_engine.model_loader`, `GlobalSettings` from the models module, and `uuid4` from `uuid`.

### Step 2 — Add the `generate_audio` action

Add a `@action(detail=True, methods=['post'], url_path='generate-audio')` method to `SegmentViewSet`. Use `self.get_object()` to fetch the segment (DRF handles 404 automatically).

### Step 3 — Validate text content

Check that `segment.text_content` is non-empty after stripping whitespace. If empty, return HTTP 400 with an error message explaining the segment has no text to generate audio from.

### Step 4 — Check lock state

If `segment.is_locked` is `True`, return HTTP 409 Conflict with an error message instructing the user to unlock before generating audio. This differs from the bulk endpoint, which silently skips locked segments.

### Step 5 — Check TTS model availability

Call `KokoroModelLoader.is_model_available()`. If the model is not available, return HTTP 503 Service Unavailable with a message telling the user to install the Kokoro ONNX model file.

### Step 6 — Read GlobalSettings

Fetch the `GlobalSettings` singleton using `get_or_create()` or `first()` with a fallback to `create()`. Extract `default_voice_id` and `tts_speed`.

### Step 7 — Define the background task function

Create a closure `task_fn()` that imports `generate_audio`, `construct_audio_path`, and `construct_audio_url` from `core_engine.tts_wrapper` (lazy import inside the function to avoid circular imports). Build the output path, call `generate_audio()` with the segment's text, the voice ID, speed, and output path. If the result dict has `success: True`, update the segment's `audio_file` (URL path) and `audio_duration` fields and call `save(update_fields=[...])`. If `success: False`, raise an `Exception` with the error message — the TaskManager wrapper will catch it and mark the task as `FAILED`.

### Step 8 — Submit the task and return 202

Generate a task ID in the format `tts_{segment_id}_{uuid_hex_8chars}`. Submit the task function to `get_task_manager().submit_task()`. Return HTTP 202 Accepted with a JSON body containing `task_id`, `segment_id`, `status: "PENDING"`, and a `message`.

---

## Expected Output

```
backend/
└── api/
    └── views.py                ← MODIFIED (generate_audio action added to SegmentViewSet)
```

---

## Validation

- [ ] `POST /api/segments/{id}/generate-audio/` returns 202 with a `task_id`.
- [ ] Empty `text_content` returns 400 with descriptive error.
- [ ] Locked segment returns 409 with descriptive error.
- [ ] Missing TTS model returns 503.
- [ ] Non-existent segment returns 404.
- [ ] Background task generates a `.wav` file at the expected path.
- [ ] After task completion, `Segment.audio_file` and `audio_duration` are populated.

---

## Notes

- The `task_fn` closure captures `segment` and `settings_obj` from the outer scope. For a single-segment call, this is safe — the segment object is read in the background thread and `.save(update_fields=[...])` is a simple atomic SQL UPDATE.
- Return 202 (Accepted), not 200 — the operation is asynchronous. The client must poll the task status endpoint for completion.
- The `get_object()` call uses DRF's built-in 404 logic — no need to manually handle `DoesNotExist`.
- The task ID format includes the segment ID for debuggability in logs.

---

> **Parent:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_02_02_Implement_ThreadPoolExecutor.md](./Task_03_02_02_Implement_ThreadPoolExecutor.md)
> **Next Task:** [Task_03_02_04_Build_Generate_All_Audio_Endpoint.md](./Task_03_02_04_Build_Generate_All_Audio_Endpoint.md)
