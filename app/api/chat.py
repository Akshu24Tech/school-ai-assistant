import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agents import agent
from app.config import get_settings
from app.memory import store
from app.models.schemas import ChatRequest, ChatResponse, HistoryResponse, HistoryTurn
from app.utils import audit
from app.utils.auth import require_api_key
from app.utils.exceptions import EmptyRequest

router = APIRouter(dependencies=[Depends(require_api_key)])
log = logging.getLogger("app.api")


@router.post("/chat", response_model=ChatResponse, tags=["chat"])
def chat(req: ChatRequest):
    message = req.message.strip()
    if not message:
        raise EmptyRequest()

    session_id = req.session_id or store.new_session()
    prior = store.recent_turns(session_id, get_settings().memory_window)

    started = time.perf_counter()
    result = agent.run(message, req.student_id, req.role, prior)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    store.save_turn(session_id, req.student_id, message, result.response, result.intent)
    audit.record(message, result.intent, result.tools_used, elapsed_ms, result.response)

    return ChatResponse(
        intent=result.intent,
        response=result.response,
        status=result.status,
        plan=result.plan,
        tools_used=result.tools_used,
        data=result.data,
        session_id=session_id,
        execution_ms=elapsed_ms,
    )


@router.get("/chat/history", response_model=HistoryResponse, tags=["chat"])
def history(session_id: str | None = Query(None, description="Omit to get the latest session")):
    session_id = session_id or store.latest_session()
    if not session_id:
        raise HTTPException(status_code=404, detail="No conversations yet.")
    turns = store.all_turns(session_id)
    return HistoryResponse(session_id=session_id, turns=[HistoryTurn(**t) for t in turns])
