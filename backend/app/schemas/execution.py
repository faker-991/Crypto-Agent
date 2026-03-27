from pydantic import BaseModel, ConfigDict, Field


class ExecutionEventDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    integration: str | None = None
    endpoint: str | None = None
    input_summary: dict | None = None
    output_summary: dict | None = None
    degraded: bool = False
    error: str | None = None


class ExecutionEvent(BaseModel):
    name: str
    actor: str
    detail: ExecutionEventDetail = Field(default_factory=ExecutionEventDetail)
