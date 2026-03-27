from pathlib import Path

from app.api.assets import read_live_asset, read_top_assets, search_assets
from app.schemas.assets import AssetDiscoveryResponse, AssetLiveSnapshot
from app.schemas.kline import Candle, EndpointSummary, TickerSummary


class StubDiscoveryService:
    def get_top_assets(self, limit: int = 20) -> AssetDiscoveryResponse:
        return AssetDiscoveryResponse(
            items=[
                {
                    "symbol": "BTC",
                    "name": "Bitcoin",
                    "display_name_zh": "比特币",
                    "rank": 1,
                    "image": "btc.png",
                    "market_cap": None,
                    "current_price": 90000,
                    "price_change_percentage_24h": 1.2,
                    "binance_symbol": "BTCUSDT",
                    "is_binance_supported": True,
                }
            ]
        )

    def search_assets(self, query: str) -> AssetDiscoveryResponse:
        return AssetDiscoveryResponse(
            items=[
                {
                    "symbol": query.upper(),
                    "name": query.title(),
                    "display_name_zh": "测试币",
                    "rank": None,
                    "image": None,
                    "market_cap": None,
                    "current_price": None,
                    "price_change_percentage_24h": None,
                    "binance_symbol": f"{query.upper()}USDT",
                    "is_binance_supported": True,
                }
            ]
        )


class StubMarketDataService:
    def get_live_snapshot(self, symbol: str, timeframe: str, market_type: str) -> AssetLiveSnapshot:
        if symbol.upper() == "BAD":
            return AssetLiveSnapshot(
                symbol="BAD",
                binance_symbol="BADUSDT",
                name="Bad Coin",
                market_type=market_type,
                timeframe=timeframe,
                is_supported=False,
                source="unavailable",
                candles=[],
                ticker_summary=None,
                endpoint_summary=None,
                degraded_reason="symbol is not supported on Binance spot",
                chart_summary=None,
            )

        return AssetLiveSnapshot(
            symbol=symbol.upper(),
            binance_symbol=f"{symbol.upper()}USDT",
            name="Bitcoin",
            market_type=market_type,
            timeframe=timeframe,
            is_supported=True,
            source="binance",
            candles=[
                Candle(
                    symbol=f"{symbol.upper()}USDT",
                    timeframe=timeframe,
                    open_time=1710000000000,
                    open=100.0,
                    high=110.0,
                    low=95.0,
                    close=108.0,
                    volume=1200.0,
                )
            ],
            ticker_summary=TickerSummary(
                symbol=f"{symbol.upper()}USDT",
                last_price=108.0,
                open_price=100.0,
                high_price=110.0,
                low_price=95.0,
                price_change=8.0,
                price_change_percent=8.0,
                volume=1200.0,
                quote_volume=120000.0,
                bid_price=107.8,
                ask_price=108.2,
            ),
            endpoint_summary=EndpointSummary(
                integration="binance",
                endpoint="klines",
                market_type=market_type,
                url="https://example.com/klines",
                method="GET",
            ),
            degraded_reason=None,
            chart_summary={
                "trend_regime": "uptrend",
                "breakout_signal": False,
                "drawdown_state": "near-high",
                "support_levels": [95.0],
                "resistance_levels": [110.0],
                "conclusion": "uptrend on this timeframe with support near 95.00 and resistance near 110.00.",
            },
        )


def test_get_top_assets_returns_items(tmp_path: Path) -> None:
    del tmp_path

    response = read_top_assets(StubDiscoveryService())

    assert response.items[0].symbol == "BTC"
    assert response.items[0].display_name_zh == "比特币"
    assert response.items[0].rank == 1


def test_search_assets_returns_discovery_items(tmp_path: Path) -> None:
    del tmp_path

    response = search_assets("doge", asset_discovery_service=StubDiscoveryService())

    assert response.items[0].symbol == "DOGE"
    assert response.items[0].display_name_zh == "测试币"


def test_get_live_asset_returns_snapshot_with_chart_summary(tmp_path: Path) -> None:
    del tmp_path

    payload = read_live_asset("BTC", market="spot", timeframe="1m", market_data_service=StubMarketDataService())

    assert payload.symbol == "BTC"
    assert payload.binance_symbol == "BTCUSDT"
    assert payload.is_supported is True
    assert payload.source == "binance"
    assert payload.chart_summary is not None
    assert payload.chart_summary.trend_regime == "uptrend"


def test_get_live_asset_returns_unavailable_payload_for_unsupported_route(tmp_path: Path) -> None:
    del tmp_path

    payload = read_live_asset("BAD", market="spot", timeframe="1m", market_data_service=StubMarketDataService())

    assert payload.symbol == "BAD"
    assert payload.is_supported is False
    assert payload.candles == []
    assert payload.source == "unavailable"
