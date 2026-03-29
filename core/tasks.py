# ============================================================================
# IIStudio — Task-трекер (аналог Jira, локальный)
# Хранение: .iistudio/tasks.json
# ============================================================================

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

TASKS_DIR = Path(".iistudio")
TASKS_FILE = TASKS_DIR / "tasks.json"


class TaskStatus(str, Enum):
    TODO        = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE        = "DONE"
    BLOCKED     = "BLOCKED"
    CANCELLED   = "CANCELLED"


@dataclass
class Task:
    id: str
    title: str
    description: str = ""
    status: str = TaskStatus.TODO.value
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    done_at: Optional[str] = None
    priority: int = 0  # 0=normal, 1=high, 2=critical
    assignee: Optional[str] = None

    @property
    def short_id(self) -> str:
        return self.id[:6].upper()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class TaskTracker:
    """Локальный task-трекер, аналог Jira board."""

    STATUS_EMOJI = {
        "TODO":        "📋",
        "IN_PROGRESS": "🔄",
        "DONE":        "✅",
        "BLOCKED":     "🚫",
        "CANCELLED":   "❌",
    }

    def __init__(self, tasks_file: Path = TASKS_FILE) -> None:
        self.tasks_file = tasks_file
        self._tasks: Dict[str, Task] = {}
        self._load()

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create(
        self,
        title: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        priority: int = 0,
    ) -> Task:
        """Создать новую задачу."""
        task = Task(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            tags=tags or [],
            priority=priority,
        )
        self._tasks[task.id] = task
        self._save()
        return task

    def get(self, task_id: str) -> Optional[Task]:
        """Найти задачу по ID (полному или короткому)."""
        # Точное совпадение
        if task_id in self._tasks:
            return self._tasks[task_id]
        # Поиск по короткому ID (первые 6 символов)
        query = task_id.upper()
        for t in self._tasks.values():
            if t.short_id == query or t.id.upper().startswith(query):
                return t
        return None

    def list(
        self,
        status: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Task]:
        """Список задач с фильтрацией."""
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status.upper()]
        if tag:
            tasks = [t for t in tasks if tag in t.tags]
        # Сортировка: сначала высокий приоритет, потом по дате
        tasks.sort(key=lambda t: (-t.priority, t.created_at))
        return tasks

    def update_status(self, task_id: str, status: TaskStatus) -> Optional[Task]:
        task = self.get(task_id)
        if not task:
            return None
        task.status = status.value
        task.updated_at = datetime.now(timezone.utc).isoformat()
        if status == TaskStatus.IN_PROGRESS and not task.started_at:
            task.started_at = task.updated_at
        if status == TaskStatus.DONE:
            task.done_at = task.updated_at
        self._save()
        return task

    def start(self, task_id: str) -> Optional[Task]:
        return self.update_status(task_id, TaskStatus.IN_PROGRESS)

    def done(self, task_id: str) -> Optional[Task]:
        return self.update_status(task_id, TaskStatus.DONE)

    def block(self, task_id: str) -> Optional[Task]:
        return self.update_status(task_id, TaskStatus.BLOCKED)

    def cancel(self, task_id: str) -> Optional[Task]:
        return self.update_status(task_id, TaskStatus.CANCELLED)

    def delete(self, task_id: str) -> bool:
        task = self.get(task_id)
        if not task:
            return False
        del self._tasks[task.id]
        self._save()
        return True

    def update(self, task_id: str, **kwargs) -> Optional[Task]:
        task = self.get(task_id)
        if not task:
            return None
        for k, v in kwargs.items():
            if hasattr(task, k):
                setattr(task, k, v)
        task.updated_at = datetime.now(timezone.utc).isoformat()
        self._save()
        return task

    # ── Статистика ────────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, int]:
        counts: Dict[str, int] = {s.value: 0 for s in TaskStatus}
        for t in self._tasks.values():
            counts[t.status] = counts.get(t.status, 0) + 1
        counts["total"] = len(self._tasks)
        return counts

    def format_board(self) -> str:
        """Форматировать доску как Jira."""
        lines = ["", "┌─── IIStudio Tasks ───────────────────────────────────┐"]
        stats = self.stats()
        lines.append(
            f"│  📋 TODO: {stats['TODO']}  🔄 IN_PROGRESS: {stats['IN_PROGRESS']}  "
            f"✅ DONE: {stats['DONE']}  🚫 BLOCKED: {stats['BLOCKED']}  │"
        )
        lines.append("├──────────────────────────────────────────────────────┤")

        tasks = self.list()
        if not tasks:
            lines.append("│  Задач нет. Создай: /task описание задачи           │")
        else:
            for t in tasks:
                emoji = self.STATUS_EMOJI.get(t.status, "?")
                priority_mark = "🔴" if t.priority == 2 else ("🟡" if t.priority == 1 else "")
                tags_str = " ".join(f"#{tag}" for tag in t.tags[:3])
                title = t.title[:40] + ("…" if len(t.title) > 40 else "")
                lines.append(
                    f"│  [{t.short_id}] {emoji} {priority_mark} {title:<42}│"
                )
                if tags_str:
                    lines.append(f"│      {tags_str:<50}│")

        lines.append("└──────────────────────────────────────────────────────┘")
        return "\n".join(lines)

    # ── Персистентность ───────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self.tasks_file.exists():
            self._tasks = {}
            return
        try:
            data = json.loads(self.tasks_file.read_text(encoding="utf-8"))
            self._tasks = {t["id"]: Task.from_dict(t) for t in data.get("tasks", [])}
        except Exception:
            self._tasks = {}

    def _save(self) -> None:
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"tasks": [t.to_dict() for t in self._tasks.values()]}
        self.tasks_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
