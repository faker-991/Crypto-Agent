from __future__ import annotations

import json

from app.runtime.trace_runtime import TraceRuntime


def test_start_span_returns_canonical_span_shape() -> None:
    runtime = TraceRuntime()

    span = runtime.start_span(
        trace_id="trace-runtime-1",
        parent_span_id="parent-span",
        kind="tool",
        name="fetch_page",
        input_summary={"url": "https://example.com"},
        attributes={
            "tool_name": "fetch_page",
            "tool_server": "research",
            "tool_domain": "research",
            "args": {"url": "https://example.com"},
            "result_preview": {"title": "Example"},
            "retry_count": 0,
            "degraded": False,
        },
    )

    assert span["trace_id"] == "trace-runtime-1"
    assert span["span_id"]
    assert span["parent_span_id"] == "parent-span"
    assert span["kind"] == "tool"
    assert span["attributes"]["tool_name"] == "fetch_page"
    assert isinstance(span["metrics"], dict)
    assert isinstance(span["audit"], dict)


def test_finish_span_computes_duration_and_merges_attributes() -> None:
    runtime = TraceRuntime()

    span = runtime.start_span(
        trace_id="trace-runtime-2",
        parent_span_id=None,
        kind="tool",
        name="get_ticker",
        input_summary={"symbol": "BTCUSDT"},
        attributes={
            "tool_name": "get_ticker",
            "tool_server": "binance",
            "tool_domain": "market",
            "args": {"symbol": "BTCUSDT"},
            "result_preview": {"symbol": "BTCUSDT"},
            "retry_count": 0,
            "degraded": False,
        },
    )

    finished = runtime.finish_span(
        span_id=span["span_id"],
        status="success",
        output_summary={"symbol": "BTCUSDT", "last_price": 100.0},
        metrics={"input_bytes": 12, "output_bytes": 48},
        audit={"actor": "ResearchAgent"},
        attributes={"retry_count": 1, "source": "cache"},
    )

    assert finished["span_id"] == span["span_id"]
    assert finished["duration_ms"] >= 0
    assert finished["attributes"]["tool_name"] == "get_ticker"
    assert finished["attributes"]["retry_count"] == 1
    assert finished["attributes"]["source"] == "cache"


def test_finalize_trace_produces_summary_counts() -> None:
    runtime = TraceRuntime()

    llm_span = runtime.start_span(
        trace_id="trace-runtime-3",
        parent_span_id=None,
        kind="llm",
        name="planner_llm",
        input_summary={"prompt": "plan"},
        attributes={
            "model": "gpt-5",
            "provider": "openai",
            "temperature": 0.2,
            "decision_summary": "Call research tool.",
            "action": "search_web",
            "termination_reason": "continue",
        },
    )
    runtime.finish_span(
        span_id=llm_span["span_id"],
        status="success",
        output_summary={"decision": "search_web"},
        metrics={
            "prompt_tokens": 12,
            "completion_tokens": 3,
            "total_tokens": 15,
            "input_bytes": 40,
            "output_bytes": 20,
        },
        audit={"actor": "Planner"},
    )

    ok_tool_span = runtime.start_span(
        trace_id="trace-runtime-3",
        parent_span_id=llm_span["span_id"],
        kind="tool",
        name="search_web",
        input_summary={"query": "BTC"},
        attributes={
            "tool_name": "search_web",
            "tool_server": "research",
            "tool_domain": "research",
            "args": {"query": "BTC"},
            "result_preview": {"result": "ok"},
            "retry_count": 0,
            "degraded": False,
        },
    )
    runtime.finish_span(
        span_id=ok_tool_span["span_id"],
        status="success",
        output_summary={"result": "ok"},
        metrics={"input_bytes": 7, "output_bytes": 50},
        audit={"actor": "ResearchAgent"},
    )

    degraded_tool_span = runtime.start_span(
        trace_id="trace-runtime-3",
        parent_span_id=llm_span["span_id"],
        kind="tool",
        name="fetch_page",
        input_summary={"url": "https://example.com"},
        attributes={
            "tool_name": "fetch_page",
            "tool_server": "research",
            "tool_domain": "research",
            "args": {"url": "https://example.com"},
            "result_preview": {"title": "Example"},
            "retry_count": 0,
            "degraded": False,
        },
    )
    runtime.finish_span(
        span_id=degraded_tool_span["span_id"],
        status="degraded",
        output_summary={"text": "partial"},
        metrics={"input_bytes": 9, "output_bytes": 10},
        audit={"actor": "ResearchAgent"},
    )

    failed_tool_span = runtime.start_span(
        trace_id="trace-runtime-3",
        parent_span_id=llm_span["span_id"],
        kind="tool",
        name="get_klines",
        input_summary={"symbol": "ETHUSDT"},
        attributes={
            "tool_name": "get_klines",
            "tool_server": "binance",
            "tool_domain": "market",
            "args": {"symbol": "ETHUSDT"},
            "result_preview": {"error": "timeout"},
            "retry_count": 0,
            "degraded": True,
        },
    )
    runtime.finish_span(
        span_id=failed_tool_span["span_id"],
        status="failed",
        output_summary={},
        metrics={"input_bytes": 0, "output_bytes": 0},
        audit={"actor": "KlineAgent"},
    )

    trace = runtime.finalize_trace(
        trace_id="trace-runtime-3",
        summary={
            "user_query": "Analyze BTC",
            "status": "partial_failure",
            "conversation_id": "conversation-1",
        },
    )

    assert trace["metrics_summary"] == {
        "prompt_tokens": 12,
        "completion_tokens": 3,
        "total_tokens": 15,
        "input_bytes": 56,
        "output_bytes": 80,
    }
    assert trace["tool_usage_summary"] == {
        "total_calls": 3,
        "failed_calls": 1,
        "degraded_calls": 1,
    }
    assert trace["llm_call_count"] == 1
    assert trace["tool_call_count"] == 3
    assert trace["failure_count"] == 2


