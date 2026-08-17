# Composio API Research Agent & Verification Pipeline

This directory contains the automated agent pipeline built to research, audit, and analyze the feasibility of turning 100 applications into agent-callable toolkits for Composio.

## Project Structure

- `apps_list.json`: The source file containing the 100 target apps, structured by category with website links and hints.
- `requirements.txt`: Python package dependencies (including `google-genai` and `google-generativeai`).
- `research_agent.py`: The core script that queries the Gemini API using `gemini-3.5-flash` with structured Pydantic schemas. It gathers app descriptions, auth methods, self-serve paths, API formats, and buildability blockers, saving results incrementally to `data/raw_results.json`.
- `verify_agent.py`: The validation script that audits findings. It performs a deep search-based verification loop on a 15-app representative sample, logging discrepancies and applying corrections to output `data/verified_results.json`.
- `generate_report.py`: Compiles the final data and verification metrics into a single interactive, responsive HTML report (`index.html`) using raw data injection and client-side sorting, searching, and chart rendering.
- `index.html`: The final deliverable—a self-explanatory, premium interactive case study that displays the insights, process, and raw data matrix.
- `list_models.py` & `test_search.py` & `test_gemini_search.py`: Diagnostic utilities used to verify API key capabilities, models, and network accessibility.

## How to Set Up and Run

### 1. Prerequisite Environment
Make sure you have Python 3.10+ installed and a valid Gemini API Key.
Create a `.env` file in the root of the project (or ensure it is present in the main project's backend `.env` as referenced by the scripts):
```env
GEMINI_API_KEY="your-gemini-api-key-here"
```

### 2. Install Dependencies
Create a virtual environment and install the required libraries:
```bash
python -m venv venv
# On Windows (PowerShell):
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Run the Research Agent
Run the main research script to query Gemini and gather raw data for all 100 apps. The script saves results incrementally:
```bash
python research_agent.py --resume
```
*Note: If rate limits (429) are encountered, the script automatically backs off, sleeps, and retries.*

### 4. Run the Verification Loop
Once raw research is completed, run the verification script to run the automated audit loop on the sample apps and save the corrected final dataset:
```bash
python verify_agent.py
```

### 5. Compile the Dashboard Report
Run the report generator to compile the dataset and logs into the final interactive web page:
```bash
python generate_report.py
```
This outputs `index.html` in the current directory, ready to be viewed in any web browser.
