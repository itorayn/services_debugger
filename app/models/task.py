from typing import Optional, Literal
from pydantic import BaseModel, Field


class Task(BaseModel):
    """Модель данных задачи которую необходимо выполнить на удаленном хосте."""

    task_id: Optional[str] = Field(min_length=8, max_length=8)
    name: str
    task_type: Literal['log_dump', 'pcap_dump']
    is_alive: bool

    class Config:
        """Конфигурация модели."""

        from_attributes = True
