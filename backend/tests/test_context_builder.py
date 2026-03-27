from pathlib import Path

from app.orchestrator.context_builder import ContextBuilder
from app.services.session_state_service import SessionStateService
from app.services.trace_log_service import TraceLogService


def test_context_builder_copies_query_and_session_state(tmp_path: Path) -> None:
    SessionStateService(tmp_path).write_state(
        {
            "current_asset": "BTC",
            "last_intent": "kline_analysis",
            "last_timeframes": ["4h"],
            "last_report_type": None,
            "recent_assets": ["BTC"],
            "current_task": "checking BTC 4h",
            "last_skill": "kline_scorecard",
            "last_agent": "KlineAgent",
        }
    )

    context = ContextBuilder(tmp_path).build(query="看下 BTC 4h")

    assert context.user_request.raw_query == "看下 BTC 4h"
    assert context.session_context.current_asset == "BTC"
    assert context.session_context.last_intent == "kline_analysis"
    assert context.session_context.last_timeframes == ["4h"]
    assert "SummaryAgent" in context.capabilities.available_agents
    assert context.constraints.must_clarify_if_asset_missing is True


def test_context_builder_limits_recent_task_summaries_to_latest_three(tmp_path: Path) -> None:
    trace_log_service = TraceLogService(tmp_path)
    trace_log_service.write_trace(
        user_query="trace 1",
        status="execute",
        plan={"goal": "trace 1", "mode": "single_task", "needs_clarification": False, "tasks": []},
        task_results=[],
        execution_summary={"summary": "summary 1"},
    )
    trace_log_service.write_trace(
        user_query="trace 2",
        status="execute",
        plan={"goal": "trace 2", "mode": "single_task", "needs_clarification": False, "tasks": []},
        task_results=[],
        execution_summary={"summary": "summary 2"},
    )
    trace_log_service.write_trace(
        user_query="trace 3",
        status="execute",
        plan={"goal": "trace 3", "mode": "single_task", "needs_clarification": False, "tasks": []},
        task_results=[],
        execution_summary={"summary": "summary 3"},
    )
    trace_log_service.write_trace(
        user_query="trace 4",
        status="execute",
        plan={"goal": "trace 4", "mode": "single_task", "needs_clarification": False, "tasks": []},
        task_results=[],
        execution_summary={"summary": "summary 4"},
    )

    context = ContextBuilder(tmp_path).build(query="再看看")

    assert context.recent_context.recent_task_summaries == ["summary 4", "summary 3", "summary 2"]


def test_context_builder_defaults_memory_context_and_marks_follow_up_queries(tmp_path: Path) -> None:
    SessionStateService(tmp_path).write_state(
        {
            "current_asset": "SUI",
            "last_intent": "asset_due_diligence",
            "last_timeframes": ["1d"],
            "last_report_type": None,
            "recent_assets": ["SUI"],
            "current_task": "evaluating SUI",
            "last_skill": "protocol_due_diligence",
            "last_agent": "ResearchAgent",
        }
    )

    context = ContextBuilder(tmp_path).build(query="那它周线呢")

    assert context.user_request.request_type == "follow_up"
    assert context.memory_context.relevant_memories == []
    assert context.user_request.normalized_goal
