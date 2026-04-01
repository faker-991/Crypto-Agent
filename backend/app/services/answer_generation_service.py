import json
import os
from pathlib import Path

import httpx

from app.schemas.conversation import AnswerGenerationResult


class OpenAIAnswerAdapter:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
        env_file: Path | None = None,
    ) -> None:
        env_values = self._read_env_file(
            env_file or Path(__file__).resolve().parents[2] / ".env"
        )
        self.api_key = (
            api_key
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("ROUTER_LLM_API_KEY")
            or env_values.get("OPENAI_API_KEY")
            or env_values.get("ROUTER_LLM_API_KEY")
        )
        self.model = (
            model
            or os.getenv("OPENAI_MODEL")
            or os.getenv("ROUTER_LLM_MODEL")
            or env_values.get("OPENAI_MODEL")
            or env_values.get("ROUTER_LLM_MODEL")
        )
        self.base_url = (
            base_url
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("ROUTER_LLM_BASE_URL")
            or env_values.get("OPENAI_BASE_URL")
            or env_values.get("ROUTER_LLM_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        resolved_timeout = timeout
        if resolved_timeout is None:
            raw_timeout = (
                os.getenv("OPENAI_TIMEOUT")
                or os.getenv("ROUTER_LLM_TIMEOUT")
                or env_values.get("OPENAI_TIMEOUT")
                or env_values.get("ROUTER_LLM_TIMEOUT")
            )
            resolved_timeout = float(raw_timeout) if raw_timeout else 60.0
        self.client = client or httpx.Client(timeout=resolved_timeout)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    def generate_answer(self, *, prompt: dict) -> tuple[str | None, dict]:
        if not self.is_configured():
            return None, {}
        response = self.client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a crypto research assistant. "
                            "Answer only from the provided execution context. "
                            "If data is unavailable, say so explicitly. "
                            "Do not invent tool calls or prices. "
                            "If market_context contains market_cap, total_volume, or price_change_percentage_24h, "
                            "you must treat those values as available and include them when relevant instead of saying they are missing. "
                            "If analysis_timeframes or market_summary.analysis_summary are present, do not claim the related timeframes are unavailable. "
                            "If research_digest contains findings, risks, catalysts, or source headlines about Fed, Iran, war, oil, ETF, inflation, or yields, "
                            "you must treat those macro inputs as available and summarize their impact instead of saying the macro context is missing."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(prompt, ensure_ascii=False),
                    },
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage") or {}
        if not content:
            return None, usage
        return self._strip_code_fence(content), usage

    def _strip_code_fence(self, content: str) -> str:
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return text

    def _read_env_file(self, env_file: Path) -> dict[str, str]:
        if not env_file.exists():
            return {}
        values: dict[str, str] = {}
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"' ")
        return values


