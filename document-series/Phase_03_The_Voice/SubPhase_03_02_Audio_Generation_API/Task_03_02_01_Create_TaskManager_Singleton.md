# Task 03.02.01 — Create TaskManager Singleton

> **Sub-Phase:** 03.02 — Audio Generation API
> **Phase:** Phase 03 — The Voice
> **Complexity:** High
> **Dependencies:** None
> **Parent Document:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md)

---

## Objective

Implement the core `TaskManager` singleton class that manages background task registration, status tracking, and lifecycle. This is the foundation for all asynchronous audio generation work in StoryFlow.

---

## Instructions

### Step 1 — Create the tasks module

Create `backend/api/tasks.py`. Import `threading`, `time`, `logging`, and `concurrent.futures`.

### Step 2 — Define task status constants

Define module-level constants for the four task states: `TASK_PENDING = "PENDING"`, `TASK_PROCESSING = "PROCESSING"`, `TASK_COMPLETED = "COMPLETED"`, `TASK_FAILED = "FAILED"`. These are simple strings, not an Enum, for JSON serialization simplicity.

### Step 3 — Implement the singleton pattern

Implement `TaskManager` using the double-checked locking singleton pattern. The `__new__` method acquires a class-level `threading.Lock`, checks if `_instance` is `None`, and creates the instance if so. The `_init()` method (called once during first creation) initializes: a `ThreadPoolExecutor(max_workers=1)`, an empty `_tasks` dictionary for the task registry, a `threading.Lock` named `_tasks_lock` for thread-safe access, and a `_cleanup_threshold` of 3600 seconds (1 hour).

### Step 4 — Implement `submit_task(task_fn, task_id=None) → str`

Accept a callable and an optional task ID. If no ID is provided, generate one using UUID. Register the task in `_tasks` with status `PENDING`, empty progress, empty completed segments list, empty errors list, a `created_at` timestamp, and `completed_at` as `None`. Wrap `task_fn` in a `wrapper()` that transitions status to `PROCESSING` at start, then to `COMPLETED` on success or `FAILED` on exception, always setting `completed_at`. Submit the wrapper to the executor. Trigger cleanup of old tasks. Return the task ID.

### Step 5 — Implement `get_task_status(task_id) → dict | None`

Acquire `_tasks_lock`, look up the task ID, and return a shallow copy of the task state dict (to prevent race conditions during response serialization). Return `None` if the task ID is not found.

### Step 6 — Implement public state mutation methods

Implement `update_task_progress(task_id, current, total, **kwargs)` to update the progress sub-dict with current, total, percentage (integer 0–100), and any additional kwargs like `current_segment_id`. Implement `add_completed_segment(task_id, segment_id, result)` to append a dict with `segment_id`, `audio_url`, and `duration` to the completed segments list. Implement `add_error(task_id, segment_id, error_message)` to append a dict with `segment_id` and `error` to the errors list. All three methods must acquire `_tasks_lock` and silently ignore unknown task IDs.

### Step 7 — Add a convenience accessor

Add a module-level function `get_task_manager() → TaskManager` that simply returns `TaskManager()`. This provides a clean import for other modules.

---

## Expected Output

```
backend/
└── api/
    └── tasks.py                ← CREATED
```

---

## Validation

- [ ] `TaskManager()` returns the same instance on repeated calls (singleton).
- [ ] `submit_task()` registers a task with `PENDING` status and returns a task ID.
- [ ] `get_task_status()` returns a dict copy of the task state.
- [ ] `get_task_status()` returns `None` for unknown task IDs.
- [ ] `update_task_progress()` correctly computes percentage as an integer.
- [ ] `update_task_progress()` handles `total=0` without division-by-zero.
- [ ] All state mutations are guarded by `_tasks_lock`.
- [ ] `get_task_manager()` returns the singleton instance.

---

## Notes

- The singleton is critical: there must be exactly ONE thread pool and ONE task registry in the application. Multiple instances would create multiple executors, defeating the `max_workers=1` constraint.
- `max_workers=1` is deliberate — TTS inference is CPU/GPU-intensive. Concurrent inference on a single machine would either OOM or severely degrade performance.
- The `wrapper()` function runs in the background thread and MUST handle all exceptions. Unhandled exceptions in `ThreadPoolExecutor` futures are silently swallowed.
- The `_tasks_lock` protects against concurrent access from the API request thread (reading status) and the background thread (writing status).

---

> **Parent:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Next Task:** [Task_03_02_02_Implement_ThreadPoolExecutor.md](./Task_03_02_02_Implement_ThreadPoolExecutor.md)
