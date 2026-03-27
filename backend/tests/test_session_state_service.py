from pathlib import Path

from app.services.session_state_service import SessionStateService


def test_session_state_persists_extended_fields(tmp_path: Path) -> None:
    service = SessionStateService(tmp_path)

    state = service.write_state(
        {
            "current_asset": "SUI",
            "last_intent": "asset_due_diligence",
            "last_timeframes": ["1d"],
            "last_report_type": None,
            "recent_assets": ["SUI"],
            "current_task": "reviewing SUI",
            "last_skill": "protocol_due_diligence",
            "last_agent": "ResearchAgent",
        }
    )

    assert state.current_task == "reviewing SUI"
    assert state.last_skill == "protocol_due_diligence"
    assert state.last_agent == "ResearchAgent"
