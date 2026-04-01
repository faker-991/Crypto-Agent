from pathlib import Path

import httpx
import pytest

from app.services.react_llm_service import FallbackReActLLMClient, OpenAICompatibleReActLLMClient
from app.services.answer_generation_service import OpenAIAnswerAdapter


def test_react_llm_client_reads_openai_fields_from_env_file(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=test-key",
                "OPENAI_MODEL=test-react-model",
                "OPENAI_BASE_URL=https://example.com/v1",
                "OPENAI_TIMEOUT=15",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_TIMEOUT", raising=False)

    client = OpenAICompatibleReActLLMClient(env_file=env_path)

    assert client.api_key == "test-key"
    assert client.model == "test-react-model"
    assert client.base_url == "https://example.com/v1"
    assert client.is_configured() is True


def test_react_llm_client_returns_normalized_completion_payload(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://example.com/v1/chat/completions")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"decision_summary":"Search first.","action":"search_web","args":{"query":"BTC catalysts"},"termination":false,"termination_reason":null}'
                        }
                    }
                ],
                "usage": {"prompt_tokens": 101, "completion_tokens": 29, "total_tokens": 130},
            },
        )

    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_MODEL", "kimi/kimi-k2.5")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.com/v1")
    client = OpenAICompatibleReActLLMClient(client=httpx.Client(transport=httpx.MockTransport(handler)))

    response = client.complete(messages=[{"role": "user", "content": "BTC"}], response_format={"type": "json_object"})

    assert response.content
    assert response.model == "kimi/kimi-k2.5"
    assert response.provider == "openai-compatible"
    assert response.temperature == 0.1
    assert response.usage.total_tokens == 130


def test_react_llm_client_raises_when_upstream_returns_empty_content(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}}], "usage": {}})

    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_MODEL", "kimi/kimi-k2.5")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.com/v1")
    client = OpenAICompatibleReActLLMClient(client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(RuntimeError, match="empty_llm_response"):
        client.complete(messages=[{"role": "user", "content": "BTC"}], response_format={"type": "json_object"})


def test_react_llm_client_defaults_to_longer_timeout(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_TIMEOUT", raising=False)
    monkeypatch.delenv("ROUTER_LLM_TIMEOUT", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_MODEL", "kimi/kimi-k2.5")

    client = OpenAICompatibleReActLLMClient()

    assert client.client.timeout.connect == 60.0
    assert client.client.timeout.read == 60.0


def test_answer_generation_adapter_defaults_to_longer_timeout(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_TIMEOUT", raising=False)
    monkeypatch.delenv("ROUTER_LLM_TIMEOUT", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_MODEL", "kimi/kimi-k2.5")

    adapter = OpenAIAnswerAdapter()

    assert adapter.client.timeout.connect == 60.0
    assert adapter.client.timeout.read == 60.0


def test_fallback_react_llm_client_short_circuits_after_timeout() -> None:
    class Primary:
        def __init__(self) -> None:
            self.calls = 0
            self.model = "remote-model"
            self.provider = "openai-compatible"
            self.temperature = 0.1

        def complete(self, *args, **kwargs):
            self.calls += 1
            raise httpx.ReadTimeout("The read operation timed out")

    class Fallback:
        def __init__(self) -> None:
            self.calls = 0
            self.model = "heuristic-model"
            self.provider = "heuristic"
            self.temperature = 0.0

        def complete(self, *args, **kwargs):
            self.calls += 1
            from types import SimpleNamespace

            return SimpleNamespace(content='{"ok":true}')

    primary = Primary()
    fallback = Fallback()
    client = FallbackReActLLMClient(primary, fallback)

    response1 = client.complete(messages=[{"role": "user", "content": "x"}])
    response2 = client.complete(messages=[{"role": "user", "content": "y"}])

    assert primary.calls == 1
    assert fallback.calls == 2
    assert response1.fallback_error == "The read operation timed out"
    assert response2.fallback_error == "primary_short_circuited_after_timeout"
