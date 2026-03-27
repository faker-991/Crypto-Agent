from pathlib import Path

from app.api import planner
from app.api.planner import PlannerExecuteRequest, execute_query
from app.orchestrator.orchestrator_service import OrchestratorService
from app.main import create_app


def test_planner_execute_api_returns_execute_payload(tmp_path: Path) -> None:
    service = OrchestratorService(memory_root=tmp_path)

    payload = execute_query(
        PlannerExecuteRequest(user_query="帮我研究一下 SUI 基本面"),
        service,
    )

    assert payload["status"] == "execute"
    assert payload["plan"]["tasks"][0]["task_type"] == "research"


def test_main_mounts_planner_execute_endpoint(tmp_path: Path) -> None:
    app = create_app(memory_root=tmp_path, enable_scheduler=False)
    paths = {route.path for route in app.routes}

    assert "/api/planner/execute" in paths
    assert planner.get_orchestrator_service in app.dependency_overrides
