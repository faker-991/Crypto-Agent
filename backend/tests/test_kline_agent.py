import json
from pathlib import Path

from app.agents.kline_agent import KlineAgent
from app.schemas.kline import Candle, EndpointSummary, MarketDataPayload


class FakeMarketDataService:
    def __init__(self, payloads: dict[str, MarketDataPayload]) -> None:
        self.payloads = payloads
        self.calls: list[dict[str, str]] = []

    def get_klines(self, symbol: str, timeframe: str, market_type: str) -> MarketDataPayload:
        self.calls.append({"symbol": symbol, "timeframe": timeframe, "market_type": market_type})
        return self.payloads[timeframe]


def _build_payload(
    timeframe: str,
    market_type: str = "spot",
    degraded_reason: str | None = None,
    source: str = "binance",
    candles: list[Candle] | None = None,
) -> MarketDataPayload:
    endpoint_summary = EndpointSummary(
        integration="binance",
        endpoint="klines",
        market_type=market_type,
        url="https://api.binance.com/klines",
        method="GET",
    )
    generated_candles = [
        Candle(
            symbol="BTC",
            timeframe=timeframe,
            open_time=index + 1,
            open=100.0 + index,
            high=104.0 + index,
            low=98.0 + index,
            close=102.0 + index,
            volume=1_000.0 + (index * 10),
        )
        for index in range(40)
    ]
    return MarketDataPayload(
        symbol="BTC",
        timeframe=timeframe,
        market_type=market_type,
        source=source,
        candles=generated_candles if candles is None else candles,
        endpoint_summary=endpoint_summary,
        ticker_summary=None,
        degraded_reason=degraded_reason,
    )


def test_kline_scorecard_writes_asset_files(tmp_path: Path) -> None:
    agent = KlineAgent(memory_root=tmp_path)
    agent.market_data_service = FakeMarketDataService(
        {
            "1d": _build_payload("1d"),
            "1w": _build_payload("1w"),
        }
    )

    result = agent.execute(
        skill="kline_scorecard",
        payload={
            "asset": "BTC",
            "timeframes": ["1d", "1w"],
            "focus": ["trend", "support_resistance"],
            "horizon": "mid_long_term",
        },
    )

    assert result["asset"] == "BTC"
    assert set(result["analyses"].keys()) == {"1d", "1w"}
    assert isinstance(result["summary"], str)
    assert result["status"] == "success"
    assert result["evidence_sufficient"] is True
    assert result["rounds_used"] == 2
    assert len(result["tool_calls"]) == 4
    assert result["tool_calls"][0]["tool"] == "get_klines"
    assert result["tool_calls"][1]["tool"] == "compute_indicators"
    assert "BTC" in result["summary"]
    assert "1d" in result["summary"]
    assert "1w" in result["summary"]
    assert (tmp_path / "assets" / "BTC.md").exists()
    assert (tmp_path / "assets" / "BTC.json").exists()

    metadata = json.loads((tmp_path / "assets" / "BTC.json").read_text(encoding="utf-8"))
    assert metadata["symbol"] == "BTC"
    assert metadata["kline_analysis"]["market_type"] == "spot"


def test_kline_scorecard_preserves_provenance_metadata(tmp_path: Path) -> None:
    agent = KlineAgent(memory_root=tmp_path)
    agent.market_data_service = FakeMarketDataService({"1d": _build_payload("1d")})

    result = agent.execute(
        skill="kline_scorecard",
        payload={"asset": "BTC", "timeframes": ["1d"]},
    )

    provenance = result["kline_provenance"]["1d"]
    assert provenance["source"] == "binance"
    assert provenance["endpoint_summary"]["integration"] == "binance"
    assert provenance["endpoint_summary"]["endpoint"] == "klines"
    assert provenance["degraded_reason"] is None


