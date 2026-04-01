import json
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from app.agents.kline_result_assembler import KlineResultAssembler
from app.agents.tools.kline_runtime_tools import build_kline_tool_executors, build_kline_tool_specs
from app.agents.tools.kline_tools import KlineToolbox
from app.agents.tools.market_tools import MarketToolbox, build_market_tool_executors, build_market_tool_specs
from app.runtime.react_loop_service import ReActLoopService
from app.runtime.tool_runtime import ToolRuntime
from app.runtime.trace_runtime import TraceRuntime
from app.schemas.kline import Candle, MarketDataPayload
from app.services.react_llm_service import FallbackReActLLMClient, OpenAICompatibleReActLLMClient
from app.services.kline_analysis_service import KlineAnalysisService
from app.services.market_data_service import MarketDataService

if TYPE_CHECKING:
    from app.clients.mcp_registry import MCPToolCall, MCPToolRegistry


class KlineAgent:
    name = "KlineAgent"

    def __init__(
        self,
        memory_root: Path,
        market_data_service: MarketDataService | None = None,
        llm_client: Any | None = None,
        mcp_registry: "MCPToolRegistry | None" = None,
    ) -> None:
        self.memory_root = memory_root
        self.assets_root = memory_root / "assets"
        self.assets_root.mkdir(parents=True, exist_ok=True)
        self.market_data_service = market_data_service or MarketDataService()
        self.analysis_service = KlineAnalysisService()
        self.mcp_registry = mcp_registry
        self.market_toolbox = MarketToolbox(market_data_service=self.market_data_service)
        self.kline_toolbox = KlineToolbox(self.market_data_service)
        self.result_assembler = KlineResultAssembler(self.analysis_service)
        self.llm_client = self._resolve_llm_client(llm_client)

    def execute(self, skill: str, payload: dict) -> dict:
        if skill != "kline_scorecard":
            raise ValueError(f"Unsupported kline skill: {skill}")

        asset = payload["asset"].upper()
        previous_memory = self._read_previous_memory(asset)
        focus = payload.get("focus", [])
        horizon = payload.get("horizon")
        requested_market_type = payload.get("market_type", "spot")
        timeframes = payload.get("timeframes") or ["1d"]
        trace_id = f"kline-{asset.lower()}"
        self.market_toolbox = MarketToolbox(market_data_service=self.market_data_service)
        self.kline_toolbox = KlineToolbox(self.market_data_service)
        candle_cache: dict[str, MarketDataPayload] = {}
        market_executors = build_market_tool_executors(self.market_toolbox)
        tool_specs = [
            spec
            for spec in build_market_tool_specs()
            if spec["name"] in {"get_klines", "get_ticker"}
        ] + build_kline_tool_specs()

        def get_klines(args: dict[str, Any], trace_context: dict[str, Any] | None = None) -> dict:
            result = market_executors["market.get_klines"](args, trace_context=trace_context)
            output = result.get("output") or {}
            if output:
                candle_cache[str(output.get("timeframe"))] = MarketDataPayload.model_validate(output)
            return result

        tool_runtime = ToolRuntime(
            tool_specs=tool_specs,
            tool_executors={
                "market.get_klines": get_klines,
                "market.get_ticker": market_executors["market.get_ticker"],
                **build_kline_tool_executors(self.kline_toolbox, candle_cache),
            },
        )
        trace_runtime = TraceRuntime()
        loop_service = ReActLoopService(
            llm_client=self.llm_client,
            tool_runtime=tool_runtime,
            trace_runtime=trace_runtime,
            observation_builder=self._build_observation,
            missing_information_builder=self._derive_missing_information,
            evidence_sufficiency_checker=self._is_evidence_sufficient,
            agent_name=self.name,
        )
        terminal_state, observations, tool_results = loop_service.run(
            asset=asset,
            tool_specs=tool_specs,
            initial_context={
                "trace_id": trace_id,
                "asset": asset,
                "horizon": horizon,
                "focus": focus,
                "timeframes": timeframes,
                "market_type": requested_market_type,
                "asset_memory": previous_memory,
            },
        )
        market_type = self._resolve_market_type(requested_market_type, candle_cache)
        result = self.result_assembler.assemble(
            asset=asset,
            requested_timeframes=timeframes,
            focus=focus,
            horizon=horizon,
            market_type=market_type,
            previous_memory=previous_memory,
            terminal_state=terminal_state,
            tool_results=tool_results,
            candle_cache=candle_cache,
        )
        result["trace_summary"] = trace_runtime.finalize_trace(
            trace_id=trace_id,
            summary={"status": result.get("status", terminal_state.get("status", "insufficient"))},
        )
        self._write_asset_files(asset, result)
        return result

    def _resolve_llm_client(self, llm_client: Any | None) -> Any:
        heuristic = HeuristicKlineLLMClient()
        if llm_client is None:
            remote = OpenAICompatibleReActLLMClient()
            return FallbackReActLLMClient(remote, heuristic) if remote.is_configured() else heuristic
        if isinstance(llm_client, (HeuristicKlineLLMClient, FallbackReActLLMClient)):
            return llm_client
        return FallbackReActLLMClient(llm_client, heuristic)

    def _resolve_market_type(self, requested_market_type: str, candle_cache: dict[str, MarketDataPayload]) -> str:
        for payload in candle_cache.values():
            if payload.market_type:
                return payload.market_type
        return requested_market_type

    def _build_observation(self, result: dict[str, Any]) -> dict[str, Any] | None:
        tool_name = result.get("tool_name")
        output_summary = result.get("output_summary") or {}
        if tool_name == "compute_indicators":
            timeframe = output_summary.get("timeframe")
            status = output_summary.get("status")
            return {
                "tool_name": tool_name,
                "status": result.get("status"),
                "summary": f"Computed indicators for {timeframe}.",
                "structured_data": {
                    "findings": [f"{timeframe}_indicator_status={status}"] if timeframe else [],
                    "timeframes": [timeframe] if timeframe else [],
                    "source_urls": [],
                    "risks": [],
                    "catalysts": [],
                },
                "output_summary": output_summary,
                "error": result.get("error"),
            }
        if tool_name == "get_klines":
            timeframe = output_summary.get("timeframe")
            candle_count = output_summary.get("candle_count")
            return {
                "tool_name": tool_name,
                "status": result.get("status"),
                "summary": f"Loaded {candle_count} candles for {timeframe}.",
                "structured_data": {
                    "findings": [f"{timeframe}_candles={candle_count}"] if timeframe else [],
                    "timeframes": [timeframe] if timeframe else [],
                    "source_urls": [],
                    "risks": [],
                    "catalysts": [],
                },
                "output_summary": output_summary,
                "error": result.get("error"),
            }
        return None

    def _derive_missing_information(self, *, context: dict[str, Any], observations: list[dict[str, Any]]) -> list[str]:
        requested = [str(item) for item in (context.get("timeframes") or ["1d"])]
        loaded = {
            str((observation.get("output_summary") or {}).get("timeframe"))
            for observation in observations
            if observation.get("tool_name") == "get_klines" and observation.get("status") in {"success", "degraded"}
        }
        indicators = {
            str((observation.get("output_summary") or {}).get("timeframe"))
            for observation in observations
            if observation.get("tool_name") == "compute_indicators" and observation.get("status") in {"success", "degraded"}
        }
        missing: list[str] = []
        for timeframe in requested:
            if timeframe not in loaded:
                missing.append(f"Market data unavailable for {timeframe}.")
            if timeframe in loaded and timeframe not in indicators:
                missing.append(f"Indicator coverage missing for {timeframe}.")
        return missing

    def _is_evidence_sufficient(self, *, context: dict[str, Any], observations: list[dict[str, Any]]) -> bool:
        return not self._derive_missing_information(context=context, observations=observations)

    def _adapt_registry_result(
        self,
        call: "MCPToolCall",
        asset: str,
        timeframe: str,
        market_type: str,
    ) -> MarketDataPayload:
        if call.error or not call.output:
            return MarketDataPayload(
                symbol=asset,
                timeframe=timeframe,
                market_type=market_type,
                source="unavailable",
                candles=[],
                endpoint_summary=None,
                ticker_summary=None,
                degraded_reason=call.error or "mcp_call_failed",
            )
        raw = call.output
        resolved_market_type = raw.get("market_type") or market_type
        raw_candles = raw.get("candles") or []
        candles = [
            Candle(
                symbol=asset,
                timeframe=timeframe,
                open_time=int(item[0]),
                open=float(item[1]),
                high=float(item[2]),
                low=float(item[3]),
                close=float(item[4]),
                volume=float(item[5]),
            )
            for item in raw_candles
        ]
        return MarketDataPayload(
            symbol=asset,
            timeframe=timeframe,
            market_type=resolved_market_type,
            source="binance" if candles else "unavailable",
            candles=candles,
            endpoint_summary=None,
            ticker_summary=None,
        )

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


