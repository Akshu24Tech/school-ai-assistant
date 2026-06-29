from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="What the user is asking, in plain language")
    student_id: str = Field("S101", description="The student the question is about")
    role: Literal["student", "teacher", "parent"] = Field(
        "student", description="Who is asking — tunes the assistant's tone"
    )
    session_id: str | None = Field(
        None, description="Pass back a session_id to keep the conversation in context"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Show my attendance for this month.",
                "student_id": "S101",
                "role": "student",
            }
        }
    }


class ChatResponse(BaseModel):
    intent: str = Field(..., description="The intent the agent identified")
    response: str = Field(..., description="The natural-language answer")
    status: str = Field(..., description="A quick status flag, e.g. Good / Pending / OK")
    plan: list[str] = Field(..., description="The execution plan the agent followed")
    tools_used: list[str] = Field(..., description="ERP tools the agent called")
    data: dict = Field(default_factory=dict, description="Raw tool results, for transparency")
    session_id: str = Field(..., description="Reuse this to continue the conversation")
    execution_ms: int = Field(..., description="How long the turn took, in milliseconds")


class HistoryTurn(BaseModel):
    message: str
    response: str
    intent: str
    created_at: str


class HistoryResponse(BaseModel):
    session_id: str
    turns: list[HistoryTurn]
