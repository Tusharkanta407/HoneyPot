from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
import traceback
from typing import Optional, List, Dict, Any

try:
    import openai
except ImportError:
    openai = None


from pathlib import Path
import os

from dotenv import load_dotenv
load_dotenv(override=True)

import os
prefix = os.getenv("OPENAI_API_KEY", "")[:10]
suffix = os.getenv("OPENAI_API_KEY", "")[-6:]  # last 6 chars
print("APP key prefix:", prefix, "suffix:", suffix)

from app.memory.session_store import (
    create_session,
    session_exists,
    get_session,
    append_message,
    update_detection,
    update_persona,
    add_extracted,
    mark_completed,
)
from app.tools.detection_tools import ScamDetectionTool
# NEW: Import the Manager
from app.chains.agent_manager import AgentManager
from app.tools.extraction_tools import ComprehensiveExtractionTool
from app.callbacks.guvi_callback import send_guvi_callback

app = FastAPI(title="Honeypot AI")

# Initialize Global Tools
_scam_tool = ScamDetectionTool()
_agent_manager = AgentManager()
_extract_tool = ComprehensiveExtractionTool()

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
        
        # If session already ended, do not activate any agent again
        if session.get("completed") is True:
            return {
                "status": "success",
                "reply": "",
                "sessionId": session_id,
                "is_scam": bool(session.get("is_scam")),
                "scam_type": session.get("scam_type") or "none",
                "generated_response": "",
                "persona": session.get("persona"),
                "confidence": session.get("confidence") or 0.0,
                "intelligence": session.get("extracted"),
                "agent_active": False,
                "note": "session_completed",
            }

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

        # 2.5 NON-SCAM STOP RULE
        # If we have received multiple messages and still can't confirm scam intent,
        # do NOT activate any agent (stop even the skeptical/neutral persona).
        scammer_msg_count = sum(1 for m in history if m.get("sender") == "scammer")
        NON_SCAM_MAX_MESSAGES = int(os.getenv("NON_SCAM_MAX_MESSAGES", "3"))
        if not detection_result.get("is_scam") and scammer_msg_count >= NON_SCAM_MAX_MESSAGES:
            # Lock-in "not scam" for this session to avoid repeatedly re-checking.
            update_detection(session_id, False, "none", 0.0)
            mark_completed(session_id)
            s_final = get_session(session_id)
            return {
                "status": "success",
                "reply": "",
                "sessionId": session_id,
                "is_scam": False,
                "scam_type": "none",
                "generated_response": "",
                "persona": None,
                "confidence": 0.0,
                "intelligence": s_final["extracted"],
                "agent_active": False,
                "note": f"non_scam_after_{scammer_msg_count}_messages",
            }

        # 2.7 INTELLIGENCE EXTRACTION (per incoming scammer message)
        # Only extract when scam is confirmed and message is from the other party.
        is_scam_now = bool(get_session(session_id).get("is_scam"))
        if is_scam_now and payload.message.sender == "scammer":
            try:
                intel = _extract_tool._run(payload.message.text)

                for v in intel.get("phone_numbers", []) or []:
                    add_extracted(session_id, "phoneNumbers", v)
                for v in intel.get("upi_ids", []) or []:
                    add_extracted(session_id, "upiIds", v)
                for v in intel.get("urls", []) or []:
                    add_extracted(session_id, "phishingLinks", v)
                for v in intel.get("account_numbers", []) or []:
                    add_extracted(session_id, "bankAccounts", v)

                # Suspicious keywords (simple list; dedup happens in add_extracted)
                msg_lower = (payload.message.text or "").lower()
                keyword_candidates = [
                    "urgent",
                    "verify",
                    "verify now",
                    "account blocked",
                    "account suspended",
                    "otp",
                    "pin",
                    "cvv",
                    "click",
                    "link",
                    "upi",
                    "payment",
                    "send money",
                ]
                for kw in keyword_candidates:
                    if kw in msg_lower:
                        add_extracted(session_id, "suspiciousKeywords", kw)
            except Exception as e:
                logging.error(f"Extraction failed: {e}")

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

        # 5. TERMINATION + FINAL CALLBACK (scam sessions only)
        s_final = get_session(session_id)
        extracted = s_final.get("extracted") or {}

        def _intel_category_count(ex: Dict[str, Any]) -> int:
            """Count how many high-value categories we have at least once."""
            keys = ("bankAccounts", "upiIds", "phishingLinks", "phoneNumbers")
            return sum(1 for k in keys if len(ex.get(k) or []) > 0)

        scammer_turns = sum(1 for m in (s_final.get("messages") or []) if m.get("sender") == "scammer")
        # Default strategy for hackathon scoring:
        # - Engage up to ~10 scammer turns for depth
        # - Aim for at least 2 intel categories before ending (UPI/link/phone/bank)
        # - Still keep a hard cap to avoid infinite loops
        SCAM_MAX_MESSAGES = int(os.getenv("SCAM_MAX_MESSAGES", "20"))  # total messages exchanged (scammer+agent)
        SCAM_TARGET_SCAMMER_TURNS = int(os.getenv("SCAM_TARGET_SCAMMER_TURNS", "10"))
        INTEL_MIN_CATEGORIES = int(os.getenv("INTEL_MIN_CATEGORIES", "2"))
        intel_cats = _intel_category_count(extracted)

        should_terminate = (
            bool(s_final.get("is_scam"))
            and not bool(s_final.get("completed"))
            and (
                # Primary: end after enough engagement depth (10 scammer turns),
                # even if we failed to reach 2 categories.
                (scammer_turns >= SCAM_TARGET_SCAMMER_TURNS)
                # Secondary: hard cap on total messages
                or (int(s_final.get("total_messages") or 0) >= SCAM_MAX_MESSAGES)
            )
        )

        callback_result = None
        if should_terminate:
            callback_result = send_guvi_callback(s_final)
            if callback_result.get("ok"):
                mark_completed(session_id)
                s_final = get_session(session_id)

        # 6. FINAL RESPONSE
        return {
            "status": "success",
            "reply": reply_text,
            "sessionId": session_id,
            "is_scam": s_final.get("is_scam"),
            "scam_type": s_final.get("scam_type"),
            "generated_response": reply_text,
            "persona": s_final.get("persona"),
            "confidence": s_final.get("confidence"),
            "intelligence": s_final.get("extracted"),
            "agent_active": not bool(s_final.get("completed")),
            "callback": callback_result,
        }

    except HTTPException:
        raise
    except Exception as e:
        is_quota_error = (
            (openai and isinstance(e, getattr(openai, "RateLimitError", ())))
            or "429" in str(e)
            or "quota" in str(e).lower()
            or "insufficient_quota" in str(e).lower()
        )
        if is_quota_error:
            raise HTTPException(
                status_code=503,
                detail="LLM quota exceeded (OpenAI/OpenRouter). Check your plan/credits.",
            )
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


