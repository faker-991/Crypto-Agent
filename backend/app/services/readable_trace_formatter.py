from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse


FAILURE_STATUSES = {"failed", "degraded", "insufficient"}


def build_readable_workflow(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    spans = _prepare_spans(payload)
    if not spans:
        return None

    status = _string(payload.get("status")) or "unknown"
    timeline = [_build_timeline_node(span) for span in spans]
    first_failed_span_id = next(
        (span["span_id"] for span in spans if _string(span.get("status")) in FAILURE_STATUSES),
        None,
    )
    evidence_records = _build_evidence_records(spans)
    reasoning_steps = _build_reasoning_steps(payload, spans, evidence_records)
    first_failed_step_id = next(
        (step["step_id"] for step in reasoning_steps if _string(step.get("status")) in FAILURE_STATUSES),
        None,
    )
    audit_summary = _build_audit_summary(payload, spans, status, first_failed_span_id, first_failed_step_id)
    overview = _build_overview(audit_summary)
    conclusions = _build_conclusions(payload, status, evidence_records, reasoning_steps)

    return {
        "audit_summary": audit_summary,
        "overview": overview,
        "meta": {
            "first_failed_span_id": first_failed_span_id,
            "first_failed_step_id": first_failed_step_id,
            "timeline_count": len(timeline),
        },
        "conclusions": conclusions,
        "evidence_records": evidence_records,
        "reasoning_steps": reasoning_steps,
        "final_conclusion": _build_final_conclusion(payload, status),
        "timeline": timeline,
    }


def _prepare_spans(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_spans = payload.get("spans") or payload.get("pseudo_spans") or []
    spans = [span for span in raw_spans if isinstance(span, dict)]
    spans.sort(key=_span_sort_key)
    if _string(payload.get("status")) == "cancelled":
        spans = [span for span in spans if span.get("end_ts")]
    return spans


def _build_audit_summary(
    payload: dict[str, Any],
    spans: list[dict[str, Any]],
    status: str,
    first_failed_span_id: str | None,
    first_failed_step_id: str | None,
) -> dict[str, Any]:
    metrics_summary = payload.get("metrics_summary") if isinstance(payload.get("metrics_summary"), dict) else {}
    llm_spans = [span for span in spans if _string(span.get("kind")) == "llm"]
    tool_spans = [span for span in spans if _string(span.get("kind")) == "tool"]
    failed_calls = sum(1 for span in spans if _string(span.get("status")) == "failed")
    degraded_calls = sum(1 for span in spans if _string(span.get("status")) == "degraded")
    models_used = sorted(
        {
            _string((span.get("attributes") or {}).get("model"))
            for span in llm_spans
            if isinstance(span.get("attributes"), dict)
        }
        - {None}
    )
    providers_used = sorted(
        {
            _string((span.get("attributes") or {}).get("provider"))
            for span in llm_spans
            if isinstance(span.get("attributes"), dict)
        }
        - {None}
    )
    return {
        "trace_status": status,
        "started_at": spans[0].get("start_ts") if spans else None,
        "ended_at": next((span.get("end_ts") for span in reversed(spans) if span.get("end_ts")), None),
        "duration_ms": _trace_duration_ms(spans),
        "prompt_tokens": int(metrics_summary.get("prompt_tokens") or 0),
        "completion_tokens": int(metrics_summary.get("completion_tokens") or 0),
        "total_tokens": int(metrics_summary.get("total_tokens") or 0),
        "llm_calls": int(payload.get("llm_call_count") or len(llm_spans)),
        "tool_calls": int(payload.get("tool_call_count") or len(tool_spans)),
        "failed_calls": failed_calls,
        "degraded_calls": degraded_calls,
        "failures": int(payload.get("failure_count") or sum(1 for span in spans if _string(span.get("status")) in FAILURE_STATUSES)),
        "models_used": models_used,
        "providers_used": providers_used,
        "fallback_used": any(
            _string((span.get("attributes") or {}).get("fallback_error"))
            for span in llm_spans
            if isinstance(span.get("attributes"), dict)
        ),
        "first_failed_span_id": first_failed_span_id,
        "first_failed_step_id": first_failed_step_id,
        "callback_summary": _build_callback_summary(llm_spans),
    }


def _build_overview(audit_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "trace_status": _string(audit_summary.get("trace_status")) or "unknown",
        "total_tokens": int(audit_summary.get("total_tokens") or 0),
        "llm_calls": int(audit_summary.get("llm_calls") or 0),
        "tool_calls": int(audit_summary.get("tool_calls") or 0),
        "failures": int(audit_summary.get("failures") or 0),
        "total_duration_ms": audit_summary.get("duration_ms"),
    }


def _build_conclusions(
    payload: dict[str, Any],
    status: str,
    evidence_records: list[dict[str, Any]],
    reasoning_steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if status in {"clarify", "cancelled"}:
        return []
    execution_summary = payload.get("execution_summary") if isinstance(payload.get("execution_summary"), dict) else {}
    final_answer = _string(payload.get("final_answer"))
    summary = _string(execution_summary.get("summary"))
    missing_information = [item for item in execution_summary.get("missing_information", []) if isinstance(item, str)]
    if not final_answer and not summary and not missing_information and not execution_summary:
        return []
    return [
        {
            "conclusion_id": "final",
            "kind": "final",
            "text": final_answer or summary or "",
            "status": status,
            "summary": summary,
            "missing_information": missing_information,
            "evidence_ids": [record["evidence_id"] for record in evidence_records],
            "derived_from_step_ids": [step["step_id"] for step in reasoning_steps],
        }
    ]


def _build_final_conclusion(payload: dict[str, Any], status: str) -> dict[str, Any] | None:
    conclusions = _build_conclusions(payload, status, [], [])
    if not conclusions:
        return None
    execution_summary = payload.get("execution_summary") if isinstance(payload.get("execution_summary"), dict) else {}
    final_answer = _string(payload.get("final_answer"))
    return {
        "status": status,
        "final_answer": final_answer,
        "summary": conclusions[0].get("summary"),
        "evidence_sufficient": execution_summary.get("evidence_sufficient"),
        "missing_information": conclusions[0].get("missing_information") or [],
        "degraded_reason": _string(execution_summary.get("degraded_reason")),
    }


def _build_timeline_node(span: dict[str, Any]) -> dict[str, Any]:
    attributes = span.get("attributes") if isinstance(span.get("attributes"), dict) else {}
    audit = span.get("audit") if isinstance(span.get("audit"), dict) else {}
    return {
        "span_id": span.get("span_id"),
        "parent_span_id": span.get("parent_span_id"),
        "kind": _string(span.get("kind")) or "unknown",
        "name": _string(span.get("name")) or "unknown",
        "status": _string(span.get("status")) or "unknown",
        "title": _timeline_title(span),
        "summary": _timeline_summary(span),
        "start_ts": span.get("start_ts"),
        "end_ts": span.get("end_ts"),
        "duration_ms": span.get("duration_ms"),
        "metrics": span.get("metrics") if isinstance(span.get("metrics"), dict) else {},
        "detail_tabs": {
            "input": span.get("input_summary") if isinstance(span.get("input_summary"), dict) else {},
            "output": span.get("output_summary") if isinstance(span.get("output_summary"), dict) else {},
            "error": {
                "error": span.get("error"),
                "exception_type": attributes.get("exception_type"),
                "status": span.get("status"),
            },
            "audit": {
                "span_id": span.get("span_id"),
                "parent_span_id": span.get("parent_span_id"),
                "actor": audit.get("actor") or attributes.get("agent"),
                "tool_server": attributes.get("tool_server"),
                "tool_domain": attributes.get("tool_domain"),
                "start_ts": span.get("start_ts"),
                "end_ts": span.get("end_ts"),
                "duration_ms": span.get("duration_ms"),
                "audit_level": audit.get("audit_level"),
                "replay_mode": audit.get("replay_mode"),
            },
        },
    }


def _timeline_title(span: dict[str, Any]) -> str:
    kind = _string(span.get("kind")) or "unknown"
    name = _string(span.get("name")) or "unknown"
    if kind == "tool":
        return f"Tool: {name}"
    if kind == "llm":
        return f"LLM: {name}"
    if kind == "planner":
        return "Planner"
    if kind == "agent":
        return f"Agent: {name}"
    return name


def _timeline_summary(span: dict[str, Any]) -> str:
    kind = _string(span.get("kind")) or "unknown"
    status = _string(span.get("status")) or "unknown"
    metrics = span.get("metrics") if isinstance(span.get("metrics"), dict) else {}
    input_summary = span.get("input_summary") if isinstance(span.get("input_summary"), dict) else {}
    output_summary = span.get("output_summary") if isinstance(span.get("output_summary"), dict) else {}
    attributes = span.get("attributes") if isinstance(span.get("attributes"), dict) else {}
    duration = _format_duration(span.get("duration_ms"))

    if kind == "tool":
        parts = [
            _string(attributes.get("tool_server")) or "tool",
            _string(span.get("name")) or "unknown",
            _string(input_summary.get("timeframe")),
            status,
            duration,
        ]
        return " · ".join(part for part in parts if part)
    if kind == "llm":
        prompt = metrics.get("prompt_tokens")
        completion = metrics.get("completion_tokens")
        parts = [
            f"prompt={prompt}" if isinstance(prompt, int) else None,
            f"completion={completion}" if isinstance(completion, int) else None,
            duration,
        ]
        return " · ".join(part for part in parts if part)
    if kind == "planner":
        return " · ".join(part for part in [status, _string(output_summary.get("status")), duration] if part)
    if kind == "agent":
        return " · ".join(part for part in [status, _string(output_summary.get("summary")), duration] if part)
    return " · ".join(part for part in [status, duration] if part)


def _build_evidence_records(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for span in spans:
        if _string(span.get("kind")) != "tool":
            continue
        tool_name = _string(span.get("name")) or _string((span.get("attributes") or {}).get("tool_name"))
        if tool_name == "search_web":
            records.extend(_build_search_evidence(span))
        elif tool_name == "fetch_page":
            record = _build_fetch_evidence(span)
            if record:
                records.append(record)
        elif tool_name in {"get_klines", "get_ticker", "get_market_snapshot", "get_protocol_snapshot"}:
            record = _build_market_evidence(span, tool_name)
            if record:
                records.append(record)
    return records


def _build_search_evidence(span: dict[str, Any]) -> list[dict[str, Any]]:
    output_summary = span.get("output_summary") if isinstance(span.get("output_summary"), dict) else {}
    input_summary = span.get("input_summary") if isinstance(span.get("input_summary"), dict) else {}
    query = _string(input_summary.get("query")) or _string(output_summary.get("query"))
    provider = _string(output_summary.get("provider"))
    records = [
        {
            "evidence_id": f"{span.get('span_id')}:search",
            "type": "search_result",
            "title": query or "search_web",
            "summary": f"Search provider={provider or 'unknown'}",
            "source_kind": "tool",
            "source_tool": "search_web",
            "source_url": None,
            "source_domain": None,
            "source_span_id": span.get("span_id"),
            "captured_at": span.get("end_ts") or span.get("start_ts"),
            "confidence": None,
            "attributes": {
                "query": query,
                "provider": provider,
                "result_count": len(output_summary.get("results") or []),
            },
        }
    ]
    for index, item in enumerate(output_summary.get("results") or []):
        if not isinstance(item, dict):
            continue
        url = _string(item.get("url"))
        records.append(
            {
                "evidence_id": f"{span.get('span_id')}:result:{index}",
                "type": "search_result",
                "title": _string(item.get("title")) or url or f"search result {index + 1}",
                "summary": _string(item.get("snippet")) or "",
                "source_kind": "tool",
                "source_tool": "search_web",
                "source_url": url,
                "source_domain": _extract_domain(url),
                "source_span_id": span.get("span_id"),
                "captured_at": span.get("end_ts") or span.get("start_ts"),
                "confidence": None,
                "attributes": {
                    "query": query,
                    "provider": provider,
                    "snippet": _string(item.get("snippet")),
                },
            }
        )
    return records


def _build_fetch_evidence(span: dict[str, Any]) -> dict[str, Any] | None:
    output_summary = span.get("output_summary") if isinstance(span.get("output_summary"), dict) else {}
    input_summary = span.get("input_summary") if isinstance(span.get("input_summary"), dict) else {}
    url = _string(input_summary.get("url")) or _string(output_summary.get("url"))
    if not url and not output_summary:
        return None
    return {
        "evidence_id": f"{span.get('span_id')}:fetch",
        "type": "webpage",
        "title": _string(output_summary.get("title")) or url or "fetch_page",
        "summary": _string(output_summary.get("summary")) or _string(span.get("error")) or "",
        "source_kind": "tool",
        "source_tool": "fetch_page",
        "source_url": url,
        "source_domain": _extract_domain(url),
        "source_span_id": span.get("span_id"),
        "captured_at": span.get("end_ts") or span.get("start_ts"),
        "confidence": None,
        "attributes": {
            "strategy": _string(output_summary.get("strategy")),
            "failure_reason": _string(output_summary.get("failure_reason")) or _string(span.get("error")),
            "extraction_status": _string(span.get("status")),
        },
    }


def _build_market_evidence(span: dict[str, Any], tool_name: str) -> dict[str, Any] | None:
    input_summary = span.get("input_summary") if isinstance(span.get("input_summary"), dict) else {}
    output_summary = span.get("output_summary") if isinstance(span.get("output_summary"), dict) else {}
    summary = _string(output_summary.get("summary")) or _string(output_summary.get("conclusion"))
    title = _string(input_summary.get("timeframe")) or tool_name
    return {
        "evidence_id": f"{span.get('span_id')}:market",
        "type": "technical" if tool_name == "get_klines" else "market",
        "title": title,
        "summary": summary or f"{tool_name} executed",
        "source_kind": "tool",
        "source_tool": tool_name,
        "source_url": None,
        "source_domain": None,
        "source_span_id": span.get("span_id"),
        "captured_at": span.get("end_ts") or span.get("start_ts"),
        "confidence": None,
        "attributes": {
            "timeframe": _string(input_summary.get("timeframe")),
            "status": _string(span.get("status")),
        },
    }


def _build_reasoning_steps(
    payload: dict[str, Any],
    spans: list[dict[str, Any]],
    evidence_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    task_results = payload.get("task_results") if isinstance(payload.get("task_results"), list) else []
    llm_spans_by_actor = _group_spans_by_actor(spans, "llm")
    tool_spans_by_actor = _group_spans_by_actor(spans, "tool")
    actor_indexes: dict[str, dict[str, int]] = {}
    evidence_ids_by_span = _group_evidence_ids_by_span(evidence_records)
    steps: list[dict[str, Any]] = []

    for task_result in task_results:
        if not isinstance(task_result, dict):
            continue
        actor = _string(task_result.get("agent")) or "Agent"
        payload_data = task_result.get("payload") if isinstance(task_result.get("payload"), dict) else {}
        agent_loop = payload_data.get("agent_loop") if isinstance(payload_data.get("agent_loop"), list) else []
        actor_indexes.setdefault(actor, {"llm": 0, "tool": 0})
        for entry in agent_loop:
            if not isinstance(entry, dict):
                continue
            llm_index = actor_indexes[actor]["llm"]
            tool_index = actor_indexes[actor]["tool"]
            llm_span = llm_spans_by_actor.get(actor, [])[llm_index] if llm_index < len(llm_spans_by_actor.get(actor, [])) else None
            tool_span = tool_spans_by_actor.get(actor, [])[tool_index] if tool_index < len(tool_spans_by_actor.get(actor, [])) else None
            action = _string(((entry.get("action") or {}).get("tool")))
            if action:
                actor_indexes[actor]["tool"] += 1
            actor_indexes[actor]["llm"] += 1
            step_id = f"{actor.lower()}-step-{int(entry.get('round') or len(steps) + 1)}"
            steps.append(
                {
                    "step_id": step_id,
                    "agent": actor,
                    "round_index": int(entry.get("round") or len(steps) + 1),
                    "decision_summary": _string(((entry.get("decision") or {}).get("summary"))) or "",
                    "action": action,
                    "args": (entry.get("action") or {}).get("input") if isinstance(entry.get("action"), dict) else {},
                    "observation_summary": _summarize_agent_loop_result(entry.get("result")),
                    "new_evidence_ids": evidence_ids_by_span.get(tool_span.get("span_id") if isinstance(tool_span, dict) else None, []),
                    "status": _reasoning_step_status(entry, llm_span, tool_span),
                    "duration_ms": _step_duration(llm_span, tool_span),
                    "llm_span_id": llm_span.get("span_id") if isinstance(llm_span, dict) else None,
                    "tool_span_id": tool_span.get("span_id") if isinstance(tool_span, dict) else None,
                    "callback": _callback_from_llm_span(llm_span),
                }
            )
    return steps


def _group_spans_by_actor(spans: list[dict[str, Any]], kind: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for span in spans:
        if _string(span.get("kind")) != kind:
            continue
        actor = _span_actor(span) or "Agent"
        grouped.setdefault(actor, []).append(span)
    return grouped


def _group_evidence_ids_by_span(evidence_records: list[dict[str, Any]]) -> dict[str | None, list[str]]:
    grouped: dict[str | None, list[str]] = {}
    for record in evidence_records:
        span_id = _string(record.get("source_span_id"))
        grouped.setdefault(span_id, []).append(record["evidence_id"])
    return grouped


def _span_actor(span: dict[str, Any]) -> str | None:
    audit = span.get("audit") if isinstance(span.get("audit"), dict) else {}
    attributes = span.get("attributes") if isinstance(span.get("attributes"), dict) else {}
    return _string(audit.get("actor")) or _string(attributes.get("agent"))


def _reasoning_step_status(entry: dict[str, Any], llm_span: dict[str, Any] | None, tool_span: dict[str, Any] | None) -> str:
    result = entry.get("result") if isinstance(entry.get("result"), dict) else {}
    for value in (
        _string(result.get("status")),
        _string(tool_span.get("status")) if isinstance(tool_span, dict) else None,
        _string(llm_span.get("status")) if isinstance(llm_span, dict) else None,
    ):
        if value:
            return value
    return "unknown"


def _step_duration(llm_span: dict[str, Any] | None, tool_span: dict[str, Any] | None) -> float | None:
    values = [
        value
        for value in (
            llm_span.get("duration_ms") if isinstance(llm_span, dict) else None,
            tool_span.get("duration_ms") if isinstance(tool_span, dict) else None,
        )
        if isinstance(value, (int, float))
    ]
    if not values:
        return None
    return round(sum(values), 3)


def _callback_from_llm_span(span: dict[str, Any] | None) -> dict[str, Any]:
    attributes = span.get("attributes") if isinstance(span, dict) and isinstance(span.get("attributes"), dict) else {}
    return {
        "started_at": attributes.get("started_at") or span.get("start_ts") if isinstance(span, dict) else None,
        "first_token_at": attributes.get("first_token_at"),
        "completed_at": attributes.get("completed_at") or span.get("end_ts") if isinstance(span, dict) else None,
        "failed_at": (attributes.get("completed_at") or span.get("end_ts")) if isinstance(span, dict) and _string(span.get("status")) == "failed" else None,
        "finish_reason": _string(attributes.get("finish_reason")) or _string(attributes.get("termination_reason")),
        "error": span.get("error") if isinstance(span, dict) else None,
    }


def _summarize_agent_loop_result(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    output_summary = result.get("output_summary") if isinstance(result.get("output_summary"), dict) else {}
    for key in ("summary", "title", "provider", "reason"):
        value = _string(output_summary.get(key)) or _string(result.get(key))
        if value:
            return value
    tool_name = _string(result.get("tool_name")) or "tool"
    status = _string(result.get("status")) or "unknown"
    return f"{tool_name} -> {status}"


def _build_callback_summary(llm_spans: list[dict[str, Any]]) -> dict[str, Any]:
    started_count = 0
    completed_count = 0
    failed_count = 0
    first_token_latencies: list[float] = []
    finish_reasons: list[str] = []
    for span in llm_spans:
        attributes = span.get("attributes") if isinstance(span.get("attributes"), dict) else {}
        started_at = _parse_timestamp(attributes.get("started_at") or span.get("start_ts"))
        first_token_at = _parse_timestamp(attributes.get("first_token_at"))
        completed_at = _parse_timestamp(attributes.get("completed_at") or span.get("end_ts"))
        if started_at:
            started_count += 1
        if completed_at:
            completed_count += 1
        if _string(span.get("status")) == "failed":
            failed_count += 1
        if started_at and first_token_at:
            first_token_latencies.append((first_token_at - started_at).total_seconds() * 1000)
        finish_reason = _string(attributes.get("finish_reason")) or _string(attributes.get("termination_reason"))
        if finish_reason:
            finish_reasons.append(finish_reason)
    return {
        "started_count": started_count,
        "completed_count": completed_count,
        "failed_count": failed_count,
        "first_token_latency_ms_avg": round(sum(first_token_latencies) / len(first_token_latencies), 3) if first_token_latencies else None,
        "finish_reasons": list(dict.fromkeys(finish_reasons)),
    }


def _extract_domain(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc or None


def _trace_duration_ms(spans: list[dict[str, Any]]) -> float | None:
    if not spans:
        return None
    start_values = [_parse_timestamp(span.get("start_ts")) for span in spans if _parse_timestamp(span.get("start_ts"))]
    end_values = [_parse_timestamp(span.get("end_ts")) for span in spans if _parse_timestamp(span.get("end_ts"))]
    if not start_values:
        return None
    if not end_values:
        return None
    duration = (max(end_values) - min(start_values)).total_seconds() * 1000
    return round(max(duration, 0.0), 3)


def _span_sort_key(item: dict[str, Any]) -> tuple[str, str]:
    start = _parse_timestamp(item.get("start_ts"))
    return (start.isoformat() if start else "9999", _string(item.get("span_id")) or "")


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _format_duration(value: Any) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    if value >= 1000:
        return f"{value / 1000:.1f}s"
    return f"{int(value)}ms"


def _string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
