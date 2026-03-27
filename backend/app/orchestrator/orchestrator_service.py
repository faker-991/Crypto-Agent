from pathlib import Path

from app.orchestrator.context_builder import ContextBuilder
from app.orchestrator.executor import Executor
from app.orchestrator.planner import Planner
from app.schemas.execution import ExecutionEvent
from app.schemas.plan import Plan
from app.schemas.planner_response import PlannerExecutionResponse
from app.services.session_state_service import SessionStateService
from app.services.trace_log_service import TraceLogService


class OrchestratorService:
    def __init__(self, memory_root: Path) -> None:
        self.memory_root = memory_root
        self.context_builder = ContextBuilder(memory_root)
        self.planner = Planner()
        self.executor = Executor(memory_root)
        self.session_state_service = SessionStateService(memory_root)
        self.trace_log_service = TraceLogService(memory_root)

    def execute(self, user_query: str, conversation_id: str | None = None) -> dict:
        context = self.context_builder.build(user_query, conversation_id=conversation_id)
        plan = self.planner.plan(context)
        explicit_asset = self.planner.extract_explicit_asset(user_query)
        if explicit_asset:
            self._lock_plan_asset(plan, explicit_asset)
        events = [
            ExecutionEvent(
                name="planner.context_built",
                actor="ContextBuilder",
                detail={"request_type": context.user_request.request_type},
            ).model_dump(),
        ]

        if plan.needs_clarification:
            events.append(
                ExecutionEvent(
                    name="planner.clarify",
                    actor="Planner",
                    detail={"question": plan.clarification_question},
                ).model_dump()
            )
            trace_path = self.trace_log_service.write_trace(
                user_query=user_query,
                status="clarify",
                plan=plan.model_dump(),
                task_results=[],
                execution_summary=None,
                events=events,
            )
            return PlannerExecutionResponse(
                status="clarify",
                plan=plan,
                task_results=[],
                final_answer=plan.clarification_question,
                trace_path=trace_path,
                events=events,
            ).model_dump()

        events.append(
            ExecutionEvent(
                name="planner.plan_created",
                actor="Planner",
                detail={"mode": plan.mode, "task_count": len(plan.tasks)},
            ).model_dump()
        )
        events.append(
            ExecutionEvent(
                name="planner.completed",
                actor="Planner",
                detail={
                    "decision_mode": plan.decision_mode,
                    "planner_source": plan.planner_source,
                    "agents_to_invoke": plan.agents_to_invoke,
                },
            ).model_dump()
        )

        for task in plan.tasks:
            events.append(
                ExecutionEvent(
                    name="executor.task_started",
                    actor="Executor",
                    detail={"task_id": task.task_id, "task_type": task.task_type},
                ).model_dump()
            )

        task_results = self.executor.execute(plan)

        for task_result in task_results:
            events.append(
                ExecutionEvent(
                    name="executor.task_completed",
                    actor=task_result.agent,
                    detail={"task_id": task_result.task_id, "task_type": task_result.task_type},
                ).model_dump()
            )

        execution_summary = self._build_execution_summary(task_results)
        if explicit_asset:
            execution_summary["asset"] = explicit_asset
        execution_summary["decision_mode"] = plan.decision_mode
        execution_summary["planner_source"] = plan.planner_source
        if plan.agents_to_invoke:
            execution_summary["agents_to_invoke"] = plan.agents_to_invoke
        final_answer = self._build_final_answer(task_results)
        if task_results and task_results[-1].task_type == "summary":
            events.append(
                ExecutionEvent(
                    name="summary.completed",
                    actor=task_results[-1].agent,
                    detail={"task_id": task_results[-1].task_id},
                ).model_dump()
            )

        trace_path = self.trace_log_service.write_trace(
            user_query=user_query,
            status="execute",
            plan=plan.model_dump(),
            task_results=[task_result.model_dump() for task_result in task_results],
            execution_summary=execution_summary,
            final_answer=final_answer,
            events=events,
        )
        self._update_session_from_results(task_results)
        return PlannerExecutionResponse(
            status="execute",
            plan=plan,
            task_results=task_results,
            final_answer=final_answer,
            execution_summary=execution_summary,
            trace_path=trace_path,
            events=events,
        ).model_dump()

    def _build_execution_summary(self, task_results: list) -> dict:
        if not task_results:
            return {}
        final_result = task_results[-1]
        payload = final_result.payload if isinstance(final_result.payload, dict) else {}
        summary = {
            "asset": payload.get("asset"),
            "summary": final_result.summary,
            "task_summaries": [result.summary for result in task_results if result.summary],
        }
        if "execution_summary" in payload and isinstance(payload["execution_summary"], dict):
            summary.update(payload["execution_summary"])
        if final_result.task_type == "kline":
            analysis_timeframes = payload.get("timeframes")
            if not isinstance(analysis_timeframes, list) or not analysis_timeframes:
                analyses = payload.get("analyses") or {}
                analysis_timeframes = sorted(analyses.keys()) if isinstance(analyses, dict) else []
            summary["analysis_timeframes"] = analysis_timeframes
            market_summary = payload.get("market_summary")
            if isinstance(market_summary, dict):
                summary["market_summary"] = market_summary
            provenance = payload.get("kline_provenance") or {}
            if isinstance(provenance, dict):
                summary["provenance"] = self._summarize_kline_provenance(provenance)
        return summary

    def _build_final_answer(self, task_results: list) -> str | None:
        if not task_results:
            return None
        payload = task_results[-1].payload
        if isinstance(payload, dict) and payload.get("final_answer"):
            return payload["final_answer"]
        return task_results[-1].summary

    def _update_session_from_results(self, task_results: list) -> None:
        if not task_results:
            return
        state = self.session_state_service.read_state()
        for result in task_results:
            payload = result.payload if isinstance(result.payload, dict) else {}
            asset = payload.get("asset")
            if asset:
                state.current_asset = asset
            if result.task_type == "kline":
                state.last_intent = "kline_analysis"
                timeframes = payload.get("timeframes") or []
                if timeframes:
                    state.last_timeframes = timeframes
            elif result.task_type == "research":
                state.last_intent = "asset_due_diligence"
            state.current_task = result.summary
            state.last_agent = result.agent
        self.session_state_service.write_state(state.model_dump())

    def _summarize_kline_provenance(self, provenance: dict) -> dict:
        entries = [entry for entry in provenance.values() if isinstance(entry, dict)]
        if not entries:
            return {}
        sources = {entry.get("source") for entry in entries if entry.get("source")}
        degraded_reasons = [
            entry.get("degraded_reason")
            for entry in entries
            if isinstance(entry.get("degraded_reason"), str) and entry.get("degraded_reason")
        ]
        return {
            "source": sources.pop() if len(sources) == 1 else "mixed",
            "degraded_reason": "; ".join(degraded_reasons) if degraded_reasons else None,
            "timeframes": list(provenance.keys()),
        }

    def _lock_plan_asset(self, plan: Plan, explicit_asset: str) -> None:
        if plan.planner_inputs is not None:
            plan.planner_inputs["asset"] = explicit_asset
        for task in plan.tasks:
            task.slots["asset"] = explicit_asset
