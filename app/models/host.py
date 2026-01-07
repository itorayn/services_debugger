from pydantic import BaseModel, Field


class Host(BaseModel):
    """Модель данных хоста к которому будут происходить подключения по протоколу SSH."""

    host_id: int | None = Field(None)
    name: str = Field(min_length=3, max_length=32)
    description: str
    ssh_address: str
    ssh_port: int
    username: str
    password: str

    class Config:
        """Конфигурация модели."""

        from_attributes = True
