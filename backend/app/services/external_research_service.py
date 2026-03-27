from app.clients.external_research_adapter import ExternalResearchAdapter


class ExternalResearchService:
    def __init__(self, adapter: ExternalResearchAdapter | None = None) -> None:
        self.adapter = adapter or ExternalResearchAdapter()

    def get_asset_context(self, asset: str) -> dict:
        try:
            market = self.adapter.fetch_market_snapshot(asset)
        except Exception:
            market = None
        try:
            protocol = self.adapter.fetch_protocol_snapshot(asset)
        except Exception:
            protocol = None
        return {"market": market, "protocol": protocol}
