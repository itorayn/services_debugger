from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class Host(BaseModel):
    host_id: Optional[int] = Field(None)
    name: str = Field(min_length=3, max_length=32)
    description: str
    ssh_address: str
    ssh_port: int
    username: str
    password: str

    class Config:
        from_attributes = True
