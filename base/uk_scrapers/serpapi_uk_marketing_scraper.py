import os
import re
import requests
from serpapi import GoogleSearch

# --- Configuration ---
QUERY = (
    'site:linkedin.com/jobs inurl:uk '
    '("send your CV" OR "apply by email") '
    '("@co.uk" OR "@gmail.com" OR "@outlook.com") '
    '(marketing OR SEO OR "social media" OR PR OR advertising)'
)

API_KEY = os.getenv("SERPAPI_API_KEY")
if not API_KEY:
    raise EnvironmentError("❌ SERPAPI_API_KEY not found in environment variables.")

print("🔍 Testing LinkedIn UK job fetch + closure detection...")

params = {
    "engine": "google",
    "q": QUERY,
    "num": 2,       # only 2 results — uses 1 SerpAPI credit
    "hl": "en",
    "gl": "uk",
    "api_key": API_KEY,
}

data = GoogleSearch(params).get_dict()
results = data.get("organic_results", []) or []

if not results:
    print("⚠️ No results fetched. Try running manually in Google to confirm the query works.")
    exit()

print(f"✅ Got {len(results)} result(s). Checking if pages are open or closed...")

# --- Closure detection phrases ---
CLOSED_PATTERNS = [
    r"no longer accepting applications",
    r"no longer taking applications",
    r"no longer accepting applicants",
    r"this job is no longer available",
    r"position filled",
    r"applications are closed",
    r"cannot apply",
    r"you can no longer apply",
]

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}

for r in results:
    link = r.get("link")
    print(f"\n🔗 Checking: {link}")

    try:
        resp = requests.get(link, headers=headers, timeout=10)
        text = resp.text.lower()

        closed = any(re.search(p, text) for p in CLOSED_PATTERNS)
        if closed:
            print("⛔ Job CLOSED — found closure text.")
        else:
            print("✅ Job seems OPEN (no closure text found).")

    except requests.RequestException as e:
        print("⚠️ Request failed:", e)
