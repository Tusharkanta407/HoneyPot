import os
import time
import logging
import json
from typing import Any, Dict, Optional

import httpx
from openai import OpenAI

from app.utils.constants import OPENROUTER_BASE, OPENAI_API_KEY, OPENAI_MODEL


GUVI_FINAL_RESULT_URL = os.getenv(
    "GUVI_FINAL_RESULT_URL",
    "https://hackathon.guvi.in/api/updateHoneyPotFinalResult",
)


def build_agent_notes(session: Dict[str, Any]) -> str:
    """
    agentNotes one-liner.

    - If USE_LLM_AGENT_NOTES=1: generate a clean one-line summary using a small slice
      of scammer messages (keeps tokens low). Falls back to deterministic if LLM fails.
    - Else: deterministic one-liner from keywords.
    """
    scammer_msgs = [
        (m.get("text") or "")
        for m in (session.get("messages") or [])
        if (m.get("sender") == "scammer")
    ]

    if os.getenv("USE_LLM_AGENT_NOTES", "0") == "1" and OPENAI_API_KEY:
        try:
            sample = scammer_msgs[:3] if len(scammer_msgs) <= 6 else (scammer_msgs[:2] + scammer_msgs[-1:])
            convo = "\n".join(f"- {t}" for t in sample if t.strip())
            client = OpenAI(base_url=OPENROUTER_BASE, api_key=OPENAI_API_KEY)
            prompt = (
                "Write ONE short sentence summarizing the scammer's tactics and goal. "
                "Do not include counts, do not list extracted items, and do not mention being an AI.\n"
                "Example: 'Scammer used urgency and payment redirection to push the victim to share OTP via a phishing link.'\n\n"
                f"Scammer messages:\n{convo}\n"
            )
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=35,
                temperature=0.2,
            )
            note = (resp.choices[0].message.content or "").strip()
            if note:
                return note
        except Exception as e:
            logging.error("LLM agentNotes failed, using fallback: %s", e)

    scammer_text = " ".join(scammer_msgs).lower()
    tactics = []
    if any(w in scammer_text for w in ("urgent", "immediately", "expire", "blocked", "suspended", "final reminder")):
        tactics.append("urgency tactics")
    if any(w in scammer_text for w in ("upi", "transfer", "ifsc", "pay")):
        tactics.append("payment redirection")
    if ("http://" in scammer_text) or ("https://" in scammer_text):
        tactics.append("phishing link")
    if any(w in scammer_text for w in ("otp", "pin", "cvv", "password")):
        tactics.append("credential request")
    if any(w in scammer_text for w in ("whatsapp", "telegram")):
        tactics.append("off-platform contact")

    if not tactics:
        return "Scammer attempted to pressure the victim into completing a risky verification/payment process."
    if len(tactics) == 1:
        return f"Scammer used {tactics[0]} to push the victim into risky actions."
    return f"Scammer used {', '.join(tactics[:-1])} and {tactics[-1]} to push the victim into risky actions."


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

