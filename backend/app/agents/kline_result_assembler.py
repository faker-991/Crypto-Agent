from __future__ import annotations

from typing import Any

from app.schemas.kline import Candle, MarketDataPayload
from app.services.kline_analysis_service import KlineAnalysisService


class KlineResultAssembler:
    def __init__(self, analysis_service: KlineAnalysisService | None = None) -> None:
        self.analysis_service = analysis_service or KlineAnalysisService()

    def assemble(
        self,
        *,
        asset: str,
        requested_timeframes: list[str],
        focus: list[str],
        horizon: str | None,
        market_type: str,
        previous_memory: dict,
        terminal_state: dict[str, Any],
        tool_results: list[dict[str, Any]],
        candle_cache: dict[str, MarketDataPayload],
    ) -> dict[str, Any]:
        analyses: dict[str, dict] = {}
        indicator_snapshots: dict[str, dict] = {}
        provenance: dict[str, dict] = {}
        missing_information = list(terminal_state.get("missing_information") or [])

        for timeframe in requested_timeframes:
            payload = candle_cache.get(timeframe)
            if payload is None:
                payload = MarketDataPayload(
                    symbol=asset,
                    timeframe=timeframe,
                    market_type=market_type,
                    source="unavailable",
                    candles=[],
                    endpoint_summary=None,
                    ticker_summary=None,
                    degraded_reason="klines_not_loaded",
                )
            analyses[timeframe] = self.analysis_service.analyze_timeframe(payload).model_dump()
            provenance[timeframe] = {
                "market_type": payload.market_type,
                "source": payload.source,
                "endpoint_summary": payload.endpoint_summary.model_dump() if payload.endpoint_summary else None,
                "degraded_reason": payload.degraded_reason,
            }
            indicator_result = next(
                (
                    result
                    for result in tool_results
                    if result.get("tool_name") == "compute_indicators"
                    and (result.get("output_summary") or {}).get("timeframe") == timeframe
                ),
                None,
            )
            if indicator_result is not None:
                indicator_snapshots[timeframe] = indicator_result.get("output") or {}
            else:
                indicator_snapshots[timeframe] = {
                    "timeframe": timeframe,
                    "status": "failed",
                    "indicator_values": {},
                    "missing_indicators": [],
                    "summary": "Indicators were not computed for this timeframe.",
                }
                missing_information.append(f"Indicator coverage missing for {timeframe}.")
            if payload.source != "binance" or not payload.candles:
                missing_information.append(f"Market data unavailable for {timeframe}.")

        final_missing = list(dict.fromkeys(item for item in missing_information if item))
        evidence_sufficient = not final_missing
        tool_calls = [self._to_tool_call(result) for result in tool_results]

        return {
            "agent": "KlineAgent",
            "status": "success" if evidence_sufficient else "insufficient",
            "evidence_status": "sufficient" if evidence_sufficient else "insufficient",
            "asset": asset,
            "focus": focus,
            "horizon": horizon,
            "market_type": market_type,
            "timeframes": requested_timeframes,
            "analyses": analyses,
            "indicator_snapshots": indicator_snapshots,
            "kline_provenance": provenance,
            "summary": self._build_summary(asset, market_type, analyses),
            "market_summary": self._build_market_summary(asset, market_type, requested_timeframes, analyses),
            "previous_memory": previous_memory,
            "evidence_sufficient": evidence_sufficient,
            "missing_information": final_missing,
            "tool_calls": tool_calls,
            "rounds_used": terminal_state.get("rounds_used", len(tool_calls)),
            "agent_loop": terminal_state.get("agent_loop", []),
            "termination_reason": terminal_state.get("termination_reason"),
        }

    def _to_tool_call(self, result: dict[str, Any]) -> dict[str, Any]:
        output_summary = result.get("output_summary") or {}
        return {
            "round": result.get("round"),
            "tool": result.get("tool_name"),
            "tool_name": result.get("tool_name"),
            "status": result.get("status"),
            "server": result.get("server"),
            "domain": result.get("domain"),
            "input": result.get("args"),
            "args": result.get("args"),
            "output": result.get("output"),
            "output_summary": output_summary,
            "reason": result.get("reason"),
            "error": result.get("error"),
            "degraded": result.get("degraded"),
            "metrics": result.get("metrics"),
            "timeframe": output_summary.get("timeframe") or (result.get("args") or {}).get("timeframe"),
        }

    def _build_summary(self, asset: str, market_type: str, analyses: dict[str, dict]) -> str:
        if not analyses:
            return f"{asset} {market_type} market summary is unavailable."
        parts: list[str] = []
        for timeframe, analysis in analyses.items():
            conclusion = analysis.get("conclusion") or "analysis unavailable."
            parts.append(f"{timeframe}: {conclusion}")
        return f"{asset} {market_type} market view. {' '.join(parts)}".strip()

    def _build_market_summary(
        self,
        asset: str,
        market_type: str,
        timeframes: list[str],
        analyses: dict[str, dict],
    ) -> dict:
        parts: list[str] = []
        for timeframe in timeframes:
            analysis = analyses.get(timeframe) or {}
            conclusion = analysis.get("conclusion")
            if isinstance(conclusion, str) and conclusion.strip():
                parts.append(f"{timeframe}: {conclusion.strip()}")
        return {
            "asset": asset,
            "market_type": market_type,
            "timeframes": timeframes,
            "analysis_summary": " ".join(parts).strip(),
        }
