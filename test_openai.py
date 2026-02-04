from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()  # loads .env
key = os.getenv("OPENAI_API_KEY")
print("Key present:", bool(key), "prefix:", key[:10] if key else None)

client = OpenAI(api_key=key)
models = client.models.list()
print("First 3 models:", [m.id for m in models.data[:3]])