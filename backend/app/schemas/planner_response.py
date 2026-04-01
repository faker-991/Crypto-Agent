from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.plan import Plan
from app.schemas.task_result import TaskResult


PlannerExecutionStatus = Literal["execute", "clarify", "failed", "partial_failure"]


class PlannerExecutionResponse(BaseModel):
    status: PlannerExecutionStatus
    plan: Plan | None = None
    task_results: list[TaskResult] = Field(default_factory=list)
    final_answer: str | None = None
    execution_summary: dict[str, Any] = Field(default_factory=dict)
    trace_path: str | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
