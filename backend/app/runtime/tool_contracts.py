from __future__ import annotations

from typing import Any, Literal, TypedDict


SpanStatus = Literal["success", "failed", "degraded", "insufficient", "skipped", "unknown"]
SpanKind = Literal["planner", "agent", "tool", "llm"]
ToolSourceType = Literal["local", "mcp"]
ToolResultStatus = Literal["success", "failed", "degraded"]


class JSONSchemaProperty(TypedDict, total=False):
    type: Literal["string", "number", "integer", "boolean", "object", "array"]


class JSONSchemaObject(TypedDict, total=False):
    type: Literal["object"]
    properties: dict[str, JSONSchemaProperty]
    required: list[str]


class ToolSpec(TypedDict, total=False):
    name: str
    server: str
    domain: str
    description: str
    usage_guidance: str
    input_schema: JSONSchemaObject
    output_schema: JSONSchemaObject
    executor_ref: str
    source_type: ToolSourceType
    audit_level: str
    replay_mode: str
    redaction_rules: dict[str, Any]


class ToolMetrics(TypedDict):
    input_bytes: int
    output_bytes: int


class ToolResult(TypedDict):
    status: ToolResultStatus
    tool_name: str
    server: str
    domain: str
    args: dict[str, Any]
    output: dict[str, Any]
    output_summary: dict[str, Any]
    error: str | None
    reason: str | None
    exception_type: str | None
    degraded: bool
    metrics: ToolMetrics


class Observation(TypedDict):
    tool_name: str
    status: ToolResultStatus
    output_summary: dict[str, Any]
    error: str | None


class ReActStepOutput(TypedDict):
    thought: str
    action: str | None
    action_input: dict[str, Any]
    observation: Observation | None


class SpanMetrics(TypedDict, total=False):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    input_bytes: int
    output_bytes: int


class SpanAudit(TypedDict, total=False):
    actor: str
    audit_level: str
    replay_mode: str


class TraceMetricsSummary(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    input_bytes: int
    output_bytes: int


class TraceToolUsageSummary(TypedDict):
    total_calls: int
    failed_calls: int
    degraded_calls: int


class TraceSpan(TypedDict):
    span_id: str
    parent_span_id: str | None
    trace_id: str
    kind: SpanKind | str
    name: str
    status: SpanStatus
    start_ts: str
    end_ts: str | None
    duration_ms: float | None
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    error: str | None
    attributes: dict[str, Any]
    metrics: SpanMetrics
    audit: SpanAudit
