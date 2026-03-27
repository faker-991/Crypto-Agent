from pathlib import Path

from app.agents.kline_agent import KlineAgent
from app.agents.research_agent import ResearchAgent
from app.agents.summary_agent import SummaryAgent
from app.schemas.plan import Plan
from app.schemas.task_result import TaskResult


class Executor:
    def __init__(
        self,
        memory_root: Path,
        research_agent: ResearchAgent | None = None,
        kline_agent: KlineAgent | None = None,
        summary_agent: SummaryAgent | None = None,
    ) -> None:
        self.research_agent = research_agent or ResearchAgent(memory_root)
        self.kline_agent = kline_agent or KlineAgent(memory_root)
        self.summary_agent = summary_agent or SummaryAgent()

    def execute(self, plan: Plan) -> list[TaskResult]:
        results: list[TaskResult] = []
        results_by_id: dict[str, TaskResult] = {}

        for task in plan.tasks:
            if task.task_type == "research":
                payload = self.research_agent.execute("protocol_due_diligence", task.slots)
                result = TaskResult(
                    task_id=task.task_id,
                    task_type=task.task_type,
                    agent=self.research_agent.name,
                    status=payload.get("status", "success"),
                    payload=payload,
                    summary=payload.get("summary"),
                    evidence_sufficient=payload.get("evidence_sufficient"),
                    missing_information=payload.get("missing_information", []),
                    tool_calls=payload.get("tool_calls", []),
                    rounds_used=payload.get("rounds_used"),
                )
            elif task.task_type == "kline":
                payload = self.kline_agent.execute("kline_scorecard", task.slots)
                result = TaskResult(
                    task_id=task.task_id,
                    task_type=task.task_type,
                    agent=self.kline_agent.name,
                    status=payload.get("status", "success"),
                    payload=payload,
                    summary=payload.get("summary"),
                    evidence_sufficient=payload.get("evidence_sufficient"),
                    missing_information=payload.get("missing_information", []),
                    tool_calls=payload.get("tool_calls", []),
                    rounds_used=payload.get("rounds_used"),
                )
            elif task.task_type == "summary":
                dependency_results = [
                    results_by_id[task_id].model_dump()
                    for task_id in task.depends_on
                    if task_id in results_by_id
                ]
                payload = self.summary_agent.summarize(dependency_results, task.slots)
                result = TaskResult(
                    task_id=task.task_id,
                    task_type=task.task_type,
                    agent=self.summary_agent.name,
                    status=payload.get("status", "success"),
                    payload=payload,
                    summary=payload.get("summary"),
                    evidence_sufficient=payload.get("evidence_sufficient"),
                    missing_information=payload.get("missing_information", []),
                    tool_calls=payload.get("tool_calls", []),
                    rounds_used=payload.get("rounds_used"),
                )
            else:
                raise ValueError(f"Unsupported task type: {task.task_type}")

            results.append(result)
            results_by_id[task.task_id] = result

        return results
