import os
import httpx
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any, List
from app.personas.library import get_best_persona, ALL_PERSONAS, Persona

# Custom HTTP client - avoids LangChain passing 'proxies' to OpenAI (rejected by newer openai pkg)
_http_client = httpx.Client()

class AgentManager:
    def __init__(self):
        self._llm = None
        self.persona_map = {p.id: p for p in ALL_PERSONAS}

    @property
    def llm(self):
        """Lazy init. Use custom http_client so 'proxies' is never passed to OpenAI client."""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                temperature=0.7,
                openai_api_key=os.getenv("OPENAI_API_KEY"),
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
        current_persona_id = session.get("persona")
        
        if current_persona_id and current_persona_id in self.persona_map:
            # Existing session - keep consistent
            persona = self.persona_map[current_persona_id]
            is_new_persona = False
        else:
            # New or Switch required
            if scam_details.get("is_scam"):
                 # Targeted persona
                persona = get_best_persona(scam_details.get("scam_type", "unknown"))
            else:
                # Neutral persona for monitoring
                persona = self.persona_map["skeptical_busy"]
            
            is_new_persona = True

        # 2. PROMPT CONSTRUCTION
        # Convert history to string
        history_text = ""
        for h in history:
            sender = h.get("sender", "unknown")
            text = h.get("text", "")
            history_text += f"{sender}: {text}\n"

        system_prompt = f"""
{persona.system_prompt}

YOUR GOAL: {persona.goal}

STYLE GUIDE:
{persona.style_guide}

CURRENT SCENARIO:
You are in a chat. You suspect or know the other person is a scammer (or a stranger).
Act your role perfecty.
NEVER break character. 
"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", f"CONVERSATION HISTORY:\n{history_text}\n\nNEW MESSAGE:\n{msg_text}\n\nReply:")
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
