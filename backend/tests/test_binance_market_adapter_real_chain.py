import httpx

from app.clients.binance_market_adapter import BinanceMarketAdapter
from app.services.binance_skill_registry import BinanceSkillRegistry


class StubTransport(httpx.BaseTransport):
    def __init__(self, payload: object, record: list[httpx.Request] | None = None) -> None:
        self.payload = payload
        self.record = record

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self.record is not None:
            self.record.append(request)
        return httpx.Response(200, json=self.payload)


def test_builds_spot_klines_request_metadata() -> None:
    adapter = BinanceMarketAdapter(registry=BinanceSkillRegistry(skill_roots=[]))
    request = adapter.build_kline_request(
        symbol="BTCUSDT",
        timeframe="1d",
        market_type="spot",
        limit=50,
    )

    assert request.base_url == "https://api.binance.com"
    assert request.endpoint == "/api/v3/klines"
    assert request.params == {"symbol": "BTCUSDT", "interval": "1d", "limit": 50}
    assert request.metadata["integration"] == "binance"
    assert request.metadata["endpoint"] == "klines"
    assert request.metadata["market_type"] == "spot"
    assert request.metadata["url"] == "https://api.binance.com/api/v3/klines"
    assert request.metadata["method"] == "GET"


def test_builds_spot_klines_request_normalizes_base_asset_to_usdt_pair() -> None:
    adapter = BinanceMarketAdapter(registry=BinanceSkillRegistry(skill_roots=[]))

    request = adapter.build_kline_request(
        symbol="BTC",
        timeframe="1d",
        market_type="spot",
        limit=50,
    )

    assert request.params["symbol"] == "BTCUSDT"


def test_builds_futures_klines_request_metadata() -> None:
    adapter = BinanceMarketAdapter(registry=BinanceSkillRegistry(skill_roots=[]))
    request = adapter.build_kline_request(
        symbol="BTCUSDT",
        timeframe="1h",
        market_type="futures",
        limit=20,
    )

    assert request.base_url == "https://fapi.binance.com"
    assert request.endpoint == "/fapi/v1/klines"
    assert request.params["symbol"] == "BTCUSDT"
    assert request.params["interval"] == "1h"
    assert request.params["limit"] == 20
    assert request.metadata["market_type"] == "derivatives-trading-usds-futures"
    assert request.metadata["url"] == "https://fapi.binance.com/fapi/v1/klines"


def test_parses_ticker_response_extracts_values() -> None:
    adapter = BinanceMarketAdapter(registry=BinanceSkillRegistry(skill_roots=[]))
    payload = {
        "symbol": "BTCUSDT",
        "lastPrice": "12750.33",
        "openPrice": "12852.91",
        "highPrice": "12958.89",
        "lowPrice": "12723.43",
        "priceChange": "-102.58",
        "priceChangePercent": "-0.797",
        "volume": "3010.201",
        "quoteVolume": "38703054.93",
        "bidPrice": "12750.32",
        "askPrice": "12750.33",
    }

    summary = adapter.parse_ticker_response(payload)

    assert summary["symbol"] == "BTCUSDT"
    assert summary["last_price"] == 12750.33
    assert summary["open_price"] == 12852.91
    assert summary["high_price"] == 12958.89
    assert summary["low_price"] == 12723.43
    assert summary["price_change"] == -102.58
    assert summary["price_change_percent"] == -0.797
    assert summary["volume"] == 3010.201
    assert summary["quote_volume"] == 38703054.93
    assert summary["bid_price"] == 12750.32
    assert summary["ask_price"] == 12750.33


def test_parses_ticker_response_handles_malformed_numbers() -> None:
    adapter = BinanceMarketAdapter(registry=BinanceSkillRegistry(skill_roots=[]))
    payload = {
        "symbol": "BTCUSDT",
        "lastPrice": "N/A",
        "openPrice": "",
        "highPrice": None,
        "lowPrice": "invalid",
        "priceChange": "-abc",
        "priceChangePercent": "N/A",
        "volume": "N/A",
        "quoteVolume": "N/A",
        "bidPrice": "N/A",
        "askPrice": "N/A",
    }

    summary = adapter.parse_ticker_response(payload)

    assert summary["symbol"] == "BTCUSDT"
    assert summary["last_price"] is None
    assert summary["open_price"] is None
    assert summary["high_price"] is None
    assert summary["low_price"] is None
    assert summary["price_change"] is None
    assert summary["price_change_percent"] is None
    assert summary["volume"] is None
    assert summary["quote_volume"] is None
    assert summary["bid_price"] is None
    assert summary["ask_price"] is None


def test_fetch_spot_ticker_returns_summary_and_metadata() -> None:
    payload = {
        "symbol": "BTCUSDT",
        "lastPrice": "12750.33",
        "openPrice": "12852.91",
        "highPrice": "12958.89",
        "lowPrice": "12723.43",
        "priceChange": "-102.58",
        "priceChangePercent": "-0.797",
        "volume": "3010.201",
        "quoteVolume": "38703054.93",
        "bidPrice": "12750.32",
        "askPrice": "12750.33",
    }
    captured: list[httpx.Request] = []
    transport = StubTransport(payload=payload, record=captured)
    adapter = BinanceMarketAdapter(
        registry=BinanceSkillRegistry(skill_roots=[]),
        client=httpx.Client(transport=transport, base_url="https://api.binance.com"),
    )

    result = adapter.fetch_spot_ticker("BTCUSDT")

    assert result["ticker"]["symbol"] == "BTCUSDT"
    assert result["metadata"]["url"] == "https://api.binance.com/api/v3/ticker/24hr"
    assert result["metadata"]["market_type"] == "spot"
    assert captured[0].url.path == "/api/v3/ticker/24hr"


def test_fetch_futures_ticker_uses_fallback_endpoint() -> None:
    payload = {
        "symbol": "BTCUSDT",
        "lastPrice": "12750.33",
    }
    captured: list[httpx.Request] = []
    transport = StubTransport(payload=payload, record=captured)
    adapter = BinanceMarketAdapter(
        registry=BinanceSkillRegistry(skill_roots=[]),
        client=httpx.Client(transport=transport, base_url="https://fapi.binance.com"),
    )

    result = adapter.fetch_futures_ticker("BTCUSDT")

    assert result["metadata"]["url"] == "https://fapi.binance.com/fapi/v1/ticker/24hr"
    assert result["metadata"]["market_type"] == "derivatives-trading-usds-futures"
    assert captured[0].url.path == "/fapi/v1/ticker/24hr"
