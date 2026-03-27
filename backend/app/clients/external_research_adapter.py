import httpx


class ExternalResearchAdapter:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=10.0)

    def fetch_top_market_assets(self, limit: int = 20) -> list[dict]:
        response = self.client.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": limit,
                "page": 1,
                "price_change_percentage": "24h",
            },
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def search_assets(self, query: str) -> list[dict]:
        response = self.client.get(
            "https://api.coingecko.com/api/v3/search",
            params={"query": query},
        )
        response.raise_for_status()
        payload = response.json()
        coins = payload.get("coins", []) if isinstance(payload, dict) else []
        return coins if isinstance(coins, list) else []

    def fetch_market_snapshot(self, asset: str) -> dict | None:
        response = self.client.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "symbols": asset.lower(),
                "price_change_percentage": "24h",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not payload:
            return None
        item = payload[0]
        return {
            "symbol": str(item.get("symbol", asset)).upper(),
            "name": item.get("name"),
            "market_cap": item.get("market_cap"),
            "fdv": item.get("fully_diluted_valuation"),
            "total_volume": item.get("total_volume"),
            "price_change_percentage_24h": item.get("price_change_percentage_24h"),
        }

    def fetch_protocol_snapshot(self, asset: str) -> dict | None:
        response = self.client.get("https://api.llama.fi/protocols")
        response.raise_for_status()
        payload = response.json()
        asset_upper = asset.upper()
        for item in payload:
            if str(item.get("symbol", "")).upper() == asset_upper or str(item.get("name", "")).upper() == asset_upper:
                return {
                    "name": item.get("name"),
                    "symbol": item.get("symbol"),
                    "tvl": item.get("tvl"),
                    "chains": item.get("chains", []),
                    "category": item.get("category"),
                    "change_1d": item.get("change_1d"),
                }
        return None
