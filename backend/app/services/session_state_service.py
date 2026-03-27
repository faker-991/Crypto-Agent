import json
from pathlib import Path

from app.schemas.intent import SessionState


class SessionStateService:
    def __init__(self, memory_root: Path) -> None:
        self.session_root = memory_root / "session"
        self.session_root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.session_root / "current_session.json"
        if not self.state_path.exists():
            self.write_state(SessionState().model_dump())

    def read_state(self) -> SessionState:
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        return SessionState.model_validate(payload)

    def write_state(self, payload: dict) -> SessionState:
        state = SessionState.model_validate(payload)
        self.state_path.write_text(
            json.dumps(state.model_dump(), indent=2) + "\n",
            encoding="utf-8",
        )
        return state

    def update_from_intent(self, intent_result) -> SessionState:
        state = self.read_state()
        if intent_result.asset:
            state.current_asset = intent_result.asset
            deduped = [asset for asset in state.recent_assets if asset != intent_result.asset]
            state.recent_assets = [intent_result.asset, *deduped][:5]
        if intent_result.intent != "other":
            state.last_intent = intent_result.intent
        if intent_result.timeframes:
            state.last_timeframes = intent_result.timeframes
        if intent_result.intent == "report_generation":
            state.last_report_type = intent_result.requested_action or "report"
        return self.write_state(state.model_dump())
