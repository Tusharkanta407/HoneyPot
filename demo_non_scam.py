"""
Multi-turn NON-SCAM demo — same session, 3 messages.

Expected behavior (with NON_SCAM_MAX_MESSAGES=3):
- Turn 1: system may still reply (neutral) while deciding
- Turn 2: system may still reply (neutral) while deciding
- Turn 3: scam still not detected => agent stops
          response includes: agent_active=false, reply=""

Run API first:
  uvicorn app.main:app --reload

Then run:
  python demo_non_scam.py
"""

import time
import httpx

BASE_URL = "http://127.0.0.1:8000"
SESSION_ID = "demo-session-non-scam-001"

NORMAL_MESSAGES = [
    "Hi team, reminder: standup is at 10:30 AM today. Please be on time.",
    "Also please upload your weekly status update to the shared folder by EOD.",
    "FYI: The office Wi‑Fi maintenance is scheduled for tonight 11 PM–1 AM.",
]


def send_message(client: httpx.Client, session_id: str, text: str) -> dict:
    payload = {
        "sessionId": session_id,
        "message": {
            "sender": "scammer",  # platform always sends 'scammer' as the incoming party
            "text": text,
            "timestamp": int(time.time() * 1000),
        },
        "conversationHistory": [],
        "metadata": {"channel": "SMS", "language": "English", "locale": "IN"},
    }
    r = client.post(f"{BASE_URL}/honeypot", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    print("=" * 60)
    print("MULTI-TURN DEMO — NON-SCAM messages (same session)")
    print("=" * 60)
    print(f"SessionId: {SESSION_ID}")
    print(f"API: {BASE_URL}")
    print()

    with httpx.Client() as client:
        for i, msg in enumerate(NORMAL_MESSAGES, 1):
            print(f"[Turn {i}] Incoming: {msg}")
            out = send_message(client, SESSION_ID, msg)

            reply = out.get("reply", "")
            agent_active = out.get("agent_active", True)  # absent means old behavior
            is_scam = out.get("is_scam")
            note = out.get("note", "")

            print(f"  is_scam: {is_scam}")
            print(f"  agent_active: {agent_active}")
            print(f"  reply: {repr(reply)}")
            if note:
                print(f"  note: {note}")
            print()

    print("=" * 60)
    print("Done. Turn 3 should show agent_active=false and reply=''.")
    print("=" * 60)


if __name__ == "__main__":
    main()

