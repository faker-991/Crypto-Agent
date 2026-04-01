from pathlib import Path
from typing import TypedDict

from app.orchestrator.orchestrator_service import OrchestratorService
from app.schemas.kline import Candle, EndpointSummary, MarketDataPayload
from pydantic import TypeAdapter


class FakeMarketDataService:
    def __init__(self, payloads: dict[str, MarketDataPayload]) -> None:
        self.payloads = payloads

    def get_klines(self, symbol: str, timeframe: str, market_type: str) -> MarketDataPayload:
        return self.payloads[timeframe]


class StubStructuredResearchAgent:
    name = "ResearchAgent"

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def execute(self, skill: str, payload: dict) -> dict:
        self.calls.append((skill, payload))
        return {
            "agent": self.name,
            "status": "success",
            "evidence_status": "sufficient",
            "summary": f"{payload['asset']} research summary",
            "findings": ["4h trend remains constructive."],
            "risks": ["macro regime shift"],
            "catalysts": ["roadmap update"],
            "missing_information": [],
            "degraded_reason": None,
            "termination_reason": "Evidence threshold met.",
            "rounds_used": 2,
            "tool_calls": [
                {
                    "status": "success",
                    "tool_name": "search_web",
                    "server": "research",
                    "domain": "research",
                    "args": {"query": f"{payload['asset']} catalysts"},
                    "output": {"results": [{"title": f"{payload['asset']} roadmap"}]},
                    "output_summary": {"results": [{"title": f"{payload['asset']} roadmap"}]},
                    "error": None,
                    "reason": None,
                    "exception_type": None,
                    "degraded": False,
                    "metrics": {"input_bytes": 11, "output_bytes": 42},
                }
            ],
        }


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


class ResearchAgentResult(TypedDict):
    agent: str
    status: str
    evidence_status: str
    summary: str
    findings: list[str]
    risks: list[str]
    catalysts: list[str]
    missing_information: list[str]
    degraded_reason: str | None
    termination_reason: str | None
    rounds_used: int
    tool_calls: list[dict]


def _build_payload(timeframe: str) -> MarketDataPayload:
    return MarketDataPayload(
        symbol="BTC",
        timeframe=timeframe,
        market_type="spot",
        source="binance",
        candles=[
            Candle(
                symbol="BTC",
                timeframe=timeframe,
                open_time=index + 1,
                open=100.0 + index,
                high=104.0 + index,
                low=98.0 + index,
                close=102.0 + index,
                volume=1000.0 + (index * 10),
            )
            for index in range(40)
        ],
        endpoint_summary=EndpointSummary(
            integration="binance",
            endpoint="klines",
            market_type="spot",
            url="https://api.binance.com/api/v3/klines",
            method="GET",
        ),
        ticker_summary=None,
        degraded_reason=None,
    )


def test_orchestrator_service_returns_clarify_without_task_execution(tmp_path: Path) -> None:
    service = OrchestratorService(memory_root=tmp_path)

    result = service.execute("看下 4h")

    assert result["status"] == "clarify"
    assert result["plan"]["needs_clarification"] is True
    assert result["task_results"] == []
    assert result["final_answer"] == "你想分析哪个资产？"
    assert any(event["name"] == "planner.clarify" for event in result["events"])


def test_orchestrator_service_returns_plan_task_results_and_final_answer(tmp_path: Path) -> None:
    service = OrchestratorService(memory_root=tmp_path)

    result = service.execute("分析 SUI 值不值得继续拿，顺便看下周线和4h走势")

    assert result["status"] == "execute"
    assert result["plan"]["mode"] == "multi_task"
    assert [task["task_type"] for task in result["plan"]["tasks"]] == ["research", "kline", "summary"]
    assert [item["task_type"] for item in result["task_results"]] == ["research", "kline", "summary"]
    assert result["final_answer"]
    assert result["trace_path"] is not None
    event_names = [event["name"] for event in result["events"]]
    assert "planner.plan_created" in event_names
    assert "executor.task_started" in event_names
    assert "summary.completed" in event_names


def test_orchestrator_service_propagates_research_evidence_status_into_task_results_and_execution_summary(
    tmp_path: Path,
) -> None:
    service = OrchestratorService(memory_root=tmp_path)
    service.executor.research_agent = StubStructuredResearchAgent()

    result = service.execute("分析 SUI 值不值得继续拿，顺便看下周线和4h走势")

    research_task = next(item for item in result["task_results"] if item["task_type"] == "research")
    validated = TypeAdapter(ResearchAgentResult).validate_python(research_task["payload"])
    assert research_task["summary"] == "SUI research summary"
    assert research_task["rounds_used"] == 2
    assert research_task["evidence_sufficient"] is True
    assert research_task["evidence_status"] == "sufficient"
    assert research_task["termination_reason"] == "Evidence threshold met."
    assert research_task["missing_information"] == []
    assert len(research_task["tool_calls"]) >= 1
    assert len(validated["tool_calls"]) >= 1
    assert_tool_result_like(research_task["tool_calls"][0])
    assert_tool_result_like(validated["tool_calls"][0])
    assert result["execution_summary"]["evidence_status"] == "sufficient"
    assert result["execution_summary"]["missing_information"] == []
    assert result["execution_summary"]["rounds_used"] == 2
    assert result["execution_summary"]["termination_reason"] == "Evidence threshold met."
    execution_research = next(
        item for item in result["execution_summary"]["task_results"] if item["task_type"] == "research"
    )
    assert execution_research["findings"] == ["4h trend remains constructive."]
    assert execution_research["risks"] == ["macro regime shift"]
    assert execution_research["catalysts"] == ["roadmap update"]
    assert execution_research["tool_calls"][0]["tool_name"] == "search_web"


def test_orchestrator_service_exposes_single_kline_execution_summary(tmp_path: Path) -> None:
    service = OrchestratorService(memory_root=tmp_path)
    service.executor.kline_agent.market_data_service = FakeMarketDataService(
        {
            "1d": _build_payload("1d"),
            "1w": _build_payload("1w"),
        }
    )

    result = service.execute("帮我看下 BTC 日线和周线走势")

    assert result["status"] == "execute"
    assert [item["task_type"] for item in result["task_results"]] == ["kline", "summary"]
    assert result["task_results"][0]["summary"]
    assert result["task_results"][1]["task_type"] == "summary"
    assert result["execution_summary"]["asset"] == "BTC"
    assert result["execution_summary"]["summary"]
    assert set(result["execution_summary"]["analysis_timeframes"]) == {"1d", "1w"}
    assert result["execution_summary"]["market_summary"]["asset"] == "BTC"
    assert set(result["execution_summary"]["market_summary"]["timeframes"]) == {"1d", "1w"}
    assert result["execution_summary"]["provenance"]["source"] == "binance"
    assert result["execution_summary"]["agent_sufficiency"]["KlineAgent"] is True


def test_orchestrator_service_keeps_explicit_query_asset_even_with_stale_session_state(tmp_path: Path) -> None:
    service = OrchestratorService(memory_root=tmp_path)
    service.session_state_service.write_state(
        {
            "current_asset": "ETH",
            "last_intent": "kline_analysis",
            "last_timeframes": ["1d"],
            "last_report_type": None,
            "recent_assets": ["ETH"],
            "current_task": "ETH spot market view",
            "last_skill": None,
            "last_agent": "KlineAgent",
        }
    )
    service.executor.kline_agent.market_data_service = FakeMarketDataService({"1d": _build_payload("1d")})

    result = service.execute("我想看 BTC 现在是否适合入手现货")

    assert result["status"] == "execute"
    assert result["execution_summary"]["asset"] == "BTC"
    assert result["task_results"][0]["payload"]["asset"] == "BTC"


def test_orchestrator_service_exposes_planner_fallback_reason_in_execution_summary(tmp_path: Path) -> None:
    service = OrchestratorService(memory_root=tmp_path)

    result = service.execute("帮我看下 BTC 小时线、15m 和 30m")

    assert result["plan"]["planner_source"] == "fallback"
    assert result["execution_summary"]["planner_source"] == "fallback"
    assert result["execution_summary"]["planner_fallback_reason"] == "llm_returned_none"