def test_finalize_trace_failure_count_only_includes_runtime_span_kinds() -> None:
    runtime = TraceRuntime()

    planner_span = runtime.start_span(
        trace_id="trace-runtime-failure-count",
        parent_span_id=None,
        kind="planner",
        name="Planner",
        input_summary={},
        attributes={},
    )
    runtime.finish_span(
        span_id=planner_span["span_id"],
        status="failed",
        output_summary={},
        metrics={},
        error="planner_error",
    )

    tool_span = runtime.start_span(
        trace_id="trace-runtime-failure-count",
        parent_span_id=None,
        kind="tool",
        name="search_web",
        input_summary={},
        attributes={"tool_name": "search_web"},
    )
    runtime.finish_span(
        span_id=tool_span["span_id"],
        status="failed",
        output_summary={},
        metrics={},
        error="tool_error",
    )

    trace = runtime.finalize_trace(trace_id="trace-runtime-failure-count")

    assert trace["failure_count"] == 1


def test_large_tool_outputs_are_truncated_before_persistence_with_explicit_flag() -> None:
    runtime = TraceRuntime()
    large_text = "x" * 1500

    span = runtime.start_span(
        trace_id="trace-runtime-4",
        parent_span_id=None,
        kind="tool",
        name="fetch_page",
        input_summary={"url": "https://example.com"},
        attributes={
            "tool_name": "fetch_page",
            "tool_server": "research",
            "tool_domain": "research",
            "args": {"url": "https://example.com"},
            "result_preview": {"title": "Example"},
            "retry_count": 0,
            "degraded": False,
        },
    )
    runtime.finish_span(
        span_id=span["span_id"],
        status="success",
        output_summary={"text": large_text},
        metrics={"input_bytes": 24, "output_bytes": len(large_text)},
        audit={"actor": "ResearchAgent"},
    )

    trace = runtime.finalize_trace(
        trace_id="trace-runtime-4",
        summary={"user_query": "Fetch page", "status": "execute"},
    )
    tool_span = next(item for item in trace["spans"] if item["span_id"] == span["span_id"])

    assert tool_span["attributes"]["output_truncated"] is True
    assert tool_span["output_summary"]["text"] != large_text
    assert len(tool_span["output_summary"]["text"]) < len(large_text)


