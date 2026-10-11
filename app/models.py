from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Inbound(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(min_length=1, max_length=512)
    phone: str = Field(pattern=r"^\d{7,20}$")
    timestamp: int = Field(ge=0)
    type: Literal["text", "audio"]
    text: str = Field(default="", max_length=4096)
    media_id: str = Field(default="", max_length=128, pattern=r"^\d*$")


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply: str = Field(min_length=1, max_length=3000)
    handoff: bool
    reason: str = Field(max_length=300)
    # Evidence is an exact knowledge-file excerpt, checked in code.
    evidence: str = Field(max_length=1500)
    kind: Literal["company_answer", "conversation", "clarification", "handoff"]


class AdminReply(BaseModel):
    text: str = Field(min_length=1, max_length=3000)


class ServiceError(Exception):
    """Only a safe code is exposed; never include provider response bodies."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)
