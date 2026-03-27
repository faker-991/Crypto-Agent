from app.schemas.task_result import TaskResult


class SummaryAgent:
    name = "SummaryAgent"

    def summarize(self, task_results: list[TaskResult | dict], payload: dict) -> dict:
        normalized_results: list[TaskResult] = []
        for item in task_results:
            if isinstance(item, TaskResult):
                normalized_results.append(item)
            else:
                normalized_results.append(TaskResult.model_validate(item))

        asset = (payload.get("asset") or "UNKNOWN").upper()
        task_summaries = [result.summary for result in normalized_results if result.summary]
        agent_sufficiency = {
            result.agent: bool(result.evidence_sufficient) if result.evidence_sufficient is not None else result.status == "success"
            for result in normalized_results
        }
        missing_information: list[str] = []
        for result in normalized_results:
            missing_information.extend(result.missing_information)

        final_answer = " ".join(task_summaries) if task_summaries else f"{asset} summary is unavailable."
        if missing_information:
            final_answer = (
                f"{final_answer} 当前有部分证据不足："
                + "；".join(dict.fromkeys(missing_information))
            ).strip()
        execution_summary = {
            "asset": asset,
            "task_summaries": task_summaries,
            "agent_sufficiency": agent_sufficiency,
            "missing_information": list(dict.fromkeys(missing_information)),
        }
        for result in normalized_results:
            payload_dict = result.payload if isinstance(result.payload, dict) else {}
            if result.task_type == "kline":
                execution_summary["analysis_timeframes"] = payload_dict.get("timeframes") or sorted(
                    (payload_dict.get("analyses") or {}).keys()
                )
                if isinstance(payload_dict.get("market_summary"), dict):
                    execution_summary["market_summary"] = payload_dict["market_summary"]
                if isinstance(payload_dict.get("kline_provenance"), dict):
                    entries = [entry for entry in payload_dict["kline_provenance"].values() if isinstance(entry, dict)]
                    sources = {entry.get("source") for entry in entries if entry.get("source")}
                    degraded = [
                        entry.get("degraded_reason")
                        for entry in entries
                        if isinstance(entry.get("degraded_reason"), str) and entry.get("degraded_reason")
                    ]
                    execution_summary["provenance"] = {
                        "source": sources.pop() if len(sources) == 1 else ("mixed" if sources else None),
                        "degraded_reason": "; ".join(degraded) if degraded else None,
                        "timeframes": list(payload_dict["kline_provenance"].keys()),
                    }
            if result.task_type == "research":
                if payload_dict.get("market_context") is not None:
                    execution_summary["market_context"] = payload_dict.get("market_context")
                if payload_dict.get("protocol_context") is not None:
                    execution_summary["protocol_context"] = payload_dict.get("protocol_context")
        return {
            "asset": asset,
            "summary": f"{asset} combined summary",
            "final_answer": final_answer,
            "status": "success" if all(agent_sufficiency.values()) else "insufficient",
            "evidence_sufficient": all(agent_sufficiency.values()) if agent_sufficiency else False,
            "missing_information": list(dict.fromkeys(missing_information)),
            "execution_summary": execution_summary,
        }