def test_sensitive_tool_spans_redact_raw_args_and_output_before_persistence() -> None:
    runtime = TraceRuntime()

    span = runtime.start_span(
        trace_id="trace-runtime-5",
        parent_span_id=None,
        kind="tool",
        name="fetch_page",
        input_summary={"url": "https://example.com/private"},
        attributes={
            "tool_name": "fetch_page",
            "tool_server": "research",
            "tool_domain": "research",
            "args": {
                "url": "https://example.com/private",
                "api_key": "sk-live-secret",
                "cookie": "session=abc123",
            },
            "result_preview": "Public title",
            "retry_count": 0,
            "degraded": False,
        },
    )
    runtime.finish_span(
        span_id=span["span_id"],
        status="success",
        output_summary={"text": "secret body", "title": "Public title"},
        metrics={"input_bytes": 64, "output_bytes": 128},
        audit={"actor": "ResearchAgent", "audit_level": "sensitive"},
    )

    trace = runtime.finalize_trace(
        trace_id="trace-runtime-5",
        summary={"user_query": "Fetch sensitive page", "status": "execute"},
    )
    tool_span = next(item for item in trace["spans"] if item["span_id"] == span["span_id"])

    assert tool_span["attributes"]["args"] == {
        "url": "https://example.com/private",
        "api_key": "[REDACTED]",
        "cookie": "[REDACTED]",
    }
    assert tool_span["attributes"]["result_preview"] == {"title": "Public title"}
    assert tool_span["output_summary"] == {
        "text": "[REDACTED]",
        "title": "Public title",
    }
    assert "sk-live-secret" not in json.dumps(tool_span, ensure_ascii=False)
    assert "session=abc123" not in json.dumps(tool_span, ensure_ascii=False)


def test_explicit_redaction_rules_are_honored_during_persistence() -> None:
    runtime = TraceRuntime()

    span = runtime.start_span(
        trace_id="trace-runtime-5b",
        parent_span_id=None,
        kind="tool",
        name="fetch_page",
        input_summary={"url": "https://example.com/private"},
        attributes={
            "args": {
                "url": "https://example.com/private",
                "session_token": "tok-secret",
            },
            "result_preview": {"title": "Public title", "snippet": "secret snippet"},
            "redaction_rules": {
                "attribute_keys": ["session_token"],
                "output_keys": ["text", "snippet"],
            },
        },
    )
    runtime.finish_span(
        span_id=span["span_id"],
        status="success",
        output_summary={"text": "secret body", "title": "Public title", "snippet": "hidden"},
        metrics={"input_bytes": 64, "output_bytes": 128},
        audit={"actor": "ResearchAgent"},
    )

    trace = runtime.finalize_trace(
        trace_id="trace-runtime-5b",
        summary={"user_query": "Fetch page", "status": "execute"},
    )
    tool_span = next(item for item in trace["spans"] if item["span_id"] == span["span_id"])

    assert tool_span["attributes"]["args"]["session_token"] == "[REDACTED]"
    assert tool_span["attributes"]["result_preview"] == {"title": "Public title", "snippet": "[REDACTED]"}
    assert tool_span["output_summary"] == {
        "text": "[REDACTED]",
        "title": "Public title",
        "snippet": "[REDACTED]",
    }


def test_legacy_fallback_spans_use_unknown_status_when_no_better_status_can_be_derived() -> None:
    runtime = TraceRuntime()

    span = runtime.start_span(
        trace_id="trace-runtime-6",
        parent_span_id=None,
        kind="agent",
        name="ResearchAgent",
        input_summary={"task": "legacy"},
        attributes={"agent": "ResearchAgent"},
    )

    trace = runtime.finalize_trace(
        trace_id="trace-runtime-6",
        summary={"user_query": "Legacy trace", "status": "execute"},
    )
    fallback_span = next(item for item in trace["spans"] if item["span_id"] == span["span_id"])

    assert fallback_span["status"] == "unknown"


def test_finalize_trace_derives_partial_failure_for_mixed_success_and_failure() -> None:
    runtime = TraceRuntime()

    ok_span = runtime.start_span(
        trace_id="trace-runtime-7",
        parent_span_id=None,
        kind="tool",
        name="search_web",
        input_summary={},
        attributes={"tool_name": "search_web"},
    )
    runtime.finish_span(
        span_id=ok_span["span_id"],
        status="success",
        output_summary={"result": "ok"},
        metrics={"input_bytes": 1, "output_bytes": 1},
    )

    failed_span = runtime.start_span(
        trace_id="trace-runtime-7",
        parent_span_id=None,
        kind="tool",
        name="fetch_page",
        input_summary={},
        attributes={"tool_name": "fetch_page"},
    )
    runtime.finish_span(
        span_id=failed_span["span_id"],
        status="failed",
        output_summary={},
        metrics={"input_bytes": 0, "output_bytes": 0},
        error="timeout",
    )

    trace = runtime.finalize_trace(trace_id="trace-runtime-7")

    assert trace["status"] == "partial_failure"
