# YOU - SessionId, memory, state
# app/memory/store.py
import threading
from typing import Dict, Any

_lock = threading.Lock()
_sessions: Dict[str, Dict[str, Any]] = {}

def create_session(session_id: str) -> Dict[str, Any]:
    with _lock:
        if session_id in _sessions:
            return _sessions[session_id]
        _sessions[session_id] = {
            "sessionId": session_id,
            "messages": [],   # list of {sender,text,timestamp}
            "is_scam": None,
            "scam_type": None,
            "confidence": None,
            "persona": None,
            "extracted": {
                "bankAccounts": [],
                "upiIds": [],
                "phishingLinks": [],
                "phoneNumbers": [],
                "suspiciousKeywords": []
            },
            "total_messages": 0,
            "completed": False  # final callback sent
        }
        return _sessions[session_id]

def get_session(session_id: str) -> Dict[str, Any]:
    with _lock:
        return _sessions.get(session_id)

def session_exists(session_id: str) -> bool:
    with _lock:
        return session_id in _sessions

def append_message(session_id: str, message: Dict[str, Any]) -> None:
    with _lock:
        s = _sessions[session_id]
        s["messages"].append(message)
        s["total_messages"] += 1

def update_detection(session_id: str, is_scam: bool, scam_type: str, confidence: float) -> None:
    with _lock:
        s = _sessions[session_id]
        s["is_scam"] = is_scam
        s["scam_type"] = scam_type
        s["confidence"] = confidence

def update_persona(session_id: str, persona: str) -> None:
    with _lock:
        _sessions[session_id]["persona"] = persona

def add_extracted(session_id: str, key: str, value: str) -> None:
    with _lock:
        arr = _sessions[session_id]["extracted"].setdefault(key, [])
        if value and value not in arr:
            arr.append(value)

def mark_completed(session_id: str) -> None:
    with _lock:
        _sessions[session_id]["completed"] = True
