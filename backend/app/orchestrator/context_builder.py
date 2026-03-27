from pathlib import Path

from app.schemas.planning_context import (
    Capabilities,
    Constraints,
    MemoryContext,
    PlanningContext,
    RecentContext,
    SessionContext,
    UserRequest,
)
from app.services.recent_summary_service import RecentSummaryService
from app.services.session_state_service import SessionStateService


FOLLOW_UP_MARKERS = ("那它", "它周线", "它日线", "再结合", "再看看")


class ContextBuilder:
    def __init__(self, memory_root: Path) -> None:
        self.session_state_service = SessionStateService(memory_root)
        self.recent_summary_service = RecentSummaryService(memory_root)

    def build(self, query: str, conversation_id: str | None = None) -> PlanningContext:
        session_state = self.session_state_service.read_state()
        return PlanningContext(
            user_request=UserRequest(
                raw_query=query,
                normalized_goal=self._normalize_goal(query, session_state.current_asset),
                request_type=self._infer_request_type(query),
            ),
            session_context=SessionContext(
                current_asset=session_state.current_asset,
                last_intent=session_state.last_intent,
                last_timeframes=session_state.last_timeframes,
                active_topic=session_state.current_task,
            ),
            recent_context=RecentContext(
                recent_task_summaries=self.recent_summary_service.get_recent(limit=3)
            ),
            memory_context=MemoryContext(relevant_memories=[]),
            capabilities=Capabilities(
                available_agents=["ResearchAgent", "KlineAgent", "SummaryAgent"],
                available_tools={
                    "research": ["web_search_tool", "rag_retrieval_tool"],
                    "kline": ["binance_kline_tool", "indicator_tool", "kline_summary_tool"],
                    "summary": [],
                },
            ),
            constraints=Constraints(),
        )

    def _normalize_goal(self, query: str, current_asset: str | None) -> str:
        normalized = query.strip()
        if current_asset and "它" in normalized:
            normalized = normalized.replace("它", current_asset)
        return normalized

    def _infer_request_type(self, query: str) -> str:
        lowered = query.strip().lower()
        if any(marker.lower() in lowered for marker in FOLLOW_UP_MARKERS):
            return "follow_up"
        if any(token in lowered for token in ("顺便", "结合", "同时", "再")):
            return "multi_task"
        return "single_task"
