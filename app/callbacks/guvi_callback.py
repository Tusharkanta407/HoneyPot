import os
import time
import logging
import json
from typing import Any, Dict, Optional

import httpx


GUVI_FINAL_RESULT_URL = os.getenv(
    "GUVI_FINAL_RESULT_URL",
    "https://hackathon.guvi.in/api/updateHoneyPotFinalResult",
)


def build_agent_notes(session: Dict[str, Any]) -> str:
    """Simple, deterministic agentNotes summary (no extra LLM call)."""
    scam_type = session.get("scam_type") or "unknown"
    extracted = session.get("extracted") or {}
    upi = extracted.get("upiIds") or []
    links = extracted.get("phishingLinks") or []
    phones = extracted.get("phoneNumbers") or []
    banks = extracted.get("bankAccounts") or []
    keywords = extracted.get("suspiciousKeywords") or []

    parts = [f"Scam type: {scam_type}."]
    if keywords:
        parts.append(f"Keywords: {', '.join(keywords[:8])}.")
    if upi:
        parts.append(f"UPI IDs captured: {len(upi)}.")
    if banks:
        parts.append(f"Bank accounts captured: {len(banks)}.")
    if phones:
        parts.append(f"Phone numbers captured: {len(phones)}.")
    if links:
        parts.append(f"Links captured: {len(links)}.")
    return " ".join(parts).strip()


def build_guvi_payload(session: Dict[str, Any]) -> Dict[str, Any]:
    extracted = session.get("extracted") or {}
    return {
        "sessionId": session.get("sessionId"),
        "scamDetected": bool(session.get("is_scam")),
        "totalMessagesExchanged": int(session.get("total_messages") or 0),
        "extractedIntelligence": {
            "bankAccounts": extracted.get("bankAccounts") or [],
            "upiIds": extracted.get("upiIds") or [],
            "phishingLinks": extracted.get("phishingLinks") or [],
            "phoneNumbers": extracted.get("phoneNumbers") or [],
            "suspiciousKeywords": extracted.get("suspiciousKeywords") or [],
        },
        "agentNotes": build_agent_notes(session),
    }


def send_guvi_callback(
    session: Dict[str, Any],
    timeout_s: float = 5.0,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Sends the mandatory final result callback to GUVI.

    Returns a dict:
      { ok: bool, status_code: int|None, error: str|None }
    """
    payload = build_guvi_payload(session)

    # Debug: print the exact payload to the uvicorn terminal
    # (use print() so it shows even if logging isn't configured)
    if os.getenv("LOG_GUVI_PAYLOAD", "0") == "1":
        print("GUVI callback URL:", GUVI_FINAL_RESULT_URL, flush=True)
        print("GUVI callback payload:\n" + json.dumps(payload, indent=2, ensure_ascii=False), flush=True)

    last_err: Optional[str] = None
    for attempt in range(1, max_retries + 1):
        try:
            with httpx.Client(timeout=timeout_s) as client:
                r = client.post(GUVI_FINAL_RESULT_URL, json=payload)
            if 200 <= r.status_code < 300:
                logging.info("GUVI callback success sessionId=%s status=%s", payload["sessionId"], r.status_code)
                return {"ok": True, "status_code": r.status_code, "error": None}

            last_err = f"GUVI callback HTTP {r.status_code}: {r.text[:300]}"
            logging.error(last_err)

        except Exception as e:
            last_err = f"GUVI callback exception: {type(e).__name__}: {e}"
            logging.error(last_err)

        # small backoff before retry
        if attempt < max_retries:
            time.sleep(0.5 * attempt)

    return {"ok": False, "status_code": None, "error": last_err}

