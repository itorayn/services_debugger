from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TaskType(StrEnum):
    LOG = 'log_dump'
    PCAP = 'pcap_dump'


class Task(BaseModel):
    """Модель данных задачи которую необходимо выполнить на удаленном хосте."""

    model_config = ConfigDict(from_attributes=True)

    task_id: str | None = Field(min_length=8, max_length=8)
    name: str
    task_type: TaskType
    is_alive: bool
