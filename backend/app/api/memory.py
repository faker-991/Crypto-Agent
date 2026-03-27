from fastapi import APIRouter, Depends

from app.schemas.memory import (
    AssetMemoryIndexResponse,
    ContextPreviewResponse,
    JournalListResponse,
    MemorySummaryResponse,
    ProfileResponse,
    ThesisResponse,
)
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/api/memory", tags=["memory"])


def get_memory_service() -> MemoryService:
    raise RuntimeError("memory service dependency is not configured")


@router.get("", response_model=MemorySummaryResponse)
def read_memory(memory_service: MemoryService = Depends(get_memory_service)) -> MemorySummaryResponse:
    return memory_service.get_memory_summary()


@router.get("/profile", response_model=ProfileResponse)
def read_profile(memory_service: MemoryService = Depends(get_memory_service)) -> ProfileResponse:
    return memory_service.get_profile()


@router.get("/assets", response_model=AssetMemoryIndexResponse)
def read_assets(memory_service: MemoryService = Depends(get_memory_service)) -> AssetMemoryIndexResponse:
    return memory_service.list_assets()


@router.get("/journal", response_model=JournalListResponse)
def read_journal(
    limit: int = 10,
    memory_service: MemoryService = Depends(get_memory_service),
) -> JournalListResponse:
    return memory_service.list_journal_entries(limit=limit)


@router.get("/context-preview", response_model=ContextPreviewResponse)
def read_context_preview(
    kind: str = "planner",
    query: str = "",
    asset: str | None = None,
    intent: str | None = None,
    timeframes: list[str] | None = None,
    memory_service: MemoryService = Depends(get_memory_service),
) -> ContextPreviewResponse:
    return memory_service.get_context_preview(
        kind=kind,
        query=query,
        asset=asset,
        intent=intent,
        timeframes=timeframes,
    )


@router.get("/thesis/{symbol}", response_model=ThesisResponse)
def read_thesis(
    symbol: str,
    memory_service: MemoryService = Depends(get_memory_service),
) -> ThesisResponse:
    return memory_service.get_thesis(symbol)
