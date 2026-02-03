from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import Optional, Type
from pydantic import PrivateAttr
import re
import os

from dotenv import load_dotenv
load_dotenv()


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
            'tech_support': {
                'keywords': ['virus', 'infected', 'microsoft', 'tech support'],
                'patterns': [r'computer.*virus', r'call.*immediately']
            },
            'impersonation': {
                'keywords': ['police', 'government', 'arrest', 'warrant'],
                'patterns': [r'legal.*action', r'arrest.*warrant']
            }
        }
        
        message_lower = message.lower()
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
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.2
        )
        self.output_parser = PydanticOutputParser(pydantic_object=LLMScamOutput)
    
    def _run(self, message: str) -> dict:
        """LLM-based semantic analysis"""
        
        prompt_template = """You are an expert scam detection AI with deep understanding of fraud tactics.

Analyze this message by understanding CONTEXT, INTENT, and MEANING - not just keywords.

CRITICAL SCAM INDICATORS:
1. **Credential Requests**: Asking for OTP, password, PIN, CVV is ALWAYS a scam
2. **Phishing Pretexts**: 
   - "Suspicious activity detected" + credential request = PHISHING
   - "Secure your account" + share OTP = PHISHING
   - Any legitimate company NEVER asks for OTP/password via message
3. **Context Matters**: 
   - "Share OTP" in any context = SCAM
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

# HYBRID DETECTION TOOL cOMBINES BOTH

from pydantic import PrivateAttr

class HybridScamDetectionTool(BaseTool):
    name: str = "hybrid_scam_detection"
    description: str = """
    Advanced hybrid detection combining rule-based and AI semantic analysis.
    """
    args_schema: Type[BaseModel] = HybridDetectionInput

    _rule_tool: RuleBasedScamDetectionTool = PrivateAttr(default=None)
    _llm_tool: LLMSemanticAnalysisTool = PrivateAttr(default=None)

    def _run(self, message: str) -> dict:
        # ✅ Lazy initialization (Pydantic-safe)
        if self._rule_tool is None:
            self._rule_tool = RuleBasedScamDetectionTool()
        if self._llm_tool is None:
            self._llm_tool = LLMSemanticAnalysisTool()

        rule_result = self._rule_tool._run(message)

        needs_llm = (
            (rule_result["is_scam"] and rule_result["confidence"] < 0.7) or
            (not rule_result["is_scam"] and rule_result["confidence"] > 0.3) or
            any(word in message.lower() for word in ["otp", "password", "pin", "cvv", "share"])
        )

        if needs_llm:
            llm_result = self._llm_tool._run(message)

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
        
        ScamDetectionTool = HybridScamDetectionTool
