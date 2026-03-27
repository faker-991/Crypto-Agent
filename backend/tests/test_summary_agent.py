from app.agents.summary_agent import SummaryAgent
from app.schemas.task_result import TaskResult


def test_summary_agent_builds_final_answer_and_execution_summary() -> None:
    agent = SummaryAgent()

    result = agent.summarize(
        task_results=[
            TaskResult(
                task_id="task-research",
                task_type="research",
                agent="ResearchAgent",
                status="success",
                payload={"asset": "SUI", "summary": "SUI research summary"},
                summary="SUI research summary",
                evidence_sufficient=True,
            ),
            TaskResult(
                task_id="task-kline",
                task_type="kline",
                agent="KlineAgent",
                status="insufficient",
                payload={"asset": "SUI", "summary": "SUI kline summary", "missing_information": ["market data unavailable"]},
                summary="SUI kline summary",
                evidence_sufficient=False,
                missing_information=["market data unavailable"],
            ),
        ],
        payload={"asset": "SUI"},
    )

    assert result["asset"] == "SUI"
    assert "SUI" in result["final_answer"]
    assert result["execution_summary"]["asset"] == "SUI"
    assert len(result["execution_summary"]["task_summaries"]) == 2
    assert result["execution_summary"]["agent_sufficiency"]["ResearchAgent"] is True
    assert result["execution_summary"]["agent_sufficiency"]["KlineAgent"] is False
    assert "证据不足" in result["final_answer"]
