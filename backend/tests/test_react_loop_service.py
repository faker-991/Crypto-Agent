from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.runtime.tool_contracts import ToolResult, ToolSpec
from app.runtime.tool_runtime import ToolRuntime
from app.runtime.trace_runtime import TraceRuntime
from app.runtime.react_loop_service import ReActLoopService


class StubLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def _next(self, method: str, *args, **kwargs) -> SimpleNamespace:
        if not self.responses:
            raise AssertionError(f"Unexpected LLM call via {method}")
        content = self.responses.pop(0)
        self.calls.append({"method": method, "args": args, "kwargs": kwargs, "content": content})
        return SimpleNamespace(
            content=content,
            text=content,
            message=SimpleNamespace(content=content),
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            model="stub-model",
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18),
        )

    def complete(self, *args, **kwargs) -> SimpleNamespace:
        return self._next("complete", *args, **kwargs)

    def chat(self, *args, **kwargs) -> SimpleNamespace:
        return self._next("chat", *args, **kwargs)

    def invoke(self, *args, **kwargs) -> SimpleNamespace:
        return self._next("invoke", *args, **kwargs)

    def generate(self, *args, **kwargs) -> SimpleNamespace:
        return self._next("generate", *args, **kwargs)

    def run(self, *args, **kwargs) -> SimpleNamespace:
        return self._next("run", *args, **kwargs)

    def create(self, *args, **kwargs) -> SimpleNamespace:
        return self._next("create", *args, **kwargs)


def _ticker_tool_spec() -> ToolSpec:
    return {
        "name": "get_ticker",
        "server": "binance",
        "domain": "market",
        "description": "Fetch a compact ticker snapshot.",
        "usage_guidance": "Use when the agent needs a current market anchor.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "market_type": {"type": "string"},
            },
            "required": ["symbol", "market_type"],
        },
        "output_schema": {
            "type": "object",
            "properties": {"symbol": {"type": "string"}},
            "required": ["symbol"],
        },
        "executor_ref": "market.get_ticker",
        "source_type": "local",
        "audit_level": "basic",
        "replay_mode": "view_only",
    }


def _search_tool_spec() -> ToolSpec:
    return {
        "name": "search_web",
        "server": "research",
        "domain": "research",
        "description": "Search for relevant sources.",
        "usage_guidance": "Use for web evidence and source discovery.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        "output_schema": {
            "type": "object",
            "properties": {"results": {"type": "array"}},
            "required": ["results"],
        },
        "executor_ref": "research.search_web",
        "source_type": "local",
        "audit_level": "basic",
        "replay_mode": "view_only",
    }


def _build_tool_runtime(
    *,
    get_ticker_handler=None,
    search_web_handler=None,
) -> ToolRuntime:
    executors = {
        "market.get_ticker": get_ticker_handler
        or (lambda args, trace_context=None: {"symbol": args["symbol"], "market_type": args["market_type"]}),
        "research.search_web": search_web_handler
        or (lambda args, trace_context=None: {"results": [{"title": "source", "url": "https://example.com"}]}),
    }
    return ToolRuntime(tool_specs=[_ticker_tool_spec(), _search_tool_spec()], tool_executors=executors)


def _build_service(
    responses: list[str],
    *,
    tool_runtime: ToolRuntime | None = None,
    trace_runtime: TraceRuntime | None = None,
    max_rounds: int = 1,
    max_same_call_repeats: int = 1,
    max_tool_failures: int = 2,
    max_no_progress_rounds: int = 2,
) -> tuple[ReActLoopService, TraceRuntime, StubLLMClient]:
    trace_runtime = trace_runtime or TraceRuntime()
    llm_client = StubLLMClient(responses)
    service = ReActLoopService(
        llm_client=llm_client,
        tool_runtime=tool_runtime or _build_tool_runtime(),
        trace_runtime=trace_runtime,
        max_rounds=max_rounds,
        max_same_call_repeats=max_same_call_repeats,
        max_tool_failures=max_tool_failures,
        max_no_progress_rounds=max_no_progress_rounds,
    )
    return service, trace_runtime, llm_client


