from fastapi import APIRouter, Depends

from app.schemas.paper_trading import PaperOrderCreate, PaperPortfolio
from app.services.paper_trading_service import PaperTradingService

router = APIRouter(prefix="/api/paper-trading", tags=["paper-trading"])


def get_paper_trading_service() -> PaperTradingService:
    raise RuntimeError("paper trading service dependency is not configured")


@router.get("/portfolio", response_model=PaperPortfolio)
def read_portfolio(
    service: PaperTradingService = Depends(get_paper_trading_service),
) -> PaperPortfolio:
    return service.get_portfolio()


@router.post("/order", response_model=PaperPortfolio)
def create_order(
    order: PaperOrderCreate,
    service: PaperTradingService = Depends(get_paper_trading_service),
) -> PaperPortfolio:
    return service.place_order(order)
