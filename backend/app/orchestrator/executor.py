from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from app.agents.kline_agent import KlineAgent
from app.agents.research_agent import ResearchAgent
from app.agents.summary_agent import SummaryAgent
from app.schemas.plan import Plan
from app.schemas.task_result import TaskResult

if TYPE_CHECKING:
    from app.clients.mcp_registry import MCPToolRegistry


class Executor:
    def __init__(
        self,
        memory_root: Path,
        research_agent: ResearchAgent | None = None,
        kline_agent: KlineAgent | None = None,
        summary_agent: SummaryAgent | None = None,
        mcp_registry: "MCPToolRegistry | None" = None,
    ) -> None:
        self.research_agent = research_agent or ResearchAgent(memory_root, mcp_registry=mcp_registry)
        self.kline_agent = kline_agent or KlineAgent(memory_root, mcp_registry=mcp_registry)
        self.summary_agent = summary_agent or SummaryAgent()

    def execute(self, plan: Plan) -> list[TaskResult]:
        results: list[TaskResult] = []
        results_by_id: dict[str, TaskResult] = {}

        for task in plan.tasks:
            task_start = datetime.now(timezone.utc)
            if task.task_type == "research":
                payload = self.research_agent.execute("protocol_due_diligence", task.slots)
                task_end = datetime.now(timezone.utc)
                result = self._build_task_result(
                    task_id=task.task_id,
                    task_type=task.task_type,
                    agent=self.research_agent.name,
                    payload=payload,
                    task_start=task_start,
                    task_end=task_end,
                )
            elif task.task_type == "kline":
                payload = self.kline_agent.execute("kline_scorecard", task.slots)
                task_end = datetime.now(timezone.utc)
                result = self._build_task_result(
                    task_id=task.task_id,
                    task_type=task.task_type,
                    agent=self.kline_agent.name,
                    payload=payload,
                    task_start=task_start,
                    task_end=task_end,
                )
            elif task.task_type == "summary":
                dependency_results = [
                    results_by_id[task_id].model_dump()
                    for task_id in task.depends_on
                    if task_id in results_by_id
                ]
                payload = self.summary_agent.summarize(dependency_results, task.slots)
                task_end = datetime.now(timezone.utc)
                result = self._build_task_result(
                    task_id=task.task_id,
                    task_type=task.task_type,
                    agent=self.summary_agent.name,
                    payload=payload,
                    task_start=task_start,
                    task_end=task_end,
                )
            else:
                raise ValueError(f"Unsupported task type: {task.task_type}")

            results.append(result)
            results_by_id[task.task_id] = result

        return results

    def _build_task_result(
        self,
        *,
        task_id: str,
        task_type: str,
        agent: str,
        payload: dict,
        task_start: datetime,
        task_end: datetime,
    ) -> TaskResult:
        evidence_status = payload.get("evidence_status")
        evidence_sufficient = self._derive_evidence_sufficient(payload, evidence_status)
        return TaskResult(
            task_id=task_id,
            task_type=task_type,
            agent=agent,
            status=payload.get("status", "success"),
            payload=payload,
            summary=payload.get("summary"),
            evidence_sufficient=evidence_sufficient,
            evidence_status=evidence_status,
            missing_information=payload.get("missing_information", []),
            degraded_reason=payload.get("degraded_reason"),
            termination_reason=payload.get("termination_reason"),
            tool_calls=payload.get("tool_calls", []),
            rounds_used=payload.get("rounds_used"),
            start_ts=task_start.isoformat().replace("+00:00", "Z"),
            end_ts=task_end.isoformat().replace("+00:00", "Z"),
            duration_ms=(task_end - task_start).total_seconds() * 1000,
        )

    def _derive_evidence_sufficient(self, payload: dict, evidence_status: str | None) -> bool | None:
        if evidence_status == "sufficient":
            return True
        if evidence_status in {"insufficient", "failed"}:
            return False
        if isinstance(payload.get("evidence_sufficient"), bool):
            return payload["evidence_sufficient"]
        return None
