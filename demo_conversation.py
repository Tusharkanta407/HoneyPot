"""
Multi-turn conversation demo — same session, 3–5 messages.
Run the API first: uvicorn app.main:app --reload
Then: python demo_conversation.py

Shows how the agent replies turn-by-turn in one session (scam flow).
"""
import httpx
import time

BASE_URL = "http://127.0.0.1:8000"
SESSION_ID = "demo-session-multi-turn-001"

# Simulated scammer messages (bank/UPI phishing style)
SCAMMER_MESSAGES = [
    "Your bank account will be blocked today. Verify immediately to avoid suspension.",
    "To verify, send ₹10 to UPI payme@ybl and open https://secure-verify.example/login . If issue call +919876543210.",
    "Please share the OTP you received on your phone to complete verification.",
    "Without OTP we cannot unblock your account. Send it in next 10 minutes.",
]

def send_message(client: httpx.Client, session_id: str, text: str, conversation_history: list) -> dict:
    payload = {
        "sessionId": session_id,
        "message": {
            "sender": "scammer",
            "text": text,
            "timestamp": int(time.time() * 1000),
        },
        "conversationHistory": conversation_history,
        "metadata": {"channel": "SMS", "language": "English", "locale": "IN"},
    }
    r = client.post(f"{BASE_URL}/honeypot", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

def main():
    print("=" * 60)
    print("MULTI-TURN DEMO — same session, scam-style messages")
    print("=" * 60)
    print(f"SessionId: {SESSION_ID}")
    print(f"API: {BASE_URL}")
    print()

    conversation_history = []
    with httpx.Client() as client:
        for i, scammer_text in enumerate(SCAMMER_MESSAGES, 1):
            print(f"[Turn {i}] Scammer: {scammer_text}")
            try:
                out = send_message(client, SESSION_ID, scammer_text, conversation_history)
            except httpx.HTTPStatusError as e:
                print(f"  Error: {e.response.status_code} — {e.response.text}")
                break
            except Exception as e:
                print(f"  Error: {e}")
                break

            reply = out.get("generated_response") or out.get("reply") or "(no reply)"
            is_scam = out.get("is_scam")
            persona = out.get("persona", "?")
            print(f"  Agent ({persona}): {reply}")
            print(f"  [is_scam={is_scam}]")
            if out.get("callback") is not None:
                print(f"  [callback={out.get('callback')}]")
            if out.get("agent_active") is False:
                print("  [agent_active=False — session ended]")
            print()

            # Build history for next request (optional; server has full state)
            conversation_history.append({"sender": "scammer", "text": scammer_text})
            conversation_history.append({"sender": "user", "text": reply})

    print("=" * 60)
    print("Demo done. Check that persona stayed consistent and replies fit the scam flow.")
    print("=" * 60)

if __name__ == "__main__":
    main()