def assert_tool_result_like(tool_call: dict) -> None:
    assert isinstance(tool_call, dict)
    assert isinstance(tool_call.get("tool_name"), str) and tool_call["tool_name"]
    assert tool_call.get("status") in {"success", "failed", "degraded"}
    assert isinstance(tool_call.get("server"), str)
    assert isinstance(tool_call.get("domain"), str)
    assert isinstance(tool_call.get("args"), dict)
    assert isinstance(tool_call.get("output"), dict)
    assert isinstance(tool_call.get("output_summary"), dict)
    assert isinstance(tool_call.get("degraded"), bool)
    assert isinstance(tool_call.get("metrics"), dict)
    assert isinstance(tool_call["metrics"].get("input_bytes"), int)
    assert isinstance(tool_call["metrics"].get("output_bytes"), int)


def test_run_executes_a_valid_tool_and_records_one_llm_span_and_one_tool_span() -> None:
    trace_id = "trace-react-valid"
    service, trace_runtime, _ = _build_service(
        [
            '{"decision_summary":"Check market anchor first.","action":"get_ticker","args":{"symbol":"SUI","market_type":"spot"},"termination":false,"termination_reason":null}'
        ]
    )

    terminal_state, observations, tool_results = service.run(
        asset="SUI",
        tool_specs=[_ticker_tool_spec()],
        initial_context={"trace_id": trace_id, "asset": "SUI"},
    )

    trace = trace_runtime.finalize_trace(trace_id=trace_id)

    assert terminal_state["rounds_used"] >= 1
    assert observations
    assert tool_results
    assert_tool_result_like(tool_results[0])
    span_kinds = {span["kind"] for span in trace["spans"]}
    assert "llm" in span_kinds
    assert "tool" in span_kinds
    llm_span = next(span for span in trace["spans"] if span["kind"] == "llm")
    assert llm_span["attributes"]["model"] == "stub-model"
    assert llm_span["attributes"]["provider"] == "StubLLMClient"
    assert "temperature" in llm_span["attributes"]


def test_run_preserves_fallback_error_on_llm_span_attributes() -> None:
    trace_id = "trace-react-fallback"
    trace_runtime = TraceRuntime()
    llm_client = StubLLMClient(
        [
            '{"decision_summary":"Check market anchor first.","action":"get_ticker","args":{"symbol":"SUI","market_type":"spot"},"termination":false,"termination_reason":null}'
        ]
    )
    service = ReActLoopService(
        llm_client=llm_client,
        tool_runtime=_build_tool_runtime(),
        trace_runtime=trace_runtime,
        max_rounds=1,
    )

    original_complete = llm_client.complete

    def complete_with_fallback(*args, **kwargs):
        response = original_complete(*args, **kwargs)
        response.provider = "heuristic-research-llm"
        response.model = "heuristic-research-llm"
        response.fallback_error = "timed out contacting remote model"
        return response

    llm_client.complete = complete_with_fallback

    service.run(
        asset="SUI",
        tool_specs=[_ticker_tool_spec()],
        initial_context={"trace_id": trace_id, "asset": "SUI"},
    )

    trace = trace_runtime.finalize_trace(trace_id=trace_id)
    llm_span = next(span for span in trace["spans"] if span["kind"] == "llm")

    assert llm_span["attributes"]["provider"] == "heuristic-research-llm"
    assert llm_span["attributes"]["model"] == "heuristic-research-llm"
    assert llm_span["attributes"]["fallback_error"] == "timed out contacting remote model"


@pytest.mark.parametrize(
    "response",
    [
        "not-json",
        '{"decision_summary":"Stop now.","action":"","args":{},"termination":false,"termination_reason":null}',
        '{"decision_summary":"Bad args.","action":"get_ticker","args":"BTC","termination":false,"termination_reason":null}',
    ],
)
def test_run_stops_current_llm_step_on_invalid_json_empty_action_or_non_object_args(response: str) -> None:
    trace_id = "trace-react-failed-step"
    service, trace_runtime, _ = _build_service([response])

    terminal_state, observations, tool_results = service.run(
        asset="SUI",
        tool_specs=[_ticker_tool_spec()],
        initial_context={"trace_id": trace_id, "asset": "SUI"},
    )

    trace = trace_runtime.finalize_trace(trace_id=trace_id)

    assert terminal_state["status"] == "failed"
    assert terminal_state["evidence_status"] == "failed"
    assert observations == []
    assert tool_results == []
    assert trace["status"] == "failed"
    assert any(span["kind"] == "llm" and span["status"] == "failed" for span in trace["spans"])
    assert not any(span["kind"] == "tool" for span in trace["spans"])


