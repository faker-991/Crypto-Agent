from fastapi import APIRouter, Depends

from app.schemas.watchlist import Watchlist, WatchlistAddRequest, WatchlistRemoveRequest
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


def get_memory_service() -> MemoryService:
    raise RuntimeError("memory service dependency is not configured")


@router.get("", response_model=Watchlist)
def read_watchlist(memory_service: MemoryService = Depends(get_memory_service)) -> Watchlist:
    return memory_service.get_watchlist()


@router.post("/add", response_model=Watchlist)
def add_watchlist_item(
    request: WatchlistAddRequest,
    memory_service: MemoryService = Depends(get_memory_service),
) -> Watchlist:
    return memory_service.add_watchlist_item(request)


@router.post("/remove", response_model=Watchlist)
def remove_watchlist_item(
    request: WatchlistRemoveRequest,
    memory_service: MemoryService = Depends(get_memory_service),
) -> Watchlist:
    return memory_service.remove_watchlist_item(request)
