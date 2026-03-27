import json
from pathlib import Path

from app.services.asset_memory_service import AssetMemoryService
from app.services.bootstrap_service import BootstrapService
from app.services.journal_memory_service import JournalMemoryService
from app.services.profile_memory_service import ProfileMemoryService
from app.services.session_state_service import SessionStateService
from app.services.trace_log_service import TraceLogService


class ContextAssemblyService:
    def __init__(self, memory_root: Path) -> None:
        self.memory_root = memory_root
        BootstrapService(memory_root).ensure_files()
        self.asset_memory_service = AssetMemoryService(memory_root)
        self.profile_memory_service = ProfileMemoryService(memory_root)
        self.session_state_service = SessionStateService(memory_root)
        self.journal_memory_service = JournalMemoryService(memory_root)
        self.trace_log_service = TraceLogService(memory_root)

    def build_planner_context(self, user_query: str) -> dict:
        return {
            "query": user_query,
            "session": self.session_state_service.read_state().model_dump(),
            "profile": self.profile_memory_service.get_profile(),
        }

    def build_research_context(self, asset: str, intent: str) -> dict:
        symbol = asset.upper()
        return {
            "intent": intent,
            "session": self.session_state_service.read_state().model_dump(),
            "profile": self.profile_memory_service.get_profile(),
            "asset": {
                "symbol": symbol,
                "content": self.asset_memory_service.get_thesis_content(symbol),
                "metadata": self.asset_memory_service.get_asset_metadata(symbol),
            },
            "watchlist": self._read_watchlist(),
            "recent_journal": self.journal_memory_service.list_recent_entries(limit=5),
        }

    def build_kline_context(self, asset: str, timeframes: list[str]) -> dict:
        symbol = asset.upper()
        return {
            "session": self.session_state_service.read_state().model_dump(),
            "profile": self.profile_memory_service.get_profile(),
            "asset": {
                "symbol": symbol,
                "metadata": self.asset_memory_service.get_asset_metadata(symbol),
            },
            "timeframes": timeframes,
            "recent_traces": self._read_recent_trace_details(limit=5, asset=symbol),
        }

    def _read_watchlist(self) -> dict:
        path = self.memory_root / "watchlist.json"
        if not path.exists():
            return {"assets": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def _read_recent_trace_details(self, limit: int, asset: str | None = None) -> list[dict]:
        items = []
        for summary in self.trace_log_service.list_traces(limit=limit):
            payload = self.trace_log_service.read_trace(summary["id"])
            if asset:
                execution = payload.get("execution_summary") or {}
                legacy_route = payload.get("route") or {}
                if execution.get("asset") != asset and legacy_route.get("payload", {}).get("asset") != asset:
                    continue
            items.append(
                {
                    "timestamp": payload.get("timestamp"),
                    "user_query": payload.get("user_query"),
                    "legacy_route": payload.get("route"),
                    "execution_summary": payload.get("execution_summary"),
                }
            )
        return items
