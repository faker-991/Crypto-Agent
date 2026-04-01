from uuid import uuid4
from datetime import datetime

from fastapi import APIRouter, Depends

from app.schemas.execution import ExecutionEvent
from app.services.readable_trace_formatter import build_readable_workflow
from app.services.trace_log_service import TraceLogService

router = APIRouter(prefix="/api/traces", tags=["traces"])


def get_trace_log_service() -> TraceLogService:
    raise RuntimeError("trace log service dependency is not configured")


@router.get("")
def read_traces(trace_log_service: TraceLogService = Depends(get_trace_log_service)) -> dict:
    items = trace_log_service.list_traces()
    return {"items": items}


@router.get("/{trace_id}")
def read_trace(trace_id: str, trace_log_service: TraceLogService = Depends(get_trace_log_service)) -> dict:
    payload = trace_log_service.read_trace(trace_id)
    payload["events"] = [_normalize_event(event) for event in payload.get("events", [])]
    payload["spans"] = _sort_spans(payload.get("spans") or payload.get("pseudo_spans") or [])
    readable_workflow = build_readable_workflow(payload)
    if readable_workflow is not None:
        payload["readable_workflow"] = readable_workflow
    return payload


def _normalize_event(event: object) -> dict:
    if not isinstance(event, dict):
        return ExecutionEvent(
            name="unknown",
            actor="unknown",
            detail={"error": "event must be an object"},
        ).model_dump()

    raw_detail = event.get("detail")
    detail: dict
    if raw_detail is None:
        detail = {}
    elif isinstance(raw_detail, dict):
        detail = raw_detail
    else:
        detail = {"error": "detail must be an object"}

    return ExecutionEvent(
        name=str(event.get("name") or "unknown"),
        actor=str(event.get("actor") or "unknown"),
        detail=detail,
        span_id=str(event.get("span_id") or uuid4().hex[:12]),
        parent_span_id=(
            str(event.get("parent_span_id"))
            if event.get("parent_span_id") is not None
            else None
        ),
        start_ts=str(event.get("start_ts")) if event.get("start_ts") is not None else None,
        end_ts=str(event.get("end_ts")) if event.get("end_ts") is not None else None,
        duration_ms=(
            float(event.get("duration_ms"))
            if isinstance(event.get("duration_ms"), int | float)
            else None
        ),
    ).model_dump()


def _sort_spans(spans: object) -> list[dict]:
    if not isinstance(spans, list):
        return []

    normalized = [span for span in spans if isinstance(span, dict)]
    normalized.sort(
        key=lambda span: (
            _parse_timestamp(span.get("start_ts")).isoformat()
            if _parse_timestamp(span.get("start_ts"))
            else "9999",
            str(span.get("span_id") or ""),
        )
    )
    return normalized


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
