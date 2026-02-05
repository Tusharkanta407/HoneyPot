import os
import httpx
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any, List
from app.personas.library import get_best_persona, ALL_PERSONAS, Persona
from app.utils.constants import OPENROUTER_BASE, OPENAI_API_KEY, OPENAI_MODEL

# Custom HTTP client - avoids LangChain passing 'proxies' to OpenAI (rejected by newer openai pkg)
_http_client = httpx.Client()

class AgentManager:
    def __init__(self):
        self._llm = None
        self.persona_map = {p.id: p for p in ALL_PERSONAS}

    @property
    def llm(self):
        """Lazy init. Uses OpenRouter (openrouter.ai) when OPENAI_API_BASE is set."""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=OPENAI_MODEL,
                temperature=0.7,
                openai_api_key=OPENAI_API_KEY,
                openai_api_base=OPENROUTER_BASE,
                http_client=_http_client,
            )
        return self._llm

    def run_agent(self, msg_text: str, history: List[Dict], session: Dict[str, Any], scam_details: Dict) -> Dict[str, Any]:
        """
        State Machine for Agent Response:
        1. Determine Persona (Load from session or Select new)
        2. Generate Reply
        """
        
        # 1. PERSONA SELECTION
        # Keep persona consistent per session, but if scam becomes confirmed after
        # initially being unknown/non-scam, switch away from skeptical_busy to a victim persona.
        current_persona_id = session.get("persona")
        scam_confirmed = bool(scam_details.get("is_scam"))

        if scam_confirmed:
            if (not current_persona_id) or (current_persona_id == "skeptical_busy"):
                persona = get_best_persona(scam_details.get("scam_type", "unknown"))
                is_new_persona = True
            else:
                persona = self.persona_map.get(
                    current_persona_id,
                    get_best_persona(scam_details.get("scam_type", "unknown")),
                )
                is_new_persona = False
        else:
            if current_persona_id and current_persona_id in self.persona_map:
                persona = self.persona_map[current_persona_id]
                is_new_persona = False
            else:
                persona = self.persona_map["skeptical_busy"]
                is_new_persona = True

        # 2. PROMPT CONSTRUCTION
        # Convert history to string — "scammer" = other party, "agent" = your previous replies
        history_text = ""
        for h in history:
            sender = h.get("sender", "unknown")
            text = h.get("text", "")
            label = "OTHER" if sender == "scammer" else "YOU"
            history_text += f"{label}: {text}\n"

        system_prompt = f"""
{persona.system_prompt}

YOUR GOAL: {persona.goal}

STYLE GUIDE:
{persona.style_guide}

CONVERSATION RULES:
- In the history, "OTHER" = the other person (possible scammer). "YOU" = your own previous replies.
- Reply ONLY as your character ({persona.name}). Keep your reply to 1-3 short sentences — this is chat, not email.
- Do NOT say you are an AI, a bot, or that this is a test. Never break character.
- Do NOT accuse the other person or use words like "scam", "fraud", "suspicious", "report", "police", "authorities".
- Do NOT threaten reporting or enforcement. Keep the conversation natural and cooperative.
- Stay in role so the conversation feels natural and the other party keeps engaging.
"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", f"CONVERSATION SO FAR:\n{history_text}\n\nNEW MESSAGE FROM OTHER:\n{msg_text}\n\nYour reply (1-3 sentences, in character):")
        ])
        
        # 3. GENERATION
        chain = prompt | self.llm
        response = chain.invoke({})
        reply_text = response.content

        return {
            "reply": reply_text,
            "persona_id": persona.id,
            "is_new_persona": is_new_persona
        }
