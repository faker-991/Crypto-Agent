import httpx
from types import SimpleNamespace

from app.schemas.kline import MarketDataPayload

from app.clients.binance_market_adapter import BinanceMarketAdapter
from app.services.binance_skill_registry import BinanceSkillRegistry
from app.services.market_data_service import MarketDataService


class StubTransport(httpx.BaseTransport):
    def __init__(self, payload: list[list[str]], record: list[httpx.Request] | None = None) -> None:
        self.payload = payload
        self.record = record

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self.record is not None:
            self.record.append(request)
        return httpx.Response(200, json=self.payload)


class MarketTypeSpyAdapter:
    def __init__(self) -> None:
        self.klines_calls: list[str] = []
        self.ticker_calls: list[str] = []
        self.placeholder_calls = 0
        self.registry = SimpleNamespace(resolve_market_key=self._resolve_market_key)

    def _resolve_market_key(self, market_type: str) -> str:
        if market_type == "futures":
            return "derivatives-trading-usds-futures"
        return market_type

    def _build_request_metadata(self, endpoint: str, market_type: str) -> dict[str, str]:
        return {
            "integration": "binance",
            "endpoint": endpoint,
            "market_type": market_type,
            "url": f"https://api.binance.com/{market_type}/{endpoint}",
            "method": "GET",
        }

    def build_kline_request(self, symbol: str, timeframe: str, market_type: str, limit: int) -> SimpleNamespace:
        return SimpleNamespace(metadata=self._build_request_metadata("klines", market_type))

    def fetch_spot_klines(self, symbol: str, timeframe: str, limit: int) -> list[tuple[int, float, float, float, float, float]]:
        self.klines_calls.append("spot")
        return [(1, 10.0, 12.0, 9.5, 11.2, 100.0)]

    def fetch_futures_klines(self, symbol: str, timeframe: str, limit: int) -> list[tuple[int, float, float, float, float, float]]:
        self.klines_calls.append("futures")
        return [(2, 20.0, 23.0, 19.0, 22.5, 200.0)]

    def fetch_spot_ticker(self, symbol: str) -> dict[str, dict[str, float]]:
        self.ticker_calls.append("spot")
        return {
            "ticker": {
                "symbol": symbol,
                "last_price": 100.0,
                "open_price": 90.0,
                "high_price": 110.0,
                "low_price": 89.0,
                "price_change": 5.0,
                "price_change_percent": 5.0,
                "volume": 1000.0,
                "quote_volume": 100000.0,
                "bid_price": 99.5,
                "ask_price": 100.5,
            },
            "metadata": self._build_request_metadata("ticker", "spot"),
        }

    def fetch_futures_ticker(self, symbol: str) -> dict[str, dict[str, float]]:
        self.ticker_calls.append("futures")
        return {
            "ticker": {
                "symbol": symbol,
                "last_price": 200.0,
                "open_price": 190.0,
                "high_price": 210.0,
                "low_price": 189.0,
                "price_change": 5.0,
                "price_change_percent": 2.5,
                "volume": 2000.0,
                "quote_volume": 200000.0,
                "bid_price": 199.0,
                "ask_price": 201.0,
            },
            "metadata": self._build_request_metadata("ticker", "derivatives-trading-usds-futures"),
        }

    def get_placeholder_klines(self, symbol: str, timeframe: str, market_type: str) -> list[tuple[int, float, float, float, float, float]]:
        self.placeholder_calls += 1
        return [
            (
                1700000000000 + index * 86400000,
                float(10 + index),
                float(12 + index),
                float(9 + index),
                float(11 + index),
                float(100 + index * 10),
            )
            for index in range(6)
        ]


class FailingAdapter(MarketTypeSpyAdapter):
    def fetch_spot_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[tuple[int, float, float, float, float, float]]:
        raise RuntimeError("network unavailable")

    def fetch_futures_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[tuple[int, float, float, float, float, float]]:
        raise RuntimeError("network unavailable")

    def fetch_spot_ticker(self, symbol: str) -> dict[str, dict[str, float]]:
        raise RuntimeError("ticker unavailable")

    def fetch_futures_ticker(self, symbol: str) -> dict[str, dict[str, float]]:
        raise RuntimeError("ticker unavailable")


