import logging
import traceback
from typing import Optional, List, Dict, Any


from pathlib import Path
import os

from dotenv import load_dotenv
load_dotenv(override=True)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.memory.session_store import (
    create_session,
    session_exists,
    get_session,
    append_message,
    update_detection,
    update_persona,
    add_extracted
)
from app.tools.detection_tools import ScamDetectionTool
# NEW: Import the Manager
from app.chains.agent_manager import AgentManager

app = FastAPI(title="Honeypot AI")

# Initialize Global Tools
_scam_tool = ScamDetectionTool()
_agent_manager = AgentManager()

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
    return {"status": "ok", "message": "honeypot-agent-active"}

@app.post("/honeypot")
def honeypot_endpoint(payload: IncomingModel):
    """
    Core Logic Loop:
    1. Input: Receive message.
    2. Detection: Analyze (Message + History) -> is_scam?
    3. Decision: 
       - If Safe -> Monitoring Mode (Neutral Persona)
       - If Scam -> Active Mode (Victim Persona)
    4. Action: Generate Reply using Persona.
    5. Output: Return reply + intelligence.
    """
    session_id = payload.sessionId
    
    try:
        # 1. SETUP SESSION
        if not session_exists(session_id):
            create_session(session_id)
        
        # Append incoming message to memory
        msg_in = {
            "sender": payload.message.sender,
            "text": payload.message.text,
            "timestamp": payload.message.timestamp,
        }
        append_message(session_id, msg_in)
        
        # Load up-to-date session
        session = get_session(session_id)
        history = session["messages"]

        # 2. CONTINUOUS DETECTION
        # We check EVERY message to see if it turns into a scam
        # (Optimization: If already confirmed scam, we can skip detection or run it lightly)
        
        is_already_known_scam = session.get("is_scam", False)
        detection_result = {
            "is_scam": is_already_known_scam,
            "scam_type": session.get("scam_type", "none"),
            "confidence": session.get("confidence", 0.0)
        }

        # If not yet confirmed 100%, keep checking
        if not is_already_known_scam:
            try:
                # Run Hybrid Detection
                # Pass history to detection tool context
                det_res = _scam_tool._run(payload.message.text, history=history)
                
                # Update if checks find something
                if det_res["is_scam"]:
                    update_detection(
                        session_id,
                        True,
                        det_res["scam_type"],
                        det_res["confidence"]
                    )
                    detection_result = det_res
                    
            except Exception as e:
                logging.error(f"Detection failed: {e}")

        # 3. AGENT EXECUTION (The "Reply" Phase)
        # The AgentManager handles persona selection (Neutral vs Victim) internally
        agent_out = _agent_manager.run_agent(
            msg_text=payload.message.text,
            history=history,
            session=session,
            scam_details=detection_result
        )

        reply_text = agent_out["reply"]
        
        # Save any new persona assignment
        if agent_out.get("is_new_persona"):
            update_persona(session_id, agent_out["persona_id"])

        # 4. STORE OUTGOING REPLY
        msg_out = {
            "sender": "agent",
            "text": reply_text,
            "timestamp": None # Current time ideally
        }
        append_message(session_id, msg_out)

        # 5. FINAL RESPONSE
        # Refresh session to get latest state
        s_final = get_session(session_id)
        
        return {
            "status": "success",
            "sessionId": session_id,
            "is_scam": s_final["is_scam"],
            "scam_type": s_final["scam_type"],
            "generated_response": reply_text,
            "persona": s_final["persona"],
            "confidence": s_final["confidence"],
            # TODO: Add extracted intelligence here
            "intelligence": s_final["extracted"]
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


