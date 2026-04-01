import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from app.agents.research_result_assembler import ResearchResultAssembler
from app.agents.tools.market_tools import (
    MarketToolbox,
    build_market_tool_executors,
    build_market_tool_specs,
)
from app.agents.tools.research_tools import (
    ResearchToolbox,
    build_research_tool_executors,
    build_research_tool_specs,
)
from app.runtime.react_loop_service import ReActLoopService
from app.runtime.tool_runtime import ToolRuntime
from app.runtime.trace_runtime import TraceRuntime
from app.services.react_llm_service import FallbackReActLLMClient, OpenAICompatibleReActLLMClient
from app.services.external_research_service import ExternalResearchService
from app.services.market_data_service import MarketDataService

if TYPE_CHECKING:
    from app.clients.mcp_registry import MCPToolRegistry


class HeuristicResearchLLMClient:
    provider = "heuristic-research-llm"
    model = "heuristic-research-llm"
    temperature = 0.0

    def complete(self, *args, **kwargs) -> SimpleNamespace:
        messages = kwargs.get("messages") or []
        payload: dict[str, Any] = {}
        if messages:
            content = messages[-1].get("content")
            if isinstance(content, str):
                try:
                    payload = json.loads(content)
                except json.JSONDecodeError:
                    payload = {}

        asset = str(payload.get("asset") or "UNKNOWN").upper()
        context = payload.get("context") or {}
        focus = payload.get("focus") or context.get("focus") or []
        observations = payload.get("observations") or []
        tool_results = payload.get("tool_results") or []
        has_market_observation = any(
            isinstance(item, dict)
            and item.get("tool_name") in {"get_market_snapshot", "get_protocol_snapshot", "get_ticker", "get_klines"}
            and item.get("status") == "success"
            for item in observations
        )
        search_observations = [
            item
            for item in observations
            if isinstance(item, dict) and item.get("tool_name") == "search_web"
        ]
        search_observation = search_observations[-1] if search_observations else None
        market_context = context.get("market_context")
        protocol_context = context.get("protocol_context")
        fetched_urls = {
            result.get("args", {}).get("url") or result.get("output_summary", {}).get("url")
            for result in tool_results
            if isinstance(result, dict) and result.get("tool_name") == "fetch_page"
        }
        successful_fetch_urls = {
            result.get("args", {}).get("url") or result.get("output_summary", {}).get("url")
            for result in tool_results
            if isinstance(result, dict) and result.get("tool_name") == "fetch_page" and result.get("status") == "success"
        }
        searched_queries = [
            str(
                result.get("args", {}).get("query")
                or result.get("output_summary", {}).get("query")
                or result.get("output", {}).get("query")
                or ""
            ).strip()
            for result in tool_results
            if isinstance(result, dict) and result.get("tool_name") == "search_web"
        ]
        searched_queries = [query for query in searched_queries if query]
        focus_tokens = self._normalize_focus(focus)
        prefers_market_snapshot = bool(focus_tokens & {"trend", "sentiment", "news", "macro"})
        target_source_count = self._target_source_count(focus_tokens)
        candidate_urls = self._rank_candidate_urls(search_observation, fetched_urls)
        primary_query = self._build_primary_query(asset, focus)
        retry_query = self._build_retry_query(asset, focus, searched_queries)

        if not has_market_observation and (market_context or prefers_market_snapshot):
            content = {
                "decision_summary": "Capture a market snapshot so the trace has a market-side anchor.",
                "action": "get_market_snapshot",
                "args": {"asset": asset},
                "termination": False,
                "termination_reason": None,
            }
        elif not has_market_observation and protocol_context and not prefers_market_snapshot:
            content = {
                "decision_summary": "Capture a protocol snapshot so the trace has a market-side anchor.",
                "action": "get_protocol_snapshot",
                "args": {"asset": asset},
                "termination": False,
                "termination_reason": None,
            }
        elif not search_observation:
            content = {
                "decision_summary": "Search the web for recent sources that can support trend, sentiment, and risk analysis.",
                "action": "search_web",
                "args": {"query": primary_query},
                "termination": False,
                "termination_reason": None,
            }
        elif candidate_urls and len(successful_fetch_urls) < target_source_count:
            content = {
                "decision_summary": "Fetch another high-quality source so the final synthesis compares multiple external references.",
                "action": "fetch_page",
                "args": {"url": candidate_urls[0]},
                "termination": False,
                "termination_reason": None,
            }
        elif retry_query and len(successful_fetch_urls) < target_source_count:
            content = {
                "decision_summary": "Broaden the web search because the first query returned no usable sources.",
                "action": "search_web",
                "args": {"query": retry_query},
                "termination": False,
                "termination_reason": None,
            }
        else:
            content = {
                "decision_summary": "Stop because the available source set has been exhausted.",
                "action": None,
                "args": {},
                "termination": True,
                "termination_reason": "No more high-value sources remain.",
            }

        raw = json.dumps(content, ensure_ascii=False)
        return SimpleNamespace(
            content=raw,
            text=raw,
            message=SimpleNamespace(content=raw),
            choices=[SimpleNamespace(message=SimpleNamespace(content=raw))],
            model=self.model,
            provider=self.provider,
            temperature=self.temperature,
            usage=SimpleNamespace(prompt_tokens=24, completion_tokens=18, total_tokens=42),
        )

    def _build_primary_query(self, asset: str, focus: list[Any]) -> str:
        focus_tokens = self._normalize_focus(focus)
        if focus_tokens & {"trend", "sentiment", "news", "macro"}:
            return f"{asset} price outlook sentiment news macro regulation"
        return f"{asset} crypto tokenomics roadmap catalysts risks"

    def _build_retry_query(self, asset: str, focus: list[Any], searched_queries: list[str]) -> str | None:
        focus_tokens = self._normalize_focus(focus)
        candidates = [
            f"{asset} market sentiment news ETF macro regulation",
            f"{asset} latest market sentiment news risks catalysts",
            f"{asset} price outlook sentiment news macro regulation",
            f"{asset} crypto tokenomics roadmap catalysts risks",
        ]
        if not (focus_tokens & {"trend", "sentiment", "news", "macro"}):
            candidates = [
                f"{asset} catalysts risks latest news",
                f"{asset} crypto tokenomics roadmap catalysts risks",
            ]
        for query in candidates:
            if query not in searched_queries:
                return query
        return None

    def _normalize_focus(self, focus: list[Any]) -> set[str]:
        normalized: set[str] = set()
        for item in focus:
            if not isinstance(item, str):
                continue
            token = item.strip().lower()
            if token:
                normalized.add(token)
        return normalized

    def _target_source_count(self, focus_tokens: set[str]) -> int:
        if focus_tokens & {"trend", "sentiment", "news", "macro"}:
            return 2
        return 1

    def _rank_candidate_urls(self, search_observation: dict[str, Any] | None, fetched_urls: set[str]) -> list[str]:
        results = []
        if isinstance(search_observation, dict):
            output_summary = search_observation.get("output_summary") or {}
            maybe_results = output_summary.get("results") or []
            if isinstance(maybe_results, list):
                results = [item for item in maybe_results if isinstance(item, dict)]
        if not results and isinstance(search_observation, dict):
            structured_data = search_observation.get("structured_data") or {}
            results = [{"url": url} for url in structured_data.get("candidate_urls") or [] if isinstance(url, str)]

        ranked = sorted(results, key=self._search_result_score, reverse=True)
        urls: list[str] = []
        for item in ranked:
            url = item.get("url")
            if not isinstance(url, str) or not url or url in fetched_urls or url in urls:
                continue
            urls.append(url)
        return urls

    def _search_result_score(self, item: dict[str, Any]) -> int:
        url = str(item.get("url") or "").lower()
        title = str(item.get("title") or "").lower()
        score = 0
        preferred_domains = {
            "bloomberg.com": 10,
            "reuters.com": 10,
            "wsj.com": 9,
            "ft.com": 9,
            "coindesk.com": 9,
            "theblock.co": 9,
            "fxstreet.com": 8,
            "fxempire.com": 8,
            "bitfinex.com": 7,
            "primexbt.com": 7,
        }
        for domain, weight in preferred_domains.items():
            if domain in url:
                score += weight
                break
        if "exa.ai" in url:
            score -= 20
        if any(token in title for token in ("bitcoin", "btc", "price", "forecast", "sentiment", "outlook")):
            score += 3
        return score


