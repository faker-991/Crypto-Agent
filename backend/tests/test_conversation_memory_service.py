from pathlib import Path

from app.schemas.conversation import (
    AnswerGenerationResult,
    ConversationIndexItem,
    ConversationMessage,
)
from app.services.conversation_memory_service import ConversationMemoryService


def test_conversation_schema_validates_index_and_message() -> None:
    item = ConversationIndexItem(
        conversation_id="conv-1",
        title="BTC analysis",
        created_at="2026-03-20T00:00:00Z",
        updated_at="2026-03-20T00:00:00Z",
        last_user_message="看看 BTC",
        message_count=2,
    )
    message = ConversationMessage(
        id="msg-1",
        role="assistant",
        content="BTC is weakening on 1d.",
        created_at="2026-03-20T00:00:01Z",
        answer_generation=AnswerGenerationResult(
            status="ready",
            provider="openai-compatible",
            model="test-model",
            answer_text="BTC is weakening on 1d.",
            used_context=["execution", "recent_messages"],
        ),
        trace_id="trace-1",
    )

    assert item.conversation_id == "conv-1"
    assert message.answer_generation is not None
    assert message.answer_generation.status == "ready"


def test_conversation_memory_service_creates_conversation_files(tmp_path: Path) -> None:
    service = ConversationMemoryService(tmp_path)

    created = service.create_conversation(title="BTC thread")

    assert created.title == "BTC thread"
    assert (tmp_path / "conversations" / "index.json").exists()
    assert (tmp_path / "conversations" / f"{created.conversation_id}.json").exists()
    assert service.list_conversations()[0].conversation_id == created.conversation_id


def test_conversation_memory_service_appends_messages_and_updates_index(tmp_path: Path) -> None:
    service = ConversationMemoryService(tmp_path)
    created = service.create_conversation(title="SUI thread")

    service.append_messages(
        created.conversation_id,
        [
            ConversationMessage(
                id="user-1",
                role="user",
                content="继续看 SUI",
                created_at="2026-03-20T00:00:00Z",
            ),
            ConversationMessage(
                id="assistant-1",
                role="assistant",
                content="SUI still needs confirmation.",
                created_at="2026-03-20T00:00:01Z",
                trace_id="trace-1",
                answer_generation=AnswerGenerationResult(
                    status="ready",
                    provider="openai-compatible",
                    model="test-model",
                    answer_text="SUI still needs confirmation.",
                    used_context=["execution", "session_state"],
                ),
            ),
        ],
    )

    transcript = service.read_conversation(created.conversation_id)
    index = service.list_conversations()

    assert len(transcript.messages) == 2
    assert transcript.messages[1].trace_id == "trace-1"
    assert index[0].message_count == 2
    assert index[0].last_user_message == "继续看 SUI"


def test_conversation_memory_service_reloads_existing_data_from_disk(tmp_path: Path) -> None:
    service = ConversationMemoryService(tmp_path)
    created = service.create_conversation(title="ETH thread")
    service.append_messages(
        created.conversation_id,
        [
            ConversationMessage(
                id="user-1",
                role="user",
                content="ETH 4h 怎么样",
                created_at="2026-03-20T00:00:00Z",
            )
        ],
    )

    reloaded = ConversationMemoryService(tmp_path)
    transcript = reloaded.read_conversation(created.conversation_id)
    index = reloaded.list_conversations()

    assert transcript.messages[0].content == "ETH 4h 怎么样"
    assert index[0].title == "ETH thread"
