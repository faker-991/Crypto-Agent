from typing import Literal

from pydantic import BaseModel, Field


class Candle(BaseModel):
    symbol: str
    timeframe: str
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class EndpointSummary(BaseModel):
    integration: str
    endpoint: str
    market_type: str
    url: str
    method: str


class TickerSummary(BaseModel):
    symbol: str
    last_price: float | None = None
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    price_change: float | None = None
    price_change_percent: float | None = None
    volume: float | None = None
    quote_volume: float | None = None
    bid_price: float | None = None
    ask_price: float | None = None


class MarketDataPayload(BaseModel):
    symbol: str
    timeframe: str
    market_type: str
    source: Literal["binance", "unavailable"]
    candles: list[Candle]
    endpoint_summary: EndpointSummary | None
    ticker_summary: TickerSummary | None
    degraded_reason: str | None = None

    def __len__(self) -> int:
        return len(self.candles)

    def __iter__(self):
        return iter(self.candles)

    def __getitem__(self, index):
        return self.candles[index]


class TimeframeAnalysis(BaseModel):
    trend_regime: str
    support_levels: list[float] = Field(default_factory=list)
    resistance_levels: list[float] = Field(default_factory=list)
    breakout_signal: bool = False
    drawdown_state: str
    conclusion: str
    candles: list[Candle] = Field(default_factory=list)


class TimeframeMarketData(BaseModel):
    market_type: str
    source: Literal["binance", "unavailable"]
    endpoint_summary: EndpointSummary | None = None
    ticker_summary: TickerSummary | None = None
    degraded_reason: str | None = None


class KlineResearchRequest(BaseModel):
    symbol: str
    timeframes: list[str]
    market_type: str = "spot"


class KlineResearchResponse(BaseModel):
    symbol: str
    market_type: str
    analyses: dict[str, TimeframeAnalysis]
    market_data: dict[str, TimeframeMarketData] = Field(default_factory=dict)
