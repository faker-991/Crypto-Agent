from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.runtime.tool_contracts import TraceMetricsSummary, TraceSpan, TraceToolUsageSummary


SENSITIVE_KEYS = {"api_key", "apikey", "cookie", "secret", "token", "password", "authorization"}
REDACTED_OUTPUT_KEYS = {"text", "body", "content", "html", "raw"}
MAX_OUTPUT_TEXT = 1000


class TraceRuntime:
    def __init__(self) -> None:
        self._spans_by_id: dict[str, TraceSpan] = {}
        self._trace_span_ids: dict[str, list[str]] = {}

    def start_span(
        self,
        *,
        trace_id: str,
        parent_span_id: str | None,
        kind: str,
        name: str,
        input_summary: dict[str, Any] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> TraceSpan:
        span: TraceSpan = {
            "span_id": uuid4().hex[:12],
            "parent_span_id": parent_span_id,
            "trace_id": trace_id,
            "kind": kind,
            "name": name,
            "status": "unknown",
            "start_ts": self._now_iso(),
            "end_ts": None,
            "duration_ms": None,
            "input_summary": dict(input_summary or {}),
            "output_summary": {},
            "error": None,
            "attributes": dict(attributes or {}),
            "metrics": {},
            "audit": {},
        }
        self._spans_by_id[span["span_id"]] = span
        self._trace_span_ids.setdefault(trace_id, []).append(span["span_id"])
        return span

    def finish_span(
        self,
        *,
        span_id: str,
        status: str,
        output_summary: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        audit: dict[str, Any] | None = None,
        attributes: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> TraceSpan:
        span = self._spans_by_id[span_id]
        end = datetime.now(timezone.utc)
        start = self._parse_iso(span["start_ts"])
        span["end_ts"] = end.isoformat().replace("+00:00", "Z")
        span["duration_ms"] = max((end - start).total_seconds() * 1000, 0.0)
        span["status"] = status
        span["output_summary"] = dict(output_summary or {})
        span["metrics"].update(metrics or {})
        span["audit"].update(audit or {})
        span["attributes"].update(attributes or {})
        if error is not None:
            span["error"] = error
        return span

    def record_error(self, *, span_id: str, error: str, exception_type: str | None = None) -> TraceSpan:
        span = self._spans_by_id[span_id]
        span["error"] = error
        if exception_type:
            span["attributes"]["exception_type"] = exception_type
        if span["status"] == "unknown":
            span["status"] = "failed"
        return span

    def finalize_trace(self, *, trace_id: str, summary: dict[str, Any] | None = None) -> dict[str, Any]:
        raw_spans = [self._spans_by_id[span_id] for span_id in self._trace_span_ids.get(trace_id, [])]
        spans = [self.prepare_span_for_persistence(span) for span in raw_spans]
        metrics_summary = self._build_metrics_summary(spans)
        tool_usage_summary = self._build_tool_usage_summary(spans)
        error_summary = self._build_error_summary(spans)
        agent_summaries = self._build_agent_summaries(spans)
        llm_call_count = sum(1 for span in spans if span.get("kind") == "llm")
        tool_call_count = tool_usage_summary["total_calls"]
        failure_count = sum(
            1
            for span in spans
            if span.get("status") in {"failed", "degraded", "insufficient"} and span.get("kind") in {"tool", "llm", "agent"}
        )

        payload = dict(summary or {})
        payload["trace_id"] = trace_id
        payload["spans"] = spans
        payload["metrics_summary"] = metrics_summary
        payload["tool_usage_summary"] = tool_usage_summary
        payload["llm_call_count"] = llm_call_count
        payload["tool_call_count"] = tool_call_count
        payload["failure_count"] = failure_count
        payload["error_summary"] = error_summary
        payload["agent_summaries"] = agent_summaries
        if "status" not in payload:
            payload["status"] = self._derive_trace_status(spans)
        return payload

    @classmethod
    def prepare_span_for_persistence(cls, span: dict[str, Any]) -> TraceSpan:
        stored = deepcopy(span)
        if not stored.get("status"):
            stored["status"] = "unknown"
        if stored.get("end_ts") is None and stored.get("status") == "unknown":
            stored["duration_ms"] = None
        output_summary = cls._truncate_output_summary(stored.get("output_summary") or {})
        if output_summary != stored.get("output_summary"):
            stored.setdefault("attributes", {})
            stored["attributes"]["output_truncated"] = True
        stored["output_summary"] = output_summary
        return cls._redact_sensitive_span(stored)

    def _build_metrics_summary(self, spans: list[dict[str, Any]]) -> TraceMetricsSummary:
        summary: TraceMetricsSummary = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "input_bytes": 0,
            "output_bytes": 0,
        }
        for span in spans:
            metrics = span.get("metrics") or {}
            for key in summary:
                value = metrics.get(key)
                if isinstance(value, int):
                    summary[key] += value
        return summary

    def _build_tool_usage_summary(self, spans: list[dict[str, Any]]) -> TraceToolUsageSummary:
        tool_spans = [span for span in spans if span.get("kind") == "tool"]
        return {
            "total_calls": len(tool_spans),
            "failed_calls": sum(1 for span in tool_spans if span.get("status") == "failed"),
            "degraded_calls": sum(
                1 for span in tool_spans if span.get("status") in {"degraded", "insufficient"}
            ),
        }

    def _build_error_summary(self, spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for span in spans:
            if span.get("status") not in {"failed", "degraded", "insufficient"}:
                continue
            items.append(
                {
                    "span_id": span.get("span_id"),
                    "kind": span.get("kind"),
                    "name": span.get("name"),
                    "status": span.get("status"),
                    "error": span.get("error"),
                }
            )
        return items

    def _build_agent_summaries(self, spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
        summaries: dict[str, dict[str, Any]] = {}
        for span in spans:
            actor = (span.get("audit") or {}).get("actor") or (span.get("attributes") or {}).get("agent")
            if not actor or actor == "Planner":
                continue
            entry = summaries.setdefault(
                actor,
                {
                    "agent": actor,
                    "span_count": 0,
                    "tool_call_count": 0,
                    "failure_count": 0,
                },
            )
            entry["span_count"] += 1
            if span.get("kind") == "tool":
                entry["tool_call_count"] += 1
            if span.get("status") in {"failed", "degraded", "insufficient"}:
                entry["failure_count"] += 1
        return list(summaries.values())

    def _derive_trace_status(self, spans: list[dict[str, Any]]) -> str:
        statuses = {span.get("status") for span in spans}
        if "failed" in statuses and any(status in statuses for status in {"success", "degraded", "insufficient"}):
            return "partial_failure"
        if "failed" in statuses:
            return "failed"
        if "degraded" in statuses or "insufficient" in statuses:
            return "partial_failure"
        if "success" in statuses:
            return "execute"
        return "unknown"

    @classmethod
    def _redact_sensitive_span(cls, span: TraceSpan) -> TraceSpan:
        audit_level = (span.get("audit") or {}).get("audit_level") or (span.get("attributes") or {}).get("audit_level")
        attributes = dict(span.get("attributes") or {})
        redaction_rules = attributes.get("redaction_rules") if isinstance(attributes.get("redaction_rules"), dict) else {}
        attribute_keys = {str(item) for item in redaction_rules.get("attribute_keys", []) if isinstance(item, str)}
        output_keys = {str(item) for item in redaction_rules.get("output_keys", []) if isinstance(item, str)}
        preview_keys = {str(item) for item in redaction_rules.get("preview_keys", []) if isinstance(item, str)}
        sensitive_mode = audit_level == "sensitive"
        if not sensitive_mode and not attribute_keys and not output_keys and not preview_keys:
            return span

        args = attributes.get("args")
        if isinstance(args, dict):
            attributes["args"] = {
                key: "[REDACTED]"
                if key in attribute_keys or (sensitive_mode and cls._is_sensitive_key(key))
                else value
                for key, value in args.items()
            }
        preview = attributes.get("result_preview")
        if isinstance(preview, str):
            preview = {"title": preview}
        if isinstance(preview, dict):
            attributes["result_preview"] = {
                key: "[REDACTED]"
                if key in preview_keys or key in output_keys or (sensitive_mode and cls._is_redacted_output_key(key))
                else value
                for key, value in preview.items()
            }
        span["attributes"] = attributes
        span["output_summary"] = {
            key: "[REDACTED]"
            if key in output_keys or (sensitive_mode and cls._is_redacted_output_key(key))
            else value
            for key, value in (span.get("output_summary") or {}).items()
        }
        return span

    @classmethod
    def _truncate_output_summary(cls, output_summary: dict[str, Any]) -> dict[str, Any]:
        truncated: dict[str, Any] = {}
        changed = False
        for key, value in output_summary.items():
            if isinstance(value, str) and len(value) > MAX_OUTPUT_TEXT:
                truncated[key] = value[:250] + "...[truncated]"
                changed = True
            else:
                truncated[key] = value
        return truncated if changed else dict(output_summary)

    @classmethod
    def _is_sensitive_key(cls, key: str) -> bool:
        lowered = key.lower()
        return lowered in SENSITIVE_KEYS or any(token in lowered for token in SENSITIVE_KEYS)

    @classmethod
    def _is_redacted_output_key(cls, key: str) -> bool:
        lowered = key.lower()
        return lowered in REDACTED_OUTPUT_KEYS

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _parse_iso(self, value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
