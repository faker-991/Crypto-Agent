from typing import Literal

from pydantic import BaseModel, Field


RequestType = Literal["single_task", "multi_task", "follow_up", "unclear"]


class UserRequest(BaseModel):
    raw_query: str
    normalized_goal: str
    request_type: RequestType


class SessionContext(BaseModel):
    current_asset: str | None = None
    last_intent: str | None = None
    last_timeframes: list[str] = Field(default_factory=list)
    active_topic: str | None = None


class RecentContext(BaseModel):
    recent_task_summaries: list[str] = Field(default_factory=list)


class MemoryContext(BaseModel):
    relevant_memories: list[str] = Field(default_factory=list)


class Capabilities(BaseModel):
    available_agents: list[str] = Field(default_factory=list)
    available_tools: dict[str, list[str]] = Field(default_factory=dict)


class Constraints(BaseModel):
    analysis_only: bool = True
    must_clarify_if_ambiguous: bool = True
    must_clarify_if_asset_missing: bool = True


class PlanningContext(BaseModel):
    user_request: UserRequest
    session_context: SessionContext
    recent_context: RecentContext
    memory_context: MemoryContext
    capabilities: Capabilities
    constraints: Constraints
