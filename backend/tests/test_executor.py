from pathlib import Path

from app.orchestrator.executor import Executor
from app.schemas.plan import Plan
from app.schemas.task import Task


class StubResearchAgent:
    name = "ResearchAgent"

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def execute(self, skill: str, payload: dict) -> dict:
        self.calls.append((skill, payload))
        return {
            "agent": self.name,
            "asset": payload["asset"],
            "status": "success",
            "evidence_sufficient": True,
            "summary": f"{payload['asset']} research summary",
            "tool_calls": [{"tool": "search_web"}],
            "rounds_used": 2,
            "source": "research",
        }


class StubKlineAgent:
    name = "KlineAgent"

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def execute(self, skill: str, payload: dict) -> dict:
        self.calls.append((skill, payload))
        return {
            "agent": self.name,
            "asset": payload["asset"],
            "status": "success",
            "evidence_sufficient": True,
            "summary": f"{payload['asset']} kline summary",
            "timeframes": payload["timeframes"],
            "tool_calls": [{"tool": "get_klines"}],
            "rounds_used": 2,
            "source": "kline",
        }


class StubSummaryAgent:
    name = "SummaryAgent"

    def __init__(self) -> None:
        self.calls: list[tuple[list[dict], dict]] = []

    def summarize(self, task_results: list[dict], payload: dict) -> dict:
        self.calls.append((task_results, payload))
        return {
            "asset": payload["asset"],
            "summary": f"{payload['asset']} combined summary",
            "final_answer": f"{payload['asset']} combined answer",
            "execution_summary": {
                "asset": payload["asset"],
                "agent_sufficiency": {"ResearchAgent": True, "KlineAgent": True},
            },
        }


def test_executor_routes_research_and_kline_tasks_to_their_agents(tmp_path: Path) -> None:
    research_agent = StubResearchAgent()
    kline_agent = StubKlineAgent()
    summary_agent = StubSummaryAgent()
    executor = Executor(
        memory_root=tmp_path,
        research_agent=research_agent,
        kline_agent=kline_agent,
        summary_agent=summary_agent,
    )
    plan = Plan(
        goal="Analyze BTC",
        mode="single_task",
        tasks=[
            Task(
                task_id="task-research",
                task_type="research",
                title="Research BTC",
                slots={"asset": "BTC"},
            ),
            Task(
                task_id="task-kline",
                task_type="kline",
                title="Check BTC 4h",
                slots={"asset": "BTC", "timeframes": ["4h"]},
            ),
        ],
    )

    results = executor.execute(plan)

    assert len(results) == 2
    assert research_agent.calls == [("protocol_due_diligence", {"asset": "BTC"})]
    assert kline_agent.calls == [("kline_scorecard", {"asset": "BTC", "timeframes": ["4h"]})]
    assert [result.task_type for result in results] == ["research", "kline"]
    assert results[0].evidence_sufficient is True
    assert results[1].tool_calls == [{"tool": "get_klines"}]


def test_executor_runs_summary_after_its_dependencies(tmp_path: Path) -> None:
    research_agent = StubResearchAgent()
    kline_agent = StubKlineAgent()
    summary_agent = StubSummaryAgent()
    executor = Executor(
        memory_root=tmp_path,
        research_agent=research_agent,
        kline_agent=kline_agent,
        summary_agent=summary_agent,
    )
    plan = Plan(
        goal="Analyze SUI",
        mode="multi_task",
        tasks=[
            Task(
                task_id="task-research",
                task_type="research",
                title="Research SUI",
                slots={"asset": "SUI"},
            ),
            Task(
                task_id="task-kline",
                task_type="kline",
                title="Check SUI 1w and 4h",
                slots={"asset": "SUI", "timeframes": ["1w", "4h"]},
            ),
            Task(
                task_id="task-summary",
                task_type="summary",
                title="Summarize SUI",
                slots={"asset": "SUI"},
                depends_on=["task-research", "task-kline"],
            ),
        ],
    )

    results = executor.execute(plan)

    assert [result.task_id for result in results] == ["task-research", "task-kline", "task-summary"]
    assert len(summary_agent.calls) == 1
    task_results, payload = summary_agent.calls[0]
    assert [item["task_id"] for item in task_results] == ["task-research", "task-kline"]
    assert payload == {"asset": "SUI"}
    assert results[-1].summary == "SUI combined summary"
    assert results[-1].payload["execution_summary"]["agent_sufficiency"]["ResearchAgent"] is True
