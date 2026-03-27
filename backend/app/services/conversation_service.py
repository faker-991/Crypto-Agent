from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.orchestrator.orchestrator_service import OrchestratorService
from app.schemas.conversation import ConversationMessage, ConversationTranscript
from app.services.answer_generation_service import AnswerGenerationService
from app.services.conversation_memory_service import ConversationMemoryService
from app.services.session_state_service import SessionStateService
from app.services.trace_log_service import TraceLogService


class ConversationService:
    def __init__(
        self,
        memory_root: Path,
        orchestrator_service: OrchestratorService,
        trace_log_service: TraceLogService,
        answer_generation_service: AnswerGenerationService | None = None,
        conversation_memory_service: ConversationMemoryService | None = None,
    ) -> None:
        self.memory_root = memory_root
        self.orchestrator_service = orchestrator_service
        self.trace_log_service = trace_log_service
        self.answer_generation_service = answer_generation_service or AnswerGenerationService()
        self.conversation_memory_service = conversation_memory_service or ConversationMemoryService(memory_root)
        self.session_state_service = SessionStateService(memory_root)

    def create_conversation(self, title: str | None = None) -> ConversationTranscript:
        return self.conversation_memory_service.create_conversation(title=title)

    def list_conversations(self):
        return self.conversation_memory_service.list_conversations()

    def get_conversation(self, conversation_id: str) -> ConversationTranscript:
        return self.conversation_memory_service.read_conversation(conversation_id)

    def send_message(self, conversation_id: str, user_message: str) -> dict:
        user_entry = ConversationMessage(
            id=f"user-{uuid4().hex}",
            role="user",
            content=user_message,
            created_at=self._now_iso(),
        )
        self.conversation_memory_service.append_messages(conversation_id, [user_entry])

        result = self.orchestrator_service.execute(user_message, conversation_id=conversation_id)
        transcript = self.conversation_memory_service.read_conversation(conversation_id)
        answer_generation = self.answer_generation_service.generate(
            user_query=user_message,
            execution_summary=result.get("execution_summary"),
            recent_messages=[message.model_dump() for message in transcript.messages[-6:]],
            session_state=self.session_state_service.read_state().model_dump(),
        )
        trace_id = self._extract_trace_id(result.get("trace_path"))
        answer_text = answer_generation.answer_text or self._fallback_message(result)
        assistant_entry = ConversationMessage(
            id=f"assistant-{uuid4().hex}",
            role="assistant",
            content=answer_text,
            created_at=self._now_iso(),
            plan_summary=result.get("plan"),
            execution_summary=result.get("execution_summary"),
            answer_generation=answer_generation,
            trace_id=trace_id,
        )
        self.conversation_memory_service.append_messages(conversation_id, [assistant_entry])
        if result.get("trace_path"):
            self.trace_log_service.append_events(
                result["trace_path"],
                [
                    {
                        "name": "answer_generation.started",
                        "actor": "AnswerGenerationService",
                        "detail": {
                            "provider": "openai-compatible",
                            "model": answer_generation.model,
                            "status": "started",
                            "used_context": ["execution", "recent_messages", "session_state"],
                        },
                    },
                    {
                        "name": "answer_generation.completed",
                        "actor": "AnswerGenerationService",
                        "detail": {
                            "provider": answer_generation.provider,
                            "model": answer_generation.model,
                            "status": answer_generation.status,
                            "used_context": answer_generation.used_context,
                            "error": answer_generation.error,
                        },
                    },
                ],
            )
        return {
            "assistant_message": assistant_entry.model_dump(),
            "plan": result.get("plan"),
            "execution_summary": result.get("execution_summary"),
            "trace_path": result.get("trace_path"),
        }

    def _extract_trace_id(self, trace_path: str | None) -> str | None:
        if not trace_path:
            return None
        return Path(trace_path).name

    def _fallback_message(self, result: dict) -> str:
        status = result.get("status")
        if status == "clarify":
            plan = result.get("plan") or {}
            return plan.get("clarification_question") or "More detail is needed."
        execution_summary = result.get("execution_summary") or {}
        return execution_summary.get("summary") or result.get("final_answer") or "Execution completed."

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
