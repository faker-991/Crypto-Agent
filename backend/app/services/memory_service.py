import json
from pathlib import Path

from app.schemas.memory import (
    AssetMemoryIndexResponse,
    AssetMemoryItemResponse,
    ContextPreviewResponse,
    JournalEntryResponse,
    JournalListResponse,
    MemorySummaryResponse,
    ProfileResponse,
    ThesisResponse,
)
from app.schemas.watchlist import (
    Watchlist,
    WatchlistAddRequest,
    WatchlistItem,
    WatchlistRemoveRequest,
)
from app.services.asset_memory_service import AssetMemoryService
from app.services.bootstrap_service import BootstrapService
from app.services.context_assembly_service import ContextAssemblyService
from app.services.journal_memory_service import JournalMemoryService
from app.services.profile_memory_service import ProfileMemoryService


class MemoryService:
    def __init__(self, memory_root: Path) -> None:
        self.memory_root = memory_root
        BootstrapService(memory_root).ensure_files()
        self.asset_memory_service = AssetMemoryService(memory_root)
        self.profile_memory_service = ProfileMemoryService(memory_root)
        self.journal_memory_service = JournalMemoryService(memory_root)
        self.context_assembly_service = ContextAssemblyService(memory_root)

    def get_watchlist(self) -> Watchlist:
        payload = json.loads((self.memory_root / "watchlist.json").read_text(encoding="utf-8"))
        return Watchlist.model_validate(payload)

    def add_watchlist_item(self, request: WatchlistAddRequest) -> Watchlist:
        watchlist = self.get_watchlist()
        existing = next((item for item in watchlist.assets if item.symbol == request.symbol), None)
        if existing:
            existing.status = request.status
            existing.priority = request.priority
        else:
            watchlist.assets.append(
                WatchlistItem(
                    symbol=request.symbol.upper(),
                    status=request.status,
                    priority=request.priority,
                )
            )
        self._write_json("watchlist.json", watchlist.model_dump())
        return watchlist

    def get_thesis(self, symbol: str) -> ThesisResponse:
        content = self.asset_memory_service.get_thesis_content(symbol)
        return ThesisResponse(symbol=symbol.upper(), content=content)

    def remove_watchlist_item(self, request: WatchlistRemoveRequest) -> Watchlist:
        watchlist = self.get_watchlist()
        watchlist.assets = [
            item for item in watchlist.assets if item.symbol.upper() != request.symbol.upper()
        ]
        self._write_json("watchlist.json", watchlist.model_dump())
        return watchlist

    def get_memory_summary(self) -> MemorySummaryResponse:
        content = (self.memory_root / "MEMORY.md").read_text(encoding="utf-8")
        return MemorySummaryResponse(content=content)

    def get_profile(self) -> ProfileResponse:
        return ProfileResponse(profile=self.profile_memory_service.get_profile())

    def list_assets(self) -> AssetMemoryIndexResponse:
        symbols = set()
        for path in self.asset_memory_service.assets_root.glob("*"):
            if path.suffix in {".md", ".json"}:
                symbols.add(path.stem.upper())
        for path in self.asset_memory_service.legacy_theses_root.glob("*.md"):
            symbols.add(path.stem.upper())
        items = [
            AssetMemoryItemResponse(
                symbol=symbol,
                has_thesis=bool(self.asset_memory_service.get_thesis_content(symbol).strip()),
                metadata=self.asset_memory_service.get_asset_metadata(symbol),
            )
            for symbol in sorted(symbols)
        ]
        return AssetMemoryIndexResponse(items=items)

    def list_journal_entries(self, limit: int = 10) -> JournalListResponse:
        return JournalListResponse(
            items=[
                JournalEntryResponse(**entry)
                for entry in self.journal_memory_service.list_recent_entries(limit=limit)
            ]
        )

    def get_context_preview(
        self,
        kind: str = "planner",
        query: str = "",
        asset: str | None = None,
        intent: str | None = None,
        timeframes: list[str] | None = None,
    ) -> ContextPreviewResponse:
        normalized_kind = kind.lower()
        if normalized_kind == "research":
            context = self.context_assembly_service.build_research_context(
                asset=asset or "",
                intent=intent or "asset_due_diligence",
            )
        elif normalized_kind == "kline":
            context = self.context_assembly_service.build_kline_context(
                asset=asset or "",
                timeframes=timeframes or [],
            )
        elif normalized_kind == "planner":
            context = self.context_assembly_service.build_planner_context(user_query=query)
        else:
            normalized_kind = "planner"
            context = self.context_assembly_service.build_planner_context(user_query=query)
        return ContextPreviewResponse(kind=normalized_kind, context=context)

    def _write_json(self, filename: str, payload: dict) -> None:
        (self.memory_root / filename).write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
