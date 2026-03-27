from typing import Any, Literal

from pydantic import BaseModel, Field


TaskType = Literal["research", "kline", "summary"]


class Task(BaseModel):
    task_id: str
    task_type: TaskType
    title: str
    slots: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
