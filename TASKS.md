# Honeypot AI — Project Tasks

See **WIN_ROADMAP.md** for analysis vs finals.md and the path to deploy.

---

## PHASE 1 — PROJECT SETUP

- [x] Create FastAPI project
- [x] Add .env for API keys
- [x] Setup requirements.txt
- [x] Create base folder structure

---

## PHASE 2 — SESSION & MEMORY (Tushar)

- [x] Implement session_store.py
- [x] Create session using sessionId
- [x] Store messages per session
- [x] Track total messages exchanged
- [x] Mark session as completed

---

## PHASE 3 — SCAM DETECTION (Sradha)

- [x] Integrate scam detection (ScamDetectionTool)
- [x] Run detection until scam confirmed (then keep state)
- [x] Store is_scam, scam_type, confidence
- [x] Handle non-scam gracefully (neutral persona)

---

## PHASE 4 — PERSONA STRATEGY

- [x] Define persona per scam type
- [x] Lock persona per session
- [x] Generate believable human replies
- [x] Ensure no detection leakage

---

## PHASE 5 — MULTI-TURN ENGAGEMENT

- [x] Continue conversation using memory
- [x] Use conversationHistory if provided (session messages)
- [x] Adapt replies dynamically (persona + history)

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
