import os
import json
import time
import argparse
import sys
from dotenv import load_dotenv
import google.generativeai as genai
from duckduckgo_search import DDGS
from pydantic import BaseModel, Field
from typing import List, Optional

# Load env
load_dotenv('c:/Users/LENOVO/Desktop/Project/clevrAI/server/.env')
gemini_key = os.getenv("GEMINI_API_KEY")
if gemini_key:
    genai.configure(api_key=gemini_key)

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

class VerificationVerdict(BaseModel):
    is_correct: bool = Field(description="True if the first-pass research details are correct, False if they need adjustment.")
    corrected_auth_methods: Optional[List[str]] = Field(description="Corrected list of auth methods (OAuth2, API key, Basic, token, None, other) if first pass was wrong.")
    corrected_self_serve: Optional[str] = Field(description="Corrected self-serve status ('self-serve', 'gated', 'mixed') if first-pass was wrong.")
    corrected_self_serve_details: Optional[str] = Field(description="Corrected explanation of credentials access path if wrong.")
    corrected_api_surface: Optional[str] = Field(description="Corrected API surface description if wrong.")
    corrected_buildability: Optional[str] = Field(description="Corrected buildability verdict ('yes' or 'no') if wrong.")
    corrected_blockers: Optional[str] = Field(description="Corrected primary blocker if wrong.")
    corrected_evidence: Optional[str] = Field(description="Corrected documentation URL if wrong.")
    reason: str = Field(description="Reason for correction or confirmation of correctness.")

def search_ddg(query, max_results=3):
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        print(f"  Verification search failed: {e}")
        return []

def verify_app(app_data):
    """Deep verify an app's details using Gemini model rotation to avoid rate limits."""
    global current_model_index
    app_name = app_data["name"]
    print(f"Deep verifying {app_name}...")
    
    prompt = f"""
    You are a strict QA auditor reviewing developer research data for Composio.
    Review the research findings for the following app and determine if they are correct or if they require updates.
    
    App Name: {app_name}
    Category: {app_data['category']}
    
    First-Pass Findings to Audit:
    - Description: {app_data.get('description')}
    - Auth Methods: {', '.join(app_data.get('auth_methods', []))}
    - Self-Serve: {app_data.get('self_serve')}
    - Self-Serve Details: {app_data.get('self_serve_details')}
    - API Surface: {app_data.get('api_surface')}
    - Existing MCP: {app_data.get('existing_mcp')}
    - Buildability: {app_data.get('buildability')}
    - Blockers: {app_data.get('blockers')}
    - Evidence URL: {app_data.get('evidence')}
    
    Compare the First-Pass Findings with your verified developer documentation knowledge.
    Specifically check:
    1. Is the app actually self-serve? (Can a free developer account or trial generate credentials?)
    2. Is the documentation URL valid and pointing to the developer page?
    3. Are the auth methods accurate?
    4. Is it buildable today or is it blocked by partnership gates, lack of API, or enterprise pricing?
    
    Output a structured JSON response. If findings are fully correct, set is_correct to True. If anything is wrong or can be improved, set is_correct to False and supply the corrected fields.
    """
    
    retries = len(MODELS_POOL) * 2
    for attempt in range(retries):
        model_name = MODELS_POOL[current_model_index]
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=VerificationVerdict,
                    temperature=0.1
                )
            )
            verdict = json.loads(response.text)
            return verdict
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower() or "resource_exhausted" in err_str.lower():
                prev_model = MODELS_POOL[current_model_index]
                current_model_index = (current_model_index + 1) % len(MODELS_POOL)
                new_model = MODELS_POOL[current_model_index]
                print(f"  Quota hit for {prev_model} on {app_name}. Rotating to {new_model}...")
                time.sleep(3)
            else:
                print(f"  Verification failed for {app_name} on {model_name}: {e}")
                return None
    return None

def main():
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="data/raw_results.json", help="Path to raw results")
    parser.add_argument("--output", default="data/verified_results.json", help="Path to write verified results")
    args = parser.parse_args()
    
    if not os.path.exists(args.raw):
        print(f"Raw results file {args.raw} not found. Run research_agent.py first.")
        return
        
    with open(args.raw, "r", encoding="utf-8") as f:
        raw_results = json.load(f)
        
    # The 15 verification sample app IDs
    sample_names = [
        "Salesforce", "Attio", "Freshdesk", "Lark (Larksuite)", "GoHighLevel",
        "fanbasis", "Sherlock", "GitHub", "Snowflake", "Monday.com",
        "Brex", "PitchBook", "NotebookLM", "Devin", "Otter AI"
    ]
    
    verified_results = []
    verification_logs = []
    
    # We will verify all. If name is in sample_names, we run the deep verifier agent.
    # Otherwise, we apply basic rules.
    for app in raw_results:
        app_name = app["name"]
        
        # Rule-based cleanups for everyone
        if app.get("buildability") == "yes" and app.get("blockers") != "None":
            app["blockers"] = "None"
        if app.get("buildability") == "no" and app.get("blockers") == "None":
            app["blockers"] = "No public API or gated credentials"
            
        # Check if this app is in the sample list
        if any(name.lower() in app_name.lower() for name in sample_names):
            verdict = verify_app(app)
            if verdict:
                is_correct = verdict["is_correct"]
                log = {
                    "id": app["id"],
                    "name": app_name,
                    "first_pass": {
                        "auth": app["auth_methods"],
                        "self_serve": app["self_serve"],
                        "buildability": app["buildability"],
                        "evidence": app["evidence"]
                    },
                    "is_correct": is_correct,
                    "reason": verdict["reason"]
                }
                
                if not is_correct:
                    print(f"  -> Discrepancy found! Correcting...")
                    # Apply corrections
                    if verdict.get("corrected_auth_methods"):
                        app["auth_methods"] = verdict["corrected_auth_methods"]
                    if verdict.get("corrected_self_serve"):
                        app["self_serve"] = verdict["corrected_self_serve"]
                    if verdict.get("corrected_self_serve_details"):
                        app["self_serve_details"] = verdict["corrected_self_serve_details"]
                    if verdict.get("corrected_api_surface"):
                        app["api_surface"] = verdict["corrected_api_surface"]
                    if verdict.get("corrected_buildability"):
                        app["buildability"] = verdict["corrected_buildability"]
                    if verdict.get("corrected_blockers"):
                        app["blockers"] = verdict["corrected_blockers"]
                    if verdict.get("corrected_evidence"):
                        app["evidence"] = verdict["corrected_evidence"]
                        
                    log["second_pass"] = {
                        "auth": app["auth_methods"],
                        "self_serve": app["self_serve"],
                        "buildability": app["buildability"],
                        "evidence": app["evidence"]
                    }
                else:
                    print(f"  -> Verified correct.")
                    
                verification_logs.append(log)
            else:
                print(f"  -> Skipping deep verification due to error.")
        
        verified_results.append(app)
        
    # Save final verified results
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(verified_results, f, indent=2, ensure_ascii=False)
        
    # Save verification logs
    with open("data/verification_logs.json", "w", encoding="utf-8") as f:
        json.dump(verification_logs, f, indent=2, ensure_ascii=False)
        
    print(f"\nVerification finished! Saved verified data to {args.output}")
    print(f"Verification logs saved to data/verification_logs.json")

if __name__ == "__main__":
    main()
