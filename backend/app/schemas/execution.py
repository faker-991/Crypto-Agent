from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ExecutionEventDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    integration: str | None = None
    endpoint: str | None = None
    input_summary: dict | None = None
    output_summary: dict | None = None
    degraded: bool = False
    error: str | None = None


class ExecutionEvent(BaseModel):
    name: str
    actor: str
    detail: ExecutionEventDetail = Field(default_factory=ExecutionEventDetail)
    span_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    parent_span_id: str | None = None
    start_ts: str | None = None
    end_ts: str | None = None
    duration_ms: float | None = None


class SpanMetricsSummary(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    input_bytes: int = 0
    output_bytes: int = 0


class ToolUsageSummary(BaseModel):
    total_calls: int = 0
    failed_calls: int = 0
    degraded_calls: int = 0


class SpanMetrics(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    input_bytes: int | None = None
    output_bytes: int | None = None


class SpanAudit(BaseModel):
    actor: str | None = None
    audit_level: str | None = None
    replay_mode: str | None = None


class TraceSpan(BaseModel):
    model_config = ConfigDict(extra="allow")

    span_id: str
    parent_span_id: str | None = None
    trace_id: str
    kind: Literal["planner", "agent", "tool", "llm"] | str
    name: str
    status: Literal["success", "failed", "degraded", "insufficient", "skipped", "unknown"] = "unknown"
    start_ts: str
    end_ts: str | None = None
    duration_ms: float | None = None
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    metrics: SpanMetrics = Field(default_factory=SpanMetrics)
    audit: SpanAudit = Field(default_factory=SpanAudit)
