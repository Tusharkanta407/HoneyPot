"""
Multi-turn conversation demo — same session, 3–5 messages.
Run the API first: uvicorn app.main:app --reload
Then: python demo_conversation.py

Shows how the agent replies turn-by-turn in one session (scam flow).
"""
import httpx
import time

BASE_URL = "http://127.0.0.1:8000"
# Use a fresh session each run so completed sessions don't affect testing
SESSION_ID = f"demo-session-multi-turn-{int(time.time())}"

# Simulated scammer messages (10-turn crypto/investment scam flow)
SCAMMER_MESSAGES = [
    "Congratulations! You are selected for part-time online work from home job.",
    "You can earn ₹3,000 to ₹5,000 daily by completing simple tasks.",
    "To activate job account, you must complete registration process.",
    "Registration fee is ₹1,200 which is refundable after first task.",
    "Send payment to UPI jobverify@paytm.",
    "After payment, you will receive login details and training material.",
    "Our HR team will guide you through WhatsApp.",
    "Please send payment screenshot for verification.",
    "If payment fails, you can contact job support officer +919845678901.",
    "Only few positions left. Complete registration today."
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
