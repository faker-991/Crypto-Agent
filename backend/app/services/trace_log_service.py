import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.runtime.trace_runtime import TraceRuntime


class TraceLogService:
    def __init__(self, memory_root: Path) -> None:
        self.trace_root = memory_root / "traces"
        self.trace_root.mkdir(parents=True, exist_ok=True)

    def write_trace(
        self,
        *,
        user_query: str,
        status: str | None = None,
        plan: dict | None = None,
        task_results: list[dict] | None = None,
        execution_summary: dict | None,
        final_answer: str | None = None,
        events: list[dict] | None = None,
        spans: list[dict] | None = None,
        metrics_summary: dict | None = None,
        tool_usage_summary: dict | None = None,
        error_summary: list[dict] | None = None,
        agent_summaries: list[dict] | None = None,
    ) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.trace_root / f"{timestamp}.json"
        base_events = list(events or [])
        base_events.extend(self._build_binance_endpoint_events(plan, task_results, execution_summary))
        canonical_spans = self._build_canonical_spans(
            timestamp=timestamp,
            status=status,
            plan=plan,
            task_results=task_results,
            spans=spans,
        )
        persisted_spans = [TraceRuntime.prepare_span_for_persistence(span) for span in canonical_spans]
        summary_cards = self._build_summary_cards(
            spans=persisted_spans,
            metrics_summary=metrics_summary,
            tool_usage_summary=tool_usage_summary,
            error_summary=error_summary,
            agent_summaries=agent_summaries,
        )
        payload: dict = {
            "timestamp": timestamp,
            "user_query": user_query,
            "execution_summary": execution_summary,
            "events": base_events,
            "spans": persisted_spans,
            "metrics_summary": summary_cards["metrics_summary"],
            "tool_usage_summary": summary_cards["tool_usage_summary"],
            "llm_call_count": summary_cards["llm_call_count"],
            "tool_call_count": summary_cards["tool_call_count"],
            "failure_count": summary_cards["failure_count"],
            "error_summary": summary_cards["error_summary"],
            "agent_summaries": summary_cards["agent_summaries"],
        }
        if status is not None:
            payload["status"] = status
        if plan is not None:
            payload["plan"] = plan
        if task_results is not None:
            payload["task_results"] = task_results
        if final_answer is not None:
            payload["final_answer"] = final_answer
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return str(path)

    def list_traces(self, limit: int = 20) -> list[dict]:
        items = []
        paths = sorted(self.trace_root.glob("*.json"), reverse=True)[:limit]
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            items.append(
                {
                    "path": str(path),
                    "id": path.name,
                    "timestamp": payload.get("timestamp"),
                    "user_query": payload.get("user_query"),
                    "status": payload.get("status") or payload.get("route", {}).get("type"),
                    "mode": payload.get("plan", {}).get("mode"),
                    "task_count": len(payload.get("plan", {}).get("tasks") or []),
                    "agent": self._infer_actor(payload),
                }
            )
        return items

    def read_trace(self, trace_id: str) -> dict:
        path = self.trace_root / trace_id
        payload = json.loads(path.read_text(encoding="utf-8"))
        if "spans" not in payload or not isinstance(payload.get("spans"), list):
            rebuilt_spans = self._build_canonical_spans(
                timestamp=payload.get("timestamp") or trace_id.removesuffix(".json"),
                status=payload.get("status"),
                plan=payload.get("plan") if isinstance(payload.get("plan"), dict) else None,
                task_results=payload.get("task_results") if isinstance(payload.get("task_results"), list) else None,
                spans=None,
            )
            if rebuilt_spans:
                payload["spans"] = rebuilt_spans
            else:
                pseudo_spans = self._build_pseudo_spans(payload)
                payload["pseudo_spans"] = pseudo_spans
                payload["spans"] = pseudo_spans
        if "metrics_summary" not in payload:
            payload["metrics_summary"] = self._build_summary_cards(
                spans=payload["spans"],
                metrics_summary=None,
                tool_usage_summary=payload.get("tool_usage_summary"),
                error_summary=payload.get("error_summary"),
                agent_summaries=payload.get("agent_summaries"),
            )["metrics_summary"]
        if "tool_usage_summary" not in payload:
            payload["tool_usage_summary"] = self._build_summary_cards(
                spans=payload["spans"],
                metrics_summary=payload.get("metrics_summary"),
                tool_usage_summary=None,
                error_summary=payload.get("error_summary"),
                agent_summaries=payload.get("agent_summaries"),
            )["tool_usage_summary"]
        if "error_summary" not in payload:
            payload["error_summary"] = self._build_summary_cards(
                spans=payload["spans"],
                metrics_summary=payload.get("metrics_summary"),
                tool_usage_summary=payload.get("tool_usage_summary"),
                error_summary=None,
                agent_summaries=payload.get("agent_summaries"),
            )["error_summary"]
        if "agent_summaries" not in payload:
            payload["agent_summaries"] = self._build_summary_cards(
                spans=payload["spans"],
                metrics_summary=payload.get("metrics_summary"),
                tool_usage_summary=payload.get("tool_usage_summary"),
                error_summary=payload.get("error_summary"),
                agent_summaries=None,
            )["agent_summaries"]
        if "llm_call_count" not in payload or "tool_call_count" not in payload or "failure_count" not in payload:
            derived = self._build_summary_cards(
                spans=payload["spans"],
                metrics_summary=payload.get("metrics_summary"),
                tool_usage_summary=payload.get("tool_usage_summary"),
                error_summary=payload.get("error_summary"),
                agent_summaries=payload.get("agent_summaries"),
            )
            payload.setdefault("llm_call_count", derived["llm_call_count"])
            payload.setdefault("tool_call_count", derived["tool_call_count"])
            payload.setdefault("failure_count", derived["failure_count"])
        return payload

    def append_events(self, trace_path: str, events: list[dict]) -> None:
        self.append_trace_data(trace_path, events=events)

    def append_trace_data(
        self,
        trace_path: str,
        *,
        events: list[dict] | None = None,
        spans: list[dict] | None = None,
        status: str | None = None,
    ) -> None:
        path = Path(trace_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["events"] = [*(payload.get("events") or []), *(events or [])]
        if spans:
            payload["spans"] = [*(payload.get("spans") or []), *spans]
            payload["spans"] = sorted(
                [span for span in payload["spans"] if isinstance(span, dict)],
                key=lambda span: (
                    self._parse_iso8601(span.get("start_ts")).isoformat()
                    if self._parse_iso8601(span.get("start_ts"))
                    else "9999",
                    str(span.get("span_id") or ""),
                ),
            )
        if status is not None:
            payload["status"] = status
        elif spans:
            payload["status"] = self._merge_status(payload.get("status"), spans)

        if payload.get("spans"):
            summary_cards = self._build_summary_cards(
                spans=payload["spans"],
                metrics_summary=None,
                tool_usage_summary=None,
                error_summary=None,
                agent_summaries=None,
            )
            payload["metrics_summary"] = summary_cards["metrics_summary"]
            payload["tool_usage_summary"] = summary_cards["tool_usage_summary"]
            payload["llm_call_count"] = summary_cards["llm_call_count"]
            payload["tool_call_count"] = summary_cards["tool_call_count"]
            payload["failure_count"] = summary_cards["failure_count"]
            payload["error_summary"] = summary_cards["error_summary"]
            payload["agent_summaries"] = summary_cards["agent_summaries"]
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _build_binance_endpoint_events(
        self,
        plan: dict | None,
        task_results: list[dict] | None,
        execution_summary: dict | None,
    ) -> list[dict]:
        if not execution_summary:
            return []
        kline_result = next(
            (
                result
                for result in (task_results or [])
                if isinstance(result, dict) and result.get("task_type") == "kline"
            ),
            None,
        )
        kline_payload = kline_result.get("payload") if isinstance(kline_result, dict) else {}
        provenance = kline_payload.get("kline_provenance") if isinstance(kline_payload, dict) else {}
        if not isinstance(provenance, dict) or not provenance:
            return []
        plan_tasks = (plan or {}).get("tasks") or []
        kline_task = next((task for task in plan_tasks if task.get("task_type") == "kline"), {})
        task_slots = kline_task.get("slots") or {}
        actor = self._infer_actor({"plan": plan}) or "skill"
        events: list[dict] = []
        for timeframe, entry in provenance.items():
            if not isinstance(entry, dict):
                continue
            endpoint_summary = entry.get("endpoint_summary") or {}
            if not endpoint_summary:
                continue
            events.append(
                {
                    "name": f"binance.endpoint.{endpoint_summary.get('endpoint', 'call')}.{timeframe}",
                    "actor": actor,
                    "detail": {
                        "integration": endpoint_summary.get("integration"),
                        "endpoint": endpoint_summary.get("endpoint"),
                        "input_summary": {
                            "asset": task_slots.get("asset") or execution_summary.get("asset"),
                            "timeframe": timeframe,
                            "market_type": entry.get("market_type") or task_slots.get("market_type"),
                        },
                        "output_summary": {
                            "source": entry.get("source"),
                            "market_type": entry.get("market_type"),
                        },
                        "degraded": bool(entry.get("degraded_reason")),
                        "error": entry.get("degraded_reason"),
                    },
                }
            )
        return events

    def _infer_actor(self, payload: dict) -> str | None:
        task_results = payload.get("task_results") or []
        if task_results:
            first_result = task_results[0] or {}
            if first_result.get("agent"):
                return first_result.get("agent")
        plan = payload.get("plan") or {}
        tasks = plan.get("tasks") or []
        first_task = tasks[0] if tasks else {}
        task_type = first_task.get("task_type")
        if task_type == "research":
            return "ResearchAgent"
        if task_type == "kline":
            return "KlineAgent"
        if task_type == "summary":
            return "SummaryAgent"
        legacy_route = payload.get("route") or {}
        if legacy_route.get("agent"):
            return legacy_route.get("agent")
        return None

    def _build_canonical_spans(
        self,
        *,
        timestamp: str,
        status: str | None,
        plan: dict | None,
        task_results: list[dict] | None,
        spans: list[dict] | None,
    ) -> list[dict]:
        derived_spans: list[dict[str, Any]] = []
        trace_id = timestamp
        iso_timestamp = self._timestamp_to_iso8601(timestamp)
        agent_span_ids_by_task: dict[str, str] = {}
        if plan is not None:
            derived_spans.append(
                {
                    "span_id": "planner",
                    "parent_span_id": None,
                    "trace_id": trace_id,
                    "kind": "planner",
                    "name": "Planner",
                    "status": "success" if status != "failed" else "failed",
                    "start_ts": iso_timestamp,
                    "end_ts": iso_timestamp,
                    "duration_ms": 0.0,
                    "input_summary": {"goal": (plan or {}).get("goal")},
                    "output_summary": {"status": status},
                    "error": None,
                    "attributes": {
                        "decision_mode": (plan or {}).get("decision_mode") or (plan or {}).get("mode"),
                        "needs_clarification": bool((plan or {}).get("needs_clarification")),
                        "planner_source": (plan or {}).get("planner_source"),
                        "planner_fallback_reason": (plan or {}).get("planner_fallback_reason"),
                    },
                    "metrics": {},
                    "audit": {"actor": "Planner"},
                }
            )

        for index, result in enumerate(task_results or [], start=1):
            result_dict = result if isinstance(result, dict) else {}
            agent = result_dict.get("agent")
            span_id = f"agent-{index}"
            agent_span_ids_by_task[str(result_dict.get("task_id") or span_id)] = span_id
            derived_spans.append(
                {
                    "span_id": span_id,
                    "parent_span_id": "planner" if plan is not None else None,
                    "trace_id": trace_id,
                    "kind": "agent",
                    "name": agent or "unknown",
                    "status": result_dict.get("status") or "unknown",
                    "start_ts": result_dict.get("start_ts") or iso_timestamp,
                    "end_ts": result_dict.get("end_ts") or iso_timestamp,
                    "duration_ms": result_dict.get("duration_ms") or 0.0,
                    "input_summary": {"task_type": result_dict.get("task_type")},
                    "output_summary": {"summary": result_dict.get("summary")},
                    "error": None,
                    "attributes": (
                        {"task_id": result_dict.get("task_id"), "agent": agent}
                        if agent
                        else {"task_id": result_dict.get("task_id")}
                    ),
                    "metrics": {},
                    "audit": {"actor": agent} if agent else {},
                }
            )

        internal_spans = self._extract_agent_internal_spans(
            trace_id=trace_id,
            task_results=task_results,
            agent_span_ids_by_task=agent_span_ids_by_task,
        )
        combined = [*derived_spans, *internal_spans, *(list(spans) if spans else [])]
        return sorted(
            [span for span in combined if isinstance(span, dict)],
            key=lambda span: (
                self._parse_iso8601(span.get("start_ts")).isoformat()
                if self._parse_iso8601(span.get("start_ts"))
                else "9999",
                str(span.get("span_id") or ""),
            ),
        )

    def _extract_agent_internal_spans(
        self,
        *,
        trace_id: str,
        task_results: list[dict] | None,
        agent_span_ids_by_task: dict[str, str],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for result in task_results or []:
            result_dict = result if isinstance(result, dict) else {}
            task_id = str(result_dict.get("task_id") or "")
            parent_agent_span_id = agent_span_ids_by_task.get(task_id)
            payload = result_dict.get("payload") if isinstance(result_dict.get("payload"), dict) else {}
            trace_summary = payload.get("trace_summary") if isinstance(payload.get("trace_summary"), dict) else {}
            raw_spans = trace_summary.get("spans")
            if not isinstance(raw_spans, list) or not raw_spans:
                raw_spans = self._derive_internal_spans_from_payload(
                    trace_id=trace_id,
                    task_id=task_id,
                    parent_agent_span_id=parent_agent_span_id,
                    task_result=result_dict,
                    payload=payload,
                )
            if not isinstance(raw_spans, list) or not raw_spans:
                continue

            span_id_map: dict[str, str] = {}
            for index, raw_span in enumerate(raw_spans, start=1):
                if not isinstance(raw_span, dict):
                    continue
                original_span_id = str(raw_span.get("span_id") or f"span-{index}")
                span_id_map[original_span_id] = f"{task_id or 'task'}-{original_span_id}"

            for index, raw_span in enumerate(raw_spans, start=1):
                if not isinstance(raw_span, dict):
                    continue
                original_span_id = str(raw_span.get("span_id") or f"span-{index}")
                original_parent = raw_span.get("parent_span_id")
                copied = deepcopy(raw_span)
                copied["span_id"] = span_id_map.get(original_span_id, f"{task_id or 'task'}-{original_span_id}")
                copied["trace_id"] = trace_id
                if isinstance(original_parent, str) and original_parent in span_id_map:
                    copied["parent_span_id"] = span_id_map[original_parent]
                else:
                    copied["parent_span_id"] = parent_agent_span_id
                normalized.append(copied)
        return normalized

    def _derive_internal_spans_from_payload(
        self,
        *,
        trace_id: str,
        task_id: str,
        parent_agent_span_id: str | None,
        task_result: dict[str, Any],
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        raw_spans: list[dict[str, Any]] = []
        task_start = task_result.get("start_ts") or self._timestamp_to_iso8601(trace_id)
        task_end = task_result.get("end_ts") or task_start
        agent_name = task_result.get("agent")
        task_status = task_result.get("status") or "unknown"
        tool_calls = payload.get("tool_calls") if isinstance(payload.get("tool_calls"), list) else []
        agent_loop = payload.get("agent_loop") if isinstance(payload.get("agent_loop"), list) else []

        llm_span_ids_by_round: dict[int, str] = {}
        for index, entry in enumerate(agent_loop, start=1):
            if not isinstance(entry, dict):
                continue
            round_number = int(entry.get("round") or index)
            decision = entry.get("decision") if isinstance(entry.get("decision"), dict) else {}
            action = entry.get("action") if isinstance(entry.get("action"), dict) else {}
            observation = entry.get("observation") if isinstance(entry.get("observation"), dict) else {}
            result = entry.get("result") if isinstance(entry.get("result"), dict) else {}
            llm_status = (
                "failed"
                if result.get("error")
                else "degraded"
                if result.get("degraded")
                else "success"
            )
            llm_span_id = f"{task_id or 'task'}-round-{round_number}"
            llm_span_ids_by_round[round_number] = llm_span_id
            raw_spans.append(
                {
                    "span_id": llm_span_id,
                    "parent_span_id": None,
                    "trace_id": trace_id,
                    "kind": "llm",
                    "name": f"{task_result.get('task_type') or 'agent'}_round_{round_number}",
                    "status": llm_status,
                    "start_ts": task_start,
                    "end_ts": task_end,
                    "duration_ms": None,
                    "input_summary": {
                        "round": round_number,
                        "decision_summary": decision.get("summary"),
                    },
                    "output_summary": {
                        "tool": action.get("tool"),
                        "termination": entry.get("termination"),
                        "observation": observation.get("summary"),
                    },
                    "error": result.get("error"),
                    "attributes": {
                        "agent": agent_name,
                        "fallback_error": result.get("fallback_error"),
                    },
                    "metrics": {},
                    "audit": {"actor": agent_name},
                }
            )

        for index, call in enumerate(tool_calls, start=1):
            if not isinstance(call, dict):
                continue
            round_number = int(call.get("round") or index)
            tool_name = str(call.get("tool") or "unknown")
            input_summary = call.get("input") if isinstance(call.get("input"), dict) else {}
            output_summary = call.get("output") if isinstance(call.get("output"), dict) else {}
            error = call.get("error")
            status = (
                "failed"
                if error
                else "degraded"
                if output_summary.get("degraded_reason") or output_summary.get("source") == "unavailable"
                else task_status if task_status in {"failed", "degraded"} and not output_summary
                else "success"
            )
            raw_spans.append(
                {
                    "span_id": f"{task_id or 'task'}-tool-{index}",
                    "parent_span_id": llm_span_ids_by_round.get(round_number),
                    "trace_id": trace_id,
                    "kind": "tool",
                    "name": tool_name,
                    "status": status,
                    "start_ts": task_start,
                    "end_ts": task_end,
                    "duration_ms": None,
                    "input_summary": input_summary,
                    "output_summary": output_summary,
                    "error": error or output_summary.get("degraded_reason"),
                    "attributes": {
                        "tool_name": tool_name,
                        "tool_server": self._infer_tool_server(tool_name),
                        "agent": agent_name,
                    },
                    "metrics": {},
                    "audit": {"actor": agent_name},
                }
            )

        return raw_spans

    def _infer_tool_server(self, tool_name: str) -> str:
        if tool_name in {"search_web", "fetch_page", "read_asset_memory"}:
            return "research"
        if tool_name in {"get_market_snapshot", "get_protocol_snapshot", "get_ticker", "get_klines"}:
            return "market"
        if tool_name in {"compute_indicators"}:
            return "kline"
        return "unknown"

    def _build_pseudo_spans(self, payload: dict) -> list[dict]:
        trace_id = payload.get("trace_id") or payload.get("timestamp") or "legacy-trace"
        legacy_route = payload.get("route") or payload.get("legacy_route") or {}
        if legacy_route:
            return [
                {
                    "span_id": "planner",
                    "parent_span_id": None,
                    "trace_id": trace_id,
                    "kind": "planner",
                    "name": "Planner",
                    "status": "unknown",
                    "start_ts": str(payload.get("timestamp") or trace_id),
                    "end_ts": None,
                    "duration_ms": None,
                    "input_summary": {},
                    "output_summary": {"route": legacy_route.get("type")},
                    "error": None,
                    "attributes": {"legacy_route": legacy_route},
                    "metrics": {},
                    "audit": {"actor": legacy_route.get("agent") or "Planner"},
                }
            ]

        return []

    def _build_summary_cards(
        self,
        *,
        spans: list[dict],
        metrics_summary: dict | None,
        tool_usage_summary: dict | None,
        error_summary: list[dict] | None,
        agent_summaries: list[dict] | None,
    ) -> dict[str, Any]:
        runtime = TraceRuntime()
        derived_metrics = runtime._build_metrics_summary(spans)
        derived_usage = runtime._build_tool_usage_summary(spans)
        derived_errors = runtime._build_error_summary(spans)
        derived_agents = runtime._build_agent_summaries(spans)
        final_metrics = metrics_summary or derived_metrics
        final_usage = tool_usage_summary or derived_usage
        final_error_summary = error_summary if error_summary is not None else derived_errors
        final_agent_summaries = agent_summaries if agent_summaries is not None else derived_agents
        return {
            "metrics_summary": final_metrics,
            "tool_usage_summary": final_usage,
            "llm_call_count": sum(1 for span in spans if span.get("kind") == "llm"),
            "tool_call_count": final_usage.get("total_calls", 0),
            "failure_count": sum(
                1
                for span in spans
                if span.get("status") in {"failed", "degraded", "insufficient"}
                and span.get("kind") in {"tool", "llm", "agent"}
            ),
            "error_summary": final_error_summary,
            "agent_summaries": final_agent_summaries,
        }

    def _timestamp_to_iso8601(self, timestamp: str) -> str:
        parsed = datetime.strptime(timestamp, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
        return parsed.isoformat().replace("+00:00", "Z")

    def _parse_iso8601(self, value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _merge_status(self, current_status: Any, spans: list[dict]) -> str | None:
        if not isinstance(current_status, str) or not current_status:
            current_status = None
        span_statuses = {
            str(span.get("status"))
            for span in spans
            if isinstance(span, dict) and isinstance(span.get("status"), str)
        }
        if current_status in {"clarify", "cancelled", "failed"}:
            return current_status
        if "failed" in span_statuses or "degraded" in span_statuses or "insufficient" in span_statuses:
            return "partial_failure"
        return current_status
