from __future__ import annotations

from app.agents.research_result_assembler import ResearchResultAssembler


def assert_tool_result_like(tool_call: dict) -> None:
    assert isinstance(tool_call, dict)
    assert isinstance(tool_call.get("tool_name"), str) and tool_call["tool_name"]
    assert tool_call.get("status") in {"success", "failed", "degraded"}
    assert isinstance(tool_call.get("server"), str)
    assert isinstance(tool_call.get("domain"), str)
    assert isinstance(tool_call.get("args"), dict)
    assert isinstance(tool_call.get("output"), dict)
    assert isinstance(tool_call.get("output_summary"), dict)
    assert isinstance(tool_call.get("degraded"), bool)
    assert isinstance(tool_call.get("metrics"), dict)


def test_research_result_assembler_derives_summary_findings_risks_catalysts_and_degraded_reason() -> None:
    assembler = ResearchResultAssembler()

    result = assembler.assemble(
        asset="BTC",
        terminal_state={
            "status": "success",
            "termination_reason": "Evidence threshold met.",
            "rounds_used": 3,
            "observations": [],
            "successful_tools": ["search_web", "fetch_page"],
            "failed_tools": [],
            "missing_information": ["Need broader market confirmation."],
            "evidence_status": "sufficient",
        },
        observations=[
            {
                "tool_name": "search_web",
                "status": "success",
                "summary": "4h trend remains constructive.",
                "structured_data": {
                    "findings": ["4h trend remains constructive."],
                    "risks": ["macro regime shift"],
                    "catalysts": ["roadmap update"],
                },
            },
            {
                "tool_name": "get_market_snapshot",
                "status": "success",
                "summary": "market snapshot adds risk context",
                "structured_data": {
                    "findings": ["market_cap=1000000000"],
                    "risks": ["macro regime shift", "execution lag"],
                    "catalysts": [],
                },
            },
            {
                "tool_name": "fetch_page",
                "status": "success",
                "summary": "4h trend remains constructive.",
                "structured_data": {
                    "findings": ["4h trend remains constructive."],
                    "risks": ["ignored research risk"],
                    "catalysts": ["ETF inflow"],
                },
            },
            {
                "tool_name": "fetch_page",
                "status": "failed",
                "summary": "failed result should not count",
                "structured_data": {
                    "findings": ["should not appear"],
                    "risks": ["should not appear"],
                    "catalysts": ["should not appear"],
                },
            },
        ],
        tool_results=[
            {
                "status": "success",
                "tool_name": "search_web",
                "server": "research",
                "domain": "research",
                "args": {"query": "BTC catalysts"},
                "output": {"results": [{"title": "BTC roadmap"}]},
                "output_summary": {"results": [{"title": "BTC roadmap"}]},
                "error": None,
                "reason": None,
                "exception_type": None,
                "degraded": False,
                "metrics": {"input_bytes": 11, "output_bytes": 42},
            },
            {
                "status": "degraded",
                "tool_name": "fetch_page",
                "server": "research",
                "domain": "research",
                "args": {"url": "https://example.com/btc"},
                "output": {},
                "output_summary": {},
                "error": "args_failed_validation",
                "reason": "schema_invalid_args",
                "exception_type": None,
                "degraded": True,
                "metrics": {"input_bytes": 0, "output_bytes": 0},
            },
        ],
    )

    assert result["agent"] == "ResearchAgent"
    assert result["status"] == "success"
    assert result["evidence_status"] == "sufficient"
    assert result["summary"]
    assert result["summary"].startswith("BTC")
    assert result["findings"] == ["4h trend remains constructive.", "market_cap=1000000000"]
    assert "macro regime shift" in result["risks"]
    assert "execution lag" in result["risks"]
    assert "should not appear" not in result["findings"]
    assert "fetch_page failed during evidence collection." not in result["risks"]
    assert "roadmap update" in result["catalysts"]
    assert "ETF inflow" in result["catalysts"]
    assert result["missing_information"] == ["Need broader market confirmation."]
    assert "schema_invalid_args" in (result["degraded_reason"] or "")
    assert result["termination_reason"] == "Evidence threshold met."
    assert result["rounds_used"] == 3
    assert len(result["tool_calls"]) == 2
    assert_tool_result_like(result["tool_calls"][0])


def test_research_result_assembler_prefers_descriptive_research_finding_over_generic_market_metric_in_summary() -> None:
    assembler = ResearchResultAssembler()

    result = assembler.assemble(
        asset="BTC",
        terminal_state={
            "status": "success",
            "termination_reason": "Evidence threshold met.",
            "rounds_used": 2,
            "observations": [],
            "successful_tools": ["get_market_snapshot", "search_web"],
            "failed_tools": [],
            "missing_information": [],
            "evidence_status": "sufficient",
        },
        observations=[
            {
                "tool_name": "get_market_snapshot",
                "status": "success",
                "summary": "Loaded market snapshot.",
                "structured_data": {
                    "findings": ["market_cap=1372609481025"],
                    "risks": [],
                    "catalysts": [],
                },
            },
            {
                "tool_name": "search_web",
                "status": "success",
                "summary": "Fed and Iran headlines pressure risk assets.",
                "structured_data": {
                    "findings": [
                        "Bitcoin rises with risk assets as Trump talks end of Iran war.",
                        "Fed pressure and oil surge keep BTC volatile.",
                    ],
                    "risks": ["iran", "fed", "oil"],
                    "catalysts": ["etf", "ceasefire"],
                },
            },
        ],
        tool_results=[],
    )

    assert result["summary"].startswith("BTC Bitcoin rises with risk assets as Trump talks end of Iran war.")
