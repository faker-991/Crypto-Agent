from pathlib import Path
from typing import TypedDict

from app.agents.research_agent import ResearchAgent
from pydantic import TypeAdapter


class ResearchAgentResult(TypedDict):
    agent: str
    status: str
    evidence_status: str
    summary: str
    findings: list[str]
    risks: list[str]
    catalysts: list[str]
    missing_information: list[str]
    degraded_reason: str | None
    termination_reason: str | None
    rounds_used: int
    tool_calls: list[dict]


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
        self.queries: list[str] = []

    def search_web(self, query: str) -> dict:
        self.queries.append(query)
        return {"status": "success", "query": query, "results": self.search_results}

    def fetch_page(self, url: str) -> dict:
        return self.pages.get(url, {"status": "failed", "url": url, "title": "", "text": "", "error": "missing"})


class StubRemoteReActLLMClient:
    def __init__(self, responses: list[str] | None = None, *, should_raise: bool = False) -> None:
        self.responses = list(responses or [])
        self.should_raise = should_raise
        self.model = "remote-react-model"
        self.provider = "openai-compatible"
        self.temperature = 0.1

    def is_configured(self) -> bool:
        return True

    def complete(self, *args, **kwargs):
        if self.should_raise:
            raise RuntimeError("remote llm unavailable")
        content = self.responses.pop(0)
        from types import SimpleNamespace

        return SimpleNamespace(
            content=content,
            text=content,
            message=SimpleNamespace(content=content),
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            model=self.model,
            provider=self.provider,
            temperature=self.temperature,
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=8, total_tokens=20),
        )


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
    assert any(
        tool_call["tool_name"] in {"get_market_snapshot", "get_protocol_snapshot"}
        and tool_call["status"] == "success"
        for tool_call in result["tool_calls"]
    )


def test_protocol_due_diligence_prefers_remote_react_llm_when_available(tmp_path: Path) -> None:
    remote = StubRemoteReActLLMClient(
        responses=[
            '{"decision_summary":"Search with remote guidance.","action":"search_web","args":{"query":"REMOTE BTC catalysts"},"termination":false,"termination_reason":null}',
            '{"decision_summary":"Stop after first source pass.","action":null,"args":{},"termination":true,"termination_reason":"enough"}',
        ]
    )
    agent = ResearchAgent(
        memory_root=tmp_path,
        external_research_service=StubExternalResearchService(market=None, protocol=None),
        research_toolbox=StubResearchToolbox(search_results=[], pages={}),
        llm_client=remote,
    )

    result = agent.execute(
        skill="protocol_due_diligence",
        payload={"asset": "BTC", "horizon": "6-12m", "focus": ["fundamentals"]},
    )

    assert result["agent_loop"][0]["action"]["tool"] == "search_web"
    assert result["agent_loop"][0]["action"]["input"]["query"] == "REMOTE BTC catalysts"


def test_protocol_due_diligence_falls_back_to_heuristic_when_remote_llm_fails(tmp_path: Path) -> None:
    remote = StubRemoteReActLLMClient(should_raise=True)
    agent = ResearchAgent(
        memory_root=tmp_path,
        external_research_service=StubExternalResearchService(market=None, protocol=None),
        research_toolbox=StubResearchToolbox(search_results=[], pages={}),
        llm_client=remote,
    )

    result = agent.execute(
        skill="protocol_due_diligence",
        payload={"asset": "BTC", "horizon": "6-12m", "focus": ["fundamentals"]},
    )

    assert result["agent_loop"][0]["action"]["tool"] == "search_web"
    assert result["agent_loop"][0]["action"]["input"]["query"] == "BTC crypto tokenomics roadmap catalysts risks"


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


