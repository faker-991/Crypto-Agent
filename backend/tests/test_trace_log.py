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
    service.write_trace(
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
    assert legacy_payload["pseudo_spans"][0]["kind"] == "planner"
    assert legacy_payload["pseudo_spans"][0]["status"] == "unknown"


def test_trace_log_service_persists_canonical_summary_and_span_fields(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)

    spans = [
        {
            "span_id": "planner-1",
            "parent_span_id": None,
            "trace_id": "trace-btc-1",
            "kind": "planner",
            "name": "Planner",
            "status": "success",
            "start_ts": "2026-03-30T00:00:00Z",
            "end_ts": "2026-03-30T00:00:01Z",
            "duration_ms": 1000.0,
            "input_summary": {"goal": "Analyze BTC"},
            "output_summary": {"decision": "research"},
            "error": None,
            "attributes": {"decision_mode": "single_task"},
            "metrics": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
            "audit": {"actor": "Planner"},
        },
        {
            "span_id": "tool-1",
            "parent_span_id": "planner-1",
            "trace_id": "trace-btc-1",
            "kind": "tool",
            "name": "search_web",
            "status": "failed",
            "start_ts": "2026-03-30T00:00:01Z",
            "end_ts": "2026-03-30T00:00:02Z",
            "duration_ms": 1000.0,
            "input_summary": {"query": "BTC"},
            "output_summary": {},
            "error": "timeout",
            "attributes": {"tool_name": "search_web"},
            "metrics": {"input_bytes": 24, "output_bytes": 0},
            "audit": {"actor": "ResearchAgent"},
        },
    ]
    path = service.write_trace(
        user_query="帮我分析 BTC",
        status="partial_failure",
        plan={
            "goal": "Analyze BTC",
            "mode": "single_task",
            "needs_clarification": False,
            "tasks": [],
        },
        task_results=[],
        execution_summary={"asset": "BTC"},
        events=[],
        spans=spans,
        metrics_summary={
            "prompt_tokens": 12,
            "completion_tokens": 3,
            "total_tokens": 15,
            "input_bytes": 24,
            "output_bytes": 0,
        },
        tool_usage_summary={"total_calls": 1, "failed_calls": 1, "degraded_calls": 0},
        error_summary=[
            {"span_id": "tool-1", "kind": "tool", "name": "search_web", "status": "failed", "error": "timeout"}
        ],
        agent_summaries=[{"agent": "ResearchAgent", "span_count": 1, "tool_call_count": 1, "failure_count": 1}],
    )

    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    assert payload["status"] == "partial_failure"
    assert payload["error_summary"][0]["name"] == "search_web"
    assert payload["agent_summaries"][0]["agent"] == "ResearchAgent"
    assert payload["spans"][0]["kind"] == "planner"
    assert payload["metrics_summary"]["total_tokens"] == 15
    assert payload["tool_usage_summary"]["total_calls"] == 1


def test_trace_log_service_does_not_invent_agent_name_for_agent_spans(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)

    path = service.write_trace(
        user_query="missing agent",
        status="execute",
        plan={"goal": "Analyze", "mode": "single_task", "needs_clarification": False, "tasks": []},
        task_results=[
            {
                "task_id": "task-1",
                "task_type": "research",
                "status": "success",
                "summary": "done",
            }
        ],
        execution_summary=None,
        events=[],
    )

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    agent_span = next(span for span in payload["spans"] if span["kind"] == "agent")

    assert agent_span["name"] == "unknown"
    assert "agent" not in agent_span["attributes"]
    assert agent_span["audit"] == {}


def test_trace_log_service_failure_count_ignores_failed_planner_spans(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)

    path = service.write_trace(
        user_query="failure count",
        status="partial_failure",
        plan=None,
        task_results=[],
        execution_summary=None,
        events=[],
        spans=[
            {
                "span_id": "planner-1",
                "parent_span_id": None,
                "trace_id": "trace-1",
                "kind": "planner",
                "name": "Planner",
                "status": "failed",
                "start_ts": "2026-03-31T00:00:00Z",
                "end_ts": "2026-03-31T00:00:01Z",
                "duration_ms": 1000.0,
                "input_summary": {},
                "output_summary": {},
                "error": "planner_error",
                "attributes": {},
                "metrics": {},
                "audit": {"actor": "Planner"},
            },
            {
                "span_id": "tool-1",
                "parent_span_id": None,
                "trace_id": "trace-1",
                "kind": "tool",
                "name": "search_web",
                "status": "failed",
                "start_ts": "2026-03-31T00:00:01Z",
                "end_ts": "2026-03-31T00:00:02Z",
                "duration_ms": 1000.0,
                "input_summary": {},
                "output_summary": {},
                "error": "tool_error",
                "attributes": {"tool_name": "search_web"},
                "metrics": {},
                "audit": {"actor": "ResearchAgent"},
            },
        ],
    )

    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    assert payload["failure_count"] == 1


def test_trace_log_service_merges_agent_internal_spans_from_task_payload(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)

    path = service.write_trace(
        user_query="merge internal spans",
        status="execute",
        plan={"goal": "Analyze BTC", "mode": "single_task", "needs_clarification": False, "tasks": []},
        task_results=[
            {
                "task_id": "task-research",
                "task_type": "research",
                "agent": "ResearchAgent",
                "status": "insufficient",
                "summary": "Need more evidence.",
                "payload": {
                    "trace_summary": {
                        "spans": [
                            {
                                "span_id": "llm-1",
                                "parent_span_id": None,
                                "trace_id": "research-btc",
                                "kind": "llm",
                                "name": "research_round_1",
                                "status": "success",
                                "start_ts": "2026-03-31T00:00:00Z",
                                "end_ts": "2026-03-31T00:00:01Z",
                                "duration_ms": 1000.0,
                                "input_summary": {"asset": "BTC"},
                                "output_summary": {"action": "search_web"},
                                "error": None,
                                "attributes": {"provider": "openai-compatible", "model": "kimi/kimi-k2.5"},
                                "metrics": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
                                "audit": {"actor": "ResearchAgent"},
                            },
                            {
                                "span_id": "tool-1",
                                "parent_span_id": "llm-1",
                                "trace_id": "research-btc",
                                "kind": "tool",
                                "name": "search_web",
                                "status": "success",
                                "start_ts": "2026-03-31T00:00:01Z",
                                "end_ts": "2026-03-31T00:00:02Z",
                                "duration_ms": 1000.0,
                                "input_summary": {"query": "BTC catalysts"},
                                "output_summary": {"provider": "exa"},
                                "error": None,
                                "attributes": {"tool_name": "search_web", "provider": "exa"},
                                "metrics": {"input_bytes": 14, "output_bytes": 42},
                                "audit": {"actor": "ResearchAgent"},
                            },
                        ]
                    }
                },
            }
        ],
        execution_summary={"asset": "BTC"},
        events=[],
    )

    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    kinds = [span["kind"] for span in payload["spans"]]
    assert "agent" in kinds
    assert "llm" in kinds
    assert "tool" in kinds
    llm_span = next(span for span in payload["spans"] if span["kind"] == "llm")
    tool_span = next(span for span in payload["spans"] if span["kind"] == "tool")
    agent_span = next(span for span in payload["spans"] if span["kind"] == "agent")
    assert llm_span["parent_span_id"] == agent_span["span_id"]
    assert tool_span["parent_span_id"] == llm_span["span_id"]
    assert llm_span["attributes"]["provider"] == "openai-compatible"
    assert tool_span["attributes"]["provider"] == "exa"
    assert payload["metrics_summary"]["total_tokens"] == 18
    assert payload["tool_usage_summary"]["total_calls"] == 1


def test_trace_log_service_persists_planner_fallback_reason_on_planner_span(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)

    path = service.write_trace(
        user_query="planner fallback",
        status="execute",
        plan={
            "goal": "Analyze BTC",
            "mode": "single_task",
            "decision_mode": "kline_only",
            "needs_clarification": False,
            "planner_source": "fallback",
            "planner_fallback_reason": "llm_returned_none",
            "tasks": [],
        },
        task_results=[],
        execution_summary={"asset": "BTC", "planner_source": "fallback", "planner_fallback_reason": "llm_returned_none"},
        events=[],
    )

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    planner_span = next(span for span in payload["spans"] if span["kind"] == "planner")

    assert planner_span["attributes"]["planner_fallback_reason"] == "llm_returned_none"


def test_trace_log_service_derived_spans_use_iso8601_timestamps(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)

    path = service.write_trace(
        user_query="iso timestamps",
        status="execute",
        plan={"goal": "Analyze BTC", "mode": "single_task", "needs_clarification": False, "tasks": []},
        task_results=[
            {
                "task_id": "task-1",
                "task_type": "research",
                "agent": "ResearchAgent",
                "status": "success",
                "summary": "done",
            }
        ],
        execution_summary=None,
        events=[],
    )

    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    assert payload["spans"][0]["start_ts"].endswith("Z")
    assert payload["spans"][0]["start_ts"].count("-") == 2
    assert payload["spans"][0]["start_ts"].count(":") >= 2
    assert payload["spans"][0]["end_ts"].endswith("Z")
    assert payload["spans"][0]["end_ts"].count("-") == 2
    assert payload["spans"][0]["end_ts"].count(":") >= 2


def test_trace_log_service_recovers_spans_from_modern_trace_with_null_spans(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)
    trace_path = tmp_path / "traces" / "20260331T000000000000Z.json"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(
        json.dumps(
            {
                "timestamp": "20260331T000000000000Z",
                "user_query": "帮我研究 BTC 最近走势",
                "status": "execute",
                "plan": {
                    "goal": "Analyze BTC",
                    "mode": "multi_task",
                    "decision_mode": "mixed_analysis",
                    "needs_clarification": False,
                    "tasks": [
                        {"task_id": "task-research", "task_type": "research", "title": "Research BTC", "slots": {}, "depends_on": []}
                    ],
                },
                "task_results": [
                    {
                        "task_id": "task-research",
                        "task_type": "research",
                        "agent": "ResearchAgent",
                        "status": "insufficient",
                        "summary": "Risk evidence is thin.",
                        "start_ts": "2026-03-31T00:00:00Z",
                        "end_ts": "2026-03-31T00:00:05Z",
                        "duration_ms": 5000.0,
                        "payload": {
                            "agent_loop": [
                                {
                                    "round": 1,
                                    "decision": {"summary": "Search for catalysts and risks."},
                                    "action": {"tool": "search_web"},
                                    "observation": {"summary": "Found several websites."},
                                    "result": {"fallback_error": "The read operation timed out"},
                                    "termination": False,
                                }
                            ],
                            "tool_calls": [
                                {
                                    "round": 1,
                                    "tool": "search_web",
                                    "input": {"query": "BTC catalysts risks"},
                                    "output": {
                                        "provider": "exa",
                                        "results": [
                                            {
                                                "title": "BTC risks",
                                                "url": "https://example.com/btc-risks",
                                                "snippet": "Risk write-up",
                                            }
                                        ],
                                    },
                                }
                            ],
                        },
                    }
                ],
                "execution_summary": {"asset": "BTC", "summary": "Risk evidence is thin."},
                "events": [],
                "spans": None,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = service.read_trace(trace_path.name)

    kinds = [span["kind"] for span in payload["spans"]]
    assert "planner" in kinds
    assert "agent" in kinds
    assert "llm" in kinds
    assert "tool" in kinds
    tool_span = next(span for span in payload["spans"] if span["kind"] == "tool")
    assert tool_span["name"] == "search_web"
    assert payload["tool_usage_summary"]["total_calls"] == 1
    assert payload["llm_call_count"] == 1
