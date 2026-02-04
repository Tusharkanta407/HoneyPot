# Win Roadmap — Analysis & Path to Deploy

Based on **finals.md** (problem statement + evaluation) and the current codebase.

---

## 1. Is the direction right?

**Yes.** The architecture matches the brief:

| Requirement (finals.md) | Current state |
|-------------------------|----------------|
| REST API, accept message events | ✅ `POST /honeypot` |
| Detect scam intent | ✅ Hybrid detection on every message until confirmed |
| Hand control to AI Agent | ✅ `AgentManager` + personas |
| Engage autonomously, multi-turn | ✅ Session + history, persona locked per session |
| Return structured JSON | ✅ JSON response |
| **Extract intelligence** | ⚠️ Session has `extracted` structure but **no extraction logic** (stub only) |
| **Report to GUVI** | ❌ **No callback** to `updateHoneyPotFinalResult` |
| **API key auth** | ❌ **No `x-api-key` validation** |

So: **direction is correct**. To “win” we must close three gaps: **extraction**, **one-time GUVI callback**, and **API key validation**. We also need **termination logic** (when to consider engagement “done” and send the callback).

---

## 2. How we should win (evaluation alignment)

From **finals.md §9** and **§12**:

1. **Scam detection accuracy** — Already in place (hybrid rule + LLM).
2. **Quality of agentic engagement** — Personas + multi-turn; keep improving prompts if needed.
3. **Intelligence extraction** — **Must implement**: UPI, bank accounts, phone numbers, phishing links, suspicious keywords; accumulate in session.
4. **API stability and response time** — Stable FastAPI; add error handling and timeouts.
5. **Ethical behavior** — Personas are fictional; no impersonation.
6. **Mandatory callback** — **Must send** `POST https://hackathon.guvi.in/api/updateHoneyPotFinalResult` **exactly once** per completed scam session with the exact payload. **If this is not sent, the solution cannot be evaluated.**

Winning = do detection + engagement well **and** extract intel **and** call GUVI once when the conversation is “finished”.

---

## 3. What we need to do from now → deploy and test

High-level order:

1. **Align API response with spec**  
   finals.md §8: agent output should include `"reply": "..."`. Add `reply` (and keep or rename `generated_response` as needed).

2. **Implement intelligence extraction**  
   - Implement `app/tools/extraction_tools.py`: regex (or small LLM) for UPI IDs, bank account patterns, phone numbers, URLs, and optionally suspicious keywords.  
   - After each **scam** message (and optionally on reply), run extraction on `message.text` (and maybe last N messages), then merge into session via `add_extracted()`.  
   - Session already has `extracted` with `bankAccounts`, `upiIds`, `phishingLinks`, `phoneNumbers`, `suspiciousKeywords`.

3. **Termination logic**  
   - Define “conversation complete”: e.g. `total_messages >= MAX` (e.g. 18–20) **or** “sufficient intelligence” (e.g. at least one of UPI/bank/phone/link).  
   - When complete and `is_scam` and not yet `completed`: send GUVI callback, then `mark_completed(session_id)` so we never send again.

4. **GUVI callback (mandatory)**  
   - New module e.g. `app/callbacks/guvi_callback.py`.  
   - One function: build payload from session (`sessionId`, `scamDetected`, `totalMessagesExchanged`, `extractedIntelligence`, `agentNotes`), POST to `https://hackathon.guvi.in/api/updateHoneyPotFinalResult`, timeout 5s.  
   - `agentNotes`: short summary (e.g. from last agent reply or a fixed template; optional: one LLM call to summarize behavior).  
   - Call this **only** from the place that implements “conversation complete”, and only if `not session["completed"]`.

5. **API authentication**  
   - finals.md §4: `x-api-key: YOUR_SECRET_API_KEY`.  
   - Add a FastAPI dependency that reads `x-api-key` header and compares to a key from env (e.g. `HONEYPOT_API_KEY`). Return 401 if missing or wrong. Apply to `POST /honeypot` (and optionally `GET /`).

6. **Hardening**  
   - Validate input (e.g. `sessionId` and `message.text` present).  
   - Try/except around extraction and callback; never crash the main request.  
   - Basic logging (incoming sessionId, scam detected, callback sent).

7. **Deploy**  
   - Deploy API to a public URL (e.g. Railway, Render, Fly.io, or VM).  
   - Set env: `OPENAI_API_KEY`, `HONEYPOT_API_KEY` (and any other secrets).  
   - Ensure HTTPS.

8. **Test end-to-end**  
   - Send first message (scam-like) → get `reply`, `is_scam`, etc.  
   - Send follow-ups with same `sessionId` → multi-turn, persona consistent.  
   - After enough messages (or sufficient intel), verify **one** POST to GUVI with correct payload (e.g. via logs or a test harness that mocks GUVI).  
   - Test with non-scam message → no callback, neutral persona.

---

## 4. What to change now (prioritized)

| Priority | What | Where |
|----------|------|--------|
| **P0** | Implement extraction (regex + optional keywords) and call it each turn for scam sessions; merge into session | `extraction_tools.py`, `main.py` |
| **P0** | Implement GUVI callback and call it once when engagement is complete | `callbacks/guvi_callback.py`, `main.py` |
| **P0** | Termination logic: when to set “complete” and trigger callback (max messages + optional “enough intel”) | `main.py` (after reply + extraction), maybe `constants.py` for MAX_MSGS |
| **P1** | Add `"reply"` to API response (per finals.md §8) | `main.py` response dict |
| **P1** | Validate `x-api-key` on `/honeypot` | `main.py` (dependency + env `HONEYPOT_API_KEY`) |
| **P2** | Input validation, error handling, logging | `main.py`, optional `api/` or `utils/` |
| **P2** | `agentNotes` improvement (e.g. template or 1 LLM summary) | `guvi_callback.py` or agent_manager |

---

## 5. Suggested implementation order

1. **Extraction** — Implement and wire in so `s_final["extracted"]` is actually filled.  
2. **Termination + callback** — Define MAX_MSGS (and optionally “enough intel”), then implement GUVI callback and call it once when done.  
3. **Response + auth** — Add `reply`, then add `x-api-key` check.  
4. **Harden + deploy** — Validation, logging, deploy, then run multi-turn tests and confirm one callback per completed scam session.

This order gets the **mandatory** evaluation requirement (callback + extraction) in place first, then aligns with the spec and secures the API, then prepares for production and testing.
