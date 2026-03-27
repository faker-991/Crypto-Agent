from typing import Any, Literal

from pydantic import BaseModel, Field


PlannerDecisionMode = Literal["clarify", "research_only", "kline_only", "mixed_analysis"]
PlannerAgentName = Literal["ResearchAgent", "KlineAgent", "SummaryAgent"]


class PlannerDecision(BaseModel):
    mode: PlannerDecisionMode
    goal: str
    requires_clarification: bool = False
    clarification_question: str | None = None
    agents_to_invoke: list[PlannerAgentName] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    reasoning_summary: str | None = None
