from typing import Literal

from pydantic import BaseModel, Field


AnswerGenerationStatus = Literal["ready", "unavailable", "skipped"]
ConversationRole = Literal["user", "assistant", "system"]


class AnswerGenerationResult(BaseModel):
    status: AnswerGenerationStatus
    provider: str | None = None
    model: str | None = None
    answer_text: str | None = None
    error: str | None = None
    used_context: list[str] = Field(default_factory=list)


class ConversationMessage(BaseModel):
    id: str
    role: ConversationRole
    content: str
    created_at: str
    plan_summary: dict | None = None
    execution_summary: dict | None = None
    answer_generation: AnswerGenerationResult | None = None
    trace_id: str | None = None


class ConversationTranscript(BaseModel):
    conversation_id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[ConversationMessage] = Field(default_factory=list)


class ConversationIndexItem(BaseModel):
    conversation_id: str
    title: str
    created_at: str
    updated_at: str
    last_user_message: str | None = None
    message_count: int = 0


class ConversationIndex(BaseModel):
    items: list[ConversationIndexItem] = Field(default_factory=list)
