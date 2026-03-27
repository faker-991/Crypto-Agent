from dataclasses import dataclass
from typing import Any, TypedDict

import httpx

from app.services.binance_skill_registry import BinanceSkillRegistry


class BinanceEndpointMetadata(TypedDict):
    integration: str
    endpoint: str
    market_type: str
    url: str
    method: str


@dataclass
class BinanceEndpointRequest:
    base_url: str
    endpoint: str
    params: dict[str, str | int]
    metadata: BinanceEndpointMetadata


class BinanceMarketAdapter:
    _ENDPOINT_FALLBACKS: dict[str, dict[str, str]] = {
        "exchangeInfo": {
            "spot": "/api/v3/exchangeInfo",
        },
        "ticker": {
            "derivatives-trading-usds-futures": "/fapi/v1/ticker/24hr",
        },
    }

    def __init__(
        self,
        client: httpx.Client | None = None,
        registry: BinanceSkillRegistry | None = None,
    ) -> None:
        self.client = client or httpx.Client(timeout=10.0)
        self.registry = registry or BinanceSkillRegistry()

    def get_capabilities(self) -> dict[str, list[str]]:
        return self.registry.get_capabilities()

    def build_kline_request(
        self,
        symbol: str,
        timeframe: str,
        market_type: str,
        limit: int = 200,
    ) -> BinanceEndpointRequest:
        return self._build_kline_request(
            symbol=symbol,
            timeframe=timeframe,
            market_type=market_type,
            limit=limit,
        )

    def fetch_public_klines(
        self,
        symbol: str,
        timeframe: str,
        market_type: str,
        limit: int = 200,
    ) -> list[tuple[int, float, float, float, float, float]]:
        request = self._build_kline_request(
            symbol=symbol,
            timeframe=timeframe,
            market_type=market_type,
            limit=limit,
        )
        response = self.client.get(
            f"{request.base_url}{request.endpoint}",
            params=request.params,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            (
                int(item[0]),
                float(item[1]),
                float(item[2]),
                float(item[3]),
                float(item[4]),
                float(item[5]),
            )
            for item in payload
        ]

    def fetch_spot_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> list[tuple[int, float, float, float, float, float]]:
        return self.fetch_public_klines(
            symbol=symbol,
            timeframe=timeframe,
            market_type="spot",
            limit=limit,
        )

    def fetch_futures_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> list[tuple[int, float, float, float, float, float]]:
        return self.fetch_public_klines(
            symbol=symbol,
            timeframe=timeframe,
            market_type="futures",
            limit=limit,
        )

    def fetch_spot_ticker(self, symbol: str) -> dict[str, Any]:
        return self._fetch_ticker(symbol=symbol, market_type="spot")

    def fetch_futures_ticker(self, symbol: str) -> dict[str, Any]:
        return self._fetch_ticker(symbol=symbol, market_type="futures")

    def fetch_spot_exchange_info(self) -> dict[str, Any]:
        request = self._build_endpoint_request(
            endpoint_key="exchangeInfo",
            market_type="spot",
            params={},
        )
        response = self.client.get(f"{request.base_url}{request.endpoint}")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def _fetch_ticker(self, symbol: str, market_type: str) -> dict[str, Any]:
        request = self._build_ticker_request(symbol=symbol, market_type=market_type)
        response = self.client.get(
            f"{request.base_url}{request.endpoint}",
            params=request.params,
        )
        response.raise_for_status()
        payload = response.json()
        return {
            "ticker": self.parse_ticker_response(payload),
            "metadata": request.metadata,
        }

    def _build_kline_request(
        self,
        symbol: str,
        timeframe: str,
        market_type: str,
        limit: int,
    ) -> BinanceEndpointRequest:
        return self._build_endpoint_request(
            endpoint_key="klines",
            market_type=market_type,
            params={
                "symbol": self._normalize_symbol(symbol),
                "interval": timeframe,
                "limit": limit,
            },
        )

    def parse_ticker_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        def to_float(key: str) -> float | None:
            value = payload.get(key)
            if value is None or value == "":
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        return {
            "symbol": payload.get("symbol", ""),
            "last_price": to_float("lastPrice"),
            "open_price": to_float("openPrice"),
            "high_price": to_float("highPrice"),
            "low_price": to_float("lowPrice"),
            "price_change": to_float("priceChange"),
            "price_change_percent": to_float("priceChangePercent"),
            "volume": to_float("volume"),
            "quote_volume": to_float("quoteVolume"),
            "bid_price": to_float("bidPrice"),
            "ask_price": to_float("askPrice"),
        }

    def _build_ticker_request(self, symbol: str, market_type: str) -> BinanceEndpointRequest:
        return self._build_endpoint_request(
            endpoint_key="ticker",
            market_type=market_type,
            params={"symbol": self._normalize_symbol(symbol)},
        )

    def _normalize_symbol(self, symbol: str) -> str:
        normalized = symbol.upper().strip()
        if not normalized:
            return normalized
        quote_assets = ("USDT", "USDC", "BUSD", "FDUSD", "BTC", "ETH")
        if any(
            len(normalized) > len(quote_asset) and normalized.endswith(quote_asset)
            for quote_asset in quote_assets
        ):
            return normalized
        return f"{normalized}USDT"

    def _build_endpoint_request(
        self,
        endpoint_key: str,
        market_type: str,
        params: dict[str, str | int],
    ) -> BinanceEndpointRequest:
        canonical_market = self.registry.resolve_market_key(market_type)
        spec = self.registry.get_spec(canonical_market)
        endpoint = spec["public_endpoints"].get(endpoint_key)
        if endpoint is None:
            endpoint = self._get_endpoint_fallback(canonical_market, endpoint_key)
        base_url = spec["base_url"]
        return BinanceEndpointRequest(
            base_url=base_url,
            endpoint=endpoint,
            params=params,
            metadata={
                "integration": "binance",
                "endpoint": endpoint_key,
                "market_type": canonical_market,
                "url": f"{base_url}{endpoint}",
                "method": "GET",
            },
        )

    def _get_endpoint_fallback(self, market: str, endpoint_key: str) -> str:
        fallback = self._ENDPOINT_FALLBACKS.get(endpoint_key, {}).get(market)
        if fallback is None:
            raise KeyError(f"Missing endpoint {endpoint_key} for market {market}")
        return fallback

    def get_placeholder_klines(
        self,
        symbol: str,
        timeframe: str,
        market_type: str,
    ) -> list[tuple[int, float, float, float, float, float]]:
        base_price = 100 if market_type == "spot" else 120
        timeframe_shift = {"1d": 2, "1w": 8}.get(timeframe, 1)
        seed = sum(ord(char) for char in symbol) % 11

        candles = []
        for index in range(6):
            open_price = base_price + seed + (index * timeframe_shift)
            close_price = open_price + 2 + (index % 2)
            high_price = close_price + 1.5
            low_price = open_price - 1.25
            volume = 1000 + (index * 120) + (timeframe_shift * 40)
            candles.append(
                (
                    1700000000000 + (index * 86400000),
                    float(open_price),
                    float(high_price),
                    float(low_price),
                    float(close_price),
                    float(volume),
                )
            )

        candles[-1] = (
            candles[-1][0],
            candles[-1][1],
            candles[-1][2] + 2.0,
            candles[-1][3],
            candles[-1][4] + 2.5,
            candles[-1][5] + 400.0,
        )
        return candles