class HeuristicKlineLLMClient:
    provider = "heuristic-kline-llm"
    model = "heuristic-kline-llm"
    temperature = 0.0

    def complete(self, *args, **kwargs) -> SimpleNamespace:
        messages = kwargs.get("messages") or []
        payload: dict[str, Any] = {}
        if messages:
            content = messages[-1].get("content")
            if isinstance(content, str):
                try:
                    payload = json.loads(content)
                except json.JSONDecodeError:
                    payload = {}
        asset = str(payload.get("asset") or "UNKNOWN").upper()
        context = payload.get("context") or {}
        tool_results = payload.get("tool_results") or []
        requested_timeframes = [str(item) for item in (context.get("timeframes") or ["1d"])]
        market_type = str(context.get("market_type") or "spot")
        loaded = {
            str((item.get("output_summary") or {}).get("timeframe"))
            for item in tool_results
            if item.get("tool_name") == "get_klines"
        }
        indicators = {
            str((item.get("output_summary") or {}).get("timeframe"))
            for item in tool_results
            if item.get("tool_name") == "compute_indicators"
        }
        next_timeframe = next((timeframe for timeframe in requested_timeframes if timeframe not in loaded), None)
        next_indicator = next((timeframe for timeframe in requested_timeframes if timeframe not in indicators), None)

        if next_timeframe is not None:
            content = {
                "decision_summary": f"Load {next_timeframe} candles before drawing conclusions.",
                "action": "get_klines",
                "args": {"symbol": asset, "timeframe": next_timeframe, "market_type": market_type},
                "termination": False,
                "termination_reason": None,
            }
        elif next_indicator is not None:
            content = {
                "decision_summary": f"Compute indicators for {next_indicator}.",
                "action": "compute_indicators",
                "args": {"timeframe": next_indicator},
                "termination": False,
                "termination_reason": None,
            }
        else:
            content = {
                "decision_summary": "Stop because each requested timeframe has enough technical context.",
                "action": None,
                "args": {},
                "termination": True,
                "termination_reason": "All requested timeframes have been processed.",
            }
        raw = json.dumps(content, ensure_ascii=False)
        return SimpleNamespace(
            content=raw,
            text=raw,
            message=SimpleNamespace(content=raw),
            choices=[SimpleNamespace(message=SimpleNamespace(content=raw))],
            model=self.model,
            provider=self.provider,
            temperature=self.temperature,
            usage=SimpleNamespace(prompt_tokens=18, completion_tokens=16, total_tokens=34),
        )