class AnswerGenerationService:
    def __init__(
        self,
        adapter: OpenAIAnswerAdapter | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.adapter = adapter or OpenAIAnswerAdapter()
        self.enabled = self.adapter.is_configured() if enabled is None else enabled

    def generate(
        self,
        *,
        user_query: str,
        execution_summary: dict | None,
        recent_messages: list[dict],
        session_state: dict,
    ) -> AnswerGenerationResult:
        if execution_summary is None:
            return AnswerGenerationResult(status="skipped")
        used_context = ["execution", "recent_messages", "session_state"]
        if not self.enabled:
            return AnswerGenerationResult(
                status="unavailable",
                provider="openai-compatible",
                model=getattr(self.adapter, "model", None),
                error="llm unavailable",
                used_context=used_context,
            )
        prompt = self._build_primary_prompt(
            user_query=user_query,
            execution_summary=execution_summary,
            recent_messages=recent_messages,
            session_state=session_state,
        )
        try:
            answer, usage = self.adapter.generate_answer(prompt=prompt)
        except Exception as exc:
            if self._is_timeout_error(exc):
                retry_prompt = self._build_minimal_retry_prompt(
                    user_query=user_query,
                    execution_summary=execution_summary,
                )
                try:
                    answer, usage = self.adapter.generate_answer(prompt=retry_prompt)
                except Exception as retry_exc:
                    return self._build_deterministic_fallback(
                        execution_summary=execution_summary,
                        error=str(retry_exc),
                    )
            else:
                return AnswerGenerationResult(
                    status="unavailable",
                    provider="openai-compatible",
                    model=getattr(self.adapter, "model", None),
                    error=str(exc),
                    used_context=used_context,
                )
        if not answer:
            return AnswerGenerationResult(
                status="unavailable",
                provider="openai-compatible",
                model=getattr(self.adapter, "model", None),
                error="empty llm response",
                used_context=used_context,
            )
        return AnswerGenerationResult(
            status="ready",
            provider="openai-compatible",
            model=getattr(self.adapter, "model", None),
            answer_text=answer,
            used_context=used_context,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )

    def _build_primary_prompt(
        self,
        *,
        user_query: str,
        execution_summary: dict,
        recent_messages: list[dict],
        session_state: dict,
    ) -> dict:
        return {
            "prompt_mode": "full",
            "user_query": user_query,
            "execution_summary": self._compact_execution_summary(execution_summary),
            "recent_messages": self._compact_recent_messages(recent_messages),
            "session_state": self._compact_session_state(session_state),
        }

    def _build_minimal_retry_prompt(
        self,
        *,
        user_query: str,
        execution_summary: dict,
    ) -> dict:
        return {
            "prompt_mode": "minimal_retry",
            "user_query": user_query,
            "execution_summary": self._compact_execution_summary(execution_summary, include_task_results=False),
        }

    def _compact_execution_summary(
        self,
        execution_summary: dict,
        *,
        include_task_results: bool = True,
    ) -> dict:
        market_summary = execution_summary.get("market_summary") or {}
        market_context = execution_summary.get("market_context") or {}
        analysis_timeframes = list((execution_summary.get("analysis_timeframes") or [])[:6])
        compact = {
            "asset": execution_summary.get("asset") or market_summary.get("asset"),
            "summary": execution_summary.get("summary"),
            "status": execution_summary.get("status"),
            "analysis_timeframes": analysis_timeframes,
            "market_summary": {
                "asset": market_summary.get("asset"),
                "price": market_summary.get("price"),
                "price_change_24h_pct": market_summary.get("price_change_24h_pct"),
                "market_cap": market_summary.get("market_cap"),
                "volume_24h": market_summary.get("volume_24h"),
                "market_type": market_summary.get("market_type"),
                "timeframes": market_summary.get("timeframes"),
                "analysis_summary": market_summary.get("analysis_summary"),
            },
            "market_context": {
                "symbol": market_context.get("symbol"),
                "name": market_context.get("name"),
                "market_cap": market_context.get("market_cap"),
                "fdv": market_context.get("fdv"),
                "total_volume": market_context.get("total_volume"),
                "price_change_percentage_24h": market_context.get("price_change_percentage_24h"),
            },
            "missing_information": list((execution_summary.get("missing_information") or [])[:6]),
            "key_points": list((execution_summary.get("key_points") or [])[:6]),
            "final_answer_preview": (execution_summary.get("final_answer") or "")[:400] or None,
            "research_digest": self._build_research_digest(execution_summary.get("task_results") or []),
        }
        if include_task_results:
            compact["task_results"] = [
                {
                    "task_type": item.get("task_type"),
                    "agent": item.get("agent"),
                    "status": item.get("status"),
                    "summary": (item.get("summary") or "")[:240] or None,
                    "missing_information": list((item.get("missing_information") or [])[:4]),
                    "tool_calls": self._compact_tool_calls(item.get("tool_calls") or []),
                }
                for item in (execution_summary.get("task_results") or [])[:4]
            ]
        return compact

    def _build_research_digest(self, task_results: list[dict]) -> dict:
        findings: list[str] = []
        risks: list[str] = []
        catalysts: list[str] = []
        source_headlines: list[str] = []
        for item in task_results[:6]:
            if not isinstance(item, dict):
                continue
            if item.get("task_type") != "research" and item.get("agent") != "ResearchAgent":
                continue
            for value in item.get("findings") or []:
                if isinstance(value, str) and value.strip():
                    findings.append(value.strip())
            for value in item.get("risks") or []:
                if isinstance(value, str) and value.strip():
                    risks.append(value.strip())
            for value in item.get("catalysts") or []:
                if isinstance(value, str) and value.strip():
                    catalysts.append(value.strip())
            for tool_call in item.get("tool_calls") or []:
                if not isinstance(tool_call, dict) or (tool_call.get("tool_name") or tool_call.get("tool")) != "search_web":
                    continue
                output_summary = tool_call.get("output_summary") or {}
                for result in output_summary.get("results") or []:
                    if isinstance(result, dict):
                        title = result.get("title")
                        if isinstance(title, str) and title.strip():
                            source_headlines.append(title.strip())
        return {
            "findings": list(dict.fromkeys(findings))[:8],
            "risks": list(dict.fromkeys(risks))[:8],
            "catalysts": list(dict.fromkeys(catalysts))[:8],
            "source_headlines": list(dict.fromkeys(source_headlines))[:8],
        }

    def _compact_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        compacted: list[dict] = []
        for item in tool_calls[:8]:
            compacted.append(
                {
                    "tool_name": item.get("tool_name") or item.get("tool"),
                    "status": item.get("status") or (item.get("output") or {}).get("status"),
                    "args": item.get("args") or item.get("input"),
                    "output_summary": item.get("output_summary") or item.get("output"),
                    "error": item.get("error"),
                }
            )
        return compacted

    def _compact_recent_messages(self, recent_messages: list[dict]) -> list[dict]:
        compacted: list[dict] = []
        for message in recent_messages[-4:]:
            compacted.append(
                {
                    "role": message.get("role"),
                    "content": (message.get("content") or "")[:240],
                }
            )
        return compacted

    def _compact_session_state(self, session_state: dict) -> dict:
        if not session_state:
            return {}
        return {
            "watchlist": list((session_state.get("watchlist") or [])[:10]),
            "focus_asset": session_state.get("focus_asset"),
            "last_trace_id": session_state.get("last_trace_id"),
        }

    def _build_deterministic_fallback(
        self,
        *,
        execution_summary: dict,
        error: str,
    ) -> AnswerGenerationResult:
        summary = (execution_summary or {}).get("summary") or "Execution completed."
        missing_information = list(((execution_summary or {}).get("missing_information") or [])[:4])
        market_context = (execution_summary or {}).get("market_context") or {}
        market_summary = (execution_summary or {}).get("market_summary") or {}
        analysis_timeframes = list(((execution_summary or {}).get("analysis_timeframes") or [])[:6])
        research_digest = self._build_research_digest((execution_summary or {}).get("task_results") or [])
        lines = [summary]
        if market_context:
            market_bits: list[str] = []
            if market_context.get("market_cap") is not None:
                market_bits.append(f"市值: {market_context['market_cap']}")
            if market_context.get("total_volume") is not None:
                market_bits.append(f"24h成交量: {market_context['total_volume']}")
            if market_context.get("price_change_percentage_24h") is not None:
                market_bits.append(f"24h涨跌: {market_context['price_change_percentage_24h']}")
            if market_bits:
                lines.append("市场快照: " + "；".join(market_bits))
        if analysis_timeframes:
            lines.append("分析周期: " + ", ".join(analysis_timeframes))
        if market_summary.get("analysis_summary"):
            lines.append("技术面: " + str(market_summary.get("analysis_summary")))
        macro_bits = [
            *[f"发现: {value}" for value in research_digest.get("findings", [])[:3]],
            *[f"风险: {value}" for value in research_digest.get("risks", [])[:2]],
            *[f"催化: {value}" for value in research_digest.get("catalysts", [])[:2]],
        ]
        if macro_bits:
            lines.append("研究摘要: " + "；".join(macro_bits))
        source_headlines = research_digest.get("source_headlines") or []
        if source_headlines:
            lines.append("网页来源: " + "；".join(source_headlines[:4]))
        if missing_information:
            lines.append("当前仍缺少：" + "; ".join(missing_information))
        answer_text = "\n\n".join(lines)
        return AnswerGenerationResult(
            status="ready",
            provider="deterministic-fallback",
            model="execution-summary",
            answer_text=answer_text,
            error=error,
            used_context=["execution"],
        )

    def _is_timeout_error(self, exc: Exception) -> bool:
        if isinstance(exc, httpx.TimeoutException):
            return True
        message = str(exc).lower()
        return (
            "timed out" in message
            or "timeout" in message
            or "server disconnected without sending a response" in message
            or "unexpected eof while reading" in message
            or "eof occurred in violation of protocol" in message
        )
