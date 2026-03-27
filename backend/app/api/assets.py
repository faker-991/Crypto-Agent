from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.assets import AssetDiscoveryResponse, AssetLiveSnapshot
from app.services.asset_discovery_service import AssetDiscoveryService
from app.services.market_data_service import MarketDataService

router = APIRouter(prefix="/api/assets", tags=["assets"])


def get_asset_discovery_service() -> AssetDiscoveryService:
    raise RuntimeError("asset discovery service dependency is not configured")


def get_market_data_service() -> MarketDataService:
    raise RuntimeError("market data service dependency is not configured")


@router.get("/discovery/top", response_model=AssetDiscoveryResponse)
def read_top_assets(
    asset_discovery_service: AssetDiscoveryService = Depends(get_asset_discovery_service),
) -> AssetDiscoveryResponse:
    try:
        return asset_discovery_service.get_top_assets(limit=20)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"默认前 20 资产暂不可用：{exc}") from exc


@router.get("/discovery/search", response_model=AssetDiscoveryResponse)
def search_assets(
    q: str = Query(default="", min_length=1),
    asset_discovery_service: AssetDiscoveryService = Depends(get_asset_discovery_service),
) -> AssetDiscoveryResponse:
    try:
        return asset_discovery_service.search_assets(q)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"资产搜索暂不可用：{exc}") from exc


@router.get("/{symbol}/live", response_model=AssetLiveSnapshot)
def read_live_asset(
    symbol: str,
    market: str = Query(default="spot"),
    timeframe: str = Query(default="1m"),
    market_data_service: MarketDataService = Depends(get_market_data_service),
) -> AssetLiveSnapshot:
    return market_data_service.get_live_snapshot(
        symbol=symbol,
        timeframe=timeframe,
        market_type=market,
    )
