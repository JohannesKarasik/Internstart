# base/serpapi_google_scraper.py

import json
import os
from datetime import datetime
from serpapi import GoogleSearch

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
API_KEY = os.getenv("SERPAPI_API_KEY")

QUERY = (
    'site:linkedin.com/jobs/denmark OR site:linkedin.com/jobs/view/ '
    '("send ansøgning" OR "send din ansøgning" OR "send dit CV" '
    'OR "ansøg via mail" OR "ansøg på mail" OR "send os din ansøgning" '
    'OR "@gmail.com" OR "@company.com")'
)

PARAMS = {
    "engine": "google",
    "q": QUERY,
    "hl": "da",
    "gl": "dk",
    "num": "50",
    "tbs": "qdr:m",  # past month
}

# -----------------------------------------------------------------------------
# SCRAPER FUNCTION
# -----------------------------------------------------------------------------
def scrape_jobs():
    if not API_KEY:
        print("❌ SERPAPI_API_KEY not found in environment variables.")
        print("Set it in your Gunicorn service file or run:")
        print('export SERPAPI_API_KEY="your_api_key_here"')
        return

    PARAMS["api_key"] = API_KEY

    print("🔍 Fetching results from SerpAPI ...")
    search = GoogleSearch(PARAMS)
    results = search.get_dict()

    organic = results.get("organic_results", [])
    jobs = []

    for r in organic:
        link = r.get("link")
        title = r.get("title")
        snippet = r.get("snippet", "")
        if link and "linkedin.com/jobs" in link:
            jobs.append({
                "title": title,
                "url": link,
                "snippet": snippet
            })

    # -----------------------------------------------------------------------------
    # SAVE RESULTS
    # -----------------------------------------------------------------------------
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = f"linkedin_denmark_jobs_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved {len(jobs)} listings to {output_file}")


# -----------------------------------------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    scrape_jobs()
