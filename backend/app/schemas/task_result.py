from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.task import TaskType


TaskStatus = Literal["success", "insufficient", "failed", "degraded"]
EvidenceStatus = Literal["sufficient", "insufficient", "failed"]


class TaskResult(BaseModel):
    task_id: str
    task_type: TaskType
    agent: str
    status: TaskStatus
    payload: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None
    evidence_sufficient: bool | None = None
    evidence_status: EvidenceStatus | None = None
    missing_information: list[str] = Field(default_factory=list)
    degraded_reason: str | None = None
    termination_reason: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    rounds_used: int | None = None
    start_ts: str | None = None
    end_ts: str | None = None
    duration_ms: float | None = None
