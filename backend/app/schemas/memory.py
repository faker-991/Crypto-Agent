from typing import Any

from pydantic import BaseModel


class ThesisResponse(BaseModel):
    symbol: str
    content: str


class MemorySummaryResponse(BaseModel):
    content: str


class ProfileResponse(BaseModel):
    profile: dict[str, Any]


class AssetMemoryItemResponse(BaseModel):
    symbol: str
    has_thesis: bool
    metadata: dict[str, Any]


class AssetMemoryIndexResponse(BaseModel):
    items: list[AssetMemoryItemResponse]


class JournalEntryResponse(BaseModel):
    date: str
    title: str
    path: str


class JournalListResponse(BaseModel):
    items: list[JournalEntryResponse]


class ContextPreviewResponse(BaseModel):
    kind: str
    context: dict[str, Any]
