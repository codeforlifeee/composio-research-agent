import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv('c:/Users/LENOVO/Desktop/Project/clevrAI/server/.env')
gemini_key = os.getenv("GEMINI_API_KEY")

print("Testing Gemini Google Search grounding with google-genai SDK...")
try:
    client = genai.Client(api_key=gemini_key)
    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents="What is the current authentication method and developer API URL for Pylon (usepylon.com)?",
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
    )
    
    print("\nResponse:")
    print(response.text)
    
    # Check if grounding metadata exists
    if response.candidates and response.candidates[0].grounding_metadata:
        print("\nGrounding Metadata (Sources):")
        metadata = response.candidates[0].grounding_metadata
        if metadata.grounding_chunks:
            for chunk in metadata.grounding_chunks:
                if chunk.web:
                    print(f"- {chunk.web.title}: {chunk.web.uri}")
except Exception as e:
    print(f"Failed: {e}")
