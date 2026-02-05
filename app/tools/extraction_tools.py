# Sradha - Regex / entity extractors
from langchain_core.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field
import re

class InformationExtractionInput(BaseModel):
    """Input for information extraction"""
    text: str = Field(description="Text to extract information from")

class PhoneExtractionTool(BaseTool):
    name: str = "extract_phone_numbers"
    description: str = """
    Extracts phone numbers from text.
    Use this to collect scammer contact information.
    """
    args_schema: Type[BaseModel] = InformationExtractionInput
    
    def _run(self, text: str) -> dict:
        """Extract phone numbers"""
        patterns = [
            r'\+91[6-9]\d{9}',           # +91 format
            r'0[6-9]\d{9}',              # 0 prefix
            r'[6-9]\d{9}',               # 10 digits
            r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}'  # Formatted
        ]
        
        phones = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            phones.extend(matches)
        
        # Remove duplicates
        phones = list(set(phones))
        
        return {
            'phone_numbers': phones,
            'count': len(phones)
        }

class BankDetailsExtractionTool(BaseTool):
    name: str = "extract_bank_details"
    description: str = """
    Extracts bank account numbers, IFSC codes, and related banking information.
    Critical for identifying scammer payment methods.
    """
    args_schema: Type[BaseModel] = InformationExtractionInput
    
    def _run(self, text: str) -> dict:
        """Extract bank details"""
        
        # Account numbers (typically 11-18 digits).
        # Avoid misclassifying phone numbers like +91XXXXXXXXXX as bank accounts.
        account_pattern = r'\b\d{11,18}\b'
        raw_accounts = re.findall(account_pattern, text)
        accounts = []
        for a in raw_accounts:
            # Exclude obvious Indian phone formats:
            # - 0XXXXXXXXXX (11 digits)
            # - 91XXXXXXXXXX (12 digits) when X starts 6-9
            if len(a) == 11 and a.startswith("0") and a[1] in "6789":
                continue
            if len(a) == 12 and a.startswith("91") and a[2] in "6789":
                continue
            accounts.append(a)
        
        # IFSC codes
        ifsc_pattern = r'\b[A-Z]{4}0[A-Z0-9]{6}\b'
        ifsc_codes = re.findall(ifsc_pattern, text)
        
        # Bank names
        bank_names = []
        common_banks = ['sbi', 'hdfc', 'icici', 'axis', 'pnb', 'bob', 'canara']
        text_lower = text.lower()
        for bank in common_banks:
            if bank in text_lower:
                bank_names.append(bank.upper())
        
        return {
            'account_numbers': list(set(accounts)),
            'ifsc_codes': list(set(ifsc_codes)),
            'bank_names': bank_names,
            'total_found': len(accounts) + len(ifsc_codes)
        }

class URLExtractionTool(BaseTool):
    name: str = "extract_urls"
    description: str = """
    Extracts URLs and websites from text.
    Helps identify phishing links and fake websites.
    """
    args_schema: Type[BaseModel] = InformationExtractionInput
    
    def _run(self, text: str) -> dict:
        """Extract URLs"""
        
        # URL patterns
        url_pattern = r'https?://[^\s]+'
        short_url_pattern = r'\b(?:bit\.ly|tinyurl\.com|goo\.gl)/\S+'
        domain_pattern = r'\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b'
        
        urls = re.findall(url_pattern, text)
        short_urls = re.findall(short_url_pattern, text)
        domains = re.findall(domain_pattern, text.lower())
        
        # Suspicious TLDs
        suspicious_tlds = ['.tk', '.ml', '.ga', '.cf', '.gq']
        suspicious = [url for url in urls if any(tld in url for tld in suspicious_tlds)]
        
        return {
            'urls': list(set(urls)),
            'short_urls': list(set(short_urls)),
            'domains': list(set(domains)),
            'suspicious_urls': suspicious,
            'count': len(urls)
        }

class UPIExtractionTool(BaseTool):
    name: str = "extract_upi_ids"
    description: str = """
    Extracts UPI IDs from text.
    UPI format: username@provider (e.g., scammer@paytm)
    """
    args_schema: Type[BaseModel] = InformationExtractionInput
    
    def _run(self, text: str) -> dict:
        """Extract UPI IDs"""
        
        # UPI pattern
        upi_pattern = r'[\w.-]+@(?:paytm|phonepe|googlepay|ybl|axl|okhdfcbank|okicici|okaxis|oksbi)'
        
        upi_ids = re.findall(upi_pattern, text.lower())
        
        return {
            'upi_ids': list(set(upi_ids)),
            'count': len(set(upi_ids))
        }

class ComprehensiveExtractionTool(BaseTool):
    name: str = "extract_all_intelligence"
    description: str = """
    Extracts all types of intelligence from text in one go.
    Use this for comprehensive analysis of scammer messages.
    Returns: phones, bank details, URLs, UPI IDs, emails, organizations.
    """
    args_schema: Type[BaseModel] = InformationExtractionInput
    
    def _run(self, text: str) -> dict:
        """Extract all information types"""
        
        # Use individual tools (instantiate inside _run because BaseTool is a Pydantic model)
        phones = PhoneExtractionTool()._run(text)
        banks = BankDetailsExtractionTool()._run(text)
        urls = URLExtractionTool()._run(text)
        upis = UPIExtractionTool()._run(text)
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, text)
        
        # Extract organization names (simple approach)
        org_pattern = r'([A-Z][a-z]+ (?:Bank|Ltd|Limited|Inc|Corporation|Foundation|Trust))'
        organizations = re.findall(org_pattern, text)
        
        return {
            'phone_numbers': phones['phone_numbers'],
            'account_numbers': banks['account_numbers'],
            'ifsc_codes': banks['ifsc_codes'],
            'bank_names': banks['bank_names'],
            'urls': urls['urls'],
            'suspicious_urls': urls['suspicious_urls'],
            'upi_ids': upis['upi_ids'],
            'emails': list(set(emails)),
            'organizations': list(set(organizations)),
            'total_items_found': (
                len(phones['phone_numbers']) +
                len(banks['account_numbers']) +
                len(urls['urls']) +
                len(upis['upi_ids']) +
                len(emails)
            )
        }