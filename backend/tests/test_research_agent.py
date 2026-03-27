from pathlib import Path

from app.agents.research_agent import ResearchAgent


class StubExternalResearchService:
    def __init__(self, market: dict | None = None, protocol: dict | None = None) -> None:
        self.market = market
        self.protocol = protocol

    def get_asset_context(self, asset: str) -> dict:
        return {
            "market": self.market,
            "protocol": self.protocol,
        }


class StubResearchToolbox:
    def __init__(self, search_results: list[dict] | None = None, pages: dict[str, dict] | None = None) -> None:
        self.search_results = search_results or []
        self.pages = pages or {}

    def search_web(self, query: str) -> dict:
        return {"status": "success", "query": query, "results": self.search_results}

    def fetch_page(self, url: str) -> dict:
        return self.pages.get(url, {"status": "failed", "url": url, "title": "", "text": "", "error": "missing"})


def test_protocol_due_diligence_writes_asset_files(tmp_path: Path) -> None:
    agent = ResearchAgent(memory_root=tmp_path, research_toolbox=StubResearchToolbox())

    result = agent.execute(
        skill="protocol_due_diligence",
        payload={
            "asset": "SUI",
            "horizon": "6-12m",
            "focus": ["fundamentals", "tokenomics", "catalysts", "risks"],
        },
    )

    assert result["asset"] == "SUI"
    assert "bull_case" in result
    assert (tmp_path / "assets" / "SUI.md").exists()
    assert (tmp_path / "assets" / "SUI.json").exists()
    assert result["tool_calls"]
    assert result["rounds_used"] >= 1


def test_protocol_due_diligence_includes_external_context_when_available(tmp_path: Path) -> None:
    agent = ResearchAgent(
        memory_root=tmp_path,
        external_research_service=StubExternalResearchService(
            market={"market_cap": 1_250_000_000, "fdv": 2_400_000_000, "price_change_percentage_24h": 8.6},
            protocol={"tvl": 810_000_000, "chains": ["Ethereum"], "category": "Restaking"},
        ),
        research_toolbox=StubResearchToolbox(
            search_results=[
                {"title": "ENA roadmap", "url": "https://example.com/ena-roadmap", "snippet": "Catalysts and risks"}
            ],
            pages={
                "https://example.com/ena-roadmap": {
                    "status": "success",
                    "url": "https://example.com/ena-roadmap",
                    "title": "ENA roadmap",
                    "text": "ENA roadmap, catalyst, ecosystem growth, and token unlock risk are discussed here.",
                }
            },
        ),
    )

    result = agent.execute(
        skill="protocol_due_diligence",
        payload={"asset": "ENA", "horizon": "6-12m", "focus": ["fundamentals", "tokenomics"]},
    )

    assert result["market_context"]["market_cap"] == 1_250_000_000
    assert result["protocol_context"]["tvl"] == 810_000_000
    assert any("FDV/TVL" in item for item in result["risks"])
    assert result["evidence_sufficient"] is True


def test_protocol_due_diligence_returns_insufficient_when_evidence_is_too_thin(tmp_path: Path) -> None:
    agent = ResearchAgent(
        memory_root=tmp_path,
        external_research_service=StubExternalResearchService(market=None, protocol=None),
        research_toolbox=StubResearchToolbox(search_results=[], pages={}),
    )

    result = agent.execute(
        skill="protocol_due_diligence",
        payload={"asset": "SUI", "horizon": "6-12m", "focus": ["fundamentals"]},
    )

    assert result["status"] == "insufficient"
    assert result["evidence_sufficient"] is False
    assert result["missing_information"]


def test_protocol_due_diligence_records_agent_loop_rounds_and_termination_reason(tmp_path: Path) -> None:
    agent = ResearchAgent(
        memory_root=tmp_path,
        external_research_service=StubExternalResearchService(
            market={"market_cap": 1_250_000_000},
            protocol=None,
        ),
        research_toolbox=StubResearchToolbox(
            search_results=[
                {"title": "BTC roadmap", "url": "https://example.com/btc-roadmap", "snippet": "Roadmap and catalysts"},
                {"title": "BTC risks", "url": "https://example.com/btc-risks", "snippet": "Risks and tokenomics"},
            ],
            pages={
                "https://example.com/btc-roadmap": {
                    "status": "success",
                    "url": "https://example.com/btc-roadmap",
                    "title": "BTC roadmap",
                    "text": "BTC roadmap catalyst adoption risk tokenomics ecosystem.",
                },
                "https://example.com/btc-risks": {
                    "status": "success",
                    "url": "https://example.com/btc-risks",
                    "title": "BTC risks",
                    "text": "BTC catalyst risk execution roadmap tokenomics discussed in detail.",
                },
            },
        ),
    )

    result = agent.execute(
        skill="protocol_due_diligence",
        payload={"asset": "BTC", "horizon": "6-12m", "focus": ["fundamentals", "tokenomics"]},
    )

    assert result["asset"] == "BTC"
    assert "agent_loop" in result
    assert len(result["agent_loop"]) >= 2
    assert result["agent_loop"][0]["round"] == 1
    assert result["agent_loop"][0]["decision"]
    assert result["agent_loop"][0]["action"]["tool"] == "search_web"
    assert result["agent_loop"][-1]["termination"]
    assert result["termination_reason"]
    assert result["rounds_used"] == len(result["agent_loop"])


