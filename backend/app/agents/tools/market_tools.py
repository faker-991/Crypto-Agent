from __future__ import annotations

from typing import Any

from app.agents.tools.kline_tools import KlineToolbox
from app.runtime.tool_contracts import ToolSpec
from app.services.external_research_service import ExternalResearchService
from app.services.market_data_service import MarketDataService


class MarketToolbox:
    def __init__(
        self,
        *,
        external_research_service: ExternalResearchService | None = None,
        market_data_service: MarketDataService | None = None,
    ) -> None:
        self.external_research_service = external_research_service or ExternalResearchService()
        self.market_data_service = market_data_service or MarketDataService()
        self.kline_toolbox = KlineToolbox(self.market_data_service)

    def get_market_snapshot(self, asset: str) -> dict | None:
        return self.external_research_service.get_asset_context(asset.upper()).get("market")

    def get_protocol_snapshot(self, asset: str) -> dict | None:
        return self.external_research_service.get_asset_context(asset.upper()).get("protocol")

    def get_ticker(self, symbol: str, market_type: str) -> dict:
        ticker = self.kline_toolbox.get_ticker(symbol=symbol, market_type=market_type)
        return ticker.model_dump() if ticker is not None else {}

    def get_klines(self, symbol: str, timeframe: str, market_type: str) -> dict:
        payload = self.market_data_service.get_klines(symbol=symbol, timeframe=timeframe, market_type=market_type)
        return payload.model_dump()


def build_market_tool_specs() -> list[ToolSpec]:
    return [
        {
            "name": "get_market_snapshot",
            "server": "market",
            "domain": "market",
            "description": "Fetch a market-context snapshot for an asset.",
            "usage_guidance": "Use when a market-cap, FDV, or liquidity anchor is missing.",
            "input_schema": {
                "type": "object",
                "properties": {"asset": {"type": "string"}},
                "required": ["asset"],
            },
            "output_schema": {"type": "object", "properties": {}, "required": []},
            "executor_ref": "market.get_market_snapshot",
            "source_type": "local",
            "audit_level": "basic",
            "replay_mode": "view_only",
        },
        {
            "name": "get_protocol_snapshot",
            "server": "market",
            "domain": "market",
            "description": "Fetch a protocol-context snapshot for an asset.",
            "usage_guidance": "Use when TVL, chains, or category context is missing.",
            "input_schema": {
                "type": "object",
                "properties": {"asset": {"type": "string"}},
                "required": ["asset"],
            },
            "output_schema": {"type": "object", "properties": {}, "required": []},
            "executor_ref": "market.get_protocol_snapshot",
            "source_type": "local",
            "audit_level": "basic",
            "replay_mode": "view_only",
        },
        {
            "name": "get_ticker",
            "server": "binance",
            "domain": "market",
            "description": "Fetch a compact ticker snapshot from Binance.",
            "usage_guidance": "Use when current price and volume anchors are needed.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "market_type": {"type": "string"},
                },
                "required": ["symbol", "market_type"],
            },
            "output_schema": {"type": "object", "properties": {}, "required": []},
            "executor_ref": "market.get_ticker",
            "source_type": "local",
            "audit_level": "basic",
            "replay_mode": "view_only",
        },
        {
            "name": "get_klines",
            "server": "binance",
            "domain": "market",
            "description": "Fetch candles from Binance.",
            "usage_guidance": "Use when the research loop needs market structure or trend context.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "timeframe": {"type": "string"},
                    "market_type": {"type": "string"},
                },
                "required": ["symbol", "timeframe", "market_type"],
            },
            "output_schema": {"type": "object", "properties": {}, "required": []},
            "executor_ref": "market.get_klines",
            "source_type": "local",
            "audit_level": "basic",
            "replay_mode": "view_only",
        },
    ]


def build_market_tool_executors(toolbox: MarketToolbox) -> dict[str, Any]:
    def get_market_snapshot(args: dict[str, Any], trace_context: dict[str, Any] | None = None) -> dict:
        snapshot = toolbox.get_market_snapshot(args["asset"])
        if snapshot is None:
            return {
                "status": "failed",
                "output": {},
                "output_summary": {},
                "error": "market_snapshot_unavailable",
                "reason": "market_snapshot_unavailable",
                "exception_type": None,
                "degraded": False,
            }
        return {
            "status": "success",
            "output": snapshot,
            "output_summary": snapshot,
            "error": None,
            "reason": None,
            "exception_type": None,
            "degraded": False,
        }

    def get_protocol_snapshot(args: dict[str, Any], trace_context: dict[str, Any] | None = None) -> dict:
        snapshot = toolbox.get_protocol_snapshot(args["asset"])
        if snapshot is None:
            return {
                "status": "failed",
                "output": {},
                "output_summary": {},
                "error": "protocol_snapshot_unavailable",
                "reason": "protocol_snapshot_unavailable",
                "exception_type": None,
                "degraded": False,
            }
        return {
            "status": "success",
            "output": snapshot,
            "output_summary": snapshot,
            "error": None,
            "reason": None,
            "exception_type": None,
            "degraded": False,
        }

    def get_ticker(args: dict[str, Any], trace_context: dict[str, Any] | None = None) -> dict:
        output = toolbox.get_ticker(args["symbol"], args["market_type"])
        if not output:
            return {
                "status": "failed",
                "output": {},
                "output_summary": {},
                "error": "ticker_unavailable",
                "reason": "ticker_unavailable",
                "exception_type": None,
                "degraded": False,
            }
        return {
            "status": "success",
            "output": output,
            "output_summary": output,
            "error": None,
            "reason": None,
            "exception_type": None,
            "degraded": False,
        }

    def get_klines(args: dict[str, Any], trace_context: dict[str, Any] | None = None) -> dict:
        output = toolbox.get_klines(args["symbol"], args["timeframe"], args["market_type"])
        degraded = bool(output.get("degraded_reason"))
        return {
            "status": "degraded" if degraded else "success",
            "output": output,
            "output_summary": {
                "symbol": output.get("symbol"),
                "timeframe": output.get("timeframe"),
                "market_type": output.get("market_type"),
                "source": output.get("source"),
                "candle_count": len(output.get("candles") or []),
            },
            "error": output.get("degraded_reason"),
            "reason": "market_data_degraded" if degraded else None,
            "exception_type": None,
            "degraded": degraded,
        }

    return {
        "market.get_market_snapshot": get_market_snapshot,
        "market.get_protocol_snapshot": get_protocol_snapshot,
        "market.get_ticker": get_ticker,
        "market.get_klines": get_klines,
    }
