from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def get_conversation_service() -> ConversationService:
    raise RuntimeError("conversation service dependency is not configured")


class ConversationCreateRequest(BaseModel):
    title: str | None = None


class ConversationMessageRequest(BaseModel):
    content: str


@router.get("")
def list_conversations(
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> dict:
    return {"items": [item.model_dump() for item in conversation_service.list_conversations()]}


@router.post("")
def create_conversation(
    request: ConversationCreateRequest,
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> dict:
    return conversation_service.create_conversation(title=request.title).model_dump()


@router.get("/{conversation_id}")
def read_conversation(
    conversation_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> dict:
    return conversation_service.get_conversation(conversation_id).model_dump()


@router.post("/{conversation_id}/messages")
def send_message(
    conversation_id: str,
    request: ConversationMessageRequest,
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> dict:
    return conversation_service.send_message(conversation_id, request.content)
