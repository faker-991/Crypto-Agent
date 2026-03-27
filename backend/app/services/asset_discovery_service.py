import time
from collections.abc import Callable

from app.clients.external_research_adapter import ExternalResearchAdapter
from app.schemas.assets import AssetDiscoveryItem, AssetDiscoveryResponse
from app.services.market_data_service import MarketDataService

DEFAULT_TOP_ASSET_CATALOG: list[dict[str, str | int]] = [
    {"symbol": "BTC", "name": "Bitcoin", "display_name_zh": "比特币", "rank": 1},
    {"symbol": "ETH", "name": "Ethereum", "display_name_zh": "以太坊", "rank": 2},
    {"symbol": "USDT", "name": "Tether", "display_name_zh": "泰达币", "rank": 3},
    {"symbol": "XRP", "name": "XRP", "display_name_zh": "瑞波币", "rank": 4},
    {"symbol": "BNB", "name": "BNB", "display_name_zh": "币安币", "rank": 5},
    {"symbol": "USDC", "name": "USD Coin", "display_name_zh": "USDC", "rank": 6},
    {"symbol": "SOL", "name": "Solana", "display_name_zh": "Solana", "rank": 7},
    {"symbol": "TRX", "name": "TRON", "display_name_zh": "波场", "rank": 8},
    {"symbol": "FIGR_HELOC", "name": "Figure Heloc", "display_name_zh": "Figure Heloc", "rank": 9},
    {"symbol": "DOGE", "name": "Dogecoin", "display_name_zh": "狗币", "rank": 10},
    {"symbol": "WBT", "name": "WhiteBIT Coin", "display_name_zh": "WhiteBIT Coin", "rank": 11},
    {"symbol": "USDS", "name": "USDS", "display_name_zh": "USDS", "rank": 12},
    {"symbol": "ADA", "name": "Cardano", "display_name_zh": "艾达币", "rank": 13},
    {"symbol": "BCH", "name": "Bitcoin Cash", "display_name_zh": "比特现金", "rank": 14},
    {"symbol": "HYPE", "name": "Hyperliquid", "display_name_zh": "Hyperliquid", "rank": 15},
    {"symbol": "LEO", "name": "LEO Token", "display_name_zh": "LEO Token", "rank": 16},
    {"symbol": "LINK", "name": "Chainlink", "display_name_zh": "Chainlink", "rank": 17},
    {"symbol": "XMR", "name": "Monero", "display_name_zh": "门罗币", "rank": 18},
    {"symbol": "USDE", "name": "Ethena USDe", "display_name_zh": "Ethena USDe", "rank": 19},
    {"symbol": "CC", "name": "Canton", "display_name_zh": "Canton", "rank": 20},
]


class AssetDiscoveryService:
    def __init__(
        self,
        research_adapter: ExternalResearchAdapter | None = None,
        market_data_service: MarketDataService | None = None,
        top_assets_catalog: list[dict[str, str | int]] | None = None,
        cache_ttl_seconds: int = 300,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.research_adapter = research_adapter or ExternalResearchAdapter()
        self.market_data_service = market_data_service or MarketDataService()
        self.top_assets_catalog = top_assets_catalog or DEFAULT_TOP_ASSET_CATALOG
        self.catalog_by_symbol = {
            str(item["symbol"]).upper(): item
            for item in self.top_assets_catalog
            if str(item.get("symbol", "")).strip()
        }
        self.cache_ttl_seconds = cache_ttl_seconds
        self.clock = clock or time.monotonic
        self._cached_search_index: list[dict[str, str | int | None]] | None = None
        self._cached_search_index_at = 0.0

    def get_top_assets(self, limit: int = 20) -> AssetDiscoveryResponse:
        items = [self._build_catalog_item(item) for item in self.top_assets_catalog[:limit]]
        return AssetDiscoveryResponse(items=items)

    def search_assets(self, query: str) -> AssetDiscoveryResponse:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return AssetDiscoveryResponse(items=[])

        matched_items = [
            self._build_search_item(item)
            for item in self._get_search_index()
            if self._matches_query(item, normalized_query)
        ]
        matched_items.sort(key=self._sort_search_items)
        return AssetDiscoveryResponse(items=matched_items[:24])

    def _build_catalog_item(self, item: dict[str, str | int]) -> AssetDiscoveryItem:
        symbol = str(item["symbol"]).upper()
        binance_symbol = f"{symbol}USDT"
        is_supported = self.market_data_service.is_symbol_supported(binance_symbol, market_type="spot")
        ticker_summary = self.market_data_service.get_spot_ticker_summary(binance_symbol) if is_supported else None

        return AssetDiscoveryItem(
            symbol=symbol,
            name=self._string_or_none(item.get("name")),
            display_name_zh=self._string_or_none(item.get("display_name_zh")),
            rank=self._int_or_none(item.get("rank")),
            image=None,
            market_cap=None,
            current_price=ticker_summary.last_price if ticker_summary else None,
            price_change_percentage_24h=ticker_summary.price_change_percent if ticker_summary else None,
            binance_symbol=binance_symbol,
            is_binance_supported=is_supported,
        )

    def _get_search_index(self) -> list[dict[str, str | int | None]]:
        now = self.clock()
        if self._cached_search_index is not None and now - self._cached_search_index_at < self.cache_ttl_seconds:
            return self._cached_search_index

        index: list[dict[str, str | int | None]] = []
        for item in self.market_data_service.list_spot_searchable_assets():
            base_symbol = str(item.get("base_asset", "")).upper().strip()
            binance_symbol = str(item.get("symbol", "")).upper().strip()
            if not base_symbol or not binance_symbol:
                continue

            metadata = self.catalog_by_symbol.get(base_symbol, {})
            index.append(
                {
                    "symbol": base_symbol,
                    "binance_symbol": binance_symbol,
                    "name": self._string_or_none(metadata.get("name")) or base_symbol,
                    "display_name_zh": self._string_or_none(metadata.get("display_name_zh")),
                    "rank": self._int_or_none(metadata.get("rank")),
                }
            )

        self._cached_search_index = index
        self._cached_search_index_at = now
        return index

    def _build_search_item(self, item: dict[str, str | int | None]) -> AssetDiscoveryItem:
        return AssetDiscoveryItem(
            symbol=str(item["symbol"]).upper(),
            name=self._string_or_none(item.get("name")),
            display_name_zh=self._string_or_none(item.get("display_name_zh")),
            rank=self._int_or_none(item.get("rank")),
            image=None,
            market_cap=None,
            current_price=None,
            price_change_percentage_24h=None,
            binance_symbol=self._string_or_none(item.get("binance_symbol")),
            is_binance_supported=True,
        )

    def _matches_query(self, item: dict[str, str | int | None], query: str) -> bool:
        haystacks = [
            self._string_or_none(item.get("symbol")),
            self._string_or_none(item.get("name")),
            self._string_or_none(item.get("display_name_zh")),
        ]
        return any(query in value.lower() for value in haystacks if value)

    def _sort_search_items(self, item: AssetDiscoveryItem) -> tuple[int, int, str]:
        return (
            0 if item.rank is not None else 1,
            item.rank if item.rank is not None else 999,
            item.symbol,
        )

    def _string_or_none(self, value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value
        return None

    def _int_or_none(self, value: object) -> int | None:
        if isinstance(value, int):
            return value
        return None
