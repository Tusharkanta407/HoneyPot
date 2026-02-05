import re
import os
import httpx
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import Optional, Type

from dotenv import load_dotenv
load_dotenv(override=True)
from app.utils.constants import OPENROUTER_BASE, OPENAI_API_KEY, OPENAI_MODEL


class ScamDetectionInput(BaseModel):
    """Input for scam detection tool"""
    message: str = Field(description="The message to analyze for scam indicators")


class LLMAnalysisInput(BaseModel):
    """Input for LLM-based semantic analysis"""
    message: str = Field(description="Message for deep semantic analysis")


class HybridDetectionInput(BaseModel):
    """Input for hybrid detection (rules + LLM)"""
    message: str = Field(description="Message to analyze using multiple methods")

class LLMScamOutput(BaseModel):
    """Structured output from LLM analysis"""
    is_scam: bool = Field(description="Whether message is a scam")
    scam_type: str = Field(description="Type of scam detected")
    confidence: float = Field(description="Confidence score 0-1", ge=0.0, le=1.0)
    reasoning: str = Field(description="Explanation of the decision")
    red_flags: list = Field(description="List of red flags detected")



#RuleBased Scam detection 
class RuleBasedScamDetectionTool(BaseTool):
    name: str = "rule_based_scam_detection"
    description: str = """
    Fast rule-based scam detection using patterns and keywords.
    Good for obvious scams with clear indicators.
    Use this first for quick initial screening.
    """
    args_schema: Type[BaseModel] = ScamDetectionInput
    
    def _run(self, message: str) -> dict:
        """Rule-based detection"""
        message_lower = message.lower().strip()

        # --- Anti-scam / warning message check (avoid false positives) ---
        # Messages that WARN about scams (e.g. "Do not share OTP") are not scams.
        warning_phrases = [
            r"do\s+not\s+share", r"don'?t\s+share", r"never\s+share",
            r"do\s+not\s+provide", r"don'?t\s+provide", r"never\s+give",
            r"do\s+not\s+click", r"don'?t\s+click", r"avoid\s+clicking",
            r"warning\s*:.*scam", r"signs\s+of\s+(?:a\s+)?(?:financial\s+)?scam",
            r"beware\s+of", r"alert\s*:.*scam", r"this\s+message\s+shows\s+signs",
            r"do\s+not\s+enter", r"don'?t\s+enter",
        ]
        if any(re.search(p, message_lower) for p in warning_phrases):
            return {
                "is_scam": False,
                "scam_type": "none",
                "confidence": 0.0,
                "method": "rule_based",
                "note": "warning_or_educational_message",
            }

        indicators = {
            'phishing': {
                'keywords': ['verify', 'suspended', 'locked', 'otp', 'suspicious activity'],
                'patterns': [
                    r'(?:share|send|provide).*otp',
                    r'suspicious.*activity',
                    r'secure.*account',
                    r'account.*(?:suspended|locked)',
                ],
                'credential_requests': [
                    r'(?:share|send|provide|enter).*(?:otp|password|pin|cvv)',
                ]
            },
            'lottery': {
                'keywords': ['won', 'winner', 'lottery', 'prize', 'congratulations'],
                'patterns': [r'won.*(?:Rs\.?|₹|\$)\s*[\d,]+', r'claim.*prize']
            },
            'investment': {
                'keywords': ['profit', 'returns', 'guaranteed', 'crypto'],
                'patterns': [r'\d+%.*(?:profit|returns)', r'guaranteed.*returns']
            },
            'job_offer': {
                'keywords': [
                    'work from home', 'wfh', 'part-time', 'part time', 'online job',
                    'daily earn', 'earn ₹', 'earn rs', 'registration', 'registration fee',
                    'activation fee', 'refundable', 'simple tasks', 'training material',
                    'hr team', 'telegram', 'whatsapp'
                ],
                'patterns': [
                    r'work\s+from\s+home',
                    r'part[\s-]?time',
                    r'(?:registration|activation)\s+fee',
                    r'(?:earn|income).*(?:daily|per\s+day)',
                    r'(?:refundable|refund)',
                ]
            },
            'tech_support': {
                'keywords': ['virus', 'infected', 'microsoft', 'tech support'],
                'patterns': [r'computer.*virus', r'call.*immediately']
            },
            'impersonation': {
                'keywords': ['police', 'government', 'arrest', 'warrant'],
                'patterns': [r'legal.*action', r'arrest.*warrant']
            }
        }

        scores = {}
        
        for scam_type, data in indicators.items():
            score = 0
            
            # Keywords
            keyword_matches = sum(1 for kw in data['keywords'] if kw in message_lower)
            score += keyword_matches
            
            # Patterns
            pattern_matches = sum(1 for p in data['patterns'] 
                                if re.search(p, message_lower, re.IGNORECASE))
            score += pattern_matches * 2
            
            # Credential requests (HIGH WEIGHT)
            if 'credential_requests' in data:
                cred_matches = sum(1 for p in data['credential_requests']
                                 if re.search(p, message_lower, re.IGNORECASE))
                score += cred_matches * 10  # Very high weight
            
            scores[scam_type] = score
        
        if not scores or max(scores.values()) == 0:
            return {
                'is_scam': False,
                'scam_type': 'none',
                'confidence': 0.0,
                'method': 'rule_based'
            }
        
        best_type = max(scores.items(), key=lambda x: x[1])
        is_scam = best_type[1] >= 2
        confidence = min(best_type[1] * 0.15, 0.85) if is_scam else 0.1
        
        return {
            'is_scam': is_scam,
            'scam_type': best_type[0] if is_scam else 'none',
            'confidence': round(confidence, 2),
            'method': 'rule_based',
            'scores': scores
        }

