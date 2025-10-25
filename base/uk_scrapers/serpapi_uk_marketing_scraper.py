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

# 🔑 --- API Key ---
API_KEY = os.getenv("SERPAPI_API_KEY")
if not API_KEY:
    raise EnvironmentError("❌ SERPAPI_API_KEY not found in environment variables.")

print("🔍 Fetching UK marketing listings from SerpAPI ...")

# 🌍 --- Base Search Parameters ---
params = {
    "engine": "google",
    "q": QUERY,
    "num": 10,               # fetch 10 per page (Google cap)
    "hl": "en",
    "gl": "uk",
    "location": "United Kingdom",
    "filter": "0",           # do not hide similar results
    "tbs": "qdr:w",          # past week
    "api_key": API_KEY,
}

# 🌀 --- Paginate up to 100 results ---
all_results = []
for start in range(0, 100, 10):  # Google supports start=0,10,20,...
    params["start"] = start
    search = GoogleSearch(params)
    data = search.get_dict()

    if "error" in data:
        print(f"⚠️ SerpAPI error on page {start//10 + 1}: {data['error']}")
        break

    organic = data.get("organic_results", [])
    if not organic:
        break

    all_results.extend(organic)
    print(f"📄 Page {start//10 + 1}: fetched {len(organic)} results...")

print(f"🌍 Total raw results fetched: {len(all_results)}")

# 🧹 --- Filter results with visible emails ---
filtered = []
for r in all_results:
    snippet = r.get("snippet", "")
    if "@" in snippet:
        filtered.append({
            "title": r.get("title"),
            "link": r.get("link"),
            "snippet": snippet,
        })

# 💾 --- Save to JSON file ---
timestamp = datetime.now().strftime("%Y%m%d_%H%M")
filename = f"linkedin_uk_marketing_jobs_{timestamp}.json"
output_path = os.path.join(os.path.dirname(__file__), filename)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(filtered, f, indent=2, ensure_ascii=False)

print(f"✅ Saved {len(filtered)} listings with visible emails to {filename}")
