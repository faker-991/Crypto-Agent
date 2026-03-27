from app.orchestrator.planner import Planner
from app.schemas.agentic_plan import PlannerDecision
from app.schemas.planning_context import (
    Capabilities,
    Constraints,
    MemoryContext,
    PlanningContext,
    RecentContext,
    SessionContext,
    UserRequest,
)


class StubPlannerLLMService:
    def __init__(self, decision: PlannerDecision | None) -> None:
        self.decision = decision
        self.calls = 0

    def is_configured(self) -> bool:
        return True

    def plan(self, context: PlanningContext) -> PlannerDecision | None:
        self.calls += 1
        return self.decision


def _build_context(
    raw_query: str,
    request_type: str = "single_task",
    current_asset: str | None = None,
) -> PlanningContext:
    return PlanningContext(
        user_request=UserRequest(
            raw_query=raw_query,
            normalized_goal=raw_query,
            request_type=request_type,
        ),
        session_context=SessionContext(
            current_asset=current_asset,
            last_intent=None,
            last_timeframes=[],
            active_topic=None,
        ),
        recent_context=RecentContext(recent_task_summaries=[]),
        memory_context=MemoryContext(relevant_memories=[]),
        capabilities=Capabilities(
            available_agents=["ResearchAgent", "KlineAgent", "SummaryAgent"],
            available_tools={},
        ),
        constraints=Constraints(),
    )


def test_planner_creates_single_kline_task_for_simple_kline_query() -> None:
    context = _build_context("看下 BTC 4h")

    plan = Planner().plan(context)

    assert plan.mode == "single_task"
    assert plan.decision_mode == "kline_only"
    assert plan.needs_clarification is False
    assert len(plan.tasks) == 2
    assert plan.tasks[0].task_type == "kline"
    assert plan.tasks[0].slots["asset"] == "BTC"
    assert plan.tasks[0].slots["timeframes"] == ["4h"]
    assert plan.tasks[1].task_type == "summary"
    assert plan.tasks[1].depends_on == ["task-kline"]


def test_planner_creates_single_research_task_for_basic_research_query() -> None:
    context = _build_context("帮我研究一下 SUI 基本面")

    plan = Planner().plan(context)

    assert plan.mode == "single_task"
    assert plan.decision_mode == "research_only"
    assert len(plan.tasks) == 2
    assert plan.tasks[0].task_type == "research"
    assert plan.tasks[0].slots["asset"] == "SUI"
    assert plan.tasks[1].task_type == "summary"
    assert plan.tasks[1].depends_on == ["task-research"]


def test_planner_creates_research_kline_and_summary_for_multi_task_query() -> None:
    context = _build_context(
        "分析 SUI 值不值得继续拿，顺便看下周线和4h走势",
        request_type="multi_task",
    )

    plan = Planner().plan(context)

    assert plan.mode == "multi_task"
    assert plan.decision_mode == "mixed_analysis"
    assert [task.task_type for task in plan.tasks] == ["research", "kline", "summary"]
    assert plan.tasks[0].slots["asset"] == "SUI"
    assert plan.tasks[1].slots["timeframes"] == ["1w", "4h"]
    assert plan.tasks[2].depends_on == ["task-research", "task-kline"]


def test_planner_uses_session_asset_for_follow_up_query() -> None:
    context = _build_context(
        "那它周线呢",
        request_type="follow_up",
        current_asset="SUI",
    )

    plan = Planner().plan(context)

    assert plan.needs_clarification is False
    assert plan.decision_mode == "kline_only"
    assert len(plan.tasks) == 2
    assert plan.tasks[0].task_type == "kline"
    assert plan.tasks[0].slots["asset"] == "SUI"
    assert plan.tasks[0].slots["timeframes"] == ["1w"]
    assert plan.tasks[1].task_type == "summary"


def test_planner_prefers_explicit_query_asset_over_session_asset() -> None:
    context = _build_context("我想看 BTC 现在是否适合入手现货", current_asset="ETH")

    plan = Planner().plan(context)

    assert plan.needs_clarification is False
    assert plan.tasks[0].slots["asset"] == "BTC"
    assert plan.tasks[1].slots["asset"] == "BTC"


def test_planner_requests_clarification_when_asset_is_missing() -> None:
    context = _build_context("看下 4h")

    plan = Planner().plan(context)

    assert plan.needs_clarification is True
    assert plan.decision_mode == "clarify"
    assert plan.clarification_question is not None
    assert "资产" in plan.clarification_question
    assert plan.tasks == []


def test_planner_uses_llm_decision_when_available() -> None:
    context = _build_context("帮我看下 BTC 日线和周线走势")
    llm_service = StubPlannerLLMService(
        PlannerDecision(
            mode="kline_only",
            goal="Analyze BTC spot structure on 1d and 1w",
            requires_clarification=False,
            clarification_question=None,
            agents_to_invoke=["KlineAgent", "SummaryAgent"],
            inputs={"asset": "BTC", "timeframes": ["1d", "1w"], "market_type": "spot"},
            reasoning_summary="The user explicitly asked for timeframe-based technical analysis.",
        )
    )

    plan = Planner(llm_service=llm_service).plan(context)

    assert llm_service.calls == 1
    assert plan.decision_mode == "kline_only"
    assert plan.reasoning_summary == "The user explicitly asked for timeframe-based technical analysis."
    assert plan.agents_to_invoke == ["KlineAgent", "SummaryAgent"]
    assert plan.tasks[0].slots["asset"] == "BTC"
    assert plan.tasks[0].slots["timeframes"] == ["1d", "1w"]
    assert plan.tasks[1].task_type == "summary"


def test_planner_overrides_llm_asset_when_query_mentions_explicit_asset() -> None:
    context = _build_context("帮我看下 BTC 日线走势", current_asset="ETH")
    llm_service = StubPlannerLLMService(
        PlannerDecision(
            mode="kline_only",
            goal="Analyze ETH spot structure on 1d",
            requires_clarification=False,
            clarification_question=None,
            agents_to_invoke=["KlineAgent", "SummaryAgent"],
            inputs={"asset": "ETH", "timeframes": ["1d"], "market_type": "spot"},
            reasoning_summary="The user explicitly asked for timeframe-based technical analysis.",
        )
    )

    plan = Planner(llm_service=llm_service).plan(context)

    assert plan.tasks[0].slots["asset"] == "BTC"
    assert plan.tasks[1].slots["asset"] == "BTC"


def test_planner_falls_back_to_safe_rules_when_llm_returns_none() -> None:
    context = _build_context("帮我研究一下 SUI 基本面")
    llm_service = StubPlannerLLMService(None)

    plan = Planner(llm_service=llm_service).plan(context)

    assert llm_service.calls == 1
    assert plan.decision_mode == "research_only"
    assert len(plan.tasks) == 2
    assert plan.tasks[0].task_type == "research"
    assert plan.tasks[1].task_type == "summary"
