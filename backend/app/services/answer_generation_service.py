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
            resolved_timeout = float(raw_timeout) if raw_timeout else 20.0
        self.client = client or httpx.Client(timeout=resolved_timeout)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    def generate_answer(self, *, prompt: dict) -> str | None:
        if not self.is_configured():
            return None
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
                            "Do not invent tool calls or prices."
                        ),
                    },
                    {
                        "role": "user",
                        "content": str(prompt),
                    },
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if not content:
            return None
        return self._strip_code_fence(content)

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
        prompt = {
            "user_query": user_query,
            "execution_summary": execution_summary,
            "recent_messages": recent_messages[-6:],
            "session_state": session_state,
        }
        try:
            answer = self.adapter.generate_answer(prompt=prompt)
        except Exception as exc:
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
        )
