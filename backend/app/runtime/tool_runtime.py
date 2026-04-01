from __future__ import annotations

import json
from typing import Any, Callable

from app.clients.mcp_registry import MCPToolRegistry
from app.runtime.tool_contracts import ToolResult, ToolSpec


class ToolRuntime:
    def __init__(
        self,
        *,
        tool_specs: list[ToolSpec],
        tool_executors: dict[str, Callable[[dict[str, Any], dict[str, Any] | None], Any]] | None = None,
        mcp_registry: MCPToolRegistry | None = None,
    ) -> None:
        self._tool_specs = {spec["name"]: spec for spec in tool_specs}
        self._tool_executors = tool_executors or {}
        self._mcp_registry = mcp_registry

    def execute(
        self,
        *,
        tool_name: str,
        args: dict[str, Any],
        trace_context: dict[str, Any] | None = None,
    ) -> ToolResult:
        spec = self._tool_specs.get(tool_name)
        if spec is None:
            return self._result(
                status="failed",
                tool_name=tool_name,
                server="unknown",
                domain="unknown",
                args=args,
                output={},
                output_summary={},
                error="unknown_tool",
                reason="unknown_tool",
                exception_type=None,
                degraded=False,
                input_bytes=0,
                output_bytes=0,
            )

        if not self._validate_args(spec.get("input_schema") or {}, args):
            return self._result(
                status="degraded",
                tool_name=tool_name,
                server=spec.get("server", "unknown"),
                domain=spec.get("domain", "unknown"),
                args=args,
                output={},
                output_summary={},
                error="args_failed_validation",
                reason="schema_invalid_args",
                exception_type=None,
                degraded=True,
                input_bytes=0,
                output_bytes=0,
            )

        input_bytes = self._json_size(args)
        try:
            raw_result = self._dispatch(spec, args, trace_context=trace_context)
        except Exception as exc:
            return self._result(
                status="failed",
                tool_name=tool_name,
                server=spec.get("server", "unknown"),
                domain=spec.get("domain", "unknown"),
                args=args,
                output={},
                output_summary={},
                error=str(exc),
                reason="tool_execution_failed",
                exception_type=exc.__class__.__name__,
                degraded=False,
                input_bytes=input_bytes,
                output_bytes=0,
            )

        normalized = self._normalize_output(raw_result)
        return self._result(
            status=normalized["status"],
            tool_name=tool_name,
            server=spec.get("server", "unknown"),
            domain=spec.get("domain", "unknown"),
            args=args,
            output=normalized["output"],
            output_summary=normalized["output_summary"],
            error=normalized["error"],
            reason=normalized["reason"],
            exception_type=normalized["exception_type"],
            degraded=normalized["degraded"],
            input_bytes=input_bytes,
            output_bytes=self._json_size(normalized["output"]),
        )

    def _dispatch(
        self,
        spec: ToolSpec,
        args: dict[str, Any],
        *,
        trace_context: dict[str, Any] | None,
    ) -> Any:
        if spec.get("source_type") == "mcp":
            if self._mcp_registry is None:
                raise RuntimeError("mcp_registry_not_configured")
            call = self._mcp_registry.call_tool(spec.get("server", ""), spec["name"], args)
            if call.error:
                raise RuntimeError(call.error)
            return call.output

        executor_ref = spec.get("executor_ref")
        executor = self._tool_executors.get(executor_ref or "")
        if executor is None:
            raise KeyError(f"Unknown tool executor: {executor_ref!r}")
        return executor(args, trace_context=trace_context)

    def _normalize_output(self, raw_result: Any) -> dict[str, Any]:
        if isinstance(raw_result, dict) and raw_result.get("status") in {"success", "failed", "degraded"}:
            output = raw_result.get("output")
            if not isinstance(output, dict):
                preserved_output = {"result": output}
                return {
                    "status": "failed",
                    "output": preserved_output,
                    "output_summary": preserved_output,
                    "error": "tool_result_output_must_be_object",
                    "reason": "invalid_tool_result",
                    "exception_type": None,
                    "degraded": False,
                }
            output_summary = raw_result.get("output_summary")
            if not isinstance(output_summary, dict):
                output_summary = output
            status = raw_result["status"]
            return {
                "status": status,
                "output": output,
                "output_summary": output_summary,
                "error": raw_result.get("error"),
                "reason": raw_result.get("reason"),
                "exception_type": raw_result.get("exception_type"),
                "degraded": bool(raw_result.get("degraded")) or status == "degraded",
            }

        output = raw_result if isinstance(raw_result, dict) else {"result": raw_result}
        return {
            "status": "success",
            "output": output,
            "output_summary": output,
            "error": None,
            "reason": None,
            "exception_type": None,
            "degraded": False,
        }

    def _validate_args(self, schema: dict[str, Any], args: Any) -> bool:
        if schema.get("type") != "object" or not isinstance(args, dict):
            return False

        properties = schema.get("properties") or {}
        required = schema.get("required") or []
        for field in required:
            if field not in args:
                return False

        for key, value in args.items():
            prop = properties.get(key)
            if not isinstance(prop, dict):
                return False
            if not self._matches_type(prop.get("type"), value):
                return False
        return True

    def _matches_type(self, expected_type: str | None, value: Any) -> bool:
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "number":
            return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "object":
            return isinstance(value, dict)
        if expected_type == "array":
            return isinstance(value, list)
        return True

    def _result(
        self,
        *,
        status: str,
        tool_name: str,
        server: str,
        domain: str,
        args: dict[str, Any],
        output: dict[str, Any],
        output_summary: dict[str, Any],
        error: str | None,
        reason: str | None,
        exception_type: str | None,
        degraded: bool,
        input_bytes: int,
        output_bytes: int,
    ) -> ToolResult:
        return {
            "status": status,
            "tool_name": tool_name,
            "server": server,
            "domain": domain,
            "args": args,
            "output": output,
            "output_summary": output_summary,
            "error": error,
            "reason": reason,
            "exception_type": exception_type,
            "degraded": degraded,
            "metrics": {
                "input_bytes": input_bytes,
                "output_bytes": output_bytes,
            },
        }

    def _json_size(self, value: Any) -> int:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
