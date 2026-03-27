from pathlib import Path

from app.services.trace_log_service import TraceLogService


class RecentSummaryService:
    def __init__(self, memory_root: Path) -> None:
        self.trace_log_service = TraceLogService(memory_root)

    def get_recent(self, limit: int = 3) -> list[str]:
        summaries: list[str] = []
        for trace in self.trace_log_service.list_traces(limit=limit * 3):
            payload = self.trace_log_service.read_trace(trace["id"])
            execution_summary = payload.get("execution_summary") or {}
            summary = execution_summary.get("summary")
            if not summary:
                answer = execution_summary.get("answer")
                if isinstance(answer, str) and answer.strip():
                    summary = answer
            if isinstance(summary, str) and summary.strip():
                summaries.append(summary.strip())
            if len(summaries) >= limit:
                break
        return summaries
