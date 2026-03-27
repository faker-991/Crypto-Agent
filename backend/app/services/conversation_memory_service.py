import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.schemas.conversation import (
    ConversationIndex,
    ConversationIndexItem,
    ConversationMessage,
    ConversationTranscript,
)


class ConversationMemoryService:
    def __init__(self, memory_root: Path) -> None:
        self.memory_root = memory_root
        self.conversations_root = memory_root / "conversations"
        self.conversations_root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.conversations_root / "index.json"
        if not self.index_path.exists():
            self._write_index(ConversationIndex())

    def list_conversations(self) -> list[ConversationIndexItem]:
        return self._read_index().items

    def create_conversation(self, title: str | None = None) -> ConversationTranscript:
        timestamp = self._now_iso()
        conversation_id = uuid4().hex
        transcript = ConversationTranscript(
            conversation_id=conversation_id,
            title=title or "New conversation",
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._write_transcript(transcript)
        index = self._read_index()
        index.items.insert(
            0,
            ConversationIndexItem(
                conversation_id=conversation_id,
                title=transcript.title,
                created_at=timestamp,
                updated_at=timestamp,
            ),
        )
        self._write_index(index)
        return transcript

    def read_conversation(self, conversation_id: str) -> ConversationTranscript:
        path = self._transcript_path(conversation_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ConversationTranscript.model_validate(payload)

    def append_messages(
        self,
        conversation_id: str,
        messages: list[ConversationMessage],
    ) -> ConversationTranscript:
        transcript = self.read_conversation(conversation_id)
        transcript.messages.extend(messages)
        transcript.updated_at = self._now_iso()
        self._write_transcript(transcript)
        self._refresh_index_item(transcript)
        return transcript

    def _refresh_index_item(self, transcript: ConversationTranscript) -> None:
        index = self._read_index()
        last_user_message = next(
            (message.content for message in reversed(transcript.messages) if message.role == "user"),
            None,
        )
        updated_items: list[ConversationIndexItem] = []
        current_item: ConversationIndexItem | None = None
        for item in index.items:
            if item.conversation_id == transcript.conversation_id:
                current_item = ConversationIndexItem(
                    conversation_id=transcript.conversation_id,
                    title=transcript.title,
                    created_at=transcript.created_at,
                    updated_at=transcript.updated_at,
                    last_user_message=last_user_message,
                    message_count=len(transcript.messages),
                )
            else:
                updated_items.append(item)
        if current_item is None:
            current_item = ConversationIndexItem(
                conversation_id=transcript.conversation_id,
                title=transcript.title,
                created_at=transcript.created_at,
                updated_at=transcript.updated_at,
                last_user_message=last_user_message,
                message_count=len(transcript.messages),
            )
        index.items = [current_item, *updated_items]
        self._write_index(index)

    def _read_index(self) -> ConversationIndex:
        payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        return ConversationIndex.model_validate(payload)

    def _write_index(self, index: ConversationIndex) -> None:
        self.index_path.write_text(
            json.dumps(index.model_dump(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _write_transcript(self, transcript: ConversationTranscript) -> None:
        self._transcript_path(transcript.conversation_id).write_text(
            json.dumps(transcript.model_dump(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _transcript_path(self, conversation_id: str) -> Path:
        return self.conversations_root / f"{conversation_id}.json"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