def test_protocol_due_diligence_retries_search_with_market_sentiment_query_when_first_search_is_empty(tmp_path: Path) -> None:
    class SequentialResearchToolbox(StubResearchToolbox):
        def __init__(self) -> None:
            super().__init__(
                search_results=[],
                pages={
                    "https://example.com/btc-sentiment": {
                        "status": "success",
                        "url": "https://example.com/btc-sentiment",
                        "title": "BTC sentiment",
                        "text": "BTC market sentiment improved, catalysts include ETF demand, risks include macro volatility.",
                    }
                },
            )
            self.search_calls = 0

        def search_web(self, query: str) -> dict:
            self.queries.append(query)
            self.search_calls += 1
            if self.search_calls == 1:
                return {"status": "success", "query": query, "results": []}
            return {
                "status": "success",
                "query": query,
                "results": [
                    {
                        "title": "BTC sentiment",
                        "url": "https://example.com/btc-sentiment",
                        "snippet": "Market sentiment, macro drivers, and ETF flows.",
                    }
                ],
            }

    toolbox = SequentialResearchToolbox()
    agent = ResearchAgent(
        memory_root=tmp_path,
        external_research_service=StubExternalResearchService(market={"market_cap": 1_000_000_000}, protocol=None),
        research_toolbox=toolbox,
    )

    result = agent.execute(
        skill="protocol_due_diligence",
        payload={"asset": "BTC", "horizon": "short_term", "focus": ["trend", "sentiment", "news"]},
    )

    search_calls = [call for call in result["tool_calls"] if call["tool_name"] == "search_web"]
    assert len(search_calls) >= 2
    assert "sentiment" in toolbox.queries[0].lower()
    assert any(query != toolbox.queries[0] for query in toolbox.queries[1:])
    assert any("sentiment" in query.lower() for query in toolbox.queries[1:])
    assert any(call["tool_name"] == "fetch_page" and call["status"] == "success" for call in result["tool_calls"])
    assert result["status"] in {"success", "insufficient"}


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
    assert result["agent_loop"][0]["action"]["tool"] == "get_market_snapshot"
    assert any(entry["action"]["tool"] == "search_web" for entry in result["agent_loop"])
    assert result["agent_loop"][-1]["termination"]
    assert result["termination_reason"]
    assert result["rounds_used"] == len(result["agent_loop"])


def test_protocol_due_diligence_prefers_market_snapshot_over_protocol_snapshot_for_trend_and_sentiment_focus(tmp_path: Path) -> None:
    agent = ResearchAgent(
        memory_root=tmp_path,
        external_research_service=StubExternalResearchService(
            market={"market_cap": 1_250_000_000},
            protocol={"tvl": 810_000_000, "chains": ["Bitcoin"], "category": "Canonical Bridge"},
        ),
        research_toolbox=StubResearchToolbox(
            search_results=[
                {"title": "BTC market note", "url": "https://example.com/btc-market-note", "snippet": "Sentiment and risks"}
            ],
            pages={
                "https://example.com/btc-market-note": {
                    "status": "success",
                    "url": "https://example.com/btc-market-note",
                    "title": "BTC market note",
                    "text": "Bitcoin sentiment improved while macro risks and ETF-driven catalysts remained in focus.",
                }
            },
        ),
    )

    result = agent.execute(
        skill="protocol_due_diligence",
        payload={"asset": "BTC", "horizon": "short_term", "focus": ["trend", "sentiment", "news"]},
    )

    first_action = result["agent_loop"][0]["action"]["tool"]
    assert first_action == "get_market_snapshot"


def test_protocol_due_diligence_requests_market_snapshot_even_without_prefetched_market_context_for_trend_focus(tmp_path: Path) -> None:
    agent = ResearchAgent(
        memory_root=tmp_path,
        external_research_service=StubExternalResearchService(
            market=None,
            protocol={"tvl": 810_000_000, "chains": ["Bitcoin"], "category": "Canonical Bridge"},
        ),
        research_toolbox=StubResearchToolbox(
            search_results=[
                {"title": "BTC market note", "url": "https://example.com/btc-market-note", "snippet": "Sentiment and risks"}
            ],
            pages={
                "https://example.com/btc-market-note": {
                    "status": "success",
                    "url": "https://example.com/btc-market-note",
                    "title": "BTC market note",
                    "text": "Bitcoin sentiment improved while macro risks and ETF-driven catalysts remained in focus.",
                }
            },
        ),
    )

    result = agent.execute(
        skill="protocol_due_diligence",
        payload={"asset": "BTC", "horizon": "short_term", "focus": ["trend", "sentiment", "news"]},
    )

    first_action = result["agent_loop"][0]["action"]["tool"]
    assert first_action == "get_market_snapshot"
    assert any(
        tool_call["tool_name"] == "get_market_snapshot"
        for tool_call in result["tool_calls"]
    )


