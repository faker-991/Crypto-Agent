import json
import os
from pathlib import Path

import httpx

from app.schemas.agentic_plan import PlannerDecision
from app.schemas.planning_context import PlanningContext


class PlannerLLMService:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
        env_file: Path | None = None,
    ) -> None:
        env_values = self._read_env_file(env_file or Path(__file__).resolve().parents[2] / ".env")
        self.api_key = (
            api_key
            or os.getenv("PLANNER_LLM_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or env_values.get("PLANNER_LLM_API_KEY")
            or env_values.get("OPENAI_API_KEY")
        )
        self.model = (
            model
            or os.getenv("PLANNER_LLM_MODEL")
            or os.getenv("OPENAI_MODEL")
            or env_values.get("PLANNER_LLM_MODEL")
            or env_values.get("OPENAI_MODEL")
        )
        self.base_url = (
            base_url
            or os.getenv("PLANNER_LLM_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or env_values.get("PLANNER_LLM_BASE_URL")
            or env_values.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        raw_timeout = (
            str(timeout)
            if timeout is not None
            else (
                os.getenv("PLANNER_LLM_TIMEOUT")
                or os.getenv("OPENAI_TIMEOUT")
                or env_values.get("PLANNER_LLM_TIMEOUT")
                or env_values.get("OPENAI_TIMEOUT")
            )
        )
        self.client = client or httpx.Client(timeout=float(raw_timeout) if raw_timeout else 20.0)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    def plan(self, context: PlanningContext) -> PlannerDecision | None:
        if not self.is_configured():
            return None
        try:
            response = self.client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": self._system_prompt()},
                        {"role": "user", "content": json.dumps(context.model_dump(), ensure_ascii=False)},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            if not content:
                return None
            return PlannerDecision.model_validate_json(self._strip_code_fence(content))
        except Exception:
            return None

    def _system_prompt(self) -> str:
        return (
            "You are a planner for a crypto analysis app. "
            "Choose exactly one mode from: clarify, research_only, kline_only, mixed_analysis. "
            "Only use these agents: ResearchAgent, KlineAgent, SummaryAgent. "
            "Return valid JSON with keys: mode, goal, requires_clarification, clarification_question, "
            "agents_to_invoke, inputs, reasoning_summary. "
            "If the asset or intent is ambiguous, choose clarify. "
            "If the user asks about price action, trend, timeframe, support, resistance, use kline_only. "
            "If the user asks about fundamentals, catalysts, risks, tokenomics, use research_only. "
            "If the user asks for both, use mixed_analysis."
        )

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
