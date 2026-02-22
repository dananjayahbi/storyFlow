"""
TaskManager — Singleton for background task management.

Provides a single-threaded executor and a thread-safe task registry
for tracking asynchronous audio generation work. All status reads
and writes are guarded by a lock so API threads and background
threads never race on the same dict.

Threading model
~~~~~~~~~~~~~~~
``max_workers=1`` is deliberate: TTS inference is CPU/GPU-intensive.
Tasks submitted while the worker is busy are queued automatically by
``ThreadPoolExecutor``. Each queued task remains in ``PENDING`` state
until the executor picks it up and transitions it to ``PROCESSING``.

Database connections
~~~~~~~~~~~~~~~~~~~~
Worker threads **must** close the Django database connection in a
``finally`` block. Without this, SQLite reports "database is locked"
errors because the background thread holds an open connection.
"""

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from django.db import connection

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Task status constants
# --------------------------------------------------------------------------

TASK_PENDING = "PENDING"
TASK_PROCESSING = "PROCESSING"
TASK_COMPLETED = "COMPLETED"
TASK_FAILED = "FAILED"


# --------------------------------------------------------------------------
# TaskManager singleton
# --------------------------------------------------------------------------


class TaskManager:
    """
    Singleton that owns the application's background thread pool and
    task registry.

    Uses double-checked locking in ``__new__`` to guarantee exactly one
    instance across all threads. The single ``ThreadPoolExecutor`` with
    ``max_workers=1`` ensures TTS jobs run sequentially (to avoid
    OOM / GPU contention).
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        # Fast path — no lock needed
        if cls._instance is not None:
            return cls._instance

        # Slow path — acquire lock
        with cls._instance_lock:
            # Double-check after acquiring lock
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._init()
                cls._instance = instance

        return cls._instance

    # ------------------------------------------------------------------
    # Initialisation (called exactly once, inside __new__)
    # ------------------------------------------------------------------

    def _init(self):
        """Initialise the executor, registry, and lock."""
        from django.conf import settings

        self._executor = ThreadPoolExecutor(max_workers=1)
        self._tasks: dict = {}
        self._tasks_lock = threading.Lock()
        self._cleanup_threshold = getattr(settings, 'TASK_CLEANUP_THRESHOLD', 3600)
        self._is_shutdown = False
        logger.info("TaskManager initialised (max_workers=1)")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit_task(self, task_fn, task_id=None) -> str:
        """
        Register *task_fn* for background execution.

        The task starts in ``PENDING`` and transitions to ``PROCESSING``
        only when the executor's worker thread picks it up (not at
        submission time). If the executor has been shut down, it is
        automatically re-created.

        Args:
            task_fn: A callable that performs the actual work.
            task_id: Optional task identifier. Generated via UUID if omitted.

        Returns:
            The task ID string.
        """
        if task_id is None:
            task_id = str(uuid.uuid4())

        # Register the task as PENDING immediately
        with self._tasks_lock:
            self._tasks[task_id] = {
                "status": TASK_PENDING,
                "progress": {},
                "completed_segments": [],
                "errors": [],
                "cancel_requested": False,
                "created_at": time.time(),
                "completed_at": None,
            }

        def wrapper():
            """
            Background wrapper: PENDING → PROCESSING → COMPLETED/FAILED.

            Always closes the Django DB connection in the ``finally``
            block to prevent SQLite "database is locked" errors.
            """
            try:
                # Transition to PROCESSING when the worker picks up this task
                with self._tasks_lock:
                    if task_id in self._tasks:
                        self._tasks[task_id]["status"] = TASK_PROCESSING

                task_fn()

                with self._tasks_lock:
                    if task_id in self._tasks:
                        self._tasks[task_id]["status"] = TASK_COMPLETED
                        self._tasks[task_id]["completed_at"] = time.time()
            except Exception as exc:
                logger.exception("Task %s failed: %s", task_id, exc)
                with self._tasks_lock:
                    if task_id in self._tasks:
                        self._tasks[task_id]["status"] = TASK_FAILED
                        self._tasks[task_id]["completed_at"] = time.time()
            finally:
                # Critical: close the DB connection held by this worker thread
                connection.close()

        # Handle submission after shutdown — re-create the executor
        try:
            self._executor.submit(wrapper)
        except RuntimeError:
            logger.warning("Executor was shut down — re-creating")
            self._executor = ThreadPoolExecutor(max_workers=1)
            self._is_shutdown = False
            self._executor.submit(wrapper)

        self._cleanup_old_tasks()

        logger.info("Task %s submitted", task_id)
        return task_id

    def get_task_status(self, task_id: str):
        """
        Return a shallow copy of the task state dict, or ``None``.

        The copy prevents race conditions if the caller serialises
        the dict while the background thread mutates the original.
        """
        with self._tasks_lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            return task.copy()

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------

    def shutdown(self, wait=True):
        """
        Gracefully stop the executor.

        Args:
            wait: If True, block until all queued tasks finish.
                  If False, return immediately (tasks may still run).
        """
        self._executor.shutdown(wait=wait)
        self._is_shutdown = True
        logger.info("TaskManager executor shut down (wait=%s)", wait)

    def cancel_task(self, task_id: str) -> bool:
        """
        Request cooperative cancellation of *task_id*.

        This sets a flag that the running task function should check
        after each segment via ``is_cancelled()``. Cancellation is
        best-effort: the currently-running segment always finishes
        because ONNX Runtime inference cannot be interrupted.

        Returns:
            True if the flag was set, False if the task ID is unknown.
        """
        with self._tasks_lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            task["cancel_requested"] = True
            return True

    def is_cancelled(self, task_id: str) -> bool:
        """
        Check whether cancellation has been requested for *task_id*.

        Returns False for unknown task IDs.
        """
        with self._tasks_lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            return task.get("cancel_requested", False)

    # ------------------------------------------------------------------
    # State mutation helpers
    # ------------------------------------------------------------------

    def update_task_progress(self, task_id: str, current: int, total: int, **kwargs):
        """
        Update the progress sub-dict for *task_id*.

        Computes percentage as an integer (0–100). Extra keyword
        arguments (e.g. ``current_segment_id``) are merged in.
        """
        with self._tasks_lock:
            task = self._tasks.get(task_id)
            if task is None:
                return

            percentage = int((current / total) * 100) if total > 0 else 0

            task["progress"] = {
                "current": current,
                "total": total,
                "percentage": percentage,
                **kwargs,
            }

    def add_completed_segment(self, task_id: str, segment_id, result: dict):
        """
        Append a completed segment record to the task's list.

        Args:
            task_id: The task identifier.
            segment_id: Segment primary key.
            result: Dict with at least ``audio_url`` and ``duration``.
        """
        with self._tasks_lock:
            task = self._tasks.get(task_id)
            if task is None:
                return

            task["completed_segments"].append({
                "segment_id": segment_id,
                "audio_url": result.get("audio_url", ""),
                "duration": result.get("duration", 0),
            })

    def add_error(self, task_id: str, segment_id, error_message: str):
        """
        Append an error record to the task's error list.

        Args:
            task_id: The task identifier.
            segment_id: Segment primary key.
            error_message: Human-readable error description.
        """
        with self._tasks_lock:
            task = self._tasks.get(task_id)
            if task is None:
                return

            task["errors"].append({
                "segment_id": segment_id,
                "error": error_message,
            })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cleanup_old_tasks(self):
        """Remove completed / failed tasks older than the threshold."""
        now = time.time()
        with self._tasks_lock:
            stale_ids = [
                tid
                for tid, t in self._tasks.items()
                if t["completed_at"] is not None
                and (now - t["completed_at"]) > self._cleanup_threshold
            ]
            for tid in stale_ids:
                del self._tasks[tid]

        if stale_ids:
            logger.info("Cleaned up %d stale task(s)", len(stale_ids))


# --------------------------------------------------------------------------
# Module-level convenience accessor
# --------------------------------------------------------------------------


def get_task_manager() -> TaskManager:
    """Return the TaskManager singleton instance."""
    return TaskManager()


# --------------------------------------------------------------------------
# Background render task function
# --------------------------------------------------------------------------


def render_task_function(project_id: str, task_id: str) -> None:
    """Background task that renders a project's video.

    Bridges the TaskManager infrastructure (Phase 03) with the video
    renderer (SubPhases 04.01–04.02).  Runs on the TaskManager's
    ``ThreadPoolExecutor``, calls ``render_project`` with a progress
    callback that feeds real-time updates into TaskManager, and
    transitions the ``Project`` status to COMPLETED or FAILED.

    Args:
        project_id: UUID string of the project to render.
        task_id:    TaskManager-assigned identifier (``render_{project_id}``).

    Note:
        Imports are deferred to avoid circular dependencies.
        The Project is **always** re-queried from the database — a
        model instance must never be shared across threads.
    """
    # Step 2 — deferred imports
    from core_engine.video_renderer import render_project  # noqa: E402
    from api.models import Project, STATUS_COMPLETED, STATUS_FAILED  # noqa: E402

    tm = get_task_manager()

    # Step 3 — progress callback
    def on_progress(current, total, phase):
        """Feed per-segment progress into the TaskManager registry."""
        tm.update_task_progress(
            task_id,
            current=current,
            total=total,
            description=phase,
        )

    try:
        # Step 4 — blocking render call
        result = render_project(project_id, on_progress=on_progress)

        # Step 5 — success: update Project model
        project = Project.objects.get(id=project_id)
        project.status = STATUS_COMPLETED
        project.output_path = result.get("output_path", "")
        project.save(update_fields=["status", "output_path"])

        # Store result data in TaskManager progress for the status endpoint
        tm.update_task_progress(
            task_id,
            current=result.get("total_segments", 0),
            total=result.get("total_segments", 0),
            description="Export complete",
            output_path=result.get("output_path", ""),
            duration=result.get("duration", 0),
            file_size=result.get("file_size", 0),
        )

    except Exception as exc:
        # Step 6 — failure: log error, set FAILED status
        logger.error(
            "Render failed for project %s: %s", project_id, exc,
            exc_info=True,
        )
        try:
            project = Project.objects.get(id=project_id)
            project.status = STATUS_FAILED
            project.save(update_fields=["status"])
        except Exception:
            pass  # prevent cascading if DB is also inaccessible

        # Re-raise so the TaskManager wrapper marks the task as FAILED
        raise
