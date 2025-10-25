import os
import json
from datetime import datetime
from serpapi import GoogleSearch
import re

# 🧩 --- Configuration ---
QUERY = (
    'site:linkedin.com/jobs ('
    'intitle:marketing OR intitle:"digital marketing" OR intitle:"social media" OR intitle:SEO OR intitle:advertising OR '
    'intitle:content OR intitle:communications OR intitle:PR OR intitle:"public relations" OR intitle:brand OR '
    'intitle:"growth" OR intitle:"media" OR intitle:"creative" OR intitle:"copywriter" OR intitle:"campaign" OR '
    'intitle:"performance" OR intitle:"influencer" OR intitle:"paid media") '
    '("send your CV" OR "apply by email" OR "email your application") '
    '("@gmail.com" OR "@outlook.com" OR "@hotmail.com" OR "@company.co.uk" OR "@co.uk" OR "@") '
    '("United Kingdom" OR "UK") "posted within the last 3 days"'
)

# 🔑 --- API Key ---
API_KEY = os.getenv("SERPAPI_API_KEY")
if not API_KEY:
    raise EnvironmentError("❌ SERPAPI_API_KEY not found in environment variables.")

print("🔍 Fetching UK marketing listings from SerpAPI (past 3 days) ...")

# 🌍 --- Search Parameters ---
params = {
    "engine": "google",
    "q": QUERY,
    "num": 10,  # limit to 10 for testing
    "hl": "en",
    "gl": "uk",
    "location": "United Kingdom",
    "filter": "0",
    "tbs": "qdr:d3",  # past 3 days
    "api_key": API_KEY,
}

# 🌀 --- Perform search ---
search = GoogleSearch(params)
data = search.get_dict()

if "error" in data:
    print(f"⚠️ SerpAPI error: {data['error']}")
    all_results = []
else:
    all_results = data.get("organic_results", []) or []
    print(f"📄 Page 1: fetched {len(all_results)} results...")

print(f"🌍 Total raw results fetched: {len(all_results)}")

# 🧹 --- Filter results with visible emails + fresh postings ---
filtered = []
for r in all_results:
    snippet = r.get("snippet", "")
    title = r.get("title", "")
    link = r.get("link", "")

    if "@" not in snippet:
        continue

    # 🕒 Remove listings mentioning "month(s)", "week(s)", or "4+ days ago"
    old_match = re.search(r"(\d+)\s+(day|days|week|weeks|month|months|year|years)\s+ago", snippet.lower())
    if old_match:
        num = int(old_match.group(1))
        unit = old_match.group(2)
        if unit.startswith(("week", "month", "year")) or num > 3:
            print(f"⏭️ Skipping old listing: '{title}' ({old_match.group(0)})")
            continue

    filtered.append({
        "title": title,
        "link": link,
        "snippet": snippet,
    })

# 💾 --- Save to JSON file ---
timestamp = datetime.now().strftime("%Y%m%d_%H%M")
filename = f"linkedin_uk_marketing_jobs_{timestamp}.json"
output_path = os.path.join(os.path.dirname(__file__), filename)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(filtered, f, indent=2, ensure_ascii=False)

print(f"✅ Saved {len(filtered)} fresh listings (past 3 days) with visible emails to {filename}")
