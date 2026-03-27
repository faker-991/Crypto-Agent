from app.services.readable_trace_formatter import build_readable_workflow


def test_build_readable_workflow_for_mixed_analysis_trace() -> None:
    payload = {
        "status": "execute",
        "plan": {
            "goal": "Analyze BTC",
            "mode": "multi_task",
            "decision_mode": "mixed_analysis",
            "reasoning_summary": "Need both external research and price structure.",
            "planner_source": "fallback",
            "agents_to_invoke": ["ResearchAgent", "KlineAgent", "SummaryAgent"],
            "tasks": [
                {
                    "task_id": "research-1",
                    "task_type": "research",
                    "title": "Research BTC",
                    "slots": {"asset": "BTC"},
                    "depends_on": [],
                },
                {
                    "task_id": "kline-1",
                    "task_type": "kline",
                    "title": "Review BTC price action",
                    "slots": {"asset": "BTC", "market_type": "spot", "timeframes": ["4h", "1d"]},
                    "depends_on": [],
                },
                {
                    "task_id": "summary-1",
                    "task_type": "summary",
                    "title": "Summarize BTC",
                    "slots": {"asset": "BTC"},
                    "depends_on": ["research-1", "kline-1"],
                },
            ],
        },
        "task_results": [
            {
                "task_id": "research-1",
                "task_type": "research",
                "agent": "ResearchAgent",
                "status": "success",
                "summary": "BTC remains worth monitoring.",
                "evidence_sufficient": True,
                "missing_information": [],
                "tool_calls": [
                    {
                        "tool": "search_web",
                        "input": {"query": "BTC crypto tokenomics roadmap catalysts risks"},
                    },
                    {
                        "tool": "fetch_page",
                        "input": {"url": "https://example.com/btc-report"},
                        "output": {"title": "BTC report"},
                    },
                ],
                "payload": {
                    "asset": "BTC",
                    "bull_case": ["Institutional demand remains durable."],
                    "bear_case": ["Macro tightening can cap upside."],
                    "risks": ["ETF flows can reverse quickly."],
                    "market_context": {"market_cap": 100},
                    "protocol_context": {"category": "store of value"},
                },
            },
            {
                "task_id": "kline-1",
                "task_type": "kline",
                "agent": "KlineAgent",
                "status": "insufficient",
                "summary": "BTC spot market view. 4h: trend intact. 1d: data incomplete.",
                "evidence_sufficient": False,
                "missing_information": ["Indicator coverage incomplete for 1d: rsi"],
                "tool_calls": [
                    {
                        "tool": "get_klines",
                        "timeframe": "4h",
                        "output": {"source": "binance", "market_type": "spot", "candles": 200},
                    },
                    {
                        "tool": "compute_indicators",
                        "timeframe": "1d",
                        "output": {"status": "partial", "missing_indicators": ["rsi"]},
                    },
                ],
                "payload": {
                    "asset": "BTC",
                    "market_type": "spot",
                    "timeframes": ["4h", "1d"],
                    "analyses": {
                        "4h": {"conclusion": "Trend intact."},
                        "1d": {"conclusion": "Data incomplete."},
                    },
                    "market_summary": {
                        "market_type": "spot",
                        "timeframes": ["4h", "1d"],
                        "analysis_summary": "4h intact; 1d incomplete",
                    },
                    "indicator_snapshots": {"1d": {"status": "partial", "missing_indicators": ["rsi"]}},
                    "kline_provenance": {
                        "4h": {
                            "source": "binance",
                            "market_type": "spot",
                            "endpoint_summary": {
                                "endpoint": "klines",
                                "url": "https://api.binance.com/api/v3/klines",
                            },
                        },
                        "1d": {
                            "source": "binance",
                            "market_type": "spot",
                            "endpoint_summary": {
                                "endpoint": "klines",
                                "url": "https://api.binance.com/api/v3/klines",
                            },
                            "degraded_reason": "indicator coverage incomplete",
                        },
                    },
                },
            },
            {
                "task_id": "summary-1",
                "task_type": "summary",
                "agent": "SummaryAgent",
                "status": "insufficient",
                "summary": "BTC combined summary",
                "evidence_sufficient": False,
                "missing_information": ["Indicator coverage incomplete for 1d: rsi"],
                "payload": {
                    "asset": "BTC",
                    "final_answer": "BTC trend is constructive but 1d evidence is incomplete.",
                    "execution_summary": {
                        "asset": "BTC",
                        "summary": "BTC trend is constructive but 1d evidence is incomplete.",
                        "missing_information": ["Indicator coverage incomplete for 1d: rsi"],
                        "agent_sufficiency": {"ResearchAgent": True, "KlineAgent": False},
                        "provenance": {"degraded_reason": "indicator coverage incomplete"},
                    },
                },
            },
        ],
        "execution_summary": {
            "asset": "BTC",
            "summary": "BTC trend is constructive but 1d evidence is incomplete.",
            "missing_information": ["Indicator coverage incomplete for 1d: rsi"],
            "agent_sufficiency": {"ResearchAgent": True, "KlineAgent": False},
            "provenance": {"degraded_reason": "indicator coverage incomplete"},
        },
        "final_answer": "BTC trend is constructive but 1d evidence is incomplete.",
    }

    workflow = build_readable_workflow(payload)

    assert workflow["final_conclusion"]["final_answer"] == "BTC trend is constructive but 1d evidence is incomplete."
    assert workflow["final_conclusion"]["summary"] == "BTC trend is constructive but 1d evidence is incomplete."
    assert workflow["final_conclusion"]["evidence_sufficient"] is False
    assert workflow["timeline"][0]["kind"] == "planner"
    assert workflow["timeline"][1]["kind"] == "research"
    assert "BTC crypto tokenomics roadmap catalysts risks" in workflow["timeline"][1]["actual_calls"][0]
    assert workflow["timeline"][2]["kind"] == "kline"
    assert "4h, 1d" in " ".join(workflow["timeline"][2]["did"])
    assert workflow["timeline"][3]["kind"] == "summary"


