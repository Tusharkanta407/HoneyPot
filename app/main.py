"""
FastAPI app entry point.
For now we only implement:
- Phase 2: session creation & tracking
- Phase 3: first-message scam detection using detection_tools
"""

from typing import Optional, List, Dict, Any

from fastapi import FastAPI
from pydantic import BaseModel

from app.memory.session_store import (
    create_session,
    session_exists,
    get_session,
    append_message,
    update_detection,
)
from app.tools.detection_tools import ScamDetectionTool

app = FastAPI(title="Honeypot AI")

_scam_tool = ScamDetectionTool()


class MessageModel(BaseModel):
    sender: str
    text: str
    timestamp: Optional[int] = None


class IncomingModel(BaseModel):
    sessionId: str
    message: MessageModel
    conversationHistory: Optional[List[Dict[str, Any]]] = []
    metadata: Optional[Dict[str, Any]] = {}


@app.get("/")
def root():
    return {"status": "ok", "message": "honeypot-phase-2-3-ready"}


@app.post("/honeypot")
def honeypot_endpoint(payload: IncomingModel):
    """
    Each call is ONE incoming message.
    Goal for now:
    - ensure a session exists
    - append the message to that session
    - if this is the FIRST message for the session,
      run ScamDetectionTool to decide scam/not scam
    - return ONLY detection info + basic session info
    """
    session_id = payload.sessionId

    # 1) create or load session
    if not session_exists(session_id):
        create_session(session_id)

    session = get_session(session_id)

    # 2) append current message
    msg = {
        "sender": payload.message.sender,
        "text": payload.message.text,
        "timestamp": payload.message.timestamp,
    }
    append_message(session_id, msg)

    # 3) if first message -> detect scam using detection_tools
    is_first = session["total_messages"] == 1
    if is_first:
        result = _scam_tool._run(payload.message.text)
        update_detection(
            session_id,
            result["is_scam"],
            result["scam_type"],
            result["confidence"],
        )

    # 4) build response from session state (not from tool directly)
    session = get_session(session_id)  # refresh after update
    return {
        "status": "success",
        "sessionId": session_id,
        "is_scam": session["is_scam"],
        "scam_type": session["scam_type"],
        "confidence": session["confidence"],
        "total_messages": session["total_messages"],
    }
# something changesd 