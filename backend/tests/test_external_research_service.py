import httpx

from app.clients.external_research_adapter import ExternalResearchAdapter
from app.services.external_research_service import ExternalResearchService


class SequencedTransport(httpx.BaseTransport):
    def __init__(self, responses: list[dict | list]) -> None:
        self.responses = responses
        self.index = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        payload = self.responses[self.index]
        self.index += 1
        return httpx.Response(200, json=payload)


def test_external_research_service_returns_normalized_asset_context() -> None:
    transport = SequencedTransport(
        responses=[
            [
                {
                    "symbol": "ena",
                    "name": "Ethena",
                    "market_cap": 1250000000,
                    "fully_diluted_valuation": 2400000000,
                    "total_volume": 310000000,
                    "price_change_percentage_24h": 8.6,
                }
            ],
            [
                {
                    "name": "Ethena",
                    "symbol": "ENA",
                    "tvl": 810000000,
                    "chains": ["Ethereum"],
                    "category": "Restaking",
                    "change_1d": 3.5,
                }
            ],
        ]
    )
    adapter = ExternalResearchAdapter(client=httpx.Client(transport=transport))
    service = ExternalResearchService(adapter=adapter)

    context = service.get_asset_context("ENA")

    assert context["market"]["market_cap"] == 1250000000
    assert context["market"]["fdv"] == 2400000000
    assert context["protocol"]["tvl"] == 810000000
    assert context["protocol"]["category"] == "Restaking"


def test_external_research_service_handles_missing_upstreams() -> None:
    class EmptyAdapter:
        def fetch_market_snapshot(self, asset: str) -> dict | None:
            return None

        def fetch_protocol_snapshot(self, asset: str) -> dict | None:
            return None

    service = ExternalResearchService(adapter=EmptyAdapter())

    context = service.get_asset_context("BTC")

    assert context == {"market": None, "protocol": None}
