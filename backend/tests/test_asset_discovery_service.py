from app.schemas.kline import TickerSummary
from app.services.asset_discovery_service import AssetDiscoveryService


class StubMarketDataService:
    def list_spot_searchable_assets(self) -> list[dict[str, str]]:
        return [
            {"symbol": "BTCUSDT", "base_asset": "BTC"},
            {"symbol": "ETHUSDT", "base_asset": "ETH"},
            {"symbol": "DOGEUSDT", "base_asset": "DOGE"},
            {"symbol": "ZECUSDT", "base_asset": "ZEC"},
        ]

    def get_spot_ticker_summary(self, symbol: str) -> TickerSummary | None:
        payloads = {
            "BTCUSDT": TickerSummary(
                symbol="BTCUSDT",
                last_price=88000.0,
                open_price=86000.0,
                high_price=89000.0,
                low_price=85000.0,
                price_change=2000.0,
                price_change_percent=2.33,
                volume=1000.0,
                quote_volume=88000000.0,
                bid_price=87990.0,
                ask_price=88010.0,
            ),
            "DOGEUSDT": TickerSummary(
                symbol="DOGEUSDT",
                last_price=0.21,
                open_price=0.2,
                high_price=0.22,
                low_price=0.19,
                price_change=0.01,
                price_change_percent=5.0,
                volume=2000000.0,
                quote_volume=420000.0,
                bid_price=0.209,
                ask_price=0.211,
            ),
        }
        return payloads.get(symbol)

    def is_symbol_supported(self, binance_symbol: str, market_type: str = "spot") -> bool:
        return binance_symbol in {"BTCUSDT", "ETHUSDT", "DOGEUSDT", "ZECUSDT"}


def test_top_assets_uses_default_catalog_order_and_binance_ticker_data() -> None:
    service = AssetDiscoveryService(market_data_service=StubMarketDataService())

    payload = service.get_top_assets(limit=3)

    assert [item.symbol for item in payload.items] == ["BTC", "ETH", "USDT"]
    assert payload.items[0].rank == 1
    assert payload.items[0].display_name_zh == "比特币"
    assert payload.items[0].current_price == 88000.0
    assert payload.items[1].rank == 2
    assert payload.items[1].current_price is None
    assert payload.items[2].binance_symbol == "USDTUSDT"
    assert payload.items[2].is_binance_supported is False


def test_search_assets_only_returns_binance_supported_assets_sorted_with_default_catalog_first() -> None:
    service = AssetDiscoveryService(market_data_service=StubMarketDataService())

    payload = service.search_assets("e")

    assert [item.symbol for item in payload.items] == ["ETH", "DOGE", "ZEC"]
    assert payload.items[0].display_name_zh == "以太坊"
    assert payload.items[0].rank == 2
    assert payload.items[1].display_name_zh == "狗币"
    assert payload.items[1].is_binance_supported is True
    assert payload.items[2].rank is None
