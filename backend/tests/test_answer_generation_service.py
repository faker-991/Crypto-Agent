from pathlib import Path

import httpx

from app.services.answer_generation_service import AnswerGenerationService
from app.services.answer_generation_service import OpenAIAnswerAdapter


def test_answer_adapter_reads_openai_fields_from_env_file(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=test-key",
                "OPENAI_MODEL=gpt-4.1-mini",
                "OPENAI_BASE_URL=https://example.com/v1",
                "OPENAI_TIMEOUT=12.5",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_TIMEOUT", raising=False)
    monkeypatch.delenv("ROUTER_LLM_API_KEY", raising=False)
    monkeypatch.delenv("ROUTER_LLM_MODEL", raising=False)
    monkeypatch.delenv("ROUTER_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("ROUTER_LLM_TIMEOUT", raising=False)

    adapter = OpenAIAnswerAdapter(env_file=env_path)

    assert adapter.api_key == "test-key"
    assert adapter.model == "gpt-4.1-mini"
    assert adapter.base_url == "https://example.com/v1"
    assert adapter.is_configured() is True


def test_answer_adapter_prefers_process_env_over_env_file(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=file-key",
                "OPENAI_MODEL=file-model",
                "OPENAI_BASE_URL=https://file.example/v1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_MODEL", "env-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://env.example/v1")

    adapter = OpenAIAnswerAdapter(env_file=env_path)

    assert adapter.api_key == "env-key"
    assert adapter.model == "env-model"
    assert adapter.base_url == "https://env.example/v1"


def test_answer_service_retries_with_minimal_prompt_after_timeout() -> None:
    class TimeoutThenSuccessAdapter:
        model = "kimi/kimi-k2.5"

        def __init__(self) -> None:
            self.prompts: list[dict] = []

        def is_configured(self) -> bool:
            return True

        def generate_answer(self, *, prompt: dict) -> tuple[str | None, dict]:
            self.prompts.append(prompt)
            if len(self.prompts) == 1:
                raise httpx.ReadTimeout("The read operation timed out")
            return "retry succeeded", {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}

    adapter = TimeoutThenSuccessAdapter()
    service = AnswerGenerationService(adapter=adapter, enabled=True)

    result = service.generate(
        user_query="帮我研究 BTC 走势",
        execution_summary={
            "asset": "BTC",
            "summary": "BTC 日线回调，4h 震荡。",
            "market_summary": {"asset": "BTC", "price_change_24h_pct": -0.2},
            "missing_information": ["sentiment evidence is thin"],
            "task_results": [{"summary": "kline summary"}],
        },
        recent_messages=[
            {"role": "user", "content": "上一次我们看的是周线"},
            {"role": "assistant", "content": "周线偏强"},
        ],
        session_state={"watchlist": ["BTC", "ETH"], "very_large": {"nested": list(range(50))}},
    )

    assert result.status == "ready"
    assert result.answer_text == "retry succeeded"
    assert result.provider == "openai-compatible"
    assert result.model == "kimi/kimi-k2.5"
    assert result.total_tokens == 14
    assert len(adapter.prompts) == 2
    assert "recent_messages" in adapter.prompts[0]
    assert "session_state" in adapter.prompts[0]
    assert adapter.prompts[1]["prompt_mode"] == "minimal_retry"
    assert "recent_messages" not in adapter.prompts[1]
    assert "session_state" not in adapter.prompts[1]


def test_answer_service_returns_deterministic_fallback_after_repeated_timeout() -> None:
    class AlwaysTimeoutAdapter:
        model = "kimi/kimi-k2.5"

        def __init__(self) -> None:
            self.calls = 0

        def is_configured(self) -> bool:
            return True

        def generate_answer(self, *, prompt: dict) -> tuple[str | None, dict]:
            self.calls += 1
            raise httpx.ReadTimeout("The read operation timed out")

    adapter = AlwaysTimeoutAdapter()
    service = AnswerGenerationService(adapter=adapter, enabled=True)

    result = service.generate(
        user_query="帮我研究 BTC 走势",
        execution_summary={
            "asset": "BTC",
            "summary": "BTC 日线回调，4h 震荡。",
            "market_summary": {"asset": "BTC"},
            "missing_information": ["sentiment evidence is thin"],
        },
        recent_messages=[{"role": "user", "content": "请结合 1h 和 4h"}],
        session_state={"watchlist": ["BTC"]},
    )

    assert adapter.calls == 2
    assert result.status == "ready"
    assert result.provider == "deterministic-fallback"
    assert result.model == "execution-summary"
    assert "BTC 日线回调" in (result.answer_text or "")
    assert result.error == "The read operation timed out"


def test_answer_service_deterministic_fallback_includes_market_context_and_timeframes() -> None:
    class AlwaysTimeoutAdapter:
        model = "kimi/kimi-k2.5"

        def is_configured(self) -> bool:
            return True

        def generate_answer(self, *, prompt: dict) -> tuple[str | None, dict]:
            raise httpx.ReadTimeout("The read operation timed out")

    service = AnswerGenerationService(adapter=AlwaysTimeoutAdapter(), enabled=True)

    result = service.generate(
        user_query="帮我研究 BTC 走势",
        execution_summary={
            "asset": "BTC",
            "summary": "BTC 综合分析。",
            "analysis_timeframes": ["1h", "4h", "1d"],
            "market_summary": {
                "asset": "BTC",
                "analysis_summary": "1h 震荡，4h 区间，1d 下跌。",
            },
            "market_context": {
                "market_cap": 1353296344336,
                "total_volume": 54887405467,
                "price_change_percentage_24h": 0.45829,
            },
            "missing_information": ["sentiment evidence is thin"],
        },
        recent_messages=[],
        session_state={},
    )

    assert result.status == "ready"
    assert result.provider == "deterministic-fallback"
    assert "市值:" in (result.answer_text or "")
    assert "24h成交量:" in (result.answer_text or "")
    assert "24h涨跌:" in (result.answer_text or "")
    assert "分析周期: 1h, 4h, 1d" in (result.answer_text or "")
    assert "技术面: 1h 震荡，4h 区间，1d 下跌。" in (result.answer_text or "")


def test_answer_service_primary_prompt_includes_research_digest_with_macro_findings() -> None:
    class CapturingAdapter:
        model = "kimi/kimi-k2.5"

        def __init__(self) -> None:
            self.prompt: dict | None = None

        def is_configured(self) -> bool:
            return True

        def generate_answer(self, *, prompt: dict) -> tuple[str | None, dict]:
            self.prompt = prompt
            return "ok", {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18}

    adapter = CapturingAdapter()
    service = AnswerGenerationService(adapter=adapter, enabled=True)

    result = service.generate(
        user_query="结合美联储和伊朗局势分析 BTC",
        execution_summary={
            "asset": "BTC",
            "summary": "BTC combined summary",
            "analysis_timeframes": ["1h", "4h", "1d"],
            "market_summary": {"asset": "BTC", "analysis_summary": "1h 震荡，4h 区间，1d 下跌。"},
            "market_context": {
                "market_cap": 1383292098522,
                "total_volume": 53471916945,
                "price_change_percentage_24h": 2.64326,
            },
            "task_results": [
                {
                    "task_type": "research",
                    "agent": "ResearchAgent",
                    "status": "success",
                    "summary": "BTC How Low Can Bitcoin Go? After Worst Quarter Since 2018, BTC ... Catalysts include etf.",
                    "missing_information": [],
                    "findings": [
                        "Bitcoin Weekly Outlook: BTC Price Eyes $47K Risk as Oil Surge, Fed Pressure Build | FXEmpire",
                        "Bitcoin Price Forecast: BTC edges up even as markets foresee no end to the Iran war",
                    ],
                    "risks": ["fed", "iran", "oil"],
                    "catalysts": ["etf", "dovish"],
                    "tool_calls": [
                        {
                            "tool_name": "search_web",
                            "status": "success",
                            "args": {"query": "BTC price outlook sentiment news macro regulation"},
                            "output_summary": {
                                "provider": "exa",
                                "results": [
                                    {"title": "Bitcoin Weekly Outlook: BTC Price Eyes $47K Risk as Oil Surge, Fed Pressure Build | FXEmpire"},
                                    {"title": "Bitcoin Price Forecast: BTC edges up even as markets foresee no end to the Iran war"},
                                ],
                            },
                        }
                    ],
                }
            ],
        },
        recent_messages=[],
        session_state={},
    )

    assert result.status == "ready"
    assert adapter.prompt is not None
    digest = adapter.prompt["execution_summary"]["research_digest"]
    assert "fed" in digest["risks"]
    assert "iran" in digest["risks"]
    assert "oil" in digest["risks"]
    assert any("Fed Pressure Build" in item for item in digest["findings"])
    assert any("Iran war" in item for item in digest["findings"])
