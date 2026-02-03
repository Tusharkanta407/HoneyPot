from langchain.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field
import re

# INPUT SCHEMAS
class ScamDetectionInput(BaseModel):
    """Input for scam detection tool"""
    message: str = Field(description="The message to analyze for scam indicators")

class ScamTypeInput(BaseModel):
    """Input for scam type identification"""
    message: str = Field(description="Message to identify scam type")

class UrgencyDetectionInput(BaseModel):
    """Input for urgency detection"""
    message: str = Field(description="Message to check for urgency")

# SCAM DETECTION TOOL
class ScamDetectionTool(BaseTool):
    name: str = "detect_scam"
    description: str = """
    Analyzes a message to detect if it's a scam.
    Returns scam type, confidence score, and matched indicators.
    Use this tool first when you receive any message.
    """
    args_schema: Type[BaseModel] = ScamDetectionInput
    
    def _run(self, message: str) -> dict:
        """Detect scam in message"""
        
        # Scam indicators
        indicators = {
            'lottery': {
                'keywords': ['won', 'winner', 'lottery', 'prize', 'congratulations', 'selected'],
                'patterns': [r'won.*(?:Rs\.?|₹|\$)\s*[\d,]+', r'claim.*prize']
            },
            'phishing': {
                'keywords': ['verify', 'suspended', 'locked', 'blocked', 'confirm', 'update'],
                'patterns': [r'account.*(?:suspended|locked)', r'verify.*(?:account|details)']
            },
            'investment': {
                'keywords': ['profit', 'returns', 'investment', 'guaranteed', 'earn'],
                'patterns': [r'\d+%.*(?:profit|returns)', r'guaranteed.*returns']
            },
            'tech_support': {
                'keywords': ['virus', 'infected', 'malware', 'hacked', 'microsoft', 'tech support'],
                'patterns': [r'computer.*(?:virus|infected)', r'call.*(?:immediately|urgent)']
            },
            'impersonation': {
                'keywords': ['police', 'officer', 'government', 'arrest', 'warrant', 'fine'],
                'patterns': [r'legal.*action', r'arrest.*warrant', r'pay.*fine']
            },
            'romance': {
                'keywords': ['love', 'darling', 'emergency', 'stuck', 'hospital', 'help me'],
                'patterns': [r'(?:love|miss) you', r'emergency.*money']
            },
            'job_offer': {
                'keywords': ['job offer', 'work from home', 'registration fee', 'earn'],
                'patterns': [r'work.*from.*home', r'(?:registration|training).*fee']
            }
        }
        
        message_lower = message.lower()
        scores = {}
        
        # Calculate scores for each type
        for scam_type, data in indicators.items():
            score = 0
            matched_keywords = []
            matched_patterns = []
            
            # Check keywords
            for keyword in data['keywords']:
                if keyword in message_lower:
                    score += 1
                    matched_keywords.append(keyword)
            
            # Check patterns (higher weight)
            for pattern in data['patterns']:
                if re.search(pattern, message_lower):
                    score += 2
                    matched_patterns.append(pattern)
            
            scores[scam_type] = {
                'score': score,
                'keywords': matched_keywords,
                'patterns_matched': len(matched_patterns)
            }
        
        # Find best match
        best_type = max(scores.items(), key=lambda x: x[1]['score'])
        
        is_scam = best_type[1]['score'] >= 2
        confidence = min(best_type[1]['score'] * 0.2, 0.95) if is_scam else 0.1
        
        return {
            'is_scam': is_scam,
            'scam_type': best_type[0] if is_scam else 'none',
            'confidence': round(confidence, 2),
            'matched_keywords': best_type[1]['keywords'],
            'all_scores': {k: v['score'] for k, v in scores.items()}
        }
# SCAM TYPE IDENTIFICATION TOOL


class ScamTypeIdentificationTool(BaseTool):
    name: str = "identify_scam_type"
    description: str = """
    Identifies the specific type of scam (lottery, phishing, investment, etc.).
    Use this after detecting a message is a scam.
    """
    args_schema: Type[BaseModel] = ScamTypeInput
    
    def _run(self, message: str) -> dict:
        """Identify specific scam type"""
         
        message_lower = message.lower()
        
        # Detailed type identification
        type_signals = {
            'lottery': ['lottery', 'prize', 'won', 'winner', 'draw'],
            'phishing': ['bank', 'account', 'suspended', 'verify', 'otp'],
            'investment': ['profit', 'returns', 'invest', 'trading', 'crypto'],
            'tech_support': ['virus', 'computer', 'microsoft', 'infected'],
            'romance': ['love', 'darling', 'emergency', 'hospital'],
            'job_offer': ['job', 'vacancy', 'work from home', 'registration fee'],
            'impersonation': ['police', 'government', 'officer', 'arrest']
        }
        
        type_scores = {}
        for scam_type, signals in type_signals.items():
            count = sum(1 for signal in signals if signal in message_lower)
            type_scores[scam_type] = count
        
        best_type = max(type_scores.items(), key=lambda x: x[1])
        
        return {
            'scam_type': best_type[0],
            'confidence': min(best_type[1] * 0.25, 0.9),
            'signals_found': best_type[1]
        }



# URGENCY DETECTION TOOL
class UrgencyDetectionTool(BaseTool):
    name: str = "detect_urgency"
    description: str = """
    Detects urgency indicators in scam messages.
    Urgency is a common scam tactic to pressure victims.
    """
    args_schema: Type[BaseModel] = UrgencyDetectionInput
    
    def _run(self, message: str) -> dict:
        """Detect urgency in message"""
        
        urgency_keywords = [
            'urgent', 'immediately', 'now', 'today', 'hurry',
            'limited time', 'expires', 'last chance', 'act now',
            'within 24 hours', 'deadline', 'before'
        ]
        
        message_lower = message.lower()
        found_keywords = [kw for kw in urgency_keywords if kw in message_lower]
        urgency_score = len(found_keywords)
        
        urgency_level = 'none'
        if urgency_score >= 3:
            urgency_level = 'high'
        elif urgency_score >= 1:
            urgency_level = 'medium'
        
        return {
            'urgency_level': urgency_level,
            'urgency_score': urgency_score,
            'keywords_found': found_keywords
        }
