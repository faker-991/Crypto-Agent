from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.kline import Candle, EndpointSummary, TickerSummary


class AssetDiscoveryItem(BaseModel):
    symbol: str
    name: str | None = None
    display_name_zh: str | None = None
    rank: int | None = None
    image: str | None = None
    market_cap: float | int | None = None
    current_price: float | None = None
    price_change_percentage_24h: float | None = None
    binance_symbol: str | None = None
    is_binance_supported: bool


class AssetDiscoveryResponse(BaseModel):
    items: list[AssetDiscoveryItem] = Field(default_factory=list)


class AssetChartSummary(BaseModel):
    trend_regime: str
    breakout_signal: bool
    drawdown_state: str
    support_levels: list[float] = Field(default_factory=list)
    resistance_levels: list[float] = Field(default_factory=list)
    conclusion: str


class AssetLiveSnapshot(BaseModel):
    symbol: str
    binance_symbol: str | None = None
    name: str | None = None
    market_type: str
    timeframe: str
    is_supported: bool
    source: Literal["binance", "unavailable"]
    candles: list[Candle] = Field(default_factory=list)
    ticker_summary: TickerSummary | None = None
    endpoint_summary: EndpointSummary | None = None
    degraded_reason: str | None = None
    chart_summary: AssetChartSummary | None = None
