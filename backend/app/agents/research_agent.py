import json
from pathlib import Path
from datetime import date

from app.agents.tools.research_tools import ResearchToolbox
from app.services.external_research_service import ExternalResearchService


class ResearchAgent:
    name = "ResearchAgent"

    def __init__(
        self,
        memory_root: Path,
        external_research_service: ExternalResearchService | None = None,
        research_toolbox: ResearchToolbox | None = None,
    ) -> None:
        self.memory_root = memory_root
        self.assets_root = memory_root / "assets"
        self.reports_root = memory_root / "reports" / "weekly"
        self.external_research_service = external_research_service or ExternalResearchService()
        self.research_toolbox = research_toolbox or ResearchToolbox()
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
        context = self.external_research_service.get_asset_context(asset)
        market_context = context.get("market")
        protocol_context = context.get("protocol")
        loop_state = self._run_due_diligence_loop(
            asset=asset,
            market_context=market_context,
            protocol_context=protocol_context,
        )
        fetched_pages = loop_state["fetched_pages"]
        missing_information = loop_state["missing_information"]
        evidence_sufficient = not missing_information
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
            fdv_tvl = self._compute_fdv_tvl_ratio(fdv, protocol_context.get('tvl') if protocol_context else None)
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
        result = {
            "agent": self.name,
            "status": "success" if evidence_sufficient else "insufficient",
            "asset": asset,
            "summary": f"{asset} is worth continued monitoring for a medium-term thesis.",
            "bull_case": bull_case,
            "bear_case": [
                f"{asset} may fail to sustain attention if catalysts weaken.",
                f"{asset} still requires deeper validation on execution and valuation.",
            ],
            "risks": risks,
            "focus": payload.get("focus", []),
            "horizon": payload.get("horizon"),
            "market_context": market_context,
            "protocol_context": protocol_context,
            "evidence_sufficient": evidence_sufficient,
            "missing_information": missing_information,
            "tool_calls": loop_state["tool_calls"],
            "rounds_used": loop_state["rounds_used"],
            "agent_loop": loop_state["agent_loop"],
            "termination_reason": loop_state["termination_reason"],
            "fetched_sources": [
                {"url": page.get("url"), "title": page.get("title")}
                for page in fetched_pages
            ],
        }
        self._write_asset_files(asset, result)
        return result

    def _run_due_diligence_loop(
        self,
        *,
        asset: str,
        market_context: dict | None,
        protocol_context: dict | None,
        max_rounds: int = 4,
    ) -> dict:
        search_query = f"{asset} crypto tokenomics roadmap catalysts risks"
        fetched_pages: list[dict] = []
        tool_calls: list[dict] = []
        agent_loop: list[dict] = []
        candidates: list[dict] = []
        seen_urls: set[str] = set()
        search_completed = False
        termination_reason = "达到最大轮次，停止循环。"

        for round_number in range(1, max_rounds + 1):
            current_missing = self._research_gaps(
                market_context=market_context,
                protocol_context=protocol_context,
                combined_text=" ".join(page.get("text", "") for page in fetched_pages).lower(),
                fetched_pages=fetched_pages,
            )
            observation = {
                "fetched_pages": len(fetched_pages),
                "missing_information": current_missing,
                "remaining_candidates": len(candidates),
            }

            if not search_completed:
                search_result = self.research_toolbox.search_web(search_query)
                search_completed = True
                new_urls: list[str] = []
                for candidate in (search_result.get("results") or [])[:5]:
                    url = candidate.get("url")
                    if not isinstance(url, str) or not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    candidates.append(candidate)
                    new_urls.append(url)
                tool_calls.append(
                    {
                        "round": round_number,
                        "tool": "search_web",
                        "input": {"query": search_query},
                        "output": {"status": search_result.get("status"), "result_count": len(search_result.get("results", []))},
                    }
                )
                step = {
                    "round": round_number,
                    "observation": observation,
                    "decision": {"reason": "先搜索催化剂、路线图和风险来源。"},
                    "action": {"tool": "search_web", "input": {"query": search_query}},
                    "result": {"status": search_result.get("status"), "result_count": len(search_result.get("results", []))},
                    "state_update": {"new_urls": new_urls, "remaining_candidates": len(candidates)},
                }
                if not new_urls:
                    termination_reason = "没有找到可继续抓取的新来源，停止循环。"
                    step["termination"] = {"reason": termination_reason}
                    agent_loop.append(step)
                    break
                agent_loop.append(step)
                continue

            if not candidates:
                termination_reason = "没有更多高价值来源，停止循环。"
                agent_loop.append(
                    {
                        "round": round_number,
                        "observation": observation,
                        "decision": {"reason": "当前没有新的高价值来源可以继续抓取。"},
                        "action": {"tool": "finish", "input": {}},
                        "result": {"status": "finished"},
                        "state_update": {"remaining_candidates": 0},
                        "termination": {"reason": termination_reason},
                    }
                )
                break

            candidate = candidates.pop(0)
            url = candidate.get("url", "")
            page = self.research_toolbox.fetch_page(url)
            if page.get("status") == "success" and page.get("text"):
                fetched_pages.append(page)
            updated_missing = self._research_gaps(
                market_context=market_context,
                protocol_context=protocol_context,
                combined_text=" ".join(page.get("text", "") for page in fetched_pages).lower(),
                fetched_pages=fetched_pages,
            )
            new_findings = [page.get("title")] if page.get("status") == "success" and page.get("title") else []
            tool_calls.append(
                {
                    "round": round_number,
                    "tool": "fetch_page",
                    "input": {"url": url},
                    "output": {"status": page.get("status"), "title": page.get("title", "")},
                }
            )
            step = {
                "round": round_number,
                "observation": observation | {"candidate_url": url},
                "decision": {"reason": "抓取当前最相关的候选页面补足证据。"},
                "action": {"tool": "fetch_page", "input": {"url": url}},
                "result": {"status": page.get("status"), "title": page.get("title", ""), "url": url},
                "state_update": {
                    "new_findings": new_findings,
                    "missing_information": updated_missing,
                    "remaining_candidates": len(candidates),
                },
            }

            if not updated_missing:
                termination_reason = "证据已足够，停止循环。"
                step["termination"] = {"reason": termination_reason}
                agent_loop.append(step)
                break
            if not new_findings and not candidates:
                termination_reason = "连续一轮没有新增信息，停止循环。"
                step["termination"] = {"reason": termination_reason}
                agent_loop.append(step)
                break
            if not candidates:
                termination_reason = "没有更多高价值来源，停止循环。"
                step["termination"] = {"reason": termination_reason}
                agent_loop.append(step)
                break

            agent_loop.append(step)
        else:
            termination_reason = "达到最大轮次，停止循环。"
            if agent_loop:
                agent_loop[-1]["termination"] = {"reason": termination_reason}

        final_missing = self._research_gaps(
            market_context=market_context,
            protocol_context=protocol_context,
            combined_text=" ".join(page.get("text", "") for page in fetched_pages).lower(),
            fetched_pages=fetched_pages,
        )
        return {
            "fetched_pages": fetched_pages,
            "tool_calls": tool_calls,
            "agent_loop": agent_loop,
            "termination_reason": termination_reason,
            "rounds_used": len(agent_loop),
            "missing_information": final_missing,
        }

    def _memory_lookup(self, payload: dict) -> dict:
        asset = payload["asset"].upper()
        md_path = self.assets_root / f"{asset}.md"
        json_path = self.assets_root / f"{asset}.json"
        content = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        metadata = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else {}
        return {
            "asset": asset,
            "content": content,
            "metadata": metadata,
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
