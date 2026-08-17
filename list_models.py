import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv('c:/Users/LENOVO/Desktop/Project/clevrAI/server/.env')
gemini_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=gemini_key)

print("Listing models:")
try:
    for m in genai.list_models():
        print(f"Name: {m.name} | Methods: {m.supported_generation_methods}")
except Exception as e:
    print(f"Error listing models: {e}")
