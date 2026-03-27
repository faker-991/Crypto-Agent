from app.api.research import read_kline_analysis
from app.schemas.kline import Candle, KlineResearchRequest, MarketDataPayload
from app.services.market_data_service import MarketDataService


def test_kline_research_returns_analysis_for_requested_timeframes() -> None:
    service = MarketDataService()

    response = read_kline_analysis(
        KlineResearchRequest(symbol="BTCUSDT", timeframes=["1d", "1w"]),
        market_data_service=service,
    )

    assert response.symbol == "BTCUSDT"
    assert set(response.analyses.keys()) == {"1d", "1w"}
    one_day = response.analyses["1d"]
    assert one_day.trend_regime in {"uptrend", "range", "downtrend", "unavailable"}
    assert isinstance(one_day.candles, list)
    assert isinstance(one_day.support_levels, list)
    assert isinstance(one_day.resistance_levels, list)


class StubMarketDataService:
    def get_klines(self, symbol: str, timeframe: str, market_type: str) -> MarketDataPayload:
        return MarketDataPayload(
            symbol=symbol.upper(),
            timeframe=timeframe,
            market_type="derivatives-trading-usds-futures" if market_type == "futures" else "spot",
            source="binance",
            candles=[
                Candle(
                    symbol=symbol.upper(),
                    timeframe=timeframe,
                    open_time=1710000000000,
                    open=100.0,
                    high=110.0,
                    low=95.0,
                    close=108.0,
                    volume=1500.0,
                )
            ],
            endpoint_summary={
                "integration": "binance",
                "endpoint": "klines",
                "market_type": "derivatives-trading-usds-futures" if market_type == "futures" else "spot",
                "url": "https://example.com",
                "method": "GET",
            },
            ticker_summary={
                "symbol": symbol.upper(),
                "last_price": 108.0,
                "price_change_percent": 5.0,
                "volume": 1500.0,
            },
            degraded_reason=None,
        )


class UnavailableMarketDataService:
    def get_klines(self, symbol: str, timeframe: str, market_type: str) -> MarketDataPayload:
        resolved_market = "derivatives-trading-usds-futures" if market_type == "futures" else "spot"
        return MarketDataPayload(
            symbol=symbol.upper(),
            timeframe=timeframe,
            market_type=resolved_market,
            source="unavailable",
            candles=[],
            endpoint_summary={
                "integration": "binance",
                "endpoint": "klines",
                "market_type": resolved_market,
                "url": "https://example.com",
                "method": "GET",
            },
            ticker_summary=None,
            degraded_reason="klines fetch failed: timeout",
        )


def test_kline_research_returns_market_metadata_by_timeframe() -> None:
    response = read_kline_analysis(
        KlineResearchRequest(symbol="BTCUSDT", timeframes=["4h", "1d"], market_type="futures"),
        market_data_service=StubMarketDataService(),
    )

    assert response.market_type == "futures"
    assert set(response.market_data.keys()) == {"4h", "1d"}
    four_hour = response.market_data["4h"]
    assert four_hour.source == "binance"
    assert four_hour.market_type == "derivatives-trading-usds-futures"
    assert four_hour.endpoint_summary.endpoint == "klines"
    assert four_hour.ticker_summary is not None
    assert four_hour.ticker_summary.last_price == 108.0


def test_kline_research_returns_empty_candles_and_degraded_reason() -> None:
    response = read_kline_analysis(
        KlineResearchRequest(symbol="BTCUSDT", timeframes=["1d"], market_type="spot"),
        market_data_service=UnavailableMarketDataService(),
    )

    payload = response.model_dump()
    assert response.market_data["1d"].source == "unavailable"
    assert response.analyses["1d"].candles == []
    assert response.market_data["1d"].degraded_reason == "klines fetch failed: timeout"
    assert set(payload["market_data"]["1d"].keys()) == {
        "market_type",
        "source",
        "endpoint_summary",
        "ticker_summary",
        "degraded_reason",
    }
    assert payload["market_data"]["1d"]["endpoint_summary"]["endpoint"] == "klines"


def test_kline_research_returns_unavailable_futures_state() -> None:
    response = read_kline_analysis(
        KlineResearchRequest(symbol="BTCUSDT", timeframes=["4h"], market_type="futures"),
        market_data_service=UnavailableMarketDataService(),
    )

    assert response.market_data["4h"].source == "unavailable"
    assert response.market_data["4h"].market_type == "derivatives-trading-usds-futures"
    assert response.analyses["4h"].candles == []