def test_protocol_due_diligence_fetches_multiple_sources_before_synthesizing_for_trend_and_sentiment_focus(tmp_path: Path) -> None:
    agent = ResearchAgent(
        memory_root=tmp_path,
        external_research_service=StubExternalResearchService(
            market={"market_cap": 1_250_000_000},
            protocol=None,
        ),
        research_toolbox=StubResearchToolbox(
            search_results=[
                {"title": "BTC macro outlook", "url": "https://www.fxstreet.com/btc-1", "snippet": "Macro risks and ETF demand"},
                {"title": "BTC ETF flows", "url": "https://blog.bitfinex.com/btc-2", "snippet": "Flows and catalysts"},
                {"title": "BTC third source", "url": "https://example.com/btc-3", "snippet": "Supplementary source"},
            ],
            pages={
                "https://www.fxstreet.com/btc-1": {
                    "status": "success",
                    "url": "https://www.fxstreet.com/btc-1",
                    "title": "BTC macro outlook",
                    "text": "Bitcoin faces macro risk while ETF demand remains a catalyst for price support.",
                },
                "https://blog.bitfinex.com/btc-2": {
                    "status": "success",
                    "url": "https://blog.bitfinex.com/btc-2",
                    "title": "BTC ETF flows",
                    "text": "ETF flows and demand trends remain a catalyst, while volatility and regulation remain risks.",
                },
                "https://example.com/btc-3": {
                    "status": "success",
                    "url": "https://example.com/btc-3",
                    "title": "BTC third source",
                    "text": "Supplementary BTC source with additional context.",
                },
            },
        ),
    )

    result = agent.execute(
        skill="protocol_due_diligence",
        payload={"asset": "BTC", "horizon": "short_term", "focus": ["trend", "sentiment", "news"]},
    )

    fetch_calls = [call for call in result["tool_calls"] if call["tool_name"] == "fetch_page" and call["status"] == "success"]
    assert len(fetch_calls) >= 2
    assert fetch_calls[0]["args"]["url"] == "https://www.fxstreet.com/btc-1"
    assert fetch_calls[1]["args"]["url"] == "https://blog.bitfinex.com/btc-2"
    assert result["status"] == "success"


def test_research_evidence_can_use_search_top_k_as_source_coverage_for_macro_focus(tmp_path: Path) -> None:
    agent = ResearchAgent(memory_root=tmp_path)
    context = {
        "focus": ["trend", "sentiment", "news", "macro"],
    }
    observations = [
        {
            "tool_name": "get_market_snapshot",
            "status": "success",
            "summary": "Loaded market snapshot.",
            "structured_data": {
                "findings": ["market_cap=1372609481025"],
                "risks": [],
                "catalysts": [],
                "source_urls": [],
            },
        },
        {
            "tool_name": "search_web",
            "status": "success",
            "summary": "Found 5 web sources for follow-up.",
            "structured_data": {
                "findings": [
                    "Bitcoin rises with risk assets as Trump talks end of Iran war.",
                    "Bitcoin weekly outlook: oil surge and Fed pressure build.",
                ],
                "risks": ["iran", "fed", "oil"],
                "catalysts": ["etf", "ceasefire"],
                "source_urls": [
                    "https://www.bloomberg.com/news/articles/btc-iran",
                    "https://www.fxempire.com/news/btc-fed",
                ],
            },
            "output_summary": {
                "results": [
                    {"url": "https://www.bloomberg.com/news/articles/btc-iran"},
                    {"url": "https://www.fxempire.com/news/btc-fed"},
                ]
            },
        },
    ]

    missing = agent._research_missing_information(context=context, observations=observations)
    sufficient = agent._research_evidence_sufficient(context=context, observations=observations)

    assert "Source coverage is missing." not in missing
    assert "Source diversity is thin." not in missing
    assert sufficient is False


def test_protocol_due_diligence_returns_typed_research_agent_result_contract(tmp_path: Path) -> None:
    agent = ResearchAgent(
        memory_root=tmp_path,
        external_research_service=StubExternalResearchService(
            market={"market_cap": 1_250_000_000, "fdv": 2_400_000_000, "price_change_percentage_24h": 8.6},
            protocol={"tvl": 810_000_000, "chains": ["Ethereum"], "category": "Restaking"},
        ),
        research_toolbox=StubResearchToolbox(
            search_results=[
                {"title": "SUI roadmap", "url": "https://example.com/sui-roadmap", "snippet": "Catalysts and risks"}
            ],
            pages={
                "https://example.com/sui-roadmap": {
                    "status": "success",
                    "url": "https://example.com/sui-roadmap",
                    "title": "SUI roadmap",
                    "text": "SUI roadmap, catalyst, ecosystem growth, and token unlock risk are discussed here.",
                }
            },
        ),
    )

    result = agent.execute(
        skill="protocol_due_diligence",
        payload={"asset": "SUI", "horizon": "6-12m", "focus": ["fundamentals", "tokenomics"]},
    )

    validated = TypeAdapter(ResearchAgentResult).validate_python(result)
    assert validated["agent"] == "ResearchAgent"
    assert validated["status"] in {"success", "failed", "insufficient", "degraded"}
    assert validated["evidence_status"] in {"sufficient", "insufficient", "failed"}
    assert validated["summary"]
    assert validated["findings"]
    assert validated["risks"]
    assert validated["catalysts"]
    assert validated["rounds_used"] >= 1
    assert len(validated["tool_calls"]) >= 1
    first_tool_call = validated["tool_calls"][0]
    assert_tool_result_like(first_tool_call)


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
