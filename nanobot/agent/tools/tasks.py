"""Task management tools for agent."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from nanobot.agent.tasks import Task, TaskStatus, TodoStore
from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.session.manager import Session


class CreateTaskTool(Tool):
    """Tool to create a new task."""

    def __init__(self, workspace: Path):
        self._store = TodoStore(workspace)

    @property
    def name(self) -> str:
        return "create_task"

    @property
    def description(self) -> str:
        return "Create a new task in the todo list. Use this when you need to track a subtask or step."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Brief title of the task (max 100 chars)",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of what needs to be done",
                },
                "dependencies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of task IDs that must be completed before this task",
                },
            },
            "required": ["title"],
        }

    async def execute(self, **kwargs) -> str:
        title = kwargs.get("title", "")
        description = kwargs.get("description", "")
        dependencies = kwargs.get("dependencies", [])

        task = Task(
            id=str(uuid.uuid4()),
            title=title[:100],
            description=description,
            dependencies=dependencies or [],
        )
        self._store.add_task(task)
        return f"Task created: {task.id} - {task.title}"


class UpdateTaskStatusTool(Tool):
    """Tool to update task status."""

    def __init__(self, workspace: Path):
        self._store = TodoStore(workspace)

    @property
    def name(self) -> str:
        return "update_task_status"

    @property
    def description(self) -> str:
        return "Update the status of a task (pending, in_progress, completed, failed, skipped)"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "ID of the task to update",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "failed", "skipped"],
                    "description": "New status for the task",
                },
            },
            "required": ["task_id", "status"],
        }

    async def execute(self, **kwargs) -> str:
        task_id = kwargs.get("task_id", "")
        status = kwargs.get("status", "")

        task = self._store.update_task(task_id, status=TaskStatus(status))
        if task:
            return f"Task updated: {task_id} -> {status}"
        return f"Task not found: {task_id}"


class ListTasksTool(Tool):
    """Tool to list tasks."""

    def __init__(self, workspace: Path):
        self._store = TodoStore(workspace)

    @property
    def name(self) -> str:
        return "list_tasks"

    @property
    def description(self) -> str:
        return "List all tasks, optionally filtered by status"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "failed", "skipped"],
                    "description": "Filter tasks by status (omit to list all)",
                },
            },
        }

    async def execute(self, **kwargs) -> str:
        status = kwargs.get("status")
        filter_status = TaskStatus(status) if status else None
        tasks = self._store.list_tasks(filter_status)

        if not tasks:
            return "No tasks found."

        lines = [f"## Tasks ({len(tasks)})\n"]
        for task in tasks:
            deps = f" [depends: {', '.join(task.dependencies)}]" if task.dependencies else ""
            lines.append(f"- [{task.status.value}] {task.id[:8]}: {task.title}{deps}")
            if task.description:
                lines.append(f"  {task.description}")

        return "\n".join(lines)


class GetTaskTool(Tool):
    """Tool to get task details."""

    def __init__(self, workspace: Path):
        self._store = TodoStore(workspace)

    @property
    def name(self) -> str:
        return "get_task"

    @property
    def description(self) -> str:
        return "Get details of a specific task"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "ID of the task to retrieve",
                },
            },
            "required": ["task_id"],
        }

    async def execute(self, **kwargs) -> str:
        task_id = kwargs.get("task_id", "")
        task = self._store.get_task(task_id)

        if not task:
            return f"Task not found: {task_id}"

        return f"""Task: {task.title}
ID: {task.id}
Status: {task.status.value}
Description: {task.description}
Dependencies: {', '.join(task.dependencies) if task.dependencies else 'none'}
Created: {task.created_at}
Updated: {task.updated_at}"""


class DeleteTaskTool(Tool):
    """Tool to delete a task."""

    def __init__(self, workspace: Path):
        self._store = TodoStore(workspace)

    @property
    def name(self) -> str:
        return "delete_task"

    @property
    def description(self) -> str:
        return "Delete a task from the todo list"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "ID of the task to delete",
                },
            },
            "required": ["task_id"],
        }

    async def execute(self, **kwargs) -> str:
        task_id = kwargs.get("task_id", "")

        if self._store.delete_task(task_id):
            return f"Task deleted: {task_id}"
        return f"Task not found: {task_id}"


class PlanTasksTool(Tool):
    """Tool to plan tasks."""

    def __init__(self, workspace: Path):
        self._store = TodoStore(workspace)

    @property
    def name(self) -> str:
        return "plan_tasks"

    @property
    def description(self) -> str:
        return "Break down a complex task into smaller subtasks. Returns a plan with task IDs."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "The main goal or task to break down",
                },
                "steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of steps to achieve the goal (ordered)",
                },
            },
            "required": ["goal", "steps"],
        }

    async def execute(self, **kwargs) -> str:
        goal = kwargs.get("goal", "")
        steps = kwargs.get("steps", [])

        task_ids = []
        prev_id = None

        for i, step in enumerate(steps, 1):
            dependencies = [prev_id] if prev_id else []
            task = Task(
                id=str(uuid.uuid4()),
                title=f"Step {i}: {step[:80]}",
                description=f"Part of goal: {goal}",
                dependencies=dependencies,
            )
            self._store.add_task(task)
            task_ids.append(task.id)
            prev_id = task.id

        return f"""Plan created for: {goal}
Total steps: {len(steps)}
Task IDs: {', '.join([tid[:8] for tid in task_ids])}
Use list_tasks() to see all tasks."""
