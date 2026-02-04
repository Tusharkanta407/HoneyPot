"""
Quick test to check if OpenRouter API key works (one small call).
Run: python test_api_key.py
Uses same .env as the app: OPENAI_API_KEY (OpenRouter key), OPENAI_API_BASE, OPENAI_MODEL.
"""
import os
from dotenv import load_dotenv

load_dotenv(override=True)

api_key = os.getenv("OPENAI_API_KEY", "")
base_url = os.getenv("OPENAI_API_BASE", "https://openrouter.ai/api/v1")
model = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")

if not api_key:
    print("❌ ERROR: OPENAI_API_KEY not found in .env")
    exit(1)

print(f"✅ API Key found: {api_key[:10]}...{api_key[-6:]}")
print(f"   Base URL: {base_url}")
print(f"   Model: {model}")
print("Testing OpenRouter API call...\n")

try:
    from openai import OpenAI

    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": "Say 'OK' if you can read this."}
        ],
        max_tokens=10,
    )

    reply = completion.choices[0].message.content
    print("✅ SUCCESS! OpenRouter API is working.")
    print(f"   Response: {reply}")
    print(f"   Model: {completion.model}")
    if completion.usage:
        print(f"   Tokens used: {completion.usage.total_tokens}")

except Exception as e:
    error_str = str(e)

    if "429" in error_str or "quota" in error_str.lower() or "insufficient_quota" in error_str.lower():
        print("❌ QUOTA EXCEEDED")
        print(f"   Error: {error_str}")
        print("\n   → Check OpenRouter credits or billing.")
    elif "401" in error_str or "invalid" in error_str.lower() or "authentication" in error_str.lower():
        print("❌ INVALID API KEY")
        print(f"   Error: {error_str}")
        print("\n   → Check .env: OPENAI_API_KEY should be your OpenRouter key (sk-or-v1-...).")
    else:
        print(f"❌ ERROR: {error_str}")
        print(f"   Type: {type(e).__name__}")