# LLM-BASED SEMANTIC ANALYSIS TOOL
class LLMSemanticAnalysisTool(BaseTool):
    name: str = "llm_semantic_analysis"
    description: str = """
    Deep semantic analysis using AI to understand context and intent.
    Best for subtle scams that require understanding meaning.
    Use this when rule-based detection is uncertain or for verification.
    """
    args_schema: Type[BaseModel] = LLMAnalysisInput
    
    
    
    def __init__(self):
        super().__init__()
        _client = httpx.Client()
        self.llm = ChatOpenAI(
            model=OPENAI_MODEL,
            temperature=0.2,
            openai_api_key=OPENAI_API_KEY,
            openai_api_base=OPENROUTER_BASE,
            http_client=_client,
        )
        self.output_parser = PydanticOutputParser(pydantic_object=LLMScamOutput)
    
    def _run(self, message: str) -> dict:
        """LLM-based semantic analysis"""
        
        prompt_template = """You are an expert scam detection AI with deep understanding of fraud tactics.

Analyze this message by understanding CONTEXT, INTENT, and MEANING - not just keywords.

INTENT (most important):
- If the message is WARNING or ADVISING the user (e.g. "Do not share OTP", "Warning: signs of scam", "Beware of") → is_scam = false.
- If the message is REQUESTING or ASKING the user to do something risky (share OTP, click link, pay, verify account) → is_scam = true.
- Same words can mean opposite things: "Share your OTP" = scam; "Do not share OTP" = not scam. Decide by intent.

CRITICAL SCAM INDICATORS:
1. **Credential Requests**: Asking for OTP, password, PIN, CVV = SCAM. Telling user NOT to share = NOT SCAM.
2. **Phishing Pretexts**: 
   - "Suspicious activity detected" + credential request = PHISHING
   - "Secure your account" + share OTP = PHISHING
   - Any legitimate company NEVER asks for OTP/password via message
3. **Context Matters**: 
   - "Share OTP" (requesting) = SCAM. "Do not share OTP" (warning) = NOT SCAM.
   - "We detected..." + action request = SCAM
   - Urgency + credential request = SCAM

SCAM TYPES:
- phishing: Impersonates legitimate service to steal credentials (OTP requests!)
- lottery: Prize/lottery scams
- investment: Fake investment schemes
- tech_support: Fake tech support
- romance: Romance scams
- job_offer: Fake job offers
- impersonation: Government/police impersonation
- none: Legitimate message

MESSAGE TO ANALYZE:
"{message}"

THINK STEP-BY-STEP:
1. What is being asked? (Especially: OTP, password, personal info?)
2. Who is claiming to ask? (Real companies don't ask for OTP via message)
3. What's the urgency/threat?
4. Would this request make sense from a legitimate source?

{format_instructions}

BE VERY STRICT: Any OTP/password request = SCAM (confidence > 0.9)
"""

        prompt = ChatPromptTemplate.from_template(prompt_template)
        formatted_prompt = prompt.format(
            message=message,
            format_instructions=self.output_parser.get_format_instructions()
        )
        
        try:
            response = self.llm.invoke(formatted_prompt)
            parsed = self.output_parser.parse(response.content)
            
            return {
                'is_scam': parsed.is_scam,
                'scam_type': parsed.scam_type,
                'confidence': round(parsed.confidence, 2),
                'reasoning': parsed.reasoning,
                'red_flags': parsed.red_flags,
                'method': 'llm_semantic'
            }
        
        except Exception as e:
            print(f"LLM analysis error: {e}")
            return {
                'is_scam': False,
                'scam_type': 'none',
                'confidence': 0.0,
                'reasoning': f'Analysis error: {str(e)}',
                'red_flags': [],
                'method': 'llm_semantic_error'
            }

