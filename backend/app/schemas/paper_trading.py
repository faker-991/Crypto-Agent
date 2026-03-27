from pydantic import BaseModel, Field


class PaperPosition(BaseModel):
    symbol: str
    market_type: str
    quantity: float
    average_entry_price: float
    last_price: float
    unrealized_pnl: float = 0.0


class PaperPortfolio(BaseModel):
    cash: float = 10000.0
    positions: list[PaperPosition] = Field(default_factory=list)


class PaperOrderCreate(BaseModel):
    symbol: str
    market_type: str
    side: str
    quantity: float
    price: float


class PaperOrderRecord(BaseModel):
    symbol: str
    market_type: str
    side: str
    quantity: float
    price: float
    notional: float
