# Task 03.02.02 — Implement ThreadPoolExecutor Integration

> **Sub-Phase:** 03.02 — Audio Generation API
> **Phase:** Phase 03 — The Voice
> **Complexity:** Medium
> **Dependencies:** Task 03.02.01 (TaskManager Singleton)
> **Parent Document:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md)

---

## Objective

Harden the ThreadPoolExecutor integration with proper task queueing semantics, graceful shutdown support, cancel support, and database connection cleanup in worker threads.

---

## Instructions

### Step 1 — Refine the wrapper function

The `wrapper()` inside `submit_task()` must transition the task from `PENDING` to `PROCESSING` when the executor picks it up (not when `submit_task()` is called). After `task_fn()` completes, set status to `COMPLETED`. On any exception, set status to `FAILED`, record the error string, and always set `completed_at`. Critically, close the Django database connection at the end of the wrapper using `django.db.connection.close()` in a `finally` block — without this, SQLite may report "database is locked" errors.

### Step 2 — Handle task queuing

With `max_workers=1`, tasks submitted while the worker is busy are queued automatically by `ThreadPoolExecutor`. No special code is needed. The task remains in `PENDING` state until the executor picks it up. Document this behavior clearly in code comments.

### Step 3 — Implement graceful shutdown

Add a `shutdown(self, wait=True)` method that calls `self._executor.shutdown(wait=wait)`. This should be called on Django server shutdown. Also handle the edge case where `submit_task()` is called after shutdown — `ThreadPoolExecutor.submit()` raises `RuntimeError` in this case. Catch it and either re-create the executor or return an error.

### Step 4 — Implement best-effort cancel support

Add `cancel_task(self, task_id)` that sets a `cancel_requested` flag on the task state dict. Add `is_cancelled(self, task_id) → bool` that reads the flag. Both methods must acquire `_tasks_lock`. The batch task function (in Task 03.02.04) checks `is_cancelled()` after each segment and breaks if true. Cancellation is best-effort: the currently-running segment always finishes because ONNX Runtime inference cannot be interrupted mid-execution.

---

## Expected Output

```
backend/
└── api/
    └── tasks.py                ← MODIFIED (wrapper refined, shutdown, cancel)
```

---

## Validation

- [ ] Task transitions `PENDING → PROCESSING` only when the executor starts it, not at submission time.
- [ ] Django database connections are closed in the worker thread's `finally` block.
- [ ] `shutdown()` cleanly stops the executor.
- [ ] `cancel_task()` sets the cancel flag on the task.
- [ ] `is_cancelled()` returns `True` after `cancel_task()` is called.
- [ ] Submitting after shutdown is handled gracefully (no crash).

---

## Notes

- The `PENDING → PROCESSING` distinction matters for the polling UI: the frontend can show "waiting in queue" vs. "generating audio" based on this.
- Database connection cleanup is critical for SQLite. Without `connection.close()`, the background thread holds a connection that may lock the database for other threads.
- Cancel is purely cooperative — the background task must check the flag. There is no mechanism to force-kill a running ONNX inference.
- For StoryFlow's single-user context, the shutdown method may rarely be called explicitly, but it prevents resource leaks in test environments.

---

> **Parent:** [SubPhase_03_02_Overview.md](./SubPhase_03_02_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_02_01_Create_TaskManager_Singleton.md](./Task_03_02_01_Create_TaskManager_Singleton.md)
> **Next Task:** [Task_03_02_03_Build_Generate_Audio_Endpoint.md](./Task_03_02_03_Build_Generate_Audio_Endpoint.md)