def test_run_marks_unknown_or_disallowed_tool_names_as_degraded_without_tool_execution() -> None:
    trace_id = "trace-react-unknown-tool"
    service, trace_runtime, _ = _build_service(
        [
            '{"decision_summary":"Try an unsupported tool.","action":"not_allowed","args":{"symbol":"SUI"},"termination":false,"termination_reason":null}'
        ],
        max_rounds=1,
    )

    terminal_state, observations, tool_results = service.run(
        asset="SUI",
        tool_specs=[_ticker_tool_spec()],
        initial_context={"trace_id": trace_id, "asset": "SUI"},
    )

    trace = trace_runtime.finalize_trace(trace_id=trace_id)

    assert terminal_state["evidence_status"] == "insufficient"
    assert observations == []
    assert tool_results == []
    assert trace["status"] == "partial_failure"
    assert any(span["kind"] == "llm" and span["status"] == "degraded" for span in trace["spans"])
    assert not any(span["kind"] == "tool" for span in trace["spans"])


def test_run_treats_termination_true_with_non_empty_action_as_degraded() -> None:
    trace_id = "trace-react-conflict"
    service, trace_runtime, _ = _build_service(
        [
            '{"decision_summary":"Stop but still selects a tool.","action":"get_ticker","args":{"symbol":"SUI","market_type":"spot"},"termination":true,"termination_reason":"done"}'
        ],
        max_rounds=1,
    )

    terminal_state, observations, tool_results = service.run(
        asset="SUI",
        tool_specs=[_ticker_tool_spec()],
        initial_context={"trace_id": trace_id, "asset": "SUI"},
    )

    trace = trace_runtime.finalize_trace(trace_id=trace_id)

    assert terminal_state["evidence_status"] == "insufficient"
    assert observations == []
    assert tool_results == []
    assert trace["status"] == "partial_failure"
    assert any(span["kind"] == "llm" and span["status"] == "degraded" for span in trace["spans"])
    assert any(span["kind"] == "llm" and span.get("attributes", {}).get("degraded_reason") for span in trace["spans"])


def test_run_stops_after_repeated_identical_tool_calls_with_insufficient_status() -> None:
    trace_id = "trace-react-repeat"
    service, trace_runtime, _ = _build_service(
        [
            '{"decision_summary":"Call the same tool twice.","action":"search_web","args":{"query":"SUI catalysts"},"termination":false,"termination_reason":null}',
            '{"decision_summary":"Repeat the same call.","action":"search_web","args":{"query":"SUI catalysts"},"termination":false,"termination_reason":null}',
            '{"decision_summary":"Still repeating.","action":"search_web","args":{"query":"SUI catalysts"},"termination":false,"termination_reason":null}',
        ],
        max_rounds=3,
        max_same_call_repeats=1,
    )

    terminal_state, observations, tool_results = service.run(
        asset="SUI",
        tool_specs=[_search_tool_spec()],
        initial_context={"trace_id": trace_id, "asset": "SUI"},
    )

    trace = trace_runtime.finalize_trace(trace_id=trace_id)

    assert terminal_state["evidence_status"] == "insufficient"
    assert len(observations) >= 2
    assert len(tool_results) >= 2
    assert terminal_state["status"] == "insufficient"
    assert terminal_state["termination_reason"]
    assert trace["status"] == "partial_failure"


