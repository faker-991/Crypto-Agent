from pathlib import Path

import httpx

from app.schemas.agentic_plan import PlannerDecision
from app.schemas.planning_context import (
    Capabilities,
    Constraints,
    MemoryContext,
    PlanningContext,
    RecentContext,
    SessionContext,
    UserRequest,
)
from app.services.planner_llm_service import PlannerLLMService


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                message="error",
                request=httpx.Request("POST", "https://example.com"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict:
        return self._payload


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict] = []

    def post(self, url: str, headers: dict, json: dict) -> FakeResponse:
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self.response


def _build_context(raw_query: str) -> PlanningContext:
    return PlanningContext(
        user_request=UserRequest(raw_query=raw_query, normalized_goal=raw_query, request_type="single_task"),
        session_context=SessionContext(
            current_asset="BTC",
            last_intent="kline_analysis",
            last_timeframes=["1d"],
            active_topic=None,
        ),
        recent_context=RecentContext(recent_task_summaries=["recent summary"]),
        memory_context=MemoryContext(relevant_memories=[]),
        capabilities=Capabilities(
            available_agents=["ResearchAgent", "KlineAgent", "SummaryAgent"],
            available_tools={},
        ),
        constraints=Constraints(),
    )


def test_planner_llm_service_returns_structured_decision() -> None:
    client = FakeClient(
        FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": """
{
  "mode": "kline_only",
  "goal": "Analyze BTC spot structure on 1d and 1w",
  "requires_clarification": false,
  "clarification_question": null,
  "agents_to_invoke": ["KlineAgent", "SummaryAgent"],
  "inputs": {"asset": "BTC", "timeframes": ["1d", "1w"], "market_type": "spot"},
  "reasoning_summary": "The user asked for timeframe-based technical analysis."
}
"""
                        }
                    }
                ]
            }
        )
    )
    service = PlannerLLMService(
        api_key="test-key",
        model="test-model",
        base_url="https://example.com/v1",
        client=client,
    )

    decision = service.plan(_build_context("帮我看下 BTC 日线和周线走势"))

    assert isinstance(decision, PlannerDecision)
    assert decision.mode == "kline_only"
    assert decision.inputs["asset"] == "BTC"
    assert decision.inputs["timeframes"] == ["1d", "1w"]
    assert decision.agents_to_invoke == ["KlineAgent", "SummaryAgent"]
    assert client.calls


def test_planner_llm_service_returns_none_for_invalid_mode() -> None:
    client = FakeClient(
        FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": """
{
  "mode": "watchlist_update",
  "goal": "Do something unsupported",
  "requires_clarification": false,
  "clarification_question": null,
  "agents_to_invoke": ["KlineAgent"],
  "inputs": {"asset": "BTC"},
  "reasoning_summary": "invalid"
}
"""
                        }
                    }
                ]
            }
        )
    )
    service = PlannerLLMService(
        api_key="test-key",
        model="test-model",
        base_url="https://example.com/v1",
        client=client,
    )

    decision = service.plan(_build_context("帮我处理 BTC"))

    assert decision is None


def test_planner_llm_service_is_not_configured_without_credentials(tmp_path: Path) -> None:
    service = PlannerLLMService(
        api_key=None,
        model=None,
        base_url="https://example.com/v1",
        env_file=tmp_path / "missing.env",
    )

    assert service.is_configured() is False
    assert service.plan(_build_context("看下 BTC")) is None


def test_planner_llm_service_prompt_requests_semantic_slots() -> None:
    service = PlannerLLMService(
        api_key="test-key",
        model="test-model",
        base_url="https://example.com/v1",
        client=FakeClient(FakeResponse({"choices": [{"message": {"content": ""}}]})),
    )

    prompt = service._system_prompt()

    assert "analysis_intent" in prompt
    assert "response_style" in prompt
    assert "1h" in prompt
    assert "小时线" in prompt


def test_planner_llm_service_defaults_to_longer_timeout(monkeypatch) -> None:
    monkeypatch.delenv("PLANNER_LLM_TIMEOUT", raising=False)
    monkeypatch.delenv("OPENAI_TIMEOUT", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_MODEL", "kimi/kimi-k2.5")

    service = PlannerLLMService()

    assert service.client.timeout.connect == 60.0
    assert service.client.timeout.read == 60.0
