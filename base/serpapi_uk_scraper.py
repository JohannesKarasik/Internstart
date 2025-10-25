# base/serpapi_uk_scraper.py

import json
import os
from datetime import datetime
from serpapi import GoogleSearch

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
API_KEY = os.getenv("SERPAPI_API_KEY")

QUERY = (
    'site:linkedin.com/jobs '
    '("send your CV to" OR "email your CV to" OR "apply by email" OR '
    '"send your application to" OR "email your application to") "@" '
    '("United Kingdom" OR "UK" OR ".co.uk")'
)

# Only show results from the past month
TIME_FILTER = "qdr:m"  # qdr:m = month, qdr:w = week, qdr:d = day

PARAMS = {
    "engine": "google",
    "q": QUERY,
    "hl": "en",          # interface language
    "gl": "gb",          # country (United Kingdom)
    "num": "100",        # up to 100 results per query
    "tbs": TIME_FILTER   # limit to past month
}

# -----------------------------------------------------------------------------
# SCRAPER FUNCTION
# -----------------------------------------------------------------------------
def scrape_uk_jobs():
    if not API_KEY:
        print("❌ SERPAPI_API_KEY not found in environment variables.")
        print("Set it in your Gunicorn service file or run:")
        print('export SERPAPI_API_KEY="your_api_key_here"')
        return

    PARAMS["api_key"] = API_KEY

    print("🔍 Fetching UK results from SerpAPI (past month only)...")
    search = GoogleSearch(PARAMS)
    results = search.get_dict()

    organic = results.get("organic_results", [])
    jobs = []

    for r in organic:
        link = r.get("link")
        title = r.get("title")
        snippet = r.get("snippet", "")

        # Only include visible email listings from the last month
        if link and "linkedin.com/jobs" in link and "@" in snippet:
            # Extra safeguard: ignore snippets mentioning older posts
            if not any(phrase in snippet.lower() for phrase in [
                "2 months ago", "3 months ago", "4 months ago", "year ago"
            ]):
                jobs.append({
                    "title": title,
                    "url": link,
                    "snippet": snippet
                })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = f"linkedin_uk_jobs_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved {len(jobs)} listings (past month only) to {output_file}")

# -----------------------------------------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    scrape_uk_jobs()
