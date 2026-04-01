from __future__ import annotations

import pytest

from app.clients.mcp_registry import MCPToolRegistry
from app.runtime.tool_runtime import ToolResult, ToolRuntime, ToolSpec


@pytest.fixture
def local_tool_spec() -> ToolSpec:
    return {
        "name": "uppercase_text",
        "server": "local",
        "domain": "research",
        "description": "Uppercase a short text snippet.",
        "usage_guidance": "Use for tiny string normalization checks.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "output_schema": {
            "type": "object",
            "properties": {"echo": {"type": "string"}},
            "required": ["echo"],
        },
        "executor_ref": "local.uppercase_text",
        "source_type": "local",
        "audit_level": "basic",
        "replay_mode": "view_only",
    }


@pytest.fixture
def mcp_tool_spec() -> ToolSpec:
    return {
        "name": "search_web",
        "server": "research",
        "domain": "research",
        "description": "Search a remote research endpoint.",
        "usage_guidance": "Use for remote search lookups.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "output_schema": {
            "type": "object",
            "properties": {"echo": {"type": "string"}},
            "required": ["echo"],
        },
        "executor_ref": "research.search_web",
        "source_type": "mcp",
        "audit_level": "basic",
        "replay_mode": "view_only",
    }


@pytest.fixture
def local_executor_calls() -> dict[str, int]:
    return {"count": 0}


@pytest.fixture
def local_executor(local_executor_calls: dict[str, int]):
    def _execute(args: dict, trace_context: dict | None = None) -> dict:
        local_executor_calls["count"] += 1
        return {"echo": str(args["text"]).upper()}

    return _execute


@pytest.fixture
def mcp_registry() -> MCPToolRegistry:
    registry = MCPToolRegistry()
    registry.register(
        name="research",
        description="Research tools",
        tools=[
            {
                "name": "search_web",
                "description": "Search a remote research endpoint.",
            }
        ],
        handler=lambda tool, args: {"echo": str(args["text"]).upper()},
    )
    return registry


@pytest.fixture
def tool_runtime(
    local_tool_spec: ToolSpec,
    mcp_tool_spec: ToolSpec,
    local_executor,
    mcp_registry: MCPToolRegistry,
) -> ToolRuntime:
    return ToolRuntime(
        tool_specs=[local_tool_spec, mcp_tool_spec],
        tool_executors={"local.uppercase_text": local_executor},
        mcp_registry=mcp_registry,
    )


def test_tool_runtime_execute_returns_normalized_result_on_success(tool_runtime: ToolRuntime) -> None:
    result: ToolResult = tool_runtime.execute(
        tool_name="uppercase_text",
        args={"text": "hello"},
        trace_context={"trace_id": "trace-tool-1"},
    )

    assert set(result) == {
        "status",
        "tool_name",
        "server",
        "domain",
        "args",
        "output",
        "output_summary",
        "error",
        "reason",
        "exception_type",
        "degraded",
        "metrics",
    }
    assert result["status"] == "success"
    assert result["tool_name"] == "uppercase_text"
    assert result["args"] == {"text": "hello"}
    assert result["output"] == {"echo": "HELLO"}
    assert result["output_summary"] == {"echo": "HELLO"}
    assert result["error"] is None
    assert result["reason"] is None
    assert result["exception_type"] is None
    assert result["degraded"] is False
    assert result["metrics"]["input_bytes"] >= 0
    assert result["metrics"]["output_bytes"] >= 0


def test_unknown_tool_name_returns_failed_with_unknown_tool_reason(tool_runtime: ToolRuntime) -> None:
    result: ToolResult = tool_runtime.execute(
        tool_name="missing_tool",
        args={"text": "hello"},
        trace_context={"trace_id": "trace-tool-unknown"},
    )

    assert result["status"] == "failed"
    assert result["reason"] == "unknown_tool"
    assert result["degraded"] is False
    assert result["output"] == {}
    assert result["output_summary"] == {}


def test_schema_invalid_args_do_not_execute_underlying_tool_and_return_degraded(
    tool_runtime: ToolRuntime,
    local_executor_calls: dict[str, int],
) -> None:
    result: ToolResult = tool_runtime.execute(
        tool_name="uppercase_text",
        args={"text": 123},
        trace_context={"trace_id": "trace-tool-invalid-args"},
    )

    assert local_executor_calls["count"] == 0
    assert result["status"] == "degraded"
    assert result["reason"] == "schema_invalid_args"
    assert result["error"] == "args_failed_validation"
    assert result["output"] == {}
    assert result["output_summary"] == {}
    assert result["metrics"] == {"input_bytes": 0, "output_bytes": 0}
    assert result["degraded"] is True


def test_local_and_mcp_backed_tools_share_the_same_top_level_keys(
    tool_runtime: ToolRuntime,
) -> None:
    local_result: ToolResult = tool_runtime.execute(
        tool_name="uppercase_text",
        args={"text": "hello"},
        trace_context={"trace_id": "trace-tool-local"},
    )
    mcp_result: ToolResult = tool_runtime.execute(
        tool_name="search_web",
        args={"text": "hello"},
        trace_context={"trace_id": "trace-tool-mcp"},
    )

    expected_keys = {
        "status",
        "tool_name",
        "server",
        "domain",
        "args",
        "output",
        "output_summary",
        "error",
        "reason",
        "exception_type",
        "degraded",
        "metrics",
    }

    assert set(local_result) == expected_keys
    assert set(mcp_result) == expected_keys
    assert set(local_result) == set(mcp_result)


def test_contract_shaped_result_with_non_dict_output_preserves_signal(tool_runtime: ToolRuntime) -> None:
    tool_runtime._tool_executors["local.uppercase_text"] = (  # type: ignore[attr-defined]
        lambda args, trace_context=None: {
            "status": "success",
            "output": "HELLO",
            "output_summary": "HELLO",
        }
    )

    result = tool_runtime.execute(
        tool_name="uppercase_text",
        args={"text": "hello"},
        trace_context={"trace_id": "trace-tool-invalid-contract"},
    )

    assert result["status"] == "failed"
    assert result["reason"] == "invalid_tool_result"
    assert result["error"] == "tool_result_output_must_be_object"
    assert result["output"] == {"result": "HELLO"}
    assert result["output_summary"] == {"result": "HELLO"}
