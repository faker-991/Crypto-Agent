import os

from app.schemas.intent import IntentResult, SessionState
from app.services.router_llm_service import OpenAIRouterAdapter, RouterLLMService


class StubAdapter:
    def __init__(self, payload: dict | None = None, *, should_raise: bool = False) -> None:
        self.payload = payload
        self.should_raise = should_raise

    def classify(self, *, user_query: str, session_state: dict, rule_hint: str | None) -> dict | None:
        if self.should_raise:
            raise RuntimeError("llm unavailable")
        return self.payload


def test_router_llm_service_parses_valid_intent_result() -> None:
    service = RouterLLMService(
        adapter=StubAdapter(
            payload={
                "intent": "kline_analysis",
                "asset": "BTC",
                "timeframes": ["1d", "1w"],
                "requested_action": "analyze_kline",
                "confidence": 0.93,
                "need_followup": False,
            }
        ),
        enabled=True,
    )

    result = service.classify(
        user_query="看下 BTC 日线和周线趋势",
        session_state=SessionState(),
        rule_hint="kline_analysis",
    )

    assert isinstance(result, IntentResult)
    assert result.intent == "kline_analysis"
    assert result.asset == "BTC"
    assert result.timeframes == ["1d", "1w"]


def test_router_llm_service_returns_none_when_adapter_fails() -> None:
    service = RouterLLMService(adapter=StubAdapter(should_raise=True), enabled=True)

    result = service.classify(
        user_query="帮我看看 SUI",
        session_state=SessionState(),
        rule_hint=None,
    )

    assert result is None


def test_openai_router_adapter_reads_timeout_from_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ROUTER_LLM_MODEL", "test-model")
    monkeypatch.setenv("ROUTER_LLM_TIMEOUT", "45")

    adapter = OpenAIRouterAdapter()

    assert adapter.client.timeout.connect == 45.0
    assert adapter.client.timeout.read == 45.0
    assert adapter.client.timeout.write == 45.0
    assert adapter.client.timeout.pool == 45.0
