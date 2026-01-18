from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    status: str = Field(
        default="success"
    )