class ResearchAgent:
    name = "ResearchAgent"

    def __init__(
        self,
        memory_root: Path,
        external_research_service: ExternalResearchService | None = None,
        research_toolbox: ResearchToolbox | None = None,
        market_data_service: MarketDataService | None = None,
        llm_client: Any | None = None,
        mcp_registry: "MCPToolRegistry | None" = None,
    ) -> None:
        self.memory_root = memory_root
        self.assets_root = memory_root / "assets"
        self.reports_root = memory_root / "reports" / "weekly"
        self.external_research_service = external_research_service or ExternalResearchService()
        self.research_toolbox = research_toolbox or ResearchToolbox(mcp_registry=mcp_registry)
        self.market_toolbox = MarketToolbox(
            external_research_service=self.external_research_service,
            market_data_service=market_data_service or MarketDataService(),
        )
        self.llm_client = self._resolve_llm_client(llm_client)
        self.result_assembler = ResearchResultAssembler()
        self.assets_root.mkdir(parents=True, exist_ok=True)
        self.reports_root.mkdir(parents=True, exist_ok=True)

    def execute(self, skill: str, payload: dict) -> dict:
        if skill == "protocol_due_diligence":
            return self._protocol_due_diligence(payload)
        if skill == "memory_lookup":
            return self._memory_lookup(payload)
        if skill == "watchlist_weekly_review":
            return self._watchlist_weekly_review(payload)
        if skill == "thesis_break_detector":
            return self._thesis_break_detector(payload)
        if skill == "new_token_screening":
            return self._new_token_screening(payload)
        if skill == "generate_report":
            return self._generate_report(payload)
        raise ValueError(f"Unsupported research skill: {skill}")

    def _protocol_due_diligence(self, payload: dict) -> dict:
        asset = payload["asset"].upper()
        trace_id = f"research-{asset.lower()}"
        context = self.external_research_service.get_asset_context(asset)
        market_context = context.get("market")
        protocol_context = context.get("protocol")
        asset_memory = self._read_asset_memory(asset)
        all_tool_specs = build_research_tool_specs() + build_market_tool_specs()
        tool_runtime = ToolRuntime(
            tool_specs=all_tool_specs,
            tool_executors={
                **build_research_tool_executors(self.research_toolbox, self.memory_root),
                **build_market_tool_executors(self.market_toolbox),
            },
        )
        trace_runtime = TraceRuntime()
        loop_service = ReActLoopService(
            llm_client=self.llm_client,
            tool_runtime=tool_runtime,
            trace_runtime=trace_runtime,
            missing_information_builder=self._research_missing_information,
            evidence_sufficiency_checker=self._research_evidence_sufficient,
            agent_name=self.name,
        )
        terminal_state, observations, tool_results = loop_service.run(
            asset=asset,
            tool_specs=all_tool_specs,
            initial_context={
                "trace_id": trace_id,
                "asset": asset,
                "horizon": payload.get("horizon"),
                "focus": payload.get("focus", []),
                "market_context": market_context,
                "protocol_context": protocol_context,
                "asset_memory": asset_memory,
            },
        )
        assembled = self.result_assembler.assemble(
            asset=asset,
            terminal_state=terminal_state,
            observations=observations,
            tool_results=tool_results,
        )
        trace_summary = trace_runtime.finalize_trace(
            trace_id=trace_id,
            summary={"status": assembled.get("status", terminal_state.get("status", "insufficient"))},
        )
        missing_information = assembled["missing_information"]
        evidence_status = assembled["evidence_status"]
        evidence_sufficient = evidence_status == "sufficient"
        risks = [
            "token unlock pressure",
            "narrative fatigue",
            "execution miss on roadmap",
        ]
        bull_case = [
            f"{asset} has enough narrative and ecosystem surface area for follow-up research.",
            f"{asset} can be tracked through catalysts, tokenomics, and momentum changes.",
        ]
        if market_context:
            market_cap = market_context.get("market_cap")
            fdv = market_context.get("fdv")
            if market_cap:
                bull_case.append(f"Current market cap sits near ${market_cap:,.0f}, which is large enough to matter but still re-ratable.")
            fdv_tvl = self._compute_fdv_tvl_ratio(fdv, protocol_context.get("tvl") if protocol_context else None)
            if fdv_tvl is not None:
                risks.append(f"FDV/TVL is {fdv_tvl:.2f}, so valuation still needs confirmation from adoption.")
        if protocol_context:
            tvl = protocol_context.get("tvl")
            category = protocol_context.get("category")
            chains = protocol_context.get("chains") or []
            if tvl:
                bull_case.append(f"DefiLlama shows roughly ${tvl:,.0f} of TVL, which gives the thesis a measurable usage anchor.")
            if category:
                bull_case.append(f"The protocol sits in the {category} category, which helps frame where catalysts should come from.")
            if chains:
                risks.append(f"Execution breadth still depends on maintaining traction across {', '.join(chains[:3])}.")
        combined_risks = list(dict.fromkeys([*assembled["risks"], *risks]))
        result = {
            **assembled,
            "asset": asset,
            "summary": assembled["summary"] or f"{asset} is worth continued monitoring for a medium-term thesis.",
            "bull_case": bull_case,
            "bear_case": [
                f"{asset} may fail to sustain attention if catalysts weaken.",
                f"{asset} still requires deeper validation on execution and valuation.",
            ],
            "risks": combined_risks,
            "focus": payload.get("focus", []),
            "horizon": payload.get("horizon"),
            "market_context": market_context,
            "protocol_context": protocol_context,
            "evidence_sufficient": evidence_sufficient,
            "missing_information": missing_information,
            "tool_calls": tool_results,
            "trace_summary": trace_summary,
            "rounds_used": assembled["rounds_used"],
            "agent_loop": terminal_state["agent_loop"],
            "termination_reason": assembled["termination_reason"],
            "fetched_sources": self._collect_fetched_sources(observations),
            "market_memory": asset_memory,
        }
        self._write_asset_files(asset, result)
        return result

    def _research_missing_information(self, *, context: dict[str, Any], observations: list[dict[str, Any]]) -> list[str]:
        findings = self._collect_observation_strings(observations, "findings")
        risks = self._collect_observation_strings(observations, "risks")
        catalysts = self._collect_observation_strings(observations, "catalysts")
        has_market_side = any(
            observation.get("status") == "success"
            and observation.get("tool_name") in {"get_market_snapshot", "get_protocol_snapshot", "get_ticker", "get_klines"}
            for observation in observations
        )
        successful_fetches = [
            observation
            for observation in observations
            if observation.get("status") == "success" and observation.get("tool_name") == "fetch_page"
        ]
        search_source_urls = {
            url
            for observation in observations
            if observation.get("status") == "success" and observation.get("tool_name") == "search_web"
            for url in ((observation.get("structured_data") or {}).get("source_urls") or [])
            if isinstance(url, str) and url
        }
        source_coverage_count = len(
            {
                *[
                    url
                    for observation in successful_fetches
                    for url in ((observation.get("structured_data") or {}).get("source_urls") or [])
                    if isinstance(url, str) and url
                ],
                *list(search_source_urls),
            }
        )
        focus_tokens = self._focus_tokens_from_context(context)
        missing: list[str] = []
        if not findings:
            missing.append("Factual findings remain thin.")
        if not risks:
            missing.append("Risk evidence is thin.")
        if not catalysts:
            missing.append("Catalyst evidence is thin.")
        if not has_market_side:
            missing.append("Market-side evidence is missing.")
        if source_coverage_count == 0:
            missing.append("Source coverage is missing.")
        elif source_coverage_count < self._minimum_fetch_sources(focus_tokens):
            missing.append("Source diversity is thin.")
        return missing

    def _research_evidence_sufficient(self, *, context: dict[str, Any], observations: list[dict[str, Any]]) -> bool:
        focus_tokens = self._focus_tokens_from_context(context)
        source_urls = {
            url
            for observation in observations
            if observation.get("status") == "success" and observation.get("tool_name") in {"fetch_page", "search_web"}
            for url in ((observation.get("structured_data") or {}).get("source_urls") or [])
            if isinstance(url, str) and url
        }
        successful_fetch_count = len(
            [
                observation
                for observation in observations
                if observation.get("status") == "success" and observation.get("tool_name") == "fetch_page"
            ]
        )
        if successful_fetch_count < self._minimum_fetch_sources(focus_tokens):
            return False
        if len(source_urls) < self._minimum_fetch_sources(focus_tokens):
            return False
        missing = self._research_missing_information(context=context, observations=observations)
        has_market_side = any(
            observation.get("status") == "success"
            and observation.get("tool_name") in {"get_market_snapshot", "get_protocol_snapshot", "get_ticker", "get_klines"}
            for observation in observations
        )
        has_research_side = successful_fetch_count > 0
        return has_market_side and has_research_side and len(missing) <= 2

    def _minimum_fetch_sources(self, focus_tokens: set[str]) -> int:
        if focus_tokens & {"trend", "sentiment", "news", "macro"}:
            return 2
        return 1

    def _focus_tokens_from_context(self, context: dict[str, Any]) -> set[str]:
        return HeuristicResearchLLMClient()._normalize_focus(list(context.get("focus") or []))

    def _collect_observation_strings(self, observations: list[dict[str, Any]], key: str) -> list[str]:
        items: list[str] = []
        for observation in observations:
            structured_data = observation.get("structured_data") or {}
            for value in structured_data.get(key) or []:
                if isinstance(value, str) and value.strip():
                    items.append(value.strip())
        return list(dict.fromkeys(items))

    def _resolve_llm_client(self, llm_client: Any | None) -> Any:
        heuristic = HeuristicResearchLLMClient()
        if llm_client is None:
            remote = OpenAICompatibleReActLLMClient()
            return FallbackReActLLMClient(remote, heuristic) if remote.is_configured() else heuristic
        if isinstance(llm_client, (HeuristicResearchLLMClient, FallbackReActLLMClient)):
            return llm_client
        return FallbackReActLLMClient(llm_client, heuristic)

    def _read_asset_memory(self, asset: str) -> dict:
        md_path = self.assets_root / f"{asset}.md"
        json_path = self.assets_root / f"{asset}.json"
        return {
            "asset": asset,
            "content": md_path.read_text(encoding="utf-8") if md_path.exists() else "",
            "metadata": json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else {},
        }

    def _collect_fetched_sources(self, observations: list[dict]) -> list[dict]:
        items: list[dict] = []
        seen_urls: set[str] = set()
        for observation in observations:
            if observation.get("tool_name") != "fetch_page":
                continue
            output_summary = observation.get("output_summary") or {}
            url = output_summary.get("url")
            if not isinstance(url, str) or not url or url in seen_urls:
                continue
            seen_urls.add(url)
            items.append({"url": url, "title": output_summary.get("title")})
        return items

    def _memory_lookup(self, payload: dict) -> dict:
        asset = payload["asset"].upper()
        memory = self._read_asset_memory(asset)
        return {
            "asset": asset,
            "content": memory["content"],
            "metadata": memory["metadata"],
            "query_type": payload.get("query_type"),
        }

    def _watchlist_weekly_review(self, payload: dict) -> dict:
        watchlist_path = self.memory_root / "watchlist.json"
        watchlist = (
            json.loads(watchlist_path.read_text(encoding="utf-8")).get("assets", [])
            if watchlist_path.exists()
            else []
        )
        ordered = sorted(watchlist, key=lambda item: item.get("priority", 99))
        top_conviction = [item["symbol"] for item in ordered[:3]]
        weakening = [item["symbol"] for item in ordered if item.get("priority", 99) > 2]
        result = {
            "scope": payload.get("scope", "all"),
            "top_conviction": top_conviction,
            "weakening_thesis": weakening,
            "risk_changes": ["No major risk regime change detected in placeholder review."],
        }
        report_path = self.reports_root / "latest.md"
        report_path.write_text(
            "# Weekly Watchlist Review\n\n"
            + f"Top conviction: {', '.join(top_conviction) or 'None'}\n\n"
            + f"Weakening thesis: {', '.join(weakening) or 'None'}\n",
            encoding="utf-8",
        )
        return result

    def _generate_report(self, payload: dict) -> dict:
        report_type = payload.get("report_type", "weekly")
        scope = payload.get("scope", "watchlist")
        review = self._watchlist_weekly_review({"scope": scope})
        dated_path = self.reports_root / f"{date.today().isoformat()}-{report_type}.md"
        body = (
            f"# {report_type.title()} Report\n\n"
            f"Scope: {scope}\n\n"
            f"Top conviction: {', '.join(review['top_conviction']) or 'None'}\n\n"
            f"Weakening thesis: {', '.join(review['weakening_thesis']) or 'None'}\n\n"
            f"Risk changes: {', '.join(review['risk_changes'])}\n"
        )
        dated_path.write_text(body, encoding="utf-8")
        return {
            "report_type": report_type,
            "scope": scope,
            "report_path": str(dated_path),
            "summary": body,
        }

    def _new_token_screening(self, payload: dict) -> dict:
        asset = (payload.get("asset") or "UNKNOWN").upper()
        context = self.external_research_service.get_asset_context(asset)
        market_context = context.get("market")
        protocol_context = context.get("protocol")
        narrative_map = {
            "ENA": "restaking and yield narrative still has trader attention",
            "ARB": "L2 governance and ecosystem catalysts can re-rate sentiment",
            "OP": "superchain expansion keeps the token in circulation discussions",
            "SUI": "high-beta ecosystem rotation can pull attention back quickly",
        }
        base_strengths = [
            f"{asset} still fits a tradable narrative where upside is driven by attention expansion.",
            f"{asset} is better treated as a tactical watch candidate than a long-duration conviction hold at this stage.",
        ]
        narrative = narrative_map.get(
            asset,
            "new listings can reprice quickly when attention, liquidity, and narrative align",
        )
        strengths = [base_strengths[0], narrative, base_strengths[1]]
        risks = [
            "listing volatility can break structure quickly",
            "insufficient price history makes valuation anchoring weak",
            "unlock or emissions pressure can cap follow-through",
        ]
        screening_view = "speculative_watch"
        if asset in {"DOGE", "XRP"}:
            screening_view = "needs_confirmation"
        if asset == "UNKNOWN":
            screening_view = "avoid_for_now"
        if market_context:
            change_24h = market_context.get("price_change_percentage_24h")
            fdv_tvl = self._compute_fdv_tvl_ratio(market_context.get("fdv"), protocol_context.get("tvl") if protocol_context else None)
            if change_24h is not None:
                strengths.append(f"24h move is {change_24h:.1f}%, which confirms current attention but also raises execution risk.")
            if fdv_tvl is not None:
                risks.append(f"FDV/TVL is {fdv_tvl:.2f}, so pricing may be ahead of real usage.")
                if fdv_tvl > 8:
                    screening_view = "needs_confirmation"
        if protocol_context:
            category = protocol_context.get("category")
            chains = protocol_context.get("chains") or []
            if category:
                strengths.append(f"DefiLlama places the protocol in {category}, which gives the listing a clearer narrative bucket.")
            if chains:
                strengths.append(f"Chain footprint already spans {', '.join(chains[:2])}.")

        result = {
            "asset": asset,
            "summary": f"{asset} passes an initial new-token screen as a {screening_view.replace('_', ' ')} candidate.",
            "screening_view": screening_view,
            "strengths": strengths,
            "risks": risks,
            "focus": payload.get("focus", []),
            "horizon": payload.get("horizon"),
            "bull_case": strengths[:2],
            "bear_case": [
                "The setup can fail fast if attention rotates away before volume confirms.",
                "Without durable catalysts, the token can remain a short-lived listing trade.",
            ],
            "market_context": market_context,
            "protocol_context": protocol_context,
        }
        self._write_asset_files(asset, result)
        return result

    def _thesis_break_detector(self, payload: dict) -> dict:
        watchlist = self._read_watchlist()
        weakening_assets = []
        stable_assets = []
        for item in watchlist:
            asset = item.get("symbol", "").upper()
            if not asset:
                continue
            metadata = self._read_asset_metadata(asset)
            verdict = self._evaluate_thesis_health(asset, item, metadata)
            if verdict is None:
                stable_assets.append(asset)
                continue
            weakening_assets.append(verdict)

        return {
            "scope": payload.get("scope", "watchlist"),
            "weakening_assets": weakening_assets,
            "stable_assets": stable_assets,
            "focus": payload.get("focus", []),
        }

    def _write_asset_files(self, asset: str, result: dict) -> None:
        md_path = self.assets_root / f"{asset}.md"
        json_path = self.assets_root / f"{asset}.json"
        md_path.write_text(
            f"# {asset} Research Thesis\n\n"
            f"## Summary\n{result['summary']}\n\n"
            "## Bull Case\n"
            + "\n".join(f"- {item}" for item in result["bull_case"])
            + "\n\n## Bear Case\n"
            + "\n".join(f"- {item}" for item in result["bear_case"])
            + "\n\n## Risks\n"
            + "\n".join(f"- {item}" for item in result["risks"])
            + "\n",
            encoding="utf-8",
        )
        json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    def _read_watchlist(self) -> list[dict]:
        watchlist_path = self.memory_root / "watchlist.json"
        if not watchlist_path.exists():
            return []
        return json.loads(watchlist_path.read_text(encoding="utf-8")).get("assets", [])

    def _read_asset_metadata(self, asset: str) -> dict:
        json_path = self.assets_root / f"{asset}.json"
        if not json_path.exists():
            return {}
        return json.loads(json_path.read_text(encoding="utf-8"))

    def _evaluate_thesis_health(self, asset: str, watch_item: dict, metadata: dict) -> dict | None:
        if not metadata:
            return {
                "asset": asset,
                "severity": "warning",
                "signals": ["missing research record"],
                "reason": "No prior thesis file exists for this watchlist asset.",
            }

        risks = [str(item).lower() for item in metadata.get("risks", [])]
        summary = str(metadata.get("summary", "")).lower()
        catalysts = metadata.get("catalysts", []) or []
        status = str(metadata.get("status", "")).lower()
        signals = []

        if status in {"weakening", "at_risk", "broken"}:
            signals.append(f"status={status}")
        if any(keyword in summary for keyword in ["faded", "cooled", "slipped", "dropping"]):
            signals.append("negative summary drift")
        if any(keyword in risks for keyword in ["narrative fatigue", "execution miss on roadmap", "token unlock pressure"]):
            signals.append("material thesis risk present")
        if not catalysts:
            signals.append("no active catalyst")
        if watch_item.get("priority", 99) >= 3 and signals:
            signals.append("low watchlist priority")

        if not signals:
            return None

        severity = "critical" if len(signals) >= 3 or status in {"at_risk", "broken"} else "warning"
        return {
            "asset": asset,
            "severity": severity,
            "signals": signals,
            "reason": f"{asset} shows thesis weakening due to {', '.join(signals[:3])}.",
        }

    def _research_gaps(
        self,
        *,
        market_context: dict | None,
        protocol_context: dict | None,
        combined_text: str,
        fetched_pages: list[dict],
    ) -> list[str]:
        missing: list[str] = []
        if not fetched_pages:
            missing.append("Web evidence unavailable.")
        if not market_context and not protocol_context:
            missing.append("Market data or protocol snapshot unavailable.")
        if combined_text and not any(token in combined_text for token in ("catalyst", "roadmap", "ecosystem", "launch", "upgrade")):
            missing.append("Catalyst evidence is thin.")
        if combined_text and not any(token in combined_text for token in ("risk", "unlock", "competition", "regulatory", "security")):
            missing.append("Risk evidence is thin.")
        has_valuation_anchor = bool(
            market_context
            and any(market_context.get(field) is not None for field in ("market_cap", "fdv", "total_volume"))
        ) or bool(protocol_context and protocol_context.get("tvl") is not None)
        if (
            combined_text
            and not has_valuation_anchor
            and not any(token in combined_text for token in ("tokenomics", "valuation", "market cap", "fdv", "tvl"))
        ):
            missing.append("Valuation or tokenomics evidence is thin.")
        return missing

    def _compute_fdv_tvl_ratio(self, fdv: float | int | None, tvl: float | int | None) -> float | None:
        if fdv in {None, 0} or tvl in {None, 0}:
            return None
        return float(fdv) / float(tvl)
