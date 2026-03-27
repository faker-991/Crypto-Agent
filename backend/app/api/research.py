from fastapi import APIRouter, Depends

from app.schemas.kline import (
    KlineResearchRequest,
    KlineResearchResponse,
    TimeframeMarketData,
)
from app.services.kline_analysis_service import KlineAnalysisService
from app.services.market_data_service import MarketDataService

router = APIRouter(prefix="/api/research", tags=["research"])


def get_market_data_service() -> MarketDataService:
    raise RuntimeError("market data service dependency is not configured")


@router.post("/kline", response_model=KlineResearchResponse)
def read_kline_analysis(
    request: KlineResearchRequest,
    market_data_service: MarketDataService = Depends(get_market_data_service),
) -> KlineResearchResponse:
    analysis_service = KlineAnalysisService()
    analyses = {}
    market_data = {}
    for timeframe in request.timeframes:
        payload = market_data_service.get_klines(
            symbol=request.symbol,
            timeframe=timeframe,
            market_type=request.market_type,
        )
        analyses[timeframe] = analysis_service.analyze_timeframe(payload)
        market_data[timeframe] = TimeframeMarketData(
            market_type=payload.market_type,
            source=payload.source,
            endpoint_summary=payload.endpoint_summary,
            ticker_summary=payload.ticker_summary,
            degraded_reason=payload.degraded_reason,
        )

    return KlineResearchResponse(
        symbol=request.symbol.upper(),
        market_type=request.market_type,
        analyses=analyses,
        market_data=market_data,
    )
