import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv('c:/Users/LENOVO/Desktop/Project/clevrAI/server/.env')
gemini_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=gemini_key)

models_to_test = [
    'gemini-3.6-flash',
    'gemini-3.7-flash',
    'gemini-3.5-flash-lite',
    'gemini-flash-latest',
    'gemini-pro-latest',
    'gemini-3.1-flash-lite'
]

print("Testing alternative models:")
for m in models_to_test:
    try:
        model = genai.GenerativeModel(m)
        response = model.generate_content("Hello! What model name are you?")
        print(f"Model: {m} | Success! Response: {response.text.strip()}")
    except Exception as e:
        print(f"Model: {m} | Failed: {e}")
