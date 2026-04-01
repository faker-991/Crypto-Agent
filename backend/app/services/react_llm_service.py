from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx


class OpenAICompatibleReActLLMClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        temperature: float = 0.1,
        provider: str = "openai-compatible",
        client: httpx.Client | None = None,
        env_file: Path | None = None,
    ) -> None:
        env_values = self._read_env_file(env_file or Path(__file__).resolve().parents[2] / ".env")
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
        raw_timeout = (
            str(timeout)
            if timeout is not None
            else (
                os.getenv("OPENAI_TIMEOUT")
                or os.getenv("ROUTER_LLM_TIMEOUT")
                or env_values.get("OPENAI_TIMEOUT")
                or env_values.get("ROUTER_LLM_TIMEOUT")
            )
        )
        self.client = client or httpx.Client(timeout=float(raw_timeout) if raw_timeout else 60.0)
        self.temperature = temperature
        self.provider = provider

    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    def complete(self, *, messages: list[dict[str, Any]], response_format: dict[str, Any] | None = None) -> SimpleNamespace:
        if not self.is_configured():
            raise RuntimeError("react_llm_not_configured")
        response = self.client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "temperature": self.temperature,
                "response_format": response_format or {"type": "json_object"},
                "messages": messages,
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if not content:
            raise RuntimeError("empty_llm_response")
        usage = payload.get("usage") or {}
        usage_ns = SimpleNamespace(
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
        )
        return SimpleNamespace(
            content=content,
            text=content,
            message=SimpleNamespace(content=content),
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            model=self.model,
            provider=self.provider,
            temperature=self.temperature,
            usage=usage_ns,
        )

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


class FallbackReActLLMClient:
    def __init__(self, primary: Any, fallback: Any) -> None:
        self.primary = primary
        self.fallback = fallback
        self.model = getattr(primary, "model", None) or getattr(fallback, "model", None)
        self.provider = getattr(primary, "provider", None) or getattr(fallback, "provider", None)
        self.temperature = getattr(primary, "temperature", None)
        self._primary_short_circuited = False

    def complete(self, *args, **kwargs):
        if self._primary_short_circuited:
            response = self.fallback.complete(*args, **kwargs)
            setattr(response, "fallback_error", "primary_short_circuited_after_timeout")
            if not getattr(response, "provider", None):
                setattr(response, "provider", getattr(self.fallback, "provider", self.fallback.__class__.__name__))
            if not getattr(response, "model", None):
                setattr(response, "model", getattr(self.fallback, "model", self.fallback.__class__.__name__))
            if not hasattr(response, "temperature"):
                setattr(response, "temperature", getattr(self.fallback, "temperature", None))
            return response
        try:
            return self.primary.complete(*args, **kwargs)
        except Exception as exc:
            if self._is_timeout_error(exc):
                self._primary_short_circuited = True
            response = self.fallback.complete(*args, **kwargs)
            setattr(response, "fallback_error", str(exc))
            if not getattr(response, "provider", None):
                setattr(response, "provider", getattr(self.fallback, "provider", self.fallback.__class__.__name__))
            if not getattr(response, "model", None):
                setattr(response, "model", getattr(self.fallback, "model", self.fallback.__class__.__name__))
            if not hasattr(response, "temperature"):
                setattr(response, "temperature", getattr(self.fallback, "temperature", None))
            return response

    def _is_timeout_error(self, exc: Exception) -> bool:
        if isinstance(exc, httpx.TimeoutException):
            return True
        message = str(exc).lower()
        return "timed out" in message or "timeout" in message
