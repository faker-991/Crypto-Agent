from pathlib import Path

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
