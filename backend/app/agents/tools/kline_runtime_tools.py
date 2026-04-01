from __future__ import annotations

from typing import Any

from app.agents.tools.kline_tools import KlineToolbox
from app.runtime.tool_contracts import ToolSpec


def build_kline_tool_specs() -> list[ToolSpec]:
    return [
        {
            "name": "compute_indicators",
            "server": "kline",
            "domain": "kline",
            "description": "Compute technical indicators for a previously fetched timeframe.",
            "usage_guidance": "Use after get_klines when indicator context is needed for technical analysis.",
            "input_schema": {
                "type": "object",
                "properties": {"timeframe": {"type": "string"}},
                "required": ["timeframe"],
            },
            "output_schema": {"type": "object", "properties": {}, "required": []},
            "executor_ref": "kline.compute_indicators",
            "source_type": "local",
            "audit_level": "basic",
            "replay_mode": "view_only",
        }
    ]


def build_kline_tool_executors(
    toolbox: KlineToolbox,
    candle_cache: dict[str, Any],
) -> dict[str, Any]:
    def compute_indicators(args: dict[str, Any], trace_context: dict[str, Any] | None = None) -> dict:
        timeframe = str(args["timeframe"])
        payload = candle_cache.get(timeframe)
        if payload is None:
            return {
                "status": "failed",
                "output": {},
                "output_summary": {"timeframe": timeframe},
                "error": "klines_not_loaded",
                "reason": "klines_not_loaded",
                "exception_type": None,
                "degraded": False,
            }
        snapshot = toolbox.compute_indicators(list(payload.candles))
        return {
            "status": "degraded" if snapshot.get("status") != "success" else "success",
            "output": {"timeframe": timeframe, **snapshot},
            "output_summary": {
                "timeframe": timeframe,
                "status": snapshot.get("status"),
                "missing_indicators": snapshot.get("missing_indicators", []),
            },
            "error": snapshot.get("summary") if snapshot.get("status") != "success" else None,
            "reason": "indicator_coverage_incomplete" if snapshot.get("status") != "success" else None,
            "exception_type": None,
            "degraded": snapshot.get("status") != "success",
        }

    return {"kline.compute_indicators": compute_indicators}
