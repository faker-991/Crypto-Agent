import json
from pathlib import Path

from app.agents.tools.kline_tools import KlineToolbox
from app.schemas.kline import MarketDataPayload
from app.services.kline_analysis_service import KlineAnalysisService
from app.services.market_data_service import MarketDataService


class KlineAgent:
    name = "KlineAgent"

    def __init__(self, memory_root: Path) -> None:
        self.memory_root = memory_root
        self.assets_root = memory_root / "assets"
        self.assets_root.mkdir(parents=True, exist_ok=True)
        self.market_data_service = MarketDataService()
        self.analysis_service = KlineAnalysisService()

    def execute(self, skill: str, payload: dict) -> dict:
        if skill != "kline_scorecard":
            raise ValueError(f"Unsupported kline skill: {skill}")

        asset = payload["asset"].upper()
        previous_memory = self._read_previous_memory(asset)
        focus = payload.get("focus", [])
        horizon = payload.get("horizon")
        requested_market_type = payload.get("market_type", "spot")
        timeframes = payload.get("timeframes") or ["1d"]
        toolbox = KlineToolbox(self.market_data_service)

        analyses: dict[str, dict] = {}
        indicator_snapshots: dict[str, dict] = {}
        provenance: dict[str, dict] = {}
        canonical_market_type: str | None = None
        tool_calls: list[dict] = []
        missing_information: list[str] = []

        for timeframe in timeframes:
            kline_payload = toolbox.get_klines(
                symbol=asset,
                timeframe=timeframe,
                market_type=requested_market_type,
            )
            canonical_market_type = canonical_market_type or kline_payload.market_type
            analyses[timeframe] = self.analysis_service.analyze_timeframe(kline_payload).model_dump()
            indicator_snapshots[timeframe] = toolbox.compute_indicators(list(kline_payload.candles))
            provenance[timeframe] = self._summarize_payload(kline_payload)
            tool_calls.append(
                {
                    "round": 1,
                    "tool": "get_klines",
                    "timeframe": timeframe,
                    "input": {"asset": asset, "market_type": requested_market_type},
                    "output": {
                        "source": kline_payload.source,
                        "market_type": kline_payload.market_type,
                        "candles": len(kline_payload.candles),
                    },
                }
            )
            tool_calls.append(
                {
                    "round": 2,
                    "tool": "compute_indicators",
                    "timeframe": timeframe,
                    "input": {"candles": len(kline_payload.candles)},
                    "output": {
                        "status": indicator_snapshots[timeframe]["status"],
                        "missing_indicators": indicator_snapshots[timeframe]["missing_indicators"],
                    },
                }
            )
            if kline_payload.source != "binance" or not kline_payload.candles:
                missing_information.append(f"Market data unavailable for {timeframe}.")
            if indicator_snapshots[timeframe]["status"] != "success":
                missing_information.append(
                    f"Indicator coverage incomplete for {timeframe}: "
                    + ", ".join(indicator_snapshots[timeframe]["missing_indicators"])
                )

        market_type = canonical_market_type or requested_market_type
        evidence_sufficient = not missing_information
        result = {
            "agent": self.name,
            "status": "success" if evidence_sufficient else "insufficient",
            "asset": asset,
            "focus": focus,
            "horizon": horizon,
            "market_type": market_type,
            "timeframes": timeframes,
            "analyses": analyses,
            "indicator_snapshots": indicator_snapshots,
            "kline_provenance": provenance,
            "summary": self._build_summary(asset, market_type, analyses),
            "market_summary": self._build_market_summary(asset, market_type, timeframes, analyses),
            "previous_memory": previous_memory,
            "evidence_sufficient": evidence_sufficient,
            "missing_information": missing_information,
            "tool_calls": tool_calls,
            "rounds_used": 2,
        }
        self._write_asset_files(asset, result)
        return result

    def _build_summary(self, asset: str, market_type: str, analyses: dict[str, dict]) -> str:
        if not analyses:
            return f"{asset} {market_type} market summary is unavailable."

        parts: list[str] = []
        for timeframe, analysis in analyses.items():
            conclusion = analysis.get("conclusion") or "analysis unavailable."
            parts.append(f"{timeframe}: {conclusion}")
        joined = " ".join(parts)
        return f"{asset} {market_type} market view. {joined}".strip()

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

    def _summarize_payload(self, payload: MarketDataPayload) -> dict:
        endpoint_summary = payload.endpoint_summary.model_dump() if payload.endpoint_summary else None
        return {
            "market_type": payload.market_type,
            "source": payload.source,
            "endpoint_summary": endpoint_summary,
            "degraded_reason": payload.degraded_reason,
        }

    def _read_previous_memory(self, asset: str) -> dict:
        path = self.assets_root / f"{asset}.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _build_memory_payload(self, asset: str, result: dict) -> dict:
        previous = dict(result["previous_memory"])
        return {
            **previous,
            "symbol": asset,
            "market_type": result.get("market_type"),
            "technical_view": result["analyses"],
            "kline_analysis": {
                "focus": result.get("focus"),
                "horizon": result.get("horizon"),
                "timeframes": sorted(result["analyses"].keys()),
                "market_type": result.get("market_type"),
                "provenance": result["kline_provenance"],
            },
        }

    def _write_asset_files(self, asset: str, result: dict) -> None:
        md_path = self.assets_root / f"{asset}.md"
        json_path = self.assets_root / f"{asset}.json"
        md_path.write_text(
            f"# {asset} Technical View\n\n"
            + "\n\n".join(
                [
                    f"## {timeframe}\n"
                    f"- Trend: {analysis['trend_regime']}\n"
                    f"- Support: {', '.join(str(level) for level in analysis['support_levels'])}\n"
                    f"- Resistance: {', '.join(str(level) for level in analysis['resistance_levels'])}\n"
                    f"- Conclusion: {analysis['conclusion']}"
                    for timeframe, analysis in result["analyses"].items()
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        json_path.write_text(
            json.dumps(self._build_memory_payload(asset, result), indent=2) + "\n",
            encoding="utf-8",
        )
