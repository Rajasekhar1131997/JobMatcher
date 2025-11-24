import threading
from typing import List, Optional
from .models import JobPayload


class JobStore:
    """Thread-safe in-memory job store. Replace with DB in production."""

    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: List[dict] = []

    def add(self, job: JobPayload) -> None:
        with self._lock:
            self._jobs.append(job.dict())

    def all(self, source: Optional[str] = None) -> List[dict]:
        with self._lock:
            if source:
                return [j for j in self._jobs if j.get("source_channel") == source]
            return list(self._jobs)


store = JobStore()
