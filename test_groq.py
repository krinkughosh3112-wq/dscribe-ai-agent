# test_groq.py
from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": "Say 'API is working!'"}],
    temperature=0.3,
    max_tokens=50
)

print(response.choices[0].message.content)