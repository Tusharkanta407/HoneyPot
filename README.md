# Agentic Honey-Pot for Scam Detection & Intelligence Extraction

## 🚀 Problem Statement

Online scams such as bank fraud, UPI fraud, phishing, and fake offers are increasingly adaptive. Scammers modify their tactics based on user responses, making static detection systems ineffective.

This project implements an **Agentic Honey-Pot** — an AI-powered REST API that:

- Detects scam intent
- Autonomously engages scammers using a believable human persona
- Handles multi-turn conversations
- Extracts actionable scam intelligence
- Reports final intelligence to the GUVI evaluation endpoint

## 🎯 Objectives

The system is designed to:

- Detect scam or fraudulent messages
- Activate an autonomous AI Agent
- Maintain a human-like persona
- Handle multi-turn conversations
- Extract scam-related intelligence
- Return structured API responses
- Secure access using an API key

## 🧠 High-Level Architecture

```
Incoming Message
      ↓
Session Manager (sessionId)
      ↓
Scam Detection Agent
      ↓
Persona Strategy Agent
      ↓
Multi-Turn Engagement Loop
      ↓
Intelligence Extraction
      ↓
Termination Check
      ↓
Final Result Callback (GUVI)
```

## 🔐 API Authentication

All requests must include:

```
x-api-key: YOUR_SECRET_API_KEY
Content-Type: application/json
```

## 📡 API Endpoint

```
POST /honeypot
```

Handles one incoming message per request.

## 📥 Input Format

### First Message (Start of Conversation)

```json
{
  "sessionId": "wertyu-dfghj-ertyui",
  "message": {
    "sender": "scammer",
    "text": "Your bank account will be blocked today. Verify immediately.",
    "timestamp": 1770005528731
  },
  "conversationHistory": [],
  "metadata": {
    "channel": "SMS",
    "language": "English",
    "locale": "IN"
  }
}
```

### Follow-Up Message (Multi-Turn)

```json
{
  "sessionId": "wertyu-dfghj-ertyui",
  "message": {
    "sender": "scammer",
    "text": "Share your UPI ID to avoid account suspension.",
    "timestamp": 1770005528731
  },
  "conversationHistory": [
    {
      "sender": "scammer",
      "text": "Your bank account will be blocked today. Verify immediately."
    },
    {
      "sender": "user",
      "text": "Why will my account be blocked?"
    }
  ]
}
```

## 📤 API Response Format

```json
{
  "status": "success",
  "reply": "Why is my account being suspended?"
}
```

## 🤖 Agent Behavior

The AI Agent:

- Engages autonomously after scam detection
- Never reveals detection
- Adapts responses dynamically
- Maintains a believable human persona
- Handles multi-turn conversations
- Performs silent intelligence extraction

## 🧠 Extracted Intelligence

Extracted only from conversation text:

- Bank account numbers
- UPI IDs
- Phone numbers
- Phishing links
- Suspicious keywords

## 📌 Mandatory Final Result Callback (CRITICAL)

### Endpoint

```
POST https://hackathon.guvi.in/api/updateHoneyPotFinalResult
```

### Payload

```json
{
  "sessionId": "abc123-session-id",
  "scamDetected": true,
  "totalMessagesExchanged": 18,
  "extractedIntelligence": {
    "bankAccounts": ["XXXX-XXXX-XXXX"],
    "upiIds": ["scammer@upi"],
    "phishingLinks": ["http://malicious-link.example"],
    "phoneNumbers": ["+91XXXXXXXXXX"],
    "suspiciousKeywords": ["urgent", "verify now", "account blocked"]
  },
  "agentNotes": "Scammer used urgency tactics and payment redirection"
}
```

### When to Send

Send **ONLY ONCE**, after:

- Scam intent is confirmed
- Sufficient engagement is completed
- Intelligence extraction is finished

---

## 🛠️ Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload
```

## 📁 Project Structure

```
app/
├── main.py                 # FastAPI entry point
├── api/
│   └── honeypot_handler.py # Main controller
├── agents/
│   ├── scam_detector_agent.py
│   ├── persona_agent.py
│   └── extraction_agent.py
├── tools/
│   ├── detection_tools.py
│   └── extraction_tools.py
├── memory/
│   └── session_store.py
├── callbacks/
│   └── guvi_callback.py
├── utils/
│   ├── constants.py
│   └── helpers.py
└── schemas.py
```
