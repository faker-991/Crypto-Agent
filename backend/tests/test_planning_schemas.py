from app.schemas.plan import Plan
from app.schemas.planner_response import PlannerExecutionResponse
from app.schemas.planning_context import (
    Capabilities,
    Constraints,
    MemoryContext,
    PlanningContext,
    RecentContext,
    SessionContext,
    UserRequest,
)
from app.schemas.task import Task
from app.schemas.task_result import TaskResult


def test_planning_context_accepts_session_recent_memory_and_capability_fields() -> None:
    context = PlanningContext(
        user_request=UserRequest(
            raw_query="看下 BTC 4h",
            normalized_goal="analyze BTC on 4h",
            request_type="single_task",
        ),
        session_context=SessionContext(
            current_asset="BTC",
            last_intent="kline_analysis",
            last_timeframes=["4h"],
            active_topic="BTC price action",
        ),
        recent_context=RecentContext(recent_task_summaries=["BTC 1d trend was still constructive"]),
        memory_context=MemoryContext(relevant_memories=["BTC remains core watchlist"]),
        capabilities=Capabilities(
            available_agents=["ResearchAgent", "KlineAgent", "SummaryAgent"],
            available_tools={"kline": ["binance_kline_tool"], "research": ["web_search_tool"]},
        ),
        constraints=Constraints(),
    )

    assert context.user_request.raw_query == "看下 BTC 4h"
    assert context.session_context.current_asset == "BTC"
    assert context.recent_context.recent_task_summaries == ["BTC 1d trend was still constructive"]
    assert context.memory_context.relevant_memories == ["BTC remains core watchlist"]
    assert context.capabilities.available_agents == ["ResearchAgent", "KlineAgent", "SummaryAgent"]
    assert context.constraints.must_clarify_if_asset_missing is True


def test_task_supports_research_kline_and_summary_types() -> None:
    research_task = Task(
        task_id="task-research",
        task_type="research",
        title="Research SUI fundamentals",
        slots={"asset": "SUI"},
    )
    kline_task = Task(
        task_id="task-kline",
        task_type="kline",
        title="Check SUI 4h",
        slots={"asset": "SUI", "timeframes": ["4h"]},
    )
    summary_task = Task(
        task_id="task-summary",
        task_type="summary",
        title="Summarize SUI",
        slots={"asset": "SUI"},
        depends_on=["task-research", "task-kline"],
    )

    assert research_task.task_type == "research"
    assert kline_task.task_type == "kline"
    assert summary_task.task_type == "summary"
    assert summary_task.depends_on == ["task-research", "task-kline"]


def test_plan_supports_clarify_mode_with_empty_tasks() -> None:
    plan = Plan(
        goal="clarify the target asset",
        mode="single_task",
        needs_clarification=True,
        clarification_question="你想分析哪个资产？",
        tasks=[],
    )

    assert plan.needs_clarification is True
    assert plan.clarification_question == "你想分析哪个资产？"
    assert plan.tasks == []


def test_planner_execution_response_supports_execute_clarify_and_failed_states() -> None:
    clarify_response = PlannerExecutionResponse(
        status="clarify",
        final_answer="你想分析哪个资产？",
    )
    execute_response = PlannerExecutionResponse(
        status="execute",
        plan=Plan(goal="Analyze BTC", mode="single_task", tasks=[]),
        task_results=[
            TaskResult(
                task_id="task-kline",
                task_type="kline",
                agent="KlineAgent",
                status="success",
                payload={"asset": "BTC"},
                summary="BTC 4h remains range-bound",
            )
        ],
        final_answer="BTC 4h remains range-bound.",
        execution_summary={"asset": "BTC"},
    )
    failed_response = PlannerExecutionResponse(
        status="failed",
        final_answer="Planning failed.",
    )

    assert clarify_response.status == "clarify"
    assert execute_response.status == "execute"
    assert execute_response.task_results[0].agent == "KlineAgent"
    assert failed_response.status == "failed"
