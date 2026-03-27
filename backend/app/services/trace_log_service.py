import json
from datetime import datetime, timezone
from pathlib import Path


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
    ) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.trace_root / f"{timestamp}.json"
        base_events = list(events or [])
        base_events.extend(self._build_binance_endpoint_events(plan, task_results, execution_summary))
        payload: dict = {
            "timestamp": timestamp,
            "user_query": user_query,
            "execution_summary": execution_summary,
            "events": base_events,
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
        return json.loads(path.read_text(encoding="utf-8"))

    def append_events(self, trace_path: str, events: list[dict]) -> None:
        path = Path(trace_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["events"] = [*(payload.get("events") or []), *events]
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
