import os
import json
from datetime import datetime
from serpapi import GoogleSearch

# 🧩 --- Configuration ---
QUERY = (
    'site:linkedin.com/jobs ('
    'intitle:marketing OR intitle:"digital marketing" OR intitle:"social media" OR intitle:SEO OR intitle:advertising OR '
    'intitle:content OR intitle:communications OR intitle:PR OR intitle:"public relations" OR intitle:brand OR '
    'intitle:"growth" OR intitle:"media" OR intitle:"creative" OR intitle:"copywriter" OR intitle:"campaign" OR '
    'intitle:"performance" OR intitle:"influencer" OR intitle:"paid media" ) '
    '("send your CV" OR "apply by email" OR "email your application") '
    '("@gmail.com" OR "@outlook.com" OR "@hotmail.com" OR "@company.co.uk" OR "@co.uk" OR "@") '
    '("United Kingdom" OR "UK")'
)

# Get SerpAPI key from environment variable
API_KEY = os.getenv("SERPAPI_API_KEY")
if not API_KEY:
    raise EnvironmentError("❌ SERPAPI_API_KEY not found in environment variables.")

# 🕒 --- Run search ---
print("🔍 Fetching UK marketing listings from SerpAPI ...")

params = {
    "engine": "google",
    "q": QUERY,
    "num": 100,            # Up to 100 results
    "tbs": "qdr:w",        # Only results from the past week
    "filter": "0",         # Do not filter similar results
    "api_key": API_KEY,
}

search = GoogleSearch(params)
results = search.get_dict()

if "error" in results:
    raise Exception(f"❌ SerpAPI error: {results['error']}")

# 🧹 --- Filter results ---
filtered = []
for r in results.get("organic_results", []):
    snippet = r.get("snippet", "")
    if "@" in snippet:  # Only listings with visible email addresses in snippet
        filtered.append({
            "title": r.get("title"),
            "link": r.get("link"),
            "snippet": snippet,
        })

# 💾 --- Save to file ---
timestamp = datetime.now().strftime("%Y%m%d_%H%M")
filename = f"linkedin_uk_marketing_jobs_{timestamp}.json"
output_path = os.path.join(os.path.dirname(__file__), filename)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(filtered, f, indent=2, ensure_ascii=False)

print(f"✅ Saved {len(filtered)} listings with visible emails to {filename}")
