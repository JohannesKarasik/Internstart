import os
import json
from datetime import datetime
from serpapi import GoogleSearch
from urllib.parse import urlparse

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

print("🔍 Fetching up to 50 UK marketing listings from SerpAPI ...")

# 🌍 --- Base Search Parameters ---
base_params = {
    "engine": "google",
    "q": QUERY,
    "num": 10,               # 10 results per page (SerpAPI limit)
    "hl": "en",
    "gl": "uk",
    "location": "United Kingdom",
    "filter": "0",           # include similar results
    "tbs": "qdr:w",          # past week
    "api_key": API_KEY,
}

# 🌀 --- Fetch up to 50 results (5 pages) ---
all_results = []
for start in range(0, 50, 10):
    params = base_params.copy()
    params["start"] = start
    print(f"📄 Fetching page starting at {start}...")

    search = GoogleSearch(params)
    data = search.get_dict()

    if "error" in data:
        print(f"⚠️ SerpAPI error: {data['error']}")
        break

    organic = data.get("organic_results", [])
    if not organic:
        print("⏹️ No more results found.")
        break

    all_results.extend(organic)

print(f"🌍 Total raw results fetched: {len(all_results)}")

# 🧹 --- Filter results with visible emails & UK domains ---
filtered = []
for r in all_results:
    snippet = r.get("snippet", "")
    link = r.get("link", "")
    title = r.get("title", "")

    # Must contain email
    if "@" not in snippet:
        continue

    # Must have .uk or /uk/ in the domain or path
    domain = urlparse(link).netloc.lower()
    path = urlparse(link).path.lower()
    if not (".uk" in domain or "/uk/" in path):
        continue

    filtered.append({
        "title": title.strip(),
        "link": link.strip(),
        "snippet": snippet.strip(),
    })

# Limit to 50 just in case
filtered = filtered[:50]

# 💾 --- Save to JSON file ---
timestamp = datetime.now().strftime("%Y%m%d_%H%M")
filename = f"linkedin_uk_marketing_jobs_{timestamp}.json"
output_path = os.path.join(os.path.dirname(__file__), filename)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(filtered, f, indent=2, ensure_ascii=False)

print(f"✅ Saved {len(filtered)} UK-only listings with visible emails to {filename}")
