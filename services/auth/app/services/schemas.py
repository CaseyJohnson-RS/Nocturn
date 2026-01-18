from pydantic import BaseModel, Field


class StatusResponce(BaseModel):
    status: str = Field(
        default="success"
    )