def test_build_readable_workflow_summary_falls_back_to_task_summaries() -> None:
    payload = {
        "status": "execute",
        "plan": {"goal": "Analyze BTC", "mode": "single_task", "needs_clarification": False, "tasks": []},
        "task_results": [],
        "execution_summary": {
            "task_summaries": ["Research says demand is stable.", "Kline says 4h trend is intact."]
        },
        "final_answer": None,
    }

    workflow = build_readable_workflow(payload)

    assert workflow["final_conclusion"]["summary"] == "Research says demand is stable. Kline says 4h trend is intact."


def test_build_readable_workflow_for_clarify_trace() -> None:
    payload = {
        "status": "clarify",
        "plan": {
            "goal": "Clarify the asset",
            "mode": "single_task",
            "decision_mode": "clarify",
            "needs_clarification": True,
            "clarification_question": "你想看哪个标的，是现货还是合约？",
            "planner_source": "fallback",
            "agents_to_invoke": [],
            "tasks": [],
        },
        "task_results": [],
        "execution_summary": None,
        "final_answer": "你想看哪个标的，是现货还是合约？",
    }

    workflow = build_readable_workflow(payload)

    assert workflow["final_conclusion"] is None
    assert len(workflow["timeline"]) == 1
    assert workflow["timeline"][0]["kind"] == "planner"
    assert "你想看哪个标的，是现货还是合约？" in " ".join(workflow["timeline"][0]["conclusion"])


def test_build_readable_workflow_for_legacy_route_trace() -> None:
    payload = {
        "route": {"type": "clarify", "agent": "RouterAgent"},
        "status": "clarify",
        "user_query": "看下 4h",
        "task_results": [],
        "execution_summary": None,
        "events": [],
    }

    workflow = build_readable_workflow(payload)

    assert workflow["timeline"][0]["kind"] == "planner"
    assert workflow["timeline"][0]["meta"]["legacy"] is True
    assert "RouterAgent" in " ".join(workflow["timeline"][0]["found"])


