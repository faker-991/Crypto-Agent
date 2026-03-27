from pathlib import Path

from app.api.trace import read_trace, read_traces
from app.services.trace_log_service import TraceLogService


def test_trace_api_lists_trace_summaries(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)
    service.write_trace(
        user_query="帮我分析 SUI",
        status="execute",
        plan={"goal": "Analyze SUI", "mode": "single_task", "needs_clarification": False, "tasks": []},
        task_results=[{"task_id": "task-research", "task_type": "research", "agent": "ResearchAgent", "status": "success", "payload": {"asset": "SUI"}, "summary": "SUI summary"}],
        execution_summary={"asset": "SUI"},
        events=[],
    )

    payload = read_traces(service)

    assert len(payload["items"]) == 1
    assert payload["items"][0]["user_query"] == "帮我分析 SUI"
    assert payload["items"][0]["status"] == "execute"
    assert payload["items"][0]["mode"] == "single_task"


def test_trace_api_reads_one_trace(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)
    path = service.write_trace(
        user_query="帮我看看 BTC",
        status="clarify",
        plan={"goal": "clarify BTC", "mode": "single_task", "needs_clarification": True, "tasks": []},
        task_results=[],
        execution_summary=None,
        events=[],
    )

    payload = read_trace(Path(path).name, service)

    assert payload["user_query"] == "帮我看看 BTC"
    assert payload["status"] == "clarify"
    assert payload["plan"]["needs_clarification"] is True
    assert "readable_workflow" in payload
    assert payload["readable_workflow"]["final_conclusion"] is None
    assert payload["readable_workflow"]["timeline"][0]["kind"] == "planner"
    assert payload["readable_workflow"]["timeline"][0]["status"] in {"success", "unknown"}


def test_trace_api_omits_readable_workflow_when_derivation_returns_none(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)
    path = service.write_trace(
        user_query="空 trace",
        status="execute",
        plan=None,
        task_results=[],
        execution_summary=None,
        events=[{"name": "planner.context_built", "actor": "ContextBuilder", "detail": {}}],
    )

    payload = read_trace(Path(path).name, service)

    assert payload["user_query"] == "空 trace"
    assert "readable_workflow" not in payload
    assert payload["events"][0]["name"] == "planner.context_built"
