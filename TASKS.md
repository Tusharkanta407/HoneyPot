# Honeypot AI — Project Tasks

---

## PHASE 1 — PROJECT SETUP

- [x] Create FastAPI project
- [x] Add .env for API keys
- [x] Setup requirements.txt
- [x] Create base folder structure

---

## PHASE 2 — SESSION & MEMORY(Tushar)

- [ ] Implement session_store.py
- [ ] Create session using sessionId
- [ ] Store messages per session
- [ ] Track total messages exchanged
- [ ] Mark session as completed

---

## PHASE 3 — SCAM DETECTION(Sradha)

- [ ] Integrate scam_detector_agent.py
- [ ] Call detection ONLY on first message
- [ ] Store is_scam, scam_type, confidence
- [ ] Handle non-scam gracefully

---

## PHASE 4 — PERSONA STRATEGY

- [ ] Define persona per scam type
- [ ] Lock persona per session
- [ ] Generate believable human replies
- [ ] Ensure no detection leakage

---

## PHASE 5 — MULTI-TURN ENGAGEMENT

- [ ] Continue conversation using memory
- [ ] Use conversationHistory if provided
- [ ] Adapt replies dynamically

---

## PHASE 6 — INTELLIGENCE EXTRACTION

- [ ] Extract UPI IDs
- [ ] Extract bank account numbers
- [ ] Extract phone numbers
- [ ] Extract phishing URLs
- [ ] Track suspicious keywords
- [ ] Accumulate intelligence across turns

---

## PHASE 7 — TERMINATION LOGIC

- [ ] Stop after sufficient intelligence
- [ ] Stop after max message count (e.g. 15–20)
- [ ] Prevent duplicate callbacks

---

## PHASE 8 — FINAL CALLBACK (MANDATORY)

- [ ] Build GUVI callback payload
- [ ] Send callback exactly once
- [ ] Include all extracted intelligence
- [ ] Include agentNotes summary
- [ ] Handle callback failure safely

---

## PHASE 9 — HARDENING

- [ ] Validate x-api-key
- [ ] Always return JSON
- [ ] Handle empty or malformed input
- [ ] Prevent crashes on LLM failure
- [ ] Add basic logging

---

## PHASE 10 — FINAL CHECK

- [ ] API reachable publicly
- [ ] Multi-turn works with same sessionId
- [ ] Persona consistent
- [ ] Intelligence extracted
- [ ] Final callback sent
- [ ] No ethical violations

---

> Mark tasks complete by changing `- [ ]` to `- [x]`
