"""Typed placeholder for the async deletion queue service."""

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True, slots=True)
class DeletionQueueSnapshot:
    """Summarize queue state for health checks and future UI status panels."""

    max_workers: int
    active_jobs: int
    submitted_jobs: int
    completed_jobs: int
    failed_jobs: int


class DeletionQueue:
    """Track queue counters for the future deletion worker implementation."""

    def __init__(self, max_workers: int) -> None:
        self._max_workers = max_workers
        self._active_jobs = 0
        self._submitted_jobs = 0
        self._completed_jobs = 0
        self._failed_jobs = 0
        self._lock = Lock()

    def snapshot(self) -> DeletionQueueSnapshot:
        """Return a point-in-time view of queue counters."""

        with self._lock:
            return DeletionQueueSnapshot(
                max_workers=self._max_workers,
                active_jobs=self._active_jobs,
                submitted_jobs=self._submitted_jobs,
                completed_jobs=self._completed_jobs,
                failed_jobs=self._failed_jobs,
            )
