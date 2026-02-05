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

    - Default: deterministic (no extra cost).
    - If USE_LLM_AGENT_NOTES=1: generate a cleaner one-liner using a small slice
      of scammer messages (keeps token usage low). Falls back to deterministic
      if the LLM call fails.
    """
    extracted = session.get("extracted") or {}
    upi = extracted.get("upiIds") or []
    links = extracted.get("phishingLinks") or []
    phones = extracted.get("phoneNumbers") or []
    banks = extracted.get("bankAccounts") or []

    # Optional: LLM-generated note (short + cleaner)
    if os.getenv("USE_LLM_AGENT_NOTES", "0") == "1" and OPENAI_API_KEY:
        try:
            scammer_msgs = [
                (m.get("text") or "")
                for m in (session.get("messages") or [])
                if (m.get("sender") == "scammer")
            ]
            # Keep context small: first 2 + last 1 (or first 3 if short)
            sample = scammer_msgs[:3] if len(scammer_msgs) <= 6 else (scammer_msgs[:2] + scammer_msgs[-1:])
            convo = "\n".join(f"- {t}" for t in sample if t.strip())

            client = OpenAI(base_url=OPENROUTER_BASE, api_key=OPENAI_API_KEY)
            prompt = (
                "Write ONE short sentence summarizing the scammer's tactics and goal. "
                "Do not include counts, do not list extracted items, and do not mention being an AI.\n"
                "Example style: 'Scammer used urgency and payment redirection to push a victim to share OTP via a phishing link.'\n\n"
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

    scammer_text = " ".join(
        (m.get("text") or "")
        for m in (session.get("messages") or [])
        if (m.get("sender") == "scammer")
    ).lower()

    tactics = []
    if any(w in scammer_text for w in ("urgent", "immediately", "expire", "blocked", "suspended", "final reminder")):
        tactics.append("urgency tactics")
    if ("upi" in scammer_text) or banks or upi:
        tactics.append("payment redirection")
    if ("http://" in scammer_text) or ("https://" in scammer_text) or links:
        tactics.append("phishing-link sharing")
    if any(w in scammer_text for w in ("otp", "pin", "cvv", "password")):
        tactics.append("credential requests")
    if ("whatsapp" in scammer_text) or phones:
        tactics.append("off-platform contact push")

    if not tactics:
        tactics_part = "suspicious persuasion tactics"
    elif len(tactics) == 1:
        tactics_part = tactics[0]
    else:
        tactics_part = ", ".join(tactics[:-1]) + " and " + tactics[-1]

    # Mention what we captured, but keep it as a single short clause.
    captured_bits = []
    if upi:
        captured_bits.append("UPI")
    if banks:
        captured_bits.append("bank account")
    if phones:
        captured_bits.append("phone number")
    if links:
        captured_bits.append("link")

    captured_part = ""
    if captured_bits:
        captured_part = f"; captured {', '.join(captured_bits)} details"

    return f"Scammer used {tactics_part}{captured_part}."


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

