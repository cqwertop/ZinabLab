from fastapi import APIRouter
from pydantic import BaseModel, Field

from ai import assistant

router = APIRouter()


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatTurn] = Field(default_factory=list)


@router.post("/chat")
async def chat(request: ChatRequest):
    history = [turn.model_dump() for turn in request.messages]
    return await assistant.answer(history)


@router.get("/chat/suggestions")
def chat_suggestions():
    return {"suggestions": assistant.suggestions(), "mode": "claude" if assistant._has_credentials() else "offline"}
