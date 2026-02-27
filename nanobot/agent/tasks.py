"""Task management system for agent planning and todo tracking."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from nanobot.session.manager import Session


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Task:
    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", TaskStatus.PENDING.value)),
            dependencies=data.get("dependencies", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata", {}),
        )


class TodoStore:
    """Persistent storage for tasks."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.tasks_file = workspace / "memory" / "TASKS.json"
        self._ensure_dir()

    def _ensure_dir(self):
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)

    def load_tasks(self) -> dict[str, Task]:
        if not self.tasks_file.exists():
            return {}
        try:
            data = json.loads(self.tasks_file.read_text(encoding="utf-8"))
            return {tid: Task.from_dict(t) for tid, t in data.items()}
        except Exception as e:
            logger.warning("Failed to load tasks: {}", e)
            return {}

    def save_tasks(self, tasks: dict[str, Task]) -> None:
        self._ensure_dir()
        data = {tid: task.to_dict() for tid, task in tasks.items()}
        self.tasks_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_task(self, task: Task) -> None:
        tasks = self.load_tasks()
        tasks[task.id] = task
        self.save_tasks(tasks)
        logger.info("Task added: {} - {}", task.id, task.title)

    def update_task(self, task_id: str, **kwargs) -> Task | None:
        tasks = self.load_tasks()
        if task_id not in tasks:
            return None
        task = tasks[task_id]
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        task.updated_at = datetime.now().isoformat()
        self.save_tasks(tasks)
        logger.info("Task updated: {} - {}", task_id, kwargs)
        return task

    def delete_task(self, task_id: str) -> bool:
        tasks = self.load_tasks()
        if task_id in tasks:
            del tasks[task_id]
            self.save_tasks(tasks)
            logger.info("Task deleted: {}", task_id)
            return True
        return False

    def get_task(self, task_id: str) -> Task | None:
        tasks = self.load_tasks()
        return tasks.get(task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        tasks = self.load_tasks()
        if status:
            return [t for t in tasks.values() if t.status == status]
        return list(tasks.values())

    def clear_completed(self) -> int:
        tasks = self.load_tasks()
        completed = [tid for tid, t in tasks.items() if t.status == TaskStatus.COMPLETED]
        for tid in completed:
            del tasks[tid]
        self.save_tasks(tasks)
        logger.info("Cleared {} completed tasks", len(completed))
        return len(completed)


class TaskTracker:
    """Track task execution during agent loop."""

    def __init__(self, session_key: str):
        self.session_key = session_key
        self.active_tasks: list[str] = []
        self.completed_tasks: list[str] = []
        self.current_task: str | None = None

    def start_task(self, task_id: str) -> None:
        if self.current_task:
            self.active_tasks.append(self.current_task)
        self.current_task = task_id
        logger.debug("Started task: {} for session {}", task_id, self.session_key)

    def complete_task(self, task_id: str) -> None:
        if task_id == self.current_task:
            self.current_task = None
            if self.active_tasks:
                self.current_task = self.active_tasks.pop()
        self.completed_tasks.append(task_id)
        logger.debug("Completed task: {} for session {}", task_id, self.session_key)

    def fail_task(self, task_id: str) -> None:
        if task_id == self.current_task:
            self.current_task = None
            if self.active_tasks:
                self.current_task = self.active_tasks.pop()
        logger.debug("Failed task: {} for session {}", task_id, self.session_key)

    def get_status(self) -> dict:
        return {
            "session_key": self.session_key,
            "current_task": self.current_task,
            "active_tasks": self.active_tasks,
            "completed_tasks": self.completed_tasks,
        }
