from __future__ import annotations

from collections import OrderedDict
from typing import Any


STAGE_ORDER = {"research": 0, "kline": 1, "summary": 2}
STATUS_ORDER = {"failed": 3, "insufficient": 2, "success": 1, "skipped": 0, "unknown": -1}


def build_readable_workflow(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    timeline: list[dict[str, Any]] = []

    planner_stage = _build_planner_stage(payload)
    if planner_stage is not None:
        timeline.append(planner_stage)

    grouped_results = _group_task_results(payload.get("task_results"))
    for group in grouped_results:
        stage = _build_agent_stage(group)
        if stage is not None:
            timeline.append(stage)

    final_conclusion = _build_final_conclusion(
        status=payload.get("status"),
        execution_summary=payload.get("execution_summary"),
        final_answer=payload.get("final_answer"),
        grouped_results=grouped_results,
    )

    if not timeline and final_conclusion is None:
        return None

    return {"final_conclusion": final_conclusion, "timeline": timeline}


def _build_planner_stage(payload: dict[str, Any]) -> dict[str, Any] | None:
    plan = _as_dict(payload.get("plan"))
    legacy_route = _as_dict(payload.get("legacy_route")) or _as_dict(payload.get("route"))

    if not plan and not legacy_route:
        return None

    did: list[str] = []
    actual_calls: list[str] = []
    found: list[str] = []
    conclusion: list[str] = []
    meta: dict[str, Any] = {}

    if plan:
        goal = _as_non_empty_string(plan.get("goal"))
        mode = _as_non_empty_string(plan.get("decision_mode")) or _as_non_empty_string(plan.get("mode"))
        planner_source = _as_non_empty_string(plan.get("planner_source"))
        if goal and mode:
            did.append(f"围绕 {goal} 规划了 {mode} 执行流程。")
        elif goal:
            did.append(f"围绕 {goal} 制定了执行流程。")
        tasks = _as_list(plan.get("tasks"))
        if tasks:
            task_titles = [_as_non_empty_string(_as_dict(task).get("title")) for task in tasks]
            task_titles = [title for title in task_titles if title]
            if task_titles:
                did.append("规划步骤：" + " -> ".join(task_titles) + "。")
        reasoning_summary = _as_non_empty_string(plan.get("reasoning_summary"))
        if reasoning_summary:
            found.append(reasoning_summary)
        agents_to_invoke = [agent for agent in (_as_list(plan.get("agents_to_invoke"))) if isinstance(agent, str) and agent]
        for agent in agents_to_invoke:
            actual_calls.append(f"准备调用 {agent}，负责{_describe_agent(agent)}。")
        clarification_question = _as_non_empty_string(plan.get("clarification_question"))
        if clarification_question:
            conclusion.append(clarification_question)
        elif agents_to_invoke:
            conclusion.append("执行路径：" + " -> ".join(agents_to_invoke) + "。")
        if planner_source:
            meta["planner_source"] = planner_source
        if mode:
            meta["decision_mode"] = mode
        meta["legacy"] = False
        return {
            "kind": "planner",
            "title": "Planner",
            "status": "success",
            "did": _dedupe(did),
            "actual_calls": _dedupe(actual_calls),
            "found": _dedupe(found),
            "conclusion": _dedupe(conclusion),
            "meta": meta,
        }

    route_type = _as_non_empty_string(legacy_route.get("type"))
    route_agent = _as_non_empty_string(legacy_route.get("agent"))
    if route_type:
        did.append(f"旧版路由选择了 {route_type}。")
    if route_agent:
        found.append(f"旧版规划路径来自 {route_agent}。")
    meta["legacy"] = True
    if route_type:
        meta["route_type"] = route_type
    return {
        "kind": "planner",
        "title": "Planner",
        "status": "unknown",
        "did": _dedupe(did),
        "actual_calls": [],
        "found": _dedupe(found),
        "conclusion": [],
        "meta": meta,
    }


def _group_task_results(task_results: Any) -> list[dict[str, Any]]:
    if not isinstance(task_results, list):
        return []

    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for raw_result in task_results:
        result = _as_dict(raw_result)
        if not result:
            continue
        task_type = _as_non_empty_string(result.get("task_type")) or "unknown"
        grouped.setdefault(task_type, []).append(result)

    ordered_items = sorted(grouped.items(), key=lambda item: (STAGE_ORDER.get(item[0], 999), item[0]))
    return [{"task_type": task_type, "results": results} for task_type, results in ordered_items]


def _build_agent_stage(group: dict[str, Any]) -> dict[str, Any] | None:
    task_type = _as_non_empty_string(group.get("task_type")) or "unknown"
    results = [item for item in _as_list(group.get("results")) if isinstance(item, dict)]
    if not results:
        return None

    if task_type == "research":
        return _build_research_stage(results)
    if task_type == "kline":
        return _build_kline_stage(results)
    if task_type == "summary":
        return _build_summary_stage(results)
    return _build_unknown_stage(task_type, results)


def _build_research_stage(results: list[dict[str, Any]]) -> dict[str, Any]:
    did: list[str] = []
    actual_calls: list[str] = []
    found: list[str] = []
    conclusion: list[str] = []
    meta: dict[str, Any] = {}

    for result in results:
        payload = _as_dict(result.get("payload"))
        asset = _as_non_empty_string(payload.get("asset")) or _as_non_empty_string(result.get("asset"))
        if asset:
            did.append(f"研究了 {asset} 的基本面与外部信息。")
        did.extend(_summaries_from_tool_calls(_as_list(result.get("tool_calls")), "research"))
        actual_calls.extend(_actual_calls_from_tool_calls(_as_list(result.get("tool_calls")), "research"))
        market_context = _as_dict(payload.get("market_context"))
        if market_context:
            found.append("拿到了该资产的市场背景信息。")
        protocol_context = _as_dict(payload.get("protocol_context"))
        if protocol_context:
            found.append("拿到了该资产的协议背景信息。")
        for key, label in (("bull_case", "看多逻辑"), ("bear_case", "看空逻辑"), ("risks", "风险点")):
            values = [item for item in _as_list(payload.get(key)) if isinstance(item, str) and item.strip()]
            found.extend([f"{label}：{value}" for value in values])
        summary = _as_non_empty_string(result.get("summary"))
        if summary:
            conclusion.append(summary)
        conclusion.extend(_missing_information_lines(result))
        loop_meta = _build_research_loop_meta(payload)
        if loop_meta:
            meta.update(loop_meta)

    return {
        "kind": "research",
        "title": "ResearchAgent",
        "status": _combine_status(results),
        "did": _dedupe(did),
        "actual_calls": _dedupe(actual_calls) or ["没有捕获到结构化调用细节。"],
        "found": _dedupe(found),
        "conclusion": _dedupe(conclusion),
        "meta": meta,
    }


def _build_kline_stage(results: list[dict[str, Any]]) -> dict[str, Any]:
    did: list[str] = []
    actual_calls: list[str] = []
    found: list[str] = []
    conclusion: list[str] = []
    meta: dict[str, Any] = {}

    for result in results:
        payload = _as_dict(result.get("payload"))
        asset = _as_non_empty_string(payload.get("asset"))
        market_type = _as_non_empty_string(payload.get("market_type"))
        timeframes = [item for item in _as_list(payload.get("timeframes")) if isinstance(item, str) and item]
        if asset and market_type and timeframes:
            did.append(f"分析了 {asset} 在 {market_type} 市场的 {', '.join(timeframes)} 周期。")
        elif asset and timeframes:
            did.append(f"分析了 {asset} 的 {', '.join(timeframes)} 周期。")
        actual_calls.extend(_actual_calls_from_tool_calls(_as_list(result.get("tool_calls")), "kline"))
        provenance = _as_dict(payload.get("kline_provenance"))
        for timeframe, entry in provenance.items():
            entry_dict = _as_dict(entry)
            endpoint_summary = _as_dict(entry_dict.get("endpoint_summary"))
            endpoint = _as_non_empty_string(endpoint_summary.get("endpoint"))
            url = _as_non_empty_string(endpoint_summary.get("url"))
            if endpoint and url:
                found.append(f"{timeframe}：从 {endpoint} 拉取了市场数据（{url}）。")
            degraded_reason = _as_non_empty_string(entry_dict.get("degraded_reason"))
            if degraded_reason:
                found.append(f"{timeframe}：因为 {degraded_reason} 进入降级状态。")
        indicator_snapshots = _as_dict(payload.get("indicator_snapshots"))
        for timeframe, snapshot in indicator_snapshots.items():
            snapshot_dict = _as_dict(snapshot)
            status = _as_non_empty_string(snapshot_dict.get("status"))
            missing = [item for item in _as_list(snapshot_dict.get("missing_indicators")) if isinstance(item, str) and item]
            if status:
                found.append(f"{timeframe}：指标计算状态为 {status}。")
            if missing:
                found.append(f"{timeframe}：缺少指标 {', '.join(missing)}。")
        analyses = _as_dict(payload.get("analyses"))
        for timeframe, analysis in analyses.items():
            conclusion_text = _as_non_empty_string(_as_dict(analysis).get("conclusion"))
            if conclusion_text:
                conclusion.append(f"{timeframe}：{conclusion_text}")
        summary = _as_non_empty_string(result.get("summary"))
        if summary:
            conclusion.append(summary)
        conclusion.extend(_missing_information_lines(result))
        if market_type:
            meta["market_type"] = market_type
        if timeframes:
            meta["timeframes"] = timeframes

    return {
        "kind": "kline",
        "title": "KlineAgent",
        "status": _combine_status(results),
        "did": _dedupe(did),
        "actual_calls": _dedupe(actual_calls) or ["没有捕获到结构化调用细节。"],
        "found": _dedupe(found),
        "conclusion": _dedupe(conclusion),
        "meta": meta,
    }


def _build_summary_stage(results: list[dict[str, Any]]) -> dict[str, Any]:
    did: list[str] = []
    actual_calls: list[str] = []
    found: list[str] = []
    conclusion: list[str] = []

    for result in results:
        payload = _as_dict(result.get("payload"))
        execution_summary = _as_dict(payload.get("execution_summary"))
        did.append("把前序 agent 的结果合并成最终回答。")
        actual_calls.extend(_actual_calls_from_tool_calls(_as_list(result.get("tool_calls")), "summary"))
        agent_sufficiency = _as_dict(execution_summary.get("agent_sufficiency"))
        for agent, ok in agent_sufficiency.items():
            found.append(f"{agent}：{'证据充足' if ok else '证据不足'}。")
        task_summaries = [item for item in _as_list(execution_summary.get("task_summaries")) if isinstance(item, str) and item]
        found.extend(task_summaries)
        final_answer = _as_non_empty_string(payload.get("final_answer"))
        if final_answer:
            conclusion.append(final_answer)
        summary = _as_non_empty_string(result.get("summary"))
        if summary:
            conclusion.append(summary)
        conclusion.extend(_missing_information_lines(result))

    return {
        "kind": "summary",
        "title": "SummaryAgent",
        "status": _combine_status(results),
        "did": _dedupe(did),
        "actual_calls": _dedupe(actual_calls) or ["没有捕获到结构化调用细节。"],
        "found": _dedupe(found),
        "conclusion": _dedupe(conclusion),
        "meta": {},
    }


def _build_unknown_stage(task_type: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    conclusion = [_as_non_empty_string(result.get("summary")) for result in results]
    return {
        "kind": "unknown",
        "title": task_type,
        "status": _combine_status(results),
        "did": [f"执行了暂未专门适配的任务类型：{task_type}。"],
        "actual_calls": ["没有捕获到结构化调用细节。"],
        "found": [],
        "conclusion": _dedupe([item for item in conclusion if item]),
        "meta": {"task_type": task_type},
    }


def _build_final_conclusion(
    *,
    status: Any,
    execution_summary: Any,
    final_answer: Any,
    grouped_results: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if _as_non_empty_string(status) == "clarify":
        return None

    summary_dict = _as_dict(execution_summary)
    final_answer_text = _as_non_empty_string(final_answer)
    summary_text = _as_non_empty_string(summary_dict.get("summary"))
    if not summary_text:
        task_summaries = [item for item in _as_list(summary_dict.get("task_summaries")) if isinstance(item, str) and item]
        if task_summaries:
            summary_text = " ".join(task_summaries)
    if not summary_text:
        summary_text = final_answer_text

    missing_information = [item for item in _as_list(summary_dict.get("missing_information")) if isinstance(item, str) and item]
    degraded_reason = _as_non_empty_string(_as_dict(summary_dict.get("provenance")).get("degraded_reason"))
    evidence_sufficient = _derive_evidence_sufficient(summary_dict, grouped_results)

    if not any([summary_text, final_answer_text, missing_information, degraded_reason, evidence_sufficient is not None]):
        return None

    return {
        "status": _as_non_empty_string(status) or "unknown",
        "final_answer": final_answer_text,
        "summary": summary_text,
        "evidence_sufficient": evidence_sufficient,
        "missing_information": missing_information,
        "degraded_reason": degraded_reason,
    }


def _derive_evidence_sufficient(summary_dict: dict[str, Any], grouped_results: list[dict[str, Any]]) -> bool | None:
    agent_sufficiency = _as_dict(summary_dict.get("agent_sufficiency"))
    if agent_sufficiency:
        return all(bool(value) for value in agent_sufficiency.values())

    for group in reversed(grouped_results):
        for result in reversed(group.get("results", [])):
            if isinstance(result, dict) and isinstance(result.get("evidence_sufficient"), bool):
                return result["evidence_sufficient"]
    return None


def _actual_calls_from_tool_calls(tool_calls: list[Any], stage_kind: str) -> list[str]:
    actual_calls: list[str] = []
    for tool_call in tool_calls:
        tool_call_dict = _as_dict(tool_call)
        if not tool_call_dict:
            continue
        tool = _as_non_empty_string(tool_call_dict.get("tool"))
        if not tool:
            continue
        if stage_kind == "research" and tool == "search_web":
            query = _as_non_empty_string(_as_dict(tool_call_dict.get("input")).get("query"))
            if query:
                actual_calls.append(f'搜索了关键词“{query}”。')
        elif stage_kind == "research" and tool == "fetch_page":
            url = _as_non_empty_string(_as_dict(tool_call_dict.get("input")).get("url"))
            title = _as_non_empty_string(_as_dict(tool_call_dict.get("output")).get("title"))
            if url and title:
                actual_calls.append(f"抓取了页面 {url}（{title}）。")
            elif url:
                actual_calls.append(f"抓取了页面 {url}。")
        elif stage_kind == "kline" and tool == "get_klines":
            timeframe = _as_non_empty_string(tool_call_dict.get("timeframe"))
            output = _as_dict(tool_call_dict.get("output"))
            source = _as_non_empty_string(output.get("source"))
            market_type = _as_non_empty_string(output.get("market_type"))
            if timeframe and source and market_type:
                actual_calls.append(f"拉取了 {market_type} 市场 {timeframe} 周期的 {source} K 线。")
        elif stage_kind == "kline" and tool == "compute_indicators":
            timeframe = _as_non_empty_string(tool_call_dict.get("timeframe"))
            output = _as_dict(tool_call_dict.get("output"))
            status = _as_non_empty_string(output.get("status"))
            missing = [item for item in _as_list(output.get("missing_indicators")) if isinstance(item, str) and item]
            if timeframe and status:
                suffix = f"；缺少 {', '.join(missing)}" if missing else ""
                actual_calls.append(f"计算了 {timeframe} 周期指标，状态为 {status}{suffix}。")
        else:
            actual_calls.append(f"调用了工具 {tool}。")
    return actual_calls


def _summaries_from_tool_calls(tool_calls: list[Any], stage_kind: str) -> list[str]:
    del stage_kind
    return [] if tool_calls else []


def _missing_information_lines(result: dict[str, Any]) -> list[str]:
    missing_information = [item for item in _as_list(result.get("missing_information")) if isinstance(item, str) and item]
    return [f"证据缺口：{item}" for item in missing_information]


def _build_research_loop_meta(payload: dict[str, Any]) -> dict[str, Any]:
    loop_entries = [item for item in _as_list(payload.get("agent_loop")) if isinstance(item, dict)]
    if not loop_entries:
        return {}

    steps: list[str] = []
    for entry in loop_entries:
        round_number = entry.get("round")
        decision_reason = _as_non_empty_string(_as_dict(entry.get("decision")).get("reason")) or "按当前观察继续执行。"
        action = _as_dict(entry.get("action"))
        tool = _as_non_empty_string(action.get("tool")) or "unknown"
        action_input = _as_dict(action.get("input"))
        result = _as_dict(entry.get("result"))
        state_update = _as_dict(entry.get("state_update"))
        termination_reason = _as_non_empty_string(_as_dict(entry.get("termination")).get("reason"))

        line = f"第 {round_number} 轮：因为{decision_reason}"
        if tool == "search_web":
            query = _as_non_empty_string(action_input.get("query"))
            result_count = result.get("result_count")
            if query:
                line += f" 调用了 search_web，搜索“{query}”"
            if result_count is not None:
                line += f"，拿到 {result_count} 条候选结果"
        elif tool == "fetch_page":
            url = _as_non_empty_string(action_input.get("url"))
            title = _as_non_empty_string(result.get("title"))
            if url:
                line += f" 抓取了页面 {url}"
            if title:
                line += f"（{title}）"
        elif tool == "finish":
            line += " 执行 finish 结束循环"
        else:
            line += f" 调用了 {tool}"

        new_findings = [item for item in _as_list(state_update.get("new_findings")) if isinstance(item, str) and item]
        if new_findings:
            line += f"，新增信息：{'；'.join(new_findings)}"
        if termination_reason:
            line += f"；{termination_reason}"
        steps.append(line + "。")

    return {
        "loop_rounds": len(loop_entries),
        "termination_reason": _as_non_empty_string(payload.get("termination_reason")),
        "loop_steps": steps,
    }


def _combine_status(results: list[dict[str, Any]]) -> str:
    statuses = [_as_non_empty_string(result.get("status")) or "unknown" for result in results]
    return max(statuses, key=lambda item: STATUS_ORDER.get(item, -1))


def _describe_agent(agent: str) -> str:
    if agent == "ResearchAgent":
        return "外部资料与基本面研究"
    if agent == "KlineAgent":
        return "市场结构与指标分析"
    if agent == "SummaryAgent":
        return "最终汇总"
    return "执行"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_non_empty_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return None


def _dedupe(items: list[str]) -> list[str]:
    seen: OrderedDict[str, None] = OrderedDict()
    for item in items:
        if item:
            seen[item] = None
    return list(seen.keys())
