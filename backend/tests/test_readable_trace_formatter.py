from app.services.readable_trace_formatter import build_readable_workflow


def test_build_readable_workflow_emits_overview_timeline_and_failure_anchor() -> None:
    payload = {
        "status": "partial_failure",
        "metrics_summary": {
            "prompt_tokens": 120,
            "completion_tokens": 30,
            "total_tokens": 150,
            "input_bytes": 64,
            "output_bytes": 128,
        },
        "tool_usage_summary": {"total_calls": 1, "failed_calls": 1, "degraded_calls": 0},
        "failure_count": 2,
        "task_results": [
            {
                "task_id": "task-research",
                "task_type": "research",
                "agent": "ResearchAgent",
                "status": "insufficient",
                "payload": {
                    "agent_loop": [
                        {
                            "round": 1,
                            "decision": {"summary": "Search recent SUI catalyst sources first."},
                            "action": {"tool": "search_web", "input": {"query": "SUI catalysts"}},
                            "result": {
                                "status": "success",
                                "tool_name": "search_web",
                                "output_summary": {
                                    "provider": "exa",
                                    "results": [
                                        {
                                            "title": "Sui ecosystem growth",
                                            "url": "https://www.coindesk.com/sui-growth",
                                            "snippet": "Sui ecosystem growth and catalysts",
                                        }
                                    ],
                                },
                            },
                        },
                        {
                            "round": 2,
                            "decision": {"summary": "Fetch the strongest result for concrete findings."},
                            "action": {"tool": "fetch_page", "input": {"url": "https://www.coindesk.com/sui-growth"}},
                            "result": {
                                "status": "failed",
                                "tool_name": "fetch_page",
                                "output_summary": {
                                    "url": "https://www.coindesk.com/sui-growth",
                                    "title": "Sui ecosystem growth",
                                    "strategy": "readability_like",
                                },
                                "reason": "403 Forbidden",
                            },
                            "termination": {"reason": "source_exhausted"},
                        },
                    ]
                },
            }
        ],
        "spans": [
            {
                "span_id": "tool-1",
                "parent_span_id": "llm-1",
                "trace_id": "trace-1",
                "kind": "tool",
                "name": "search_web",
                "status": "success",
                "start_ts": "2026-03-31T00:00:00.500Z",
                "end_ts": "2026-03-31T00:00:00.900Z",
                "duration_ms": 400.0,
                "input_summary": {"query": "SUI catalysts"},
                "output_summary": {
                    "query": "SUI catalysts",
                    "provider": "exa",
                    "results": [
                        {
                            "title": "Sui ecosystem growth",
                            "url": "https://www.coindesk.com/sui-growth",
                            "snippet": "Sui ecosystem growth and catalysts",
                        }
                    ],
                },
                "error": None,
                "attributes": {
                    "tool_name": "search_web",
                    "tool_server": "research",
                    "tool_domain": "research",
                    "args": {"query": "SUI catalysts"},
                    "result_preview": {"provider": "exa"},
                },
                "metrics": {"input_bytes": 16, "output_bytes": 24},
                "audit": {"actor": "ResearchAgent"},
            },
            {
                "span_id": "tool-2",
                "parent_span_id": "llm-2",
                "trace_id": "trace-1",
                "kind": "tool",
                "name": "fetch_page",
                "status": "failed",
                "start_ts": "2026-03-31T00:00:01.000Z",
                "end_ts": "2026-03-31T00:00:01.300Z",
                "duration_ms": 300.0,
                "input_summary": {"url": "https://www.coindesk.com/sui-growth"},
                "output_summary": {
                    "url": "https://www.coindesk.com/sui-growth",
                    "title": "Sui ecosystem growth",
                    "strategy": "readability_like",
                    "summary": "The page could not be extracted because access was forbidden.",
                    "failure_reason": "403 Forbidden",
                },
                "error": "403 Forbidden",
                "attributes": {
                    "tool_name": "fetch_page",
                    "tool_server": "research",
                    "tool_domain": "research",
                    "args": {"url": "https://www.coindesk.com/sui-growth"},
                    "result_preview": {"title": "Sui ecosystem growth", "strategy": "readability_like"},
                    "exception_type": "HTTPStatusError",
                },
                "metrics": {"input_bytes": 42, "output_bytes": 96},
                "audit": {"actor": "ResearchAgent"},
            },
            {
                "span_id": "planner-1",
                "parent_span_id": None,
                "trace_id": "trace-1",
                "kind": "planner",
                "name": "Planner",
                "status": "success",
                "start_ts": "2026-03-31T00:00:00.000Z",
                "end_ts": "2026-03-31T00:00:00.100Z",
                "duration_ms": 100.0,
                "input_summary": {"goal": "Analyze SUI"},
                "output_summary": {"status": "execute"},
                "error": None,
                "attributes": {"decision_mode": "mixed_analysis"},
                "metrics": {},
                "audit": {"actor": "Planner"},
            },
            {
                "span_id": "agent-1",
                "parent_span_id": "planner-1",
                "trace_id": "trace-1",
                "kind": "agent",
                "name": "ResearchAgent",
                "status": "insufficient",
                "start_ts": "2026-03-31T00:00:00.950Z",
                "end_ts": "2026-03-31T00:00:01.200Z",
                "duration_ms": 250.0,
                "input_summary": {"task_type": "research"},
                "output_summary": {"summary": "Need market-side confirmation."},
                "error": None,
                "attributes": {"agent": "ResearchAgent"},
                "metrics": {},
                "audit": {"actor": "ResearchAgent"},
            },
            {
                "span_id": "llm-1",
                "parent_span_id": None,
                "trace_id": "trace-1",
                "kind": "llm",
                "name": "research_round_1",
                "status": "success",
                "start_ts": "2026-03-31T00:00:00.150Z",
                "end_ts": "2026-03-31T00:00:00.450Z",
                "duration_ms": 300.0,
                "input_summary": {"asset": "SUI"},
                "output_summary": {"decision_summary": "Search first", "action": "search_web"},
                "error": None,
                "attributes": {
                    "model": "gpt-5.4",
                    "provider": "openai",
                    "temperature": 0.2,
                    "decision_summary": "Search first",
                    "action": "search_web",
                    "termination_reason": None,
                    "finish_reason": "tool_call",
                    "started_at": "2026-03-31T00:00:00.150Z",
                    "first_token_at": "2026-03-31T00:00:00.220Z",
                    "completed_at": "2026-03-31T00:00:00.450Z",
                },
                "metrics": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
                "audit": {"actor": "ResearchAgent"},
            },
            {
                "span_id": "llm-2",
                "parent_span_id": None,
                "trace_id": "trace-1",
                "kind": "llm",
                "name": "research_round_2",
                "status": "failed",
                "start_ts": "2026-03-31T00:00:00.930Z",
                "end_ts": "2026-03-31T00:00:00.990Z",
                "duration_ms": 60.0,
                "input_summary": {"asset": "SUI"},
                "output_summary": {
                    "decision_summary": "Fetch the top result",
                    "action": "fetch_page",
                },
                "error": "tool_downstream_failed",
                "attributes": {
                    "model": "gpt-5.4",
                    "provider": "openai",
                    "temperature": 0.2,
                    "decision_summary": "Fetch the top result",
                    "action": "fetch_page",
                    "termination_reason": "source_exhausted",
                    "finish_reason": "stop",
                    "started_at": "2026-03-31T00:00:00.930Z",
                    "first_token_at": "2026-03-31T00:00:00.950Z",
                    "completed_at": "2026-03-31T00:00:00.990Z",
                },
                "metrics": {"prompt_tokens": 40, "completion_tokens": 12, "total_tokens": 52},
                "audit": {"actor": "ResearchAgent"},
            },
        ],
        "execution_summary": {
            "summary": "Need market-side confirmation.",
            "missing_information": ["Market-side evidence is missing."],
            "degraded_reason": "search_failed",
        },
        "final_answer": "Need market-side confirmation.",
    }

    workflow = build_readable_workflow(payload)

    assert workflow["audit_summary"]["trace_status"] == "partial_failure"
    assert workflow["audit_summary"]["total_tokens"] == 150
    assert workflow["audit_summary"]["tool_calls"] == 2
    assert workflow["audit_summary"]["failed_calls"] == 2
    assert workflow["audit_summary"]["degraded_calls"] == 0
    assert workflow["audit_summary"]["duration_ms"] == 1300.0
    assert workflow["audit_summary"]["models_used"] == ["gpt-5.4"]
    assert workflow["audit_summary"]["providers_used"] == ["openai"]
    assert workflow["audit_summary"]["first_failed_span_id"] == "llm-2"
    assert workflow["audit_summary"]["callback_summary"]["completed_count"] == 2
    assert [node["span_id"] for node in workflow["timeline"]] == ["planner-1", "llm-1", "tool-1", "llm-2", "agent-1", "tool-2"]
    assert workflow["meta"]["first_failed_span_id"] == "llm-2"
    assert workflow["timeline"][2]["detail_tabs"]["input"]["query"] == "SUI catalysts"
    assert workflow["timeline"][2]["detail_tabs"]["output"]["query"] == "SUI catalysts"
    assert workflow["timeline"][5]["detail_tabs"]["error"]["error"] == "403 Forbidden"
    assert workflow["timeline"][2]["detail_tabs"]["audit"]["tool_server"] == "research"
    assert workflow["conclusions"][0]["kind"] == "final"
    assert workflow["conclusions"][0]["text"] == "Need market-side confirmation."
    assert workflow["evidence_records"][0]["source_tool"] == "search_web"
    assert workflow["evidence_records"][0]["attributes"]["provider"] == "exa"
    assert any(record["source_domain"] == "www.coindesk.com" for record in workflow["evidence_records"])
    assert any(record["source_tool"] == "fetch_page" for record in workflow["evidence_records"])
    assert workflow["reasoning_steps"][0]["decision_summary"] == "Search recent SUI catalyst sources first."
    assert workflow["reasoning_steps"][0]["action"] == "search_web"
    assert workflow["reasoning_steps"][0]["callback"]["finish_reason"] == "tool_call"
    assert workflow["reasoning_steps"][1]["action"] == "fetch_page"
    assert workflow["reasoning_steps"][1]["status"] == "failed"
    assert workflow["final_conclusion"]["final_answer"] == "Need market-side confirmation."


def test_build_readable_workflow_for_clarify_trace_stays_planner_only() -> None:
    payload = {
        "status": "clarify",
        "metrics_summary": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "input_bytes": 0, "output_bytes": 0},
        "tool_usage_summary": {"total_calls": 0, "failed_calls": 0, "degraded_calls": 0},
        "failure_count": 0,
        "spans": [
            {
                "span_id": "planner-1",
                "parent_span_id": None,
                "trace_id": "trace-clarify",
                "kind": "planner",
                "name": "Planner",
                "status": "success",
                "start_ts": "2026-03-31T00:00:00Z",
                "end_ts": "2026-03-31T00:00:00Z",
                "duration_ms": 0.0,
                "input_summary": {"goal": "Clarify the asset"},
                "output_summary": {"status": "clarify"},
                "error": None,
                "attributes": {"needs_clarification": True},
                "metrics": {},
                "audit": {"actor": "Planner"},
            }
        ],
        "final_answer": "你想看哪个标的，是现货还是合约？",
    }

    workflow = build_readable_workflow(payload)

    assert workflow["audit_summary"]["trace_status"] == "clarify"
    assert len(workflow["timeline"]) == 1
    assert workflow["timeline"][0]["kind"] == "planner"
    assert workflow["meta"]["first_failed_span_id"] is None
    assert workflow["final_conclusion"] is None
    assert workflow["conclusions"] == []
    assert workflow["evidence_records"] == []
    assert workflow["reasoning_steps"] == []


