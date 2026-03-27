from fastapi import APIRouter, Depends

from app.schemas.execution import ExecutionEvent
from app.services.readable_trace_formatter import build_readable_workflow
from app.services.trace_log_service import TraceLogService

router = APIRouter(prefix="/api/traces", tags=["traces"])


def get_trace_log_service() -> TraceLogService:
    raise RuntimeError("trace log service dependency is not configured")


@router.get("")
def read_traces(trace_log_service: TraceLogService = Depends(get_trace_log_service)) -> dict:
    return {"items": trace_log_service.list_traces()}


@router.get("/{trace_id}")
def read_trace(trace_id: str, trace_log_service: TraceLogService = Depends(get_trace_log_service)) -> dict:
    payload = trace_log_service.read_trace(trace_id)
    payload["events"] = [_normalize_event(event) for event in payload.get("events", [])]
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
    ).model_dump()
