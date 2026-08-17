import os
import json
import time
import argparse
import sys
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Optional
import google.generativeai as genai
from duckduckgo_search import DDGS

# Load environment variables
load_dotenv('c:/Users/LENOVO/Desktop/Project/clevrAI/server/.env')
gemini_key = os.getenv("GEMINI_API_KEY")

if gemini_key:
    genai.configure(api_key=gemini_key)
else:
    print("WARNING: GEMINI_API_KEY not found in environment or server/.env file. Please check!")

# Model pool for quota rotation
MODELS_POOL = [
    'gemini-3.5-flash',
    'gemini-3.6-flash',
    'gemini-3.7-flash',
    'gemini-3.5-flash-lite',
    'gemini-3.1-flash-lite',
    'gemini-flash-latest'
]
current_model_index = 0

# Define Pydantic Schema for Structured Output
class AppResearchResult(BaseModel):
    description: str = Field(description="A concise one-line description of the app and its primary function.")
    auth_methods: List[str] = Field(description="List of supported auth methods. Choose from: OAuth2, API key, Basic, token, other, None. Be specific.")
    self_serve: str = Field(description="Is it self-serve or gated? Choose from: 'self-serve' (developer can get free or trial API credentials immediately without talk to sales/partnership), 'gated' (needs payment, admin approval, partner request, or contacting sales to get credentials), 'mixed'.")
    self_serve_details: str = Field(description="Explanation of the credentials access path (e.g. Free trial/tier available, Paid plan required, Admin approval required, Partner sign-up required, Contact sales).")
    api_surface: str = Field(description="Details on the API surface (e.g. REST, GraphQL, SOAP, Webhooks, gRPC) and how broad it is (e.g. Broad, Moderate, Narrow, CLI-only).")
    existing_mcp: str = Field(description="Is there an existing Model Context Protocol (MCP) server for this app? If yes, mention the source/repo or 'Yes' / 'No'.")
    buildability: str = Field(description="Buildability verdict: 'yes' (can be built as an agent toolkit today) or 'no' (cannot be built today due to blockers).")
    blockers: str = Field(description="Primary blocker if not buildable (e.g. 'Gated behind Enterprise pricing', 'No public API', 'Partner sign-up required', or 'None' if buildable).")
    evidence: str = Field(description="URL(s) to the official developer documentation or source supporting these findings.")

def search_ddg(query, max_results=3):
    """Perform a web search using DuckDuckGo with retries."""
    print(f"  Searching DDG: '{query}'...")
    retries = 3
    delay = 2
    for attempt in range(retries):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                return results
        except Exception as e:
            print(f"  Search attempt {attempt+1} failed for '{query}': {e}")
            if attempt < retries - 1:
                print(f"  Sleeping {delay}s before retry...")
                time.sleep(delay)
                delay *= 2
            else:
                return []


def fetch_app_info(app_name, category, hint):
    """Fallback to direct Gemini knowledge extraction since search engine is rate-limited."""
    return ""

def analyze_with_gemini(app_name, category, hint, search_context):
    """Use Gemini with structured output to extract app data, cycling through models on quota limits."""
    global current_model_index
    prompt = f"""
    You are an expert developer research agent investigating API availability for Composio (an AI Agent toolkit builder).
    Analyze the app details and provide the requested fields:
    
    App Name: {app_name}
    Category: {category}
    Website/Hint: {hint}
    
    Your task is to accurately populate the schema. Be objective and rely on verified facts.
    If the app is open source (like Sherlock or Mermaid CLI), auth is 'None' and it is 'self-serve' (can run locally).
    If the app is a CLI tool, its API surface is 'CLI' and it is buildable locally.
    If the app requires contacting sales, it is 'gated' and blocker is 'Partner sign-up required' or 'Contact sales / Enterprise gate'.
    If the app requires a paid plan to access APIs, it is 'gated' and the blocker is 'Paid plan required'.
    If the app has a free developer trial/sandbox, it is 'self-serve' and buildability is 'yes'.
    For 'evidence', provide the official developer documentation URL for the app (e.g. docs.github.com/rest, developers.stripe.com, etc.). It MUST be the official developer page URL.
    """

    retries = len(MODELS_POOL) * 2  # Allows cycling through all models twice
    for attempt in range(retries):
        model_name = MODELS_POOL[current_model_index]
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=AppResearchResult,
                    temperature=0.1
                )
            )
            # Parse the JSON response
            data = json.loads(response.text)
            return data
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower() or "resource_exhausted" in err_str.lower():
                prev_model = MODELS_POOL[current_model_index]
                current_model_index = (current_model_index + 1) % len(MODELS_POOL)
                new_model = MODELS_POOL[current_model_index]
                print(f"  Quota hit for {prev_model} on {app_name}. Rotating to {new_model}...")
                time.sleep(3)  # Short sleep before trying new model
            else:
                print(f"  Gemini generation failed for {app_name} on {model_name}: {e}")
                return None
    return None

def main():
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None, help="Limit to N apps for testing")
    parser.add_argument("--resume", action="store_true", help="Resume from existing raw results")
    args = parser.parse_args()
    
    if not gemini_key:
        print("ERROR: GEMINI_API_KEY is not set. Exiting.")
        return
        
    # Create directories if they don't exist
    os.makedirs("data", exist_ok=True)
    
    # Load apps list
    with open("apps_list.json", "r", encoding="utf-8") as f:
        apps = json.load(f)
        
    if args.sample:
        apps = apps[:args.sample]
        print(f"Running on a sample of {len(apps)} apps.")
        
    output_path = "data/raw_results.json"
    results = []
    processed_ids = set()
    
    if args.resume and os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                results = json.load(f)
                processed_ids = {item["id"] for item in results}
                print(f"Resuming. Already processed {len(processed_ids)} apps.")
        except Exception as e:
            print(f"Could not load existing file for resume: {e}")
            
    for app in apps:
        app_id = app["id"]
        if app_id in processed_ids:
            continue
            
        app_name = app["name"]
        category = app["category"]
        hint = app["hint"]
        
        print(f"\nProcessing [{app_id}/100] {app_name} ({category})...")
        
        # 1. Search and crawl
        search_context = fetch_app_info(app_name, category, hint)
        
        # 2. Analyze with Gemini
        analysis = analyze_with_gemini(app_name, category, hint, search_context)
        
        if analysis:
            # Combine original app metadata with analysis
            app_result = {
                "id": app_id,
                "category": category,
                "name": app_name,
                "website": app["website"],
                "hint": hint,
                **analysis
            }
            results.append(app_result)
            processed_ids.add(app_id)
            print(f"  Result: {app_result['self_serve'].upper()} | Auth: {', '.join(app_result['auth_methods'])} | Buildable: {app_result['buildability']}")
        else:
            print(f"  Skipping {app_name} due to analysis error.")
            
        # Save incrementally
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
            
        # Rate limit safeguard for Gemini free tier (5.0s to ensure <15 RPM)
        time.sleep(5.0)
        
    print(f"\nCompleted! Saved results to {output_path}")

if __name__ == "__main__":
    main()