def test_memory_lookup_reads_existing_asset_memory(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "SOL.md").write_text("# SOL\n\nOld thesis", encoding="utf-8")
    (assets_dir / "SOL.json").write_text('{"symbol":"SOL","status":"watch"}', encoding="utf-8")

    agent = ResearchAgent(memory_root=tmp_path)

    result = agent.execute(
        skill="memory_lookup",
        payload={"asset": "SOL", "query_type": "historical_thesis", "time_range": "all"},
    )

    assert result["asset"] == "SOL"
    assert "Old thesis" in result["content"]


def test_watchlist_weekly_review_summarizes_watchlist(tmp_path: Path) -> None:
    (tmp_path / "watchlist.json").write_text(
        '{"assets":[{"symbol":"BTC","status":"core_watch","priority":1,"last_reviewed_at":"2026-03-17"},{"symbol":"SUI","status":"watch","priority":2,"last_reviewed_at":"2026-03-17"}]}',
        encoding="utf-8",
    )
    agent = ResearchAgent(memory_root=tmp_path)

    result = agent.execute(
        skill="watchlist_weekly_review",
        payload={"scope": "all", "focus": ["top_conviction", "weakening_thesis", "risk_changes"]},
    )

    assert result["scope"] == "all"
    assert len(result["top_conviction"]) >= 1
    assert (tmp_path / "reports" / "weekly").exists()


def test_new_token_screening_writes_asset_files_with_screening_view(tmp_path: Path) -> None:
    agent = ResearchAgent(memory_root=tmp_path)

    result = agent.execute(
        skill="new_token_screening",
        payload={
            "asset": "ENA",
            "horizon": "short_to_mid_term",
            "focus": ["listing_risk", "valuation", "market_attention", "narrative"],
        },
    )

    assert result["asset"] == "ENA"
    assert result["screening_view"] in {"speculative_watch", "needs_confirmation", "avoid_for_now"}
    assert len(result["strengths"]) >= 2
    assert len(result["risks"]) >= 2
    assert (tmp_path / "assets" / "ENA.md").exists()
    assert (tmp_path / "assets" / "ENA.json").exists()


def test_new_token_screening_uses_external_market_context(tmp_path: Path) -> None:
    agent = ResearchAgent(
        memory_root=tmp_path,
        external_research_service=StubExternalResearchService(
            market={"market_cap": 920_000_000, "fdv": 4_200_000_000, "price_change_percentage_24h": 18.2},
            protocol={"tvl": 300_000_000, "chains": ["Ethereum"], "category": "Perps"},
        ),
    )

    result = agent.execute(
        skill="new_token_screening",
        payload={"asset": "ENA", "horizon": "short_to_mid_term", "focus": ["listing_risk", "valuation"]},
    )

    assert result["market_context"]["fdv"] == 4_200_000_000
    assert result["protocol_context"]["category"] == "Perps"
    assert any("FDV/TVL" in item for item in result["risks"])


def test_thesis_break_detector_flags_assets_with_invalidations(tmp_path: Path) -> None:
    (tmp_path / "watchlist.json").write_text(
        '{"assets":[{"symbol":"BTC","status":"core_watch","priority":1},{"symbol":"SUI","status":"watch","priority":3},{"symbol":"ENA","status":"watch","priority":2}]}',
        encoding="utf-8",
    )
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "BTC.json").write_text(
        '{"asset":"BTC","summary":"Core market leader with catalysts still intact.","risks":["macro volatility"],"catalysts":["ETF inflow"],"status":"healthy"}',
        encoding="utf-8",
    )
    (assets_dir / "SUI.json").write_text(
        '{"asset":"SUI","summary":"Momentum cooled and roadmap execution slipped.","risks":["token unlock pressure","execution miss on roadmap"],"catalysts":[],"status":"weakening"}',
        encoding="utf-8",
    )
    (assets_dir / "ENA.json").write_text(
        '{"asset":"ENA","summary":"Narrative faded and market attention is dropping.","risks":["narrative fatigue"],"catalysts":[],"status":"at_risk"}',
        encoding="utf-8",
    )

    agent = ResearchAgent(memory_root=tmp_path)

    result = agent.execute(
        skill="thesis_break_detector",
        payload={
            "scope": "watchlist",
            "focus": ["invalidations", "weakening_signals", "missing_catalysts"],
        },
    )

    assert result["scope"] == "watchlist"
    assert result["weakening_assets"]
    flagged = {item["asset"]: item for item in result["weakening_assets"]}
    assert "SUI" in flagged
    assert "ENA" in flagged
    assert "BTC" not in flagged
    assert flagged["SUI"]["severity"] in {"warning", "critical"}
    assert flagged["SUI"]["signals"]
