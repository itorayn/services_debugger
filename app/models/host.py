from pydantic import BaseModel, ConfigDict, Field


class Host(BaseModel):
    """Модель данных хоста к которому будут происходить подключения по протоколу SSH."""

    model_config = ConfigDict(from_attributes=True)

    host_id: int | None = Field(default=None)
    name: str | None = Field(default=None, min_length=3, max_length=32)
    description: str | None = Field(default=None, repr=False)
    ssh_address: str = Field(..., repr=False)
    ssh_port: int = Field(..., repr=False)
    username: str = Field(..., repr=False)
    password: str = Field(..., repr=False)
