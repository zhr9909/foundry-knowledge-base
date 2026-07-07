from __future__ import annotations
import time
import threading
from typing import Optional
from .protocol import Task, TaskStatus


class TaskManager:
    """Manages task lifecycle with thread-safe operations."""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def create_task(self, task: Task) -> Task:
        with self._lock:
            self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.is_expired() and task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                task.status = TaskStatus.FAILED
                task.error = {"code": "TIMEOUT", "message": "Task expired"}
                task.completed_at = time.time()
            return task

    def update_task(self, task_id: str, **kwargs) -> Optional[Task]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                for k, v in kwargs.items():
                    setattr(task, k, v)
            return task

    def cancel_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                task.status = TaskStatus.CANCELLED
                task.completed_at = time.time()
            return task

    def list_tasks(self, limit: int = 20) -> list:
        with self._lock:
            return sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)[:limit]

    def clean_expired(self):
        with self._lock:
            now = time.time()
            expired = [tid for tid, t in list(self._tasks.items())
                       if now - t.created_at > t.ttl_seconds * 2
                       and t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)]
            for tid in expired:
                del self._tasks[tid]
