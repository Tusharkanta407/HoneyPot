# Scam types, persona maps
import os
from dotenv import load_dotenv
load_dotenv(override=True)

# OpenRouter (or direct OpenAI if base is not set)
OPENROUTER_BASE = os.getenv("OPENAI_API_BASE", "https://openrouter.ai/api/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")
