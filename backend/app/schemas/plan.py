from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.agentic_plan import PlannerAgentName, PlannerDecisionMode
from app.schemas.task import Task


PlanMode = Literal["single_task", "multi_task"]


class Plan(BaseModel):
    goal: str
    mode: PlanMode
    decision_mode: PlannerDecisionMode | None = None
    needs_clarification: bool = False
    clarification_question: str | None = None
    reasoning_summary: str | None = None
    agents_to_invoke: list[PlannerAgentName] = Field(default_factory=list)
    planner_inputs: dict[str, Any] = Field(default_factory=dict)
    planner_source: str | None = None
    tasks: list[Task] = Field(default_factory=list)