def test_build_readable_workflow_for_cancelled_trace_omits_open_spans_and_final_answer() -> None:
    payload = {
        "status": "cancelled",
        "metrics_summary": {"prompt_tokens": 60, "completion_tokens": 10, "total_tokens": 70, "input_bytes": 0, "output_bytes": 0},
        "tool_usage_summary": {"total_calls": 1, "failed_calls": 0, "degraded_calls": 0},
        "failure_count": 0,
        "spans": [
            {
                "span_id": "planner-1",
                "parent_span_id": None,
                "trace_id": "trace-cancelled",
                "kind": "planner",
                "name": "Planner",
                "status": "success",
                "start_ts": "2026-03-31T00:00:00Z",
                "end_ts": "2026-03-31T00:00:00.050Z",
                "duration_ms": 50.0,
                "input_summary": {},
                "output_summary": {},
                "error": None,
                "attributes": {},
                "metrics": {},
                "audit": {"actor": "Planner"},
            },
            {
                "span_id": "llm-1",
                "parent_span_id": None,
                "trace_id": "trace-cancelled",
                "kind": "llm",
                "name": "research_round_1",
                "status": "success",
                "start_ts": "2026-03-31T00:00:00.100Z",
                "end_ts": "2026-03-31T00:00:00.250Z",
                "duration_ms": 150.0,
                "input_summary": {"asset": "BTC"},
                "output_summary": {"action": "search_web"},
                "error": None,
                "attributes": {"model": "gpt-5.4", "provider": "openai", "temperature": 0.2},
                "metrics": {"prompt_tokens": 60, "completion_tokens": 10, "total_tokens": 70},
                "audit": {"actor": "ResearchAgent"},
            },
            {
                "span_id": "tool-open",
                "parent_span_id": "llm-1",
                "trace_id": "trace-cancelled",
                "kind": "tool",
                "name": "search_web",
                "status": "unknown",
                "start_ts": "2026-03-31T00:00:00.260Z",
                "end_ts": None,
                "duration_ms": None,
                "input_summary": {"query": "BTC catalysts"},
                "output_summary": {},
                "error": None,
                "attributes": {"tool_server": "research"},
                "metrics": {},
                "audit": {"actor": "ResearchAgent"},
            },
        ],
        "final_answer": "This answer should be hidden.",
    }

    workflow = build_readable_workflow(payload)

    assert workflow["audit_summary"]["trace_status"] == "cancelled"
    assert [node["span_id"] for node in workflow["timeline"]] == ["planner-1", "llm-1"]
    assert workflow["final_conclusion"] is None
    assert workflow["conclusions"] == []


def test_build_readable_workflow_uses_pseudo_spans_for_legacy_payloads() -> None:
    payload = {
        "status": "clarify",
        "pseudo_spans": [
            {
                "span_id": "planner",
                "parent_span_id": None,
                "trace_id": "legacy-trace",
                "kind": "planner",
                "name": "Planner",
                "status": "unknown",
                "start_ts": "20260323T000000000000Z",
                "end_ts": None,
                "duration_ms": None,
                "input_summary": {},
                "output_summary": {"route": "clarify"},
                "error": None,
                "attributes": {"legacy_route": {"type": "clarify", "agent": "RouterAgent"}},
                "metrics": {},
                "audit": {"actor": "RouterAgent"},
            }
        ],
        "final_answer": "legacy answer",
    }

    workflow = build_readable_workflow(payload)

    assert workflow["timeline"][0]["span_id"] == "planner"
    assert workflow["timeline"][0]["kind"] == "planner"
    assert workflow["audit_summary"]["total_tokens"] == 0
    assert workflow["conclusions"] == []
    assert workflow["evidence_records"] == []
    assert workflow["reasoning_steps"] == []
