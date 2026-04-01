from pathlib import Path

from app.api.conversations import (
    ConversationCreateRequest,
    ConversationMessageRequest,
    create_conversation,
    list_conversations,
    read_conversation,
    send_message,
)
from app.services.answer_generation_service import AnswerGenerationService
from app.services.conversation_service import ConversationService
from app.services.trace_log_service import TraceLogService


class StubAnswerAdapter:
    model = "stub-answer-model"

    def is_configured(self) -> bool:
        return True

    def generate_answer(self, *, prompt: dict) -> tuple[str | None, dict]:
        execution_summary = prompt.get("execution_summary") or {}
        asset = (
            execution_summary.get("market_summary", {}).get("asset")
            or execution_summary.get("asset")
            or "asset"
        )
        return f"{asset} natural answer", {"prompt_tokens": 21, "completion_tokens": 9, "total_tokens": 30}


class StubOrchestratorService:
    def __init__(self, trace_path: Path) -> None:
        self.trace_path = trace_path

    def execute(self, user_query: str, conversation_id: str | None = None) -> dict:
        return {
            "status": "execute",
            "plan": {
                "goal": user_query,
                "mode": "single_task",
                "needs_clarification": False,
                "clarification_question": None,
                "tasks": [
                    {
                        "task_id": "task-kline",
                        "task_type": "kline",
                        "title": "Analyze BTC kline",
                        "slots": {"asset": "BTC", "timeframes": ["1d"]},
                        "depends_on": [],
                    }
                ],
            },
            "task_results": [
                {
                    "task_id": "task-kline",
                    "task_type": "kline",
                    "agent": "KlineAgent",
                    "status": "success",
                    "payload": {"asset": "BTC"},
                    "summary": "BTC market summary",
                }
            ],
            "final_answer": "BTC market summary",
            "execution_summary": {"asset": "BTC", "summary": "BTC market summary"},
            "trace_path": str(self.trace_path),
        }


def build_service(tmp_path: Path) -> ConversationService:
    trace_log_service = TraceLogService(tmp_path)
    answer_generation_service = AnswerGenerationService(
        adapter=StubAnswerAdapter(),
        enabled=True,
    )
    trace_path = tmp_path / "traces" / "conversation-trace.json"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(
        '{"timestamp":"20260323T000000000000Z","user_query":"seed","status":"execute","plan":{"goal":"seed","mode":"single_task","needs_clarification":false,"tasks":[]},"task_results":[],"execution_summary":{},"events":[]}\n',
        encoding="utf-8",
    )
    return ConversationService(
        tmp_path,
        orchestrator_service=StubOrchestratorService(trace_path),
        trace_log_service=trace_log_service,
        answer_generation_service=answer_generation_service,
    )


def test_conversation_api_creates_and_lists_conversations(tmp_path: Path) -> None:
    service = build_service(tmp_path)

    created = create_conversation(ConversationCreateRequest(title="BTC thread"), service)
    listed = list_conversations(service)

    assert created["title"] == "BTC thread"
    assert listed["items"][0]["title"] == "BTC thread"


def test_conversation_api_sends_message_and_persists_assistant_reply(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    created = create_conversation(ConversationCreateRequest(title="BTC thread"), service)
    conversation_id = created["conversation_id"]

    sent = send_message(
        conversation_id,
        ConversationMessageRequest(content="帮我看一下 BTC 现货日线趋势"),
        service,
    )
    transcript = read_conversation(conversation_id, service)

    assert sent["assistant_message"]["role"] == "assistant"
    assert sent["assistant_message"]["answer_generation"]["status"] == "ready"
    assert sent["assistant_message"]["trace_id"] is not None
    assert sent["assistant_message"]["plan_summary"]["mode"] == "single_task"
    assert len(transcript["messages"]) == 2
    assert transcript["messages"][1]["content"] == "BTC natural answer"


def test_conversation_api_records_answer_generation_trace_event(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    created = create_conversation(ConversationCreateRequest(title="ETH thread"), service)
    conversation_id = created["conversation_id"]

    sent = send_message(
        conversation_id,
        ConversationMessageRequest(content="帮我看一下 BTC 现货日线趋势"),
        service,
    )
    trace_id = sent["assistant_message"]["trace_id"]
    trace_payload = service.trace_log_service.read_trace(trace_id)

    assert any(event["name"] == "answer_generation.started" for event in trace_payload["events"])
    assert any(event["name"] == "answer_generation.completed" for event in trace_payload["events"])
    answer_span = next(span for span in trace_payload["spans"] if span["kind"] == "llm" and span["name"] == "answer_generation")
    assert answer_span["status"] == "success"
    assert answer_span["metrics"]["total_tokens"] == 30
    assert trace_payload["metrics_summary"]["total_tokens"] >= 30
