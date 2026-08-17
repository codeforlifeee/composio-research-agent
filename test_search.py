from duckduckgo_search import DDGS
import time

print("Testing simple search...")
with DDGS() as ddgs:
    for q in ["Salesforce", "GitHub API", "Stripe developer docs"]:
        start_time = time.time()
        try:
            results = list(ddgs.text(q, max_results=3))
            print(f"Query: '{q}' | Success: Found {len(results)} results in {time.time() - start_time:.2f} seconds.")
        except Exception as e:
            print(f"Query: '{q}' | Failed: {e}")