def test_build_readable_workflow_ignores_malformed_tool_calls() -> None:
    payload = {
        "status": "execute",
        "plan": {"goal": "Analyze BTC", "mode": "single_task", "needs_clarification": False, "tasks": []},
        "task_results": [
            {
                "task_id": "research-1",
                "task_type": "research",
                "agent": "ResearchAgent",
                "status": "success",
                "summary": "BTC remains worth monitoring.",
                "tool_calls": ["bad", 123, None],
                "payload": {"asset": "BTC"},
            }
        ],
        "execution_summary": {"asset": "BTC"},
        "final_answer": "BTC remains worth monitoring.",
    }

    workflow = build_readable_workflow(payload)

    assert workflow["timeline"][1]["kind"] == "research"
    assert workflow["timeline"][1]["actual_calls"] == ["没有捕获到结构化调用细节。"]


def test_build_readable_workflow_includes_research_loop_rounds() -> None:
    payload = {
        "status": "execute",
        "plan": {
            "goal": "Analyze BTC",
            "mode": "single_task",
            "decision_mode": "research_only",
            "tasks": [
                {
                    "task_id": "research-1",
                    "task_type": "research",
                    "title": "Research BTC",
                    "slots": {"asset": "BTC"},
                    "depends_on": [],
                },
                {
                    "task_id": "summary-1",
                    "task_type": "summary",
                    "title": "Summarize BTC",
                    "slots": {"asset": "BTC"},
                    "depends_on": ["research-1"],
                },
            ],
        },
        "task_results": [
            {
                "task_id": "research-1",
                "task_type": "research",
                "agent": "ResearchAgent",
                "status": "success",
                "summary": "BTC remains worth monitoring.",
                "evidence_sufficient": True,
                "missing_information": [],
                "payload": {
                    "asset": "BTC",
                    "agent_loop": [
                        {
                            "round": 1,
                            "observation": {"missing_information": ["tokenomics evidence missing"]},
                            "decision": {"reason": "先搜催化剂和风险来源。"},
                            "action": {
                                "tool": "search_web",
                                "input": {"query": "BTC crypto tokenomics roadmap catalysts risks"},
                            },
                            "result": {"status": "success", "result_count": 2},
                            "state_update": {"new_urls": ["https://example.com/btc-roadmap"]},
                        },
                        {
                            "round": 2,
                            "observation": {"candidate_url": "https://example.com/btc-roadmap"},
                            "decision": {"reason": "抓取最相关页面补证据。"},
                            "action": {
                                "tool": "fetch_page",
                                "input": {"url": "https://example.com/btc-roadmap"},
                            },
                            "result": {"status": "success", "title": "BTC roadmap"},
                            "state_update": {"new_findings": ["路线图和风险已补充"]},
                            "termination": {"reason": "证据已足够，停止循环。"},
                        },
                    ],
                    "termination_reason": "证据已足够，停止循环。",
                },
            }
        ],
        "execution_summary": {"asset": "BTC", "summary": "BTC remains worth monitoring."},
        "final_answer": "BTC remains worth monitoring.",
    }

    workflow = build_readable_workflow(payload)

    research_stage = workflow["timeline"][1]
    assert research_stage["kind"] == "research"
    assert research_stage["meta"]["loop_rounds"] == 2
    assert research_stage["meta"]["termination_reason"] == "证据已足够，停止循环。"
    assert len(research_stage["meta"]["loop_steps"]) == 2
    assert "第 1 轮" in research_stage["meta"]["loop_steps"][0]
    assert "search_web" in research_stage["meta"]["loop_steps"][0]
    assert "停止循环" in research_stage["meta"]["loop_steps"][1]