def test_market_data_service_returns_structured_payload_with_metadata() -> None:
    adapter = MarketTypeSpyAdapter()
    service = MarketDataService(adapter=adapter)

    payload = service.get_klines(symbol="BTCUSDT", timeframe="1d", market_type="spot")

    assert payload.source == "binance"
    assert payload.market_type == "spot"
    assert payload.endpoint_summary is not None
    assert payload.endpoint_summary.integration == "binance"
    assert payload.endpoint_summary.endpoint == "klines"
    assert payload.ticker_summary is not None
    assert payload.ticker_summary.symbol == "BTCUSDT"
    assert len(payload.candles) == 1
    assert payload.degraded_reason is None
    assert adapter.klines_calls == ["spot"]
    assert adapter.ticker_calls == ["spot"]


def test_market_data_service_marks_fallback_as_degraded() -> None:
    adapter = FailingAdapter()
    service = MarketDataService(adapter=adapter)

    payload = service.get_klines(symbol="ETHUSDT", timeframe="1h", market_type="spot")

    assert payload.source == "unavailable"
    assert payload.endpoint_summary is not None
    assert payload.endpoint_summary.endpoint == "klines"
    assert payload.degraded_reason is not None
    assert payload.ticker_summary is None
    assert len(payload.candles) == 0
    assert adapter.placeholder_calls == 0


def test_market_data_service_marks_futures_failure_as_unavailable() -> None:
    adapter = FailingAdapter()
    service = MarketDataService(adapter=adapter)

    payload = service.get_klines(symbol="BTCUSDT", timeframe="4h", market_type="futures")

    assert payload.source == "unavailable"
    assert payload.market_type == "derivatives-trading-usds-futures"
    assert payload.endpoint_summary is not None
    assert payload.endpoint_summary.market_type == "derivatives-trading-usds-futures"
    assert payload.degraded_reason is not None
    assert payload.candles == []
    assert adapter.placeholder_calls == 0


def test_market_data_payload_is_list_like_for_compatibility() -> None:
    adapter = MarketTypeSpyAdapter()
    service = MarketDataService(adapter=adapter)

    payload = service.get_klines(symbol="SOLUSDT", timeframe="4h", market_type="spot")

    assert isinstance(payload, MarketDataPayload)
    assert len(payload) == len(payload.candles)
    assert payload[0].symbol == payload.candles[0].symbol
    assert list(payload) == payload.candles


def test_market_data_service_returns_canonical_market_type() -> None:
    adapter = MarketTypeSpyAdapter()
    service = MarketDataService(adapter=adapter)

    payload = service.get_klines(symbol="ETHUSDT", timeframe="1h", market_type="futures")

    assert payload.market_type == "derivatives-trading-usds-futures"
    assert adapter.klines_calls == ["futures"]
    assert adapter.ticker_calls == ["futures"]
    assert payload.endpoint_summary is not None
    assert payload.endpoint_summary.market_type == "derivatives-trading-usds-futures"


def test_adapter_parses_spot_klines_response() -> None:
    transport = StubTransport(
        payload=[
            [1700000000000, "100.0", "110.0", "95.0", "108.0", "1200.5"],
            [1700086400000, "108.0", "112.0", "101.0", "111.0", "1300.0"],
        ]
    )
    adapter = BinanceMarketAdapter(
        client=httpx.Client(transport=transport, base_url="https://api.binance.com")
    )

    candles = adapter.fetch_public_klines(
        symbol="BTCUSDT",
        timeframe="1d",
        market_type="spot",
        limit=2,
    )

    assert candles == [
        (1700000000000, 100.0, 110.0, 95.0, 108.0, 1200.5),
        (1700086400000, 108.0, 112.0, 101.0, 111.0, 1300.0),
    ]


def test_adapter_uses_registry_to_resolve_futures_alias() -> None:
    transport = StubTransport(
        payload=[
            [1700000000000, "100.0", "110.0", "95.0", "108.0", "1200.5"],
        ]
    )
    adapter = BinanceMarketAdapter(
        registry=BinanceSkillRegistry(skill_roots=[]),
        client=httpx.Client(transport=transport),
    )

    candles = adapter.fetch_public_klines(
        symbol="BTCUSDT",
        timeframe="1d",
        market_type="futures",
        limit=1,
    )

    assert candles == [(1700000000000, 100.0, 110.0, 95.0, 108.0, 1200.5)]
