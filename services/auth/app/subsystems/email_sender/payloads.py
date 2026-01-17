from pydantic import BaseModel


class VerifyEmailPayload(BaseModel):
    username: str
    token: str