def test_kline_scorecard_builds_market_summary_for_execution_context(tmp_path: Path) -> None:
    agent = KlineAgent(memory_root=tmp_path)
    agent.market_data_service = FakeMarketDataService(
        {
            "1d": _build_payload("1d"),
            "1w": _build_payload("1w"),
        }
    )

    result = agent.execute(
        skill="kline_scorecard",
        payload={"asset": "BTC", "timeframes": ["1d", "1w"], "market_type": "spot"},
    )

    market_summary = result["market_summary"]

    assert market_summary["asset"] == "BTC"
    assert market_summary["market_type"] == "spot"
    assert market_summary["timeframes"] == ["1d", "1w"]
    assert isinstance(market_summary["analysis_summary"], str)
    assert "1d" in market_summary["analysis_summary"]
    assert "1w" in market_summary["analysis_summary"]
    assert set(result["indicator_snapshots"].keys()) == {"1d", "1w"}
    assert result["indicator_snapshots"]["1d"]["status"] == "success"


def test_kline_scorecard_can_request_futures(tmp_path: Path) -> None:
    agent = KlineAgent(memory_root=tmp_path)
    fake_service = FakeMarketDataService(
        {
            "1w": _build_payload(
                "1w",
                market_type="derivatives-trading-usds-futures",
                degraded_reason="fallback",
            )
        }
    )
    agent.market_data_service = fake_service

    result = agent.execute(
        skill="kline_scorecard",
        payload={"asset": "BTC", "timeframes": ["1w"], "market_type": "futures"},
    )

    assert fake_service.calls
    assert fake_service.calls[0]["market_type"] == "futures"
    assert result["market_type"] == "derivatives-trading-usds-futures"
    assert result["kline_provenance"]["1w"]["market_type"] == "derivatives-trading-usds-futures"
    assert result["kline_provenance"]["1w"]["degraded_reason"] == "fallback"


def test_kline_scorecard_returns_degraded_safe_analysis_when_candles_are_empty(tmp_path: Path) -> None:
    agent = KlineAgent(memory_root=tmp_path)
    agent.market_data_service = FakeMarketDataService(
        {"1d": _build_payload("1d", source="unavailable", candles=[], degraded_reason="klines fetch failed")}
    )

    result = agent.execute(
        skill="kline_scorecard",
        payload={"asset": "BTC", "timeframes": ["1d"], "market_type": "spot"},
    )

    assert result["analyses"]["1d"]["candles"] == []
    assert result["status"] == "insufficient"
    assert result["evidence_sufficient"] is False
    assert "market data" in result["missing_information"][0].lower()
    assert "unavailable" in result["analyses"]["1d"]["conclusion"].lower()
    assert result["kline_provenance"]["1d"]["degraded_reason"] == "klines fetch failed"


def test_kline_scorecard_returns_degraded_safe_futures_analysis_when_candles_are_empty(tmp_path: Path) -> None:
    agent = KlineAgent(memory_root=tmp_path)
    agent.market_data_service = FakeMarketDataService(
        {
            "4h": _build_payload(
                "4h",
                market_type="derivatives-trading-usds-futures",
                source="unavailable",
                candles=[],
                degraded_reason="klines fetch failed",
            )
        }
    )

    result = agent.execute(
        skill="kline_scorecard",
        payload={"asset": "BTC", "timeframes": ["4h"], "market_type": "futures"},
    )

    assert result["market_type"] == "derivatives-trading-usds-futures"
    assert result["analyses"]["4h"]["candles"] == []
    assert result["status"] == "insufficient"
    assert result["evidence_sufficient"] is False
    assert "unavailable" in result["analyses"]["4h"]["conclusion"].lower()


def test_kline_scorecard_keeps_existing_memory_fields(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "ETH.md").write_text("# ETH\n\nExisting thesis", encoding="utf-8")
    (assets_dir / "ETH.json").write_text(
        json.dumps({"symbol": "ETH", "summary": "Existing thesis"}), encoding="utf-8"
    )

    agent = KlineAgent(memory_root=tmp_path)
    agent.market_data_service = FakeMarketDataService({"1d": _build_payload("1d")})

    result = agent.execute(
        skill="kline_scorecard",
        payload={"asset": "ETH", "timeframes": ["1d"], "focus": ["trend"], "horizon": "mid_long_term"},
    )

    metadata = json.loads((assets_dir / "ETH.json").read_text(encoding="utf-8"))
    assert metadata["summary"] == "Existing thesis"
    assert metadata["kline_analysis"]["focus"] == ["trend"]
    assert metadata["kline_analysis"]["provenance"]["1d"]["source"] == "binance"
    assert result["previous_memory"]["symbol"] == "ETH"
