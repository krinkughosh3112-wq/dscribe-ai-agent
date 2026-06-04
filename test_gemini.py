# test_gemini.py (Updated for new google.genai package)
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()

# Initialize client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Test the API with correct model name
response = client.models.generate_content(
    model="gemini-2.5-flash",  # Correct model name
    contents="Say 'API is working! Gemini is ready.'"
)

print(response.text)