# HYBRID DETECTION TOOL – 3-LAYER PIPELINE (handles all input types)
#
# Layer 1: Warning/safe phrases (in RuleBasedScamDetectionTool) → not scam, skip rest.
# Layer 2: Rule-based → clear scam (high conf) or clear not-scam (zero score).
# Layer 3: LLM for intent when ambiguous → same words, different intents (e.g. "do not share" vs "share").

class HybridScamDetectionTool(BaseTool):
    name: str = "hybrid_scam_detection"
    description: str = """
    Advanced hybrid detection combining rule-based and AI semantic analysis.
    """
    args_schema: Type[BaseModel] = HybridDetectionInput

    def _run(self, message: str, history: Optional[list] = None) -> dict:
        rule_tool = RuleBasedScamDetectionTool()
        rule_result = rule_tool._run(message)

        # If rule layer already decided "not scam" with a note (e.g. warning message), trust it
        if rule_result.get("note") == "warning_or_educational_message":
            return {
                "is_scam": False,
                "scam_type": "none",
                "confidence": 0.0,
                "method": "rule_based",
            }

        conf = rule_result.get("confidence", 0.0)
        rule_scam = rule_result.get("is_scam", False)
        msg_lower = message.lower()

        # Use LLM when intent is ambiguous (handles all input types better)
        risky_keywords = any(w in msg_lower for w in [
            # credentials
            "otp", "password", "pin", "cvv",
            # common phishing verbs
            "share", "verify", "click", "link", "login",
            # account scare tactics
            "account", "suspended", "blocked", "locked",
            # job/task scam signals
            "work from home", "wfh", "part-time", "part time", "online job",
            "registration", "activation", "fee", "refundable", "task", "simple task",
            "training material", "hr", "telegram", "whatsapp",
            # payment rails
            "upi", "transfer", "ifsc", "payment", "pay",
        ])
        warning_keywords = any(w in msg_lower for w in ["do not", "don't", "never share", "warning", "beware", "avoid", "signs of"])
        ambiguous = warning_keywords and risky_keywords  # could be warning or scam
        uncertain_rules = (rule_scam and conf < 0.85) or (not rule_scam and conf > 0.2) or ambiguous

        needs_llm = risky_keywords or uncertain_rules

        if needs_llm:
            try:
                llm_tool = LLMSemanticAnalysisTool()
                llm_result = llm_tool._run(message)
                # Only use LLM result if it didn't fail (method not llm_semantic_error)
                if llm_result.get("method") != "llm_semantic_error":
                    combined_confidence = (
                        llm_result["confidence"] * 0.7 +
                        rule_result["confidence"] * 0.3
                    )
                    return {
                        "is_scam": llm_result["is_scam"] or rule_result["is_scam"],
                        "scam_type": llm_result["scam_type"] or rule_result["scam_type"],
                        "confidence": round(combined_confidence, 2),
                        "method": "hybrid",
                    }
            except Exception:
                # LLM failed: use rule result so we never hide a clear scam
                pass

        return {
            "is_scam": rule_result["is_scam"],
            "scam_type": rule_result["scam_type"],
            "confidence": rule_result["confidence"],
            "method": "rule_based_only",
        }

# URGENCY DETECTION TOOL
class UrgencyDetectionTool(BaseTool):
    name: str = "detect_urgency"
    description: str = """
    Detects urgency indicators in messages.
    Urgency is a common scam tactic.
    """
    args_schema: Type[BaseModel] = ScamDetectionInput
    
    def _run(self, message: str) -> dict:
        """Detect urgency"""
        
        urgency_keywords = [
            'urgent', 'immediately', 'now', 'today', 'hurry',
            'limited time', 'expires', 'last chance', 'act now',
            'within 24 hours', 'deadline', 'before'
        ]
        
        message_lower = message.lower()
        found = [kw for kw in urgency_keywords if kw in message_lower]
        score = len(found)
        
        level = 'none'
        if score >= 3:
            level = 'high'
        elif score >= 1:
            level = 'medium'
        
        return {
            'urgency_level': level,
            'urgency_score': score,
            'keywords_found': found
        }


# Main tool used by API: hybrid (rules + LLM)
ScamDetectionTool = HybridScamDetectionTool
