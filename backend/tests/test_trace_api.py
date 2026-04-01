import json
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
    assert "spans" in payload
    assert "pseudo_spans" not in payload
    assert "metrics_summary" in payload
    assert "tool_usage_summary" in payload
    assert payload["readable_workflow"]["final_conclusion"] is None
    assert payload["readable_workflow"]["audit_summary"]["trace_status"] == "clarify"
    assert payload["readable_workflow"]["conclusions"] == []
    assert payload["readable_workflow"]["evidence_records"] == []
    assert payload["readable_workflow"]["reasoning_steps"] == []
    assert payload["readable_workflow"]["timeline"][0]["kind"] == "planner"
    assert payload["readable_workflow"]["timeline"][0]["status"] == "success"
    assert payload["readable_workflow"]["meta"]["first_failed_span_id"] is None


def test_trace_api_exposes_planner_fallback_reason_from_planner_span(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)
    path = service.write_trace(
        user_query="planner fallback trace",
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

    payload = read_trace(Path(path).name, service)
    planner_span = next(span for span in payload["spans"] if span["kind"] == "planner")

    assert planner_span["attributes"]["planner_fallback_reason"] == "llm_returned_none"


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


def test_trace_api_returns_readable_workflow_and_canonical_spans_for_legacy_trace(
    tmp_path: Path,
) -> None:
    service = TraceLogService(memory_root=tmp_path)
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

    payload = read_trace(legacy_path.name, service)

    assert "readable_workflow" in payload
    assert payload["readable_workflow"]["timeline"][0]["kind"] == "planner"
    assert payload["spans"][0]["kind"] == "planner"
    assert payload["spans"][0]["status"] == "unknown"


def test_trace_api_sorts_spans_and_exposes_timeline_meta_for_canonical_trace(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)
    canonical_path = tmp_path / "traces" / "20260331T000000000000Z.json"
    canonical_path.write_text(
        json.dumps(
            {
                "timestamp": "20260331T000000000000Z",
                "user_query": "trace sorting",
                "status": "partial_failure",
                "execution_summary": {
                    "summary": "Need more evidence.",
                    "missing_information": ["Market-side evidence is missing."],
                },
                "events": [
                    {"name": "executor.task_completed", "actor": "ResearchAgent", "detail": {"task_id": "task-1"}}
                ],
                "spans": [
                    {
                        "span_id": "tool-1",
                        "parent_span_id": "llm-1",
                        "trace_id": "20260331T000000000000Z",
                        "kind": "tool",
                        "name": "search_web",
                        "status": "failed",
                        "start_ts": "2026-03-31T00:00:00.500Z",
                        "end_ts": "2026-03-31T00:00:00.900Z",
                        "duration_ms": 400.0,
                        "input_summary": {"query": "SUI catalysts"},
                        "output_summary": {"query": "SUI catalysts"},
                        "error": "search_failed",
                        "attributes": {"tool_server": "research", "args": {"query": "SUI catalysts"}},
                        "metrics": {"input_bytes": 16, "output_bytes": 24},
                        "audit": {"actor": "ResearchAgent"},
                    },
                    {
                        "span_id": "planner-1",
                        "parent_span_id": None,
                        "trace_id": "20260331T000000000000Z",
                        "kind": "planner",
                        "name": "Planner",
                        "status": "success",
                        "start_ts": "2026-03-31T00:00:00.000Z",
                        "end_ts": "2026-03-31T00:00:00.050Z",
                        "duration_ms": 50.0,
                        "input_summary": {"goal": "Analyze SUI"},
                        "output_summary": {"status": "execute"},
                        "error": None,
                        "attributes": {},
                        "metrics": {},
                        "audit": {"actor": "Planner"},
                    },
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = read_trace(canonical_path.name, service)

    assert [span["span_id"] for span in payload["spans"]] == ["planner-1", "tool-1"]
    assert payload["metrics_summary"]["input_bytes"] == 16
    assert payload["tool_usage_summary"]["failed_calls"] == 1
    assert payload["readable_workflow"]["meta"]["first_failed_span_id"] == "tool-1"
    assert payload["readable_workflow"]["audit_summary"]["failed_calls"] == 1
    assert payload["readable_workflow"]["conclusions"][0]["kind"] == "final"
    assert payload["events"][0]["name"] == "executor.task_completed"


def test_trace_api_preserves_cancelled_status_rules_in_readable_workflow(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)
    cancelled_path = tmp_path / "traces" / "20260331T010000000000Z.json"
    cancelled_path.write_text(
        json.dumps(
            {
                "timestamp": "20260331T010000000000Z",
                "user_query": "cancelled trace",
                "status": "cancelled",
                "final_answer": "hidden",
                "execution_summary": {"summary": "should not show"},
                "events": [],
                "spans": [
                    {
                        "span_id": "planner-1",
                        "parent_span_id": None,
                        "trace_id": "20260331T010000000000Z",
                        "kind": "planner",
                        "name": "Planner",
                        "status": "success",
                        "start_ts": "2026-03-31T01:00:00.000Z",
                        "end_ts": "2026-03-31T01:00:00.050Z",
                        "duration_ms": 50.0,
                        "input_summary": {},
                        "output_summary": {},
                        "error": None,
                        "attributes": {},
                        "metrics": {},
                        "audit": {"actor": "Planner"},
                    },
                    {
                        "span_id": "tool-open",
                        "parent_span_id": None,
                        "trace_id": "20260331T010000000000Z",
                        "kind": "tool",
                        "name": "search_web",
                        "status": "unknown",
                        "start_ts": "2026-03-31T01:00:00.100Z",
                        "end_ts": None,
                        "duration_ms": None,
                        "input_summary": {"query": "BTC"},
                        "output_summary": {},
                        "error": None,
                        "attributes": {"tool_server": "research"},
                        "metrics": {},
                        "audit": {"actor": "ResearchAgent"},
                    },
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = read_trace(cancelled_path.name, service)

    assert payload["status"] == "cancelled"
    assert [node["span_id"] for node in payload["readable_workflow"]["timeline"]] == ["planner-1"]
    assert payload["readable_workflow"]["final_conclusion"] is None


def test_trace_api_recovers_readable_workflow_from_null_spans_modern_trace(tmp_path: Path) -> None:
    trace_root = tmp_path / "traces"
    trace_root.mkdir(parents=True, exist_ok=True)
    trace_path = trace_root / "20260331T000000000000Z.json"
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
                        "summary": "Need more evidence.",
                        "start_ts": "2026-03-31T00:00:00Z",
                        "end_ts": "2026-03-31T00:00:05Z",
                        "duration_ms": 5000.0,
                        "payload": {
                            "agent_loop": [
                                {
                                    "round": 1,
                                    "decision": {"summary": "Search first."},
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
                "execution_summary": {"asset": "BTC", "summary": "Need more evidence."},
                "events": [],
                "spans": None,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    service = TraceLogService(tmp_path)
    payload = read_trace(trace_path.name, service)

    assert payload["spans"]
    assert payload["readable_workflow"]["audit_summary"]["tool_calls"] == 1
    assert payload["readable_workflow"]["evidence_records"]
    assert payload["readable_workflow"]["timeline"]


def test_trace_api_preserves_stored_event_identity_fields(tmp_path: Path) -> None:
    service = TraceLogService(memory_root=tmp_path)
    path = service.write_trace(
        user_query="event identity",
        status="execute",
        plan=None,
        task_results=[],
        execution_summary=None,
        events=[
            {
                "name": "executor.task_completed",
                "actor": "ResearchAgent",
                "detail": {"task_id": "task-1"},
                "span_id": "span-123",
                "parent_span_id": "parent-456",
                "start_ts": "2026-03-31T00:00:00Z",
                "end_ts": "2026-03-31T00:00:02Z",
                "duration_ms": 2000.0,
            }
        ],
    )

    payload = read_trace(Path(path).name, service)
    event = payload["events"][0]

    assert event["span_id"] == "span-123"
    assert event["parent_span_id"] == "parent-456"
    assert event["start_ts"] == "2026-03-31T00:00:00Z"
    assert event["end_ts"] == "2026-03-31T00:00:02Z"
    assert event["duration_ms"] == 2000.0
