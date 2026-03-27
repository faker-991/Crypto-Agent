import json
from pathlib import Path

from app.services.context_assembly_service import ContextAssemblyService


def test_build_router_context_includes_session_and_profile(tmp_path: Path) -> None:
    (tmp_path / "session").mkdir(parents=True)
    (tmp_path / "session" / "current_session.json").write_text(
        json.dumps(
            {
                "current_asset": "SUI",
                "last_intent": "asset_due_diligence",
                "last_timeframes": ["1d"],
                "last_report_type": None,
                "recent_assets": ["BTC", "SUI"],
                "current_task": "reviewing SUI",
                "last_skill": "protocol_due_diligence",
                "last_agent": "ResearchAgent",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "profile.json").write_text(
        json.dumps({"investment_style": "mid_long_term", "risk_preference": "medium"}, indent=2) + "\n",
        encoding="utf-8",
    )

    service = ContextAssemblyService(tmp_path)

    context = service.build_router_context("帮我看看 SUI")

    assert context["query"] == "帮我看看 SUI"
    assert context["session"]["current_asset"] == "SUI"
    assert context["profile"]["investment_style"] == "mid_long_term"


def test_build_research_context_includes_asset_and_watchlist(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir(parents=True)
    (tmp_path / "assets" / "SUI.md").write_text("# SUI\n\nResearch body", encoding="utf-8")
    (tmp_path / "assets" / "SUI.json").write_text(
        json.dumps({"asset": "SUI", "status": "watch", "thesis_score": 7.4}, indent=2) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "watchlist.json").write_text(
        json.dumps({"assets": [{"symbol": "SUI", "status": "watch", "priority": 2}]}, indent=2) + "\n",
        encoding="utf-8",
    )

    service = ContextAssemblyService(tmp_path)

    context = service.build_research_context(asset="SUI", intent="asset_due_diligence")

    assert context["intent"] == "asset_due_diligence"
    assert context["asset"]["symbol"] == "SUI"
    assert context["asset"]["metadata"]["thesis_score"] == 7.4
    assert context["watchlist"]["assets"][0]["symbol"] == "SUI"


def test_build_kline_context_includes_recent_trace_summary(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir(parents=True)
    (tmp_path / "assets" / "BTC.json").write_text(
        json.dumps({"asset": "BTC", "status": "core_watch"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "traces").mkdir(parents=True)
    (tmp_path / "traces" / "20260317T000000000000Z.json").write_text(
        json.dumps(
            {
                "timestamp": "20260317T000000000000Z",
                "user_query": "看下 BTC 周线",
                "route": {"type": "execute", "agent": "KlineAgent", "skill": "kline_scorecard"},
                "execution_summary": {"asset": "BTC", "summary": "BTC trend is still constructive."},
                "events": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    service = ContextAssemblyService(tmp_path)

    context = service.build_kline_context(asset="BTC", timeframes=["1d", "1w"])

    assert context["asset"]["symbol"] == "BTC"
    assert context["timeframes"] == ["1d", "1w"]
    assert context["recent_traces"][0]["user_query"] == "看下 BTC 周线"
