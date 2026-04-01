from __future__ import annotations

from typing import Any


class ResearchResultAssembler:
    def assemble(
        self,
        *,
        asset: str,
        terminal_state: dict[str, Any],
        observations: list[dict[str, Any]],
        tool_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        successful_observations = [observation for observation in observations if observation.get("status") == "success"]
        findings = self._dedupe_strings(self._collect_structured_items(successful_observations, "findings"))
        risks = self._dedupe_strings(self._derive_context_risks(successful_observations))
        catalysts = self._dedupe_strings(self._collect_structured_items(successful_observations, "catalysts"))
        missing_information = self._dedupe_strings(terminal_state.get("missing_information") or [])
        degraded_reason = self._join_degraded_reasons(terminal_state, tool_results)

        summary_parts: list[str] = []
        preferred_finding = self._select_summary_finding(findings)
        if preferred_finding:
            summary_parts.append(preferred_finding)
        if risks:
            summary_parts.append(f"Risks include {risks[0]}.")
        if catalysts:
            summary_parts.append(f"Catalysts include {catalysts[0]}.")
        if not summary_parts:
            summary_parts.append("research evidence remains limited.")

        return {
            "agent": "ResearchAgent",
            "status": terminal_state.get("status", "insufficient"),
            "evidence_status": terminal_state.get("evidence_status", "insufficient"),
            "summary": f"{asset} " + " ".join(summary_parts),
            "findings": findings,
            "risks": risks,
            "catalysts": catalysts,
            "missing_information": missing_information,
            "degraded_reason": degraded_reason,
            "termination_reason": terminal_state.get("termination_reason"),
            "rounds_used": int(terminal_state.get("rounds_used") or 0),
            "tool_calls": list(tool_results),
        }

    def _select_summary_finding(self, findings: list[str]) -> str | None:
        preferred_keywords = (
            "fed",
            "federal reserve",
            "iran",
            "war",
            "oil",
            "yield",
            "inflation",
            "macro",
            "etf",
            "geopolitical",
            "risk asset",
            "btc",
            "bitcoin",
        )
        generic_prefixes = ("market_cap=", "tvl=", "last_price=", "candles=")

        for finding in findings:
            lowered = finding.lower()
            if lowered.startswith(generic_prefixes):
                continue
            if any(keyword in lowered for keyword in preferred_keywords):
                return finding

        for finding in findings:
            if not finding.lower().startswith(generic_prefixes):
                return finding

        return findings[0] if findings else None

    def _collect_structured_items(self, observations: list[dict[str, Any]], key: str) -> list[str]:
        items: list[str] = []
        for observation in observations:
            structured_data = observation.get("structured_data") or {}
            values = structured_data.get(key) or []
            for value in values:
                if isinstance(value, str) and value.strip():
                    items.append(value.strip())
        return items

    def _derive_context_risks(self, observations: list[dict[str, Any]]) -> list[str]:
        context_risks: list[str] = []
        market_observations = [
            observation
            for observation in observations
            if observation.get("tool_name") in {"get_market_snapshot", "get_protocol_snapshot"}
        ]
        if market_observations:
            context_risks.extend(self._collect_structured_items(market_observations, "risks"))
        return context_risks

    def _join_degraded_reasons(self, terminal_state: dict[str, Any], tool_results: list[dict[str, Any]]) -> str | None:
        reasons = []
        for reason in terminal_state.get("degraded_reasons") or []:
            if isinstance(reason, str) and reason:
                reasons.append(reason)
        for tool_result in tool_results:
            if tool_result.get("status") != "degraded":
                continue
            reason = tool_result.get("reason")
            if isinstance(reason, str) and reason:
                reasons.append(reason)
        unique = self._dedupe_strings(reasons)
        return "; ".join(unique) if unique else None

    def _dedupe_strings(self, values: list[Any]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str):
                continue
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered
