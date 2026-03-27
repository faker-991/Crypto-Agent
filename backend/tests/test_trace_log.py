import json
from pathlib import Path

from app.orchestrator.orchestrator_service import OrchestratorService
from app.services.trace_log_service import TraceLogService


def test_orchestrator_execute_writes_plan_trace_log(tmp_path: Path) -> None:
    service = OrchestratorService(memory_root=tmp_path)

    result = service.execute("帮我分析一下 SUI 值不值得长期跟踪")

    assert result["status"] == "execute"
    trace_dir = tmp_path / "traces"
    trace_files = sorted(trace_dir.glob("*.json"))
    assert trace_files, "expected at least one trace file"

    payload = json.loads(trace_files[-1].read_text(encoding="utf-8"))
    assert payload["user_query"] == "帮我分析一下 SUI 值不值得长期跟踪"
    assert payload["status"] == "execute"
    assert payload["plan"]["tasks"][0]["task_type"] == "research"
    assert payload["task_results"][0]["agent"] == "ResearchAgent"
    assert payload["execution_summary"]["asset"] == "SUI"
    assert payload["plan"]["decision_mode"] == "research_only"
    assert any(event["name"] == "planner.completed" for event in payload["events"])


def test_clarify_plan_still_writes_trace_log(tmp_path: Path) -> None:
    service = OrchestratorService(memory_root=tmp_path)

    result = service.execute("看下 4h")

    assert result["status"] == "clarify"
    trace_files = sorted((tmp_path / "traces").glob("*.json"))
    assert trace_files
    payload = json.loads(trace_files[-1].read_text(encoding="utf-8"))
    assert payload["status"] == "clarify"
    assert payload["plan"]["needs_clarification"] is True
    assert payload["execution_summary"] is None


def test_trace_log_service_lists_new_and_legacy_traces(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)
    first_path = service.write_trace(
        user_query="帮我看看 BTC",
        status="clarify",
        plan={"goal": "clarify BTC", "mode": "single_task", "needs_clarification": True, "tasks": []},
        task_results=[],
        execution_summary=None,
        events=[],
    )
    second_path = service.write_trace(
        user_query="帮我分析 SUI",
        status="execute",
        plan={"goal": "Analyze SUI", "mode": "single_task", "needs_clarification": False, "tasks": []},
        task_results=[{"task_id": "task-research", "task_type": "research", "agent": "ResearchAgent", "status": "success", "payload": {"asset": "SUI"}, "summary": "SUI summary"}],
        execution_summary={"asset": "SUI"},
        events=[{"name": "agent.completed", "actor": "ResearchAgent", "detail": {"asset": "SUI"}}],
    )
    legacy_path = tmp_path / "traces" / "20260323T000000000000Z.json"
    legacy_path.write_text(
        json.dumps(
            {
                "timestamp": "20260323T000000000000Z",
                "user_query": "历史 router trace",
                "route": {"type": "clarify", "agent": "RouterAgent"},
                "execution_summary": None,
                "events": [],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    traces = service.list_traces(limit=10)

    assert len(traces) == 3
    assert traces[0]["path"] == second_path
    assert traces[0]["user_query"] == "帮我分析 SUI"
    assert traces[0]["status"] == "execute"
    assert traces[0]["mode"] == "single_task"
    payload = service.read_trace(Path(second_path).name)
    assert payload["execution_summary"]["asset"] == "SUI"
    assert payload["plan"]["goal"] == "Analyze SUI"
    legacy_payload = service.read_trace(legacy_path.name)
    assert legacy_payload["route"]["type"] == "clarify"