def test_run_stops_when_tool_failures_exceed_the_threshold() -> None:
    trace_id = "trace-react-tool-failures"
    failing_runtime = _build_tool_runtime(
        get_ticker_handler=lambda args, trace_context=None: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    service, trace_runtime, _ = _build_service(
        [
            '{"decision_summary":"Try the same failing call again.","action":"get_ticker","args":{"symbol":"SUI","market_type":"spot"},"termination":false,"termination_reason":null}',
            '{"decision_summary":"Retry the same failing call.","action":"get_ticker","args":{"symbol":"SUI","market_type":"spot"},"termination":false,"termination_reason":null}',
        ],
        tool_runtime=failing_runtime,
        max_rounds=2,
        max_tool_failures=1,
    )

    terminal_state, observations, tool_results = service.run(
        asset="SUI",
        tool_specs=[_ticker_tool_spec()],
        initial_context={"trace_id": trace_id, "asset": "SUI"},
    )

    trace = trace_runtime.finalize_trace(trace_id=trace_id)

    assert terminal_state["status"] == "failed"
    assert terminal_state["evidence_status"] == "failed"
    assert len(tool_results) >= 1
    assert trace["status"] == "failed"
    assert trace["tool_usage_summary"]["failed_calls"] >= 1
    assert all(span["status"] == "failed" for span in trace["spans"] if span["kind"] == "tool")
    assert observations == []


def test_run_forces_terminal_insufficient_evidence_even_when_termination_is_true() -> None:
    trace_id = "trace-react-insufficient"
    service, trace_runtime, _ = _build_service(
        [
            '{"decision_summary":"Stop once evidence is thin.","action":"search_web","args":{"query":"SUI catalysts"},"termination":true,"termination_reason":"enough for now"}'
        ],
        max_rounds=1,
    )

    terminal_state, observations, tool_results = service.run(
        asset="SUI",
        tool_specs=[_search_tool_spec()],
        initial_context={"trace_id": trace_id, "asset": "SUI"},
    )

    trace = trace_runtime.finalize_trace(trace_id=trace_id)

    assert terminal_state["evidence_status"] == "insufficient"
    assert observations == []
    assert tool_results == []
    assert trace["status"] == "partial_failure"


def _fetch_tool_spec() -> ToolSpec:
    return {
        "name": "fetch_page",
        "server": "research",
        "domain": "research",
        "description": "Fetch and normalize a page.",
        "usage_guidance": "Use when a source should be inspected directly.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        "output_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        "executor_ref": "research.fetch_page",
        "source_type": "local",
        "audit_level": "basic",
        "replay_mode": "view_only",
    }


def test_run_does_not_treat_preloaded_market_context_as_market_side_evidence() -> None:
    trace_id = "trace-react-preloaded-context"
    tool_runtime = ToolRuntime(
        tool_specs=[_search_tool_spec(), _fetch_tool_spec()],
        tool_executors={
            "research.search_web": lambda args, trace_context=None: {
                "results": [{"title": "SUI roadmap", "url": "https://example.com/sui", "snippet": "Catalyst and risk"}]
            },
            "research.fetch_page": lambda args, trace_context=None: {
                "url": args["url"],
                "title": "SUI roadmap",
                "text": "Catalyst, roadmap, ecosystem growth, and execution risk.",
            },
        },
    )
    service, trace_runtime, _ = _build_service(
        [
            '{"decision_summary":"Search for sources.","action":"search_web","args":{"query":"SUI catalysts"},"termination":false,"termination_reason":null}',
            '{"decision_summary":"Fetch the source.","action":"fetch_page","args":{"url":"https://example.com/sui"},"termination":false,"termination_reason":null}',
            '{"decision_summary":"Stop after one page.","action":null,"args":{},"termination":true,"termination_reason":"enough for now"}',
        ],
        tool_runtime=tool_runtime,
        max_rounds=3,
    )

    terminal_state, observations, tool_results = service.run(
        asset="SUI",
        tool_specs=[_search_tool_spec(), _fetch_tool_spec()],
        initial_context={
            "trace_id": trace_id,
            "asset": "SUI",
            "market_context": {"market_cap": 1_000_000_000},
            "protocol_context": {"tvl": 500_000_000},
        },
    )

    trace = trace_runtime.finalize_trace(trace_id=trace_id)

    assert len(observations) == 2
    assert len(tool_results) == 2
    assert terminal_state["status"] == "insufficient"
    assert terminal_state["evidence_status"] == "insufficient"
    assert "Market-side evidence is missing." in terminal_state["missing_information"]
    assert trace["status"] == "partial_failure"


def test_run_counts_only_new_evidence_as_progress() -> None:
    trace_id = "trace-react-no-progress"
    repeated_runtime = _build_tool_runtime(
        search_web_handler=lambda args, trace_context=None: {
            "results": [{"title": "same source", "url": "https://example.com/same", "snippet": "same snippet"}]
        }
    )
    service, _, _ = _build_service(
        [
            '{"decision_summary":"Search first variant.","action":"search_web","args":{"query":"SUI catalysts"},"termination":false,"termination_reason":null}',
            '{"decision_summary":"Search a different phrasing.","action":"search_web","args":{"query":"SUI roadmap"},"termination":false,"termination_reason":null}',
        ],
        tool_runtime=repeated_runtime,
        max_rounds=2,
        max_no_progress_rounds=1,
    )

    terminal_state, observations, tool_results = service.run(
        asset="SUI",
        tool_specs=[_search_tool_spec()],
        initial_context={"trace_id": trace_id, "asset": "SUI"},
    )

    assert len(observations) == 2
    assert len(tool_results) == 2
    assert terminal_state["status"] == "insufficient"
    assert terminal_state["termination_reason"] == "no_progress_threshold_reached"
