from datetime import date

from pydantic import BaseModel, Field


class WatchlistItem(BaseModel):
    symbol: str
    status: str = "watch"
    priority: int = 2
    last_reviewed_at: str = Field(default_factory=lambda: date.today().isoformat())


class Watchlist(BaseModel):
    assets: list[WatchlistItem] = Field(default_factory=list)


class WatchlistAddRequest(BaseModel):
    symbol: str
    status: str = "watch"
    priority: int = 2


class WatchlistRemoveRequest(BaseModel):
    symbol: str
