from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.task import TaskType


TaskStatus = Literal["success", "insufficient", "failed"]


class TaskResult(BaseModel):
    task_id: str
    task_type: TaskType
    agent: str
    status: TaskStatus
    payload: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None
    evidence_sufficient: bool | None = None
    missing_information: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    rounds_used: int | None = None
