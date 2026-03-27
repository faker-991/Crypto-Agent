from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.orchestrator.orchestrator_service import OrchestratorService
from app.schemas.planner_response import PlannerExecutionResponse

router = APIRouter(prefix="/api/planner", tags=["planner"])


def get_orchestrator_service() -> OrchestratorService:
    raise RuntimeError("orchestrator service dependency is not configured")


class PlannerExecuteRequest(BaseModel):
    user_query: str


@router.post("/execute")
def execute_query(
    request: PlannerExecuteRequest,
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service),
) -> dict:
    return PlannerExecutionResponse(**orchestrator_service.execute(request.user_query)).model_dump()
