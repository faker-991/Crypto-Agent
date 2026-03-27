from typing import Literal

from pydantic import BaseModel, Field


IntentName = Literal[
    "asset_due_diligence",
    "kline_analysis",
    "new_token_review",
    "watchlist_review",
    "watchlist_update",
    "thesis_break_check",
    "report_generation",
    "memory_query",
    "other",
]


class IntentResult(BaseModel):
    intent: IntentName
    asset: str | None = None
    assets: list[str] = Field(default_factory=list)
    timeframes: list[str] = Field(default_factory=list)
    horizon: str | None = None
    requested_action: str | None = None
    focus: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    need_followup: bool = False
    followup_question: str | None = None


class SessionState(BaseModel):
    current_asset: str | None = None
    last_intent: str | None = None
    last_timeframes: list[str] = Field(default_factory=list)
    last_report_type: str | None = None
    recent_assets: list[str] = Field(default_factory=list)
    current_task: str | None = None
    last_skill: str | None = None
    last_agent: str | None = None


class RouteMapping(BaseModel):
    agent: str | None = None
    skill: str | None = None


class RouteExecutionResult(BaseModel):
    type: Literal["execute", "clarify", "fallback"]
    agent: str | None = None
    skill: str | None = None
    payload: dict = Field(default_factory=dict)
    intent_result: IntentResult | None = None
    question: str | None = None
    message: str | None = None


class RouteRequest(BaseModel):
    user_query: str
