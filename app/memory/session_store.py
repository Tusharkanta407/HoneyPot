# YOU - SessionId, memory, state
# app/memory/store.py
import threading
import time
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
            # Detection state (defaults: not a scam until proven otherwise)
            "is_scam": False,
            "scam_type": "none",
            "confidence": 0.0,
            "persona": None,
            "extracted": {
                "bankAccounts": [],
                "upiIds": [],
                "phishingLinks": [],
                "phoneNumbers": [],
                "suspiciousKeywords": []
            },
            "total_messages": 0,
            "completed": False,  # final callback sent (or session ended)
            # idle-timeout callback support (if scammer stops early)
            "last_scammer_ts": None,  # epoch seconds
            "idle_version": 0,  # increments on each scammer message
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
        if message.get("sender") == "scammer":
            s["last_scammer_ts"] = time.time()
            s["idle_version"] = int(s.get("idle_version") or 0) + 1


def replace_messages(session_id: str, messages: list[Dict[str, Any]]) -> None:
    """
    Replace session messages with platform-provided conversationHistory (normalized),
    without treating them as a new live scammer message (so we don't trigger idle timers).
    """
    with _lock:
        s = _sessions[session_id]
        s["messages"] = messages
        s["total_messages"] = len(messages)
        s["last_scammer_ts"] = None
        s["idle_version"] = 0


def get_idle_version(session_id: str) -> int:
    with _lock:
        return int(_sessions[session_id].get("idle_version") or 0)

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
