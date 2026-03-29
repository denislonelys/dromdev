# ============================================================================
# IIStudio — Очередь задач (asyncio-based)
# ============================================================================

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class TaskStatus(str, Enum):
    PENDING    = "pending"
    IN_PROGRESS = "in_progress"
    DONE       = "done"
    FAILED     = "failed"
    CANCELLED  = "cancelled"


@dataclass
class Task:
    task_id: str
    func: Callable
    args: tuple
    kwargs: dict
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    priority: int = 0  # выше = важнее

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "priority": self.priority,
        }


class TaskQueue:
    """Asyncio очередь задач с приоритетами и отслеживанием статусов."""

    def __init__(self, max_size: int = 1000) -> None:
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_size)
        self._tasks: Dict[str, Task] = {}
        self._lock = asyncio.Lock()

    async def submit(
        self,
        func: Callable,
        *args: Any,
        priority: int = 0,
        task_id: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Добавить задачу в очередь.

        Args:
            func: async функция для выполнения
            *args: аргументы
            priority: приоритет (выше = раньше выполняется)
            task_id: кастомный ID (автогенерируется если None)
            **kwargs: именованные аргументы

        Returns:
            task_id
        """
        tid = task_id or str(uuid.uuid4())[:8]
        task = Task(
            task_id=tid,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
        )
        async with self._lock:
            self._tasks[tid] = task
        # PriorityQueue: меньше число = выше приоритет, поэтому инвертируем
        await self._queue.put((-priority, tid, task))
        return tid

    async def get(self) -> Task:
        """Получить следующую задачу из очереди (блокирует если пуста)."""
        _, _, task = await self._queue.get()
        return task

    def task_done(self) -> None:
        self._queue.task_done()

    async def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task:
                return task.to_dict()
        return None

    async def get_all(self) -> List[Dict[str, Any]]:
        async with self._lock:
            return [t.to_dict() for t in self._tasks.values()]

    async def cancel(self, task_id: str) -> bool:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                return True
        return False

    async def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Any = None,
        error: Optional[str] = None,
    ) -> None:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = status
                if result is not None:
                    task.result = result
                if error is not None:
                    task.error = error
                now = datetime.now(timezone.utc).isoformat()
                if status == TaskStatus.IN_PROGRESS:
                    task.started_at = now
                elif status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED):
                    task.finished_at = now

    @property
    def qsize(self) -> int:
        return self._queue.qsize()

    @property
    def total_tasks(self) -> int:
        return len(self._tasks)
