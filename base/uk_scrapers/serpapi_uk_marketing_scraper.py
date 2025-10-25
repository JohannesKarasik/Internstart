import os
import json
from datetime import datetime, timedelta
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
    '("United Kingdom" OR "UK") "posted within the last week"'
)

# 🔑 --- API Key ---
API_KEY = os.getenv("SERPAPI_API_KEY")
if not API_KEY:
    raise EnvironmentError("❌ SERPAPI_API_KEY not found in environment variables.")

print("🔍 Fetching UK marketing listings from SerpAPI (past week only) ...")

# 🌍 --- Search Parameters ---
params = {
    "engine": "google",
    "q": QUERY,
    "num": 10,               # 10 per run
    "hl": "en",
    "gl": "uk",
    "location": "United Kingdom",
    "filter": "0",
    "tbs": "qdr:w",          # filter past week
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

# 🧹 --- Filter results with visible emails + recent postings ---
filtered = []
for r in all_results:
    snippet = r.get("snippet", "")
    title = r.get("title", "")
    link = r.get("link", "")

    if "@" not in snippet:
        continue

    # 🕒 Skip old results if snippet mentions time older than 1 week
    if re.search(r"(\b\d+\s+(month|months|year|years|week|weeks)\b)", snippet.lower()):
        # Extract the numeric value
        match = re.search(r"\b(\d+)\s+(month|months|year|years|week|weeks)\b", snippet.lower())
        if match:
            num = int(match.group(1))
            unit = match.group(2)
            if unit.startswith("month") or unit.startswith("year") or num > 1:
                print(f"⏭️ Skipping old listing: '{title}' ({match.group(0)})")
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

print(f"✅ Saved {len(filtered)} fresh listings (past week) with visible emails to {filename}")
