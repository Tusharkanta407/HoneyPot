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
    # 1-2: hook (guaranteed returns)
    "Hello! Your number is selected for our premium crypto investment plan. Guaranteed 12% daily profit. Reply YES to start.",
    "Our official dashboard is https://pro-crypto-earn.example/login — create account and I will activate your VIP access.",
    # 3-5: move off-platform + ask for small deposit
    "For faster support, WhatsApp our manager at +919876543210. We will guide you step-by-step.",
    "To activate VIP and unlock withdrawals, pay a small refundable activation fee ₹999 via UPI to vipfund@ybl.",
    "If UPI fails, transfer ₹999 to HDFC account 12345678901234, IFSC HDFC0001234 and send screenshot.",
    # 6-7: phishing/verification pressure
    "Urgent: your VIP slot expires in 30 minutes. Complete activation now or your profit offer will be cancelled.",
    "After payment, click https://kyc-verify.crypto-earn.example/verify and complete KYC to enable withdrawals.",
    # 8-10: credential / OTP pressure (common scam pattern)
    "We sent an OTP to your phone for verification. Share the OTP to confirm your identity and unlock withdrawals.",
    "Do not delay. Without OTP, your withdrawal request cannot be processed.",
    "Final reminder: reply with OTP now to avoid account suspension and loss of profits.",
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
