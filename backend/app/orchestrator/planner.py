import re
from typing import Any

from app.orchestrator.planner_normalizer import normalize_inputs
from app.schemas.agentic_plan import PlannerDecision
from app.schemas.plan import Plan
from app.schemas.planning_context import PlanningContext
from app.schemas.task import Task
from app.services.planner_llm_service import PlannerLLMService


ASSET_PATTERN = re.compile(r"\b(BTC|ETH|SOL|SUI|AAVE|ENA|ARB|OP|BNB|DOGE|XRP)\b", re.IGNORECASE)


class Planner:
    def __init__(self, llm_service: PlannerLLMService | None = None) -> None:
        self.llm_service = llm_service or PlannerLLMService()

    def plan(self, context: PlanningContext) -> Plan:
        fallback_reason = "not_configured"
        llm_decision = None
        if self.llm_service.is_configured():
            llm_decision = self.llm_service.plan(context)
            fallback_reason = "llm_returned_none"
        if llm_decision is not None:
            return self._build_plan_from_decision(
                context,
                llm_decision,
                planner_source="llm",
                planner_fallback_reason=None,
            )
        fallback_decision = self._fallback_decision(context)
        return self._build_plan_from_decision(
            context,
            fallback_decision,
            planner_source="fallback",
            planner_fallback_reason=fallback_reason,
        )

    def extract_explicit_asset(self, query: str) -> str | None:
        return self._extract_asset(query)

    def _fallback_decision(self, context: PlanningContext) -> PlannerDecision:
        query = context.user_request.raw_query
        request_type = context.user_request.request_type
        explicit_asset = self._extract_asset(query)
        asset = explicit_asset or context.session_context.current_asset
        wants_kline = self._is_kline_query(query, request_type)
        wants_research = self._is_research_query(query, request_type)
        timeframes = self._extract_timeframes(query)

        if request_type == "follow_up":
            wants_kline = wants_kline or bool(timeframes)
            wants_research = wants_research and "基本面" in query

        if wants_kline and asset is None and context.constraints.must_clarify_if_asset_missing:
            return PlannerDecision(
                mode="clarify",
                goal=context.user_request.normalized_goal,
                requires_clarification=True,
                clarification_question="你想分析哪个资产？",
                agents_to_invoke=["SummaryAgent"],
            )

        if wants_research and asset is None and context.constraints.must_clarify_if_asset_missing:
            return PlannerDecision(
                mode="clarify",
                goal=context.user_request.normalized_goal,
                requires_clarification=True,
                clarification_question="你想研究哪个资产？",
                agents_to_invoke=["SummaryAgent"],
            )

        if wants_research and wants_kline:
            return PlannerDecision(
                mode="mixed_analysis",
                goal=context.user_request.normalized_goal,
                agents_to_invoke=["ResearchAgent", "KlineAgent", "SummaryAgent"],
                inputs={"asset": asset, "timeframes": timeframes or ["1d"], "market_type": "spot"},
                reasoning_summary="The query asks for both fundamental research and price-action analysis.",
            )

        if wants_kline:
            return PlannerDecision(
                mode="kline_only",
                goal=context.user_request.normalized_goal,
                agents_to_invoke=["KlineAgent", "SummaryAgent"],
                inputs={"asset": asset, "timeframes": timeframes or ["1d"], "market_type": "spot"},
                reasoning_summary="The query is primarily about chart structure or timeframe-based analysis.",
            )

        if wants_research:
            return PlannerDecision(
                mode="research_only",
                goal=context.user_request.normalized_goal,
                agents_to_invoke=["ResearchAgent", "SummaryAgent"],
                inputs={"asset": asset},
                reasoning_summary="The query is primarily about fundamentals, catalysts, or risk.",
            )

        return PlannerDecision(
            mode="clarify",
            goal=context.user_request.normalized_goal,
            requires_clarification=True,
            clarification_question="你想做项目研究、K线分析，还是结合两者一起看？",
            agents_to_invoke=["SummaryAgent"],
            reasoning_summary="The request does not clearly indicate whether research or technical analysis is needed.",
        )

    def _build_plan_from_decision(
        self,
        context: PlanningContext,
        decision: PlannerDecision,
        *,
        planner_source: str,
        planner_fallback_reason: str | None,
    ) -> Plan:
        normalized_inputs = normalize_inputs(decision.inputs if isinstance(decision.inputs, dict) else None)
        explicit_asset = self._extract_asset(context.user_request.raw_query)
        decision_asset = normalized_inputs.get("asset")
        asset = explicit_asset or decision_asset or context.session_context.current_asset
        explicit_timeframes = self._extract_timeframes(context.user_request.raw_query)
        timeframes = normalized_inputs.get("timeframes")
        if not isinstance(timeframes, list) or not timeframes:
            timeframes = explicit_timeframes or context.session_context.last_timeframes or ["1d"]
        else:
            timeframes = self._merge_timeframes(timeframes, explicit_timeframes)
        market_type = normalized_inputs.get("market_type")
        market_type = market_type or "spot"
        research_focus = self._extract_research_focus(context.user_request.raw_query, normalized_inputs)

        if decision.mode == "clarify" or decision.requires_clarification:
            return Plan(
                goal=decision.goal,
                mode="single_task",
                decision_mode="clarify",
                needs_clarification=True,
                clarification_question=decision.clarification_question or "可以再具体一点吗？",
                reasoning_summary=decision.reasoning_summary,
                agents_to_invoke=decision.agents_to_invoke or ["SummaryAgent"],
                planner_inputs=normalized_inputs,
                planner_source=planner_source,
                planner_fallback_reason=planner_fallback_reason,
                tasks=[],
            )

        if decision.mode == "research_only" and asset:
            return Plan(
                goal=decision.goal,
                mode="single_task",
                decision_mode="research_only",
                reasoning_summary=decision.reasoning_summary,
                agents_to_invoke=decision.agents_to_invoke or ["ResearchAgent", "SummaryAgent"],
                planner_inputs={**normalized_inputs, "asset": asset},
                planner_source=planner_source,
                planner_fallback_reason=planner_fallback_reason,
                tasks=[
                    Task(
                        task_id="task-research",
                        task_type="research",
                        title=f"Research {asset}",
                        slots={"asset": asset, "focus": research_focus},
                    ),
                    Task(
                        task_id="task-summary",
                        task_type="summary",
                        title=f"Summarize {asset}",
                        slots={"asset": asset},
                        depends_on=["task-research"],
                    ),
                ],
            )

        if decision.mode == "kline_only" and asset:
            return Plan(
                goal=decision.goal,
                mode="single_task",
                decision_mode="kline_only",
                reasoning_summary=decision.reasoning_summary,
                agents_to_invoke=decision.agents_to_invoke or ["KlineAgent", "SummaryAgent"],
                planner_inputs={**normalized_inputs, "asset": asset, "timeframes": timeframes, "market_type": market_type},
                planner_source=planner_source,
                planner_fallback_reason=planner_fallback_reason,
                tasks=[
                    Task(
                        task_id="task-kline",
                        task_type="kline",
                        title=f"Analyze {asset} kline",
                        slots={"asset": asset, "timeframes": timeframes, "market_type": market_type},
                    ),
                    Task(
                        task_id="task-summary",
                        task_type="summary",
                        title=f"Summarize {asset}",
                        slots={"asset": asset},
                        depends_on=["task-kline"],
                    ),
                ],
            )

        if decision.mode == "mixed_analysis" and asset:
            return Plan(
                goal=decision.goal,
                mode="multi_task",
                decision_mode="mixed_analysis",
                reasoning_summary=decision.reasoning_summary,
                agents_to_invoke=decision.agents_to_invoke or ["ResearchAgent", "KlineAgent", "SummaryAgent"],
                planner_inputs={**normalized_inputs, "asset": asset, "timeframes": timeframes, "market_type": market_type},
                planner_source=planner_source,
                planner_fallback_reason=planner_fallback_reason,
                tasks=[
                    Task(
                        task_id="task-research",
                        task_type="research",
                        title=f"Research {asset}",
                        slots={"asset": asset, "focus": research_focus},
                    ),
                    Task(
                        task_id="task-kline",
                        task_type="kline",
                        title=f"Analyze {asset} kline",
                        slots={"asset": asset, "timeframes": timeframes, "market_type": market_type},
                    ),
                    Task(
                        task_id="task-summary",
                        task_type="summary",
                        title=f"Summarize {asset}",
                        slots={"asset": asset},
                        depends_on=["task-research", "task-kline"],
                    ),
                ],
            )

        return self._build_plan_from_decision(
            context,
            PlannerDecision(
                mode="clarify",
                goal=decision.goal or context.user_request.normalized_goal,
                requires_clarification=True,
                clarification_question="可以再具体一点吗？你想看研究、K线，还是两者一起看？",
                agents_to_invoke=["SummaryAgent"],
                reasoning_summary="The planner decision did not include enough structured inputs to execute safely.",
            ),
            planner_source=planner_source,
            planner_fallback_reason=planner_fallback_reason,
        )

    def _extract_asset(self, query: str) -> str | None:
        match = ASSET_PATTERN.search(query)
        return match.group(1).upper() if match else None

    def _extract_timeframes(self, query: str) -> list[str]:
        timeframes: list[str] = []
        lowered = query.lower()
        if "15m" in lowered:
            timeframes.append("15m")
        if "30m" in lowered:
            timeframes.append("30m")
        if "1h" in lowered or "小时线" in query:
            timeframes.append("1h")
        if "周线" in query:
            timeframes.append("1w")
        if "日线" in query:
            timeframes.append("1d")
        if "4h" in lowered or "4小时线" in query or "四小时线" in query:
            timeframes.append("4h")
        return timeframes

    def _merge_timeframes(self, semantic_timeframes: list[str], explicit_timeframes: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for timeframe in [*semantic_timeframes, *explicit_timeframes]:
            if not isinstance(timeframe, str) or not timeframe or timeframe in seen:
                continue
            seen.add(timeframe)
            merged.append(timeframe)
        return merged

    def _is_kline_query(self, query: str, request_type: str) -> bool:
        lowered = query.lower()
        return request_type == "follow_up" or any(
            token in lowered
            for token in ("k线", "走势", "周线", "日线", "小时线", "1h", "4h", "15m", "30m", "趋势", "现价", "价格", "现货", "入手")
        )

    def _is_research_query(self, query: str, request_type: str) -> bool:
        lowered = query.lower()
        return request_type == "multi_task" and "结合" in query or any(
            token in lowered
            for token in ("基本面", "研究", "值不值得", "尽调", "长期")
        )

    def _extract_research_focus(self, query: str, normalized_inputs: dict[str, Any]) -> list[str]:
        lowered = query.lower()
        focus: list[str] = []
        if any(token in query for token in ("舆情", "情绪", "新闻")) or any(
            token in lowered for token in ("sentiment", "news", "websearch")
        ):
            focus.extend(["sentiment", "news"])
        if any(token in query for token in ("走势", "趋势", "日线", "周线", "小时线")) or any(
            token in lowered for token in ("1h", "4h", "1d", "1w", "trend", "price")
        ):
            focus.append("trend")
        if normalized_inputs.get("analysis_intent") == "entry":
            focus.append("entry")
        deduped: list[str] = []
        seen: set[str] = set()
        for item in focus:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped
