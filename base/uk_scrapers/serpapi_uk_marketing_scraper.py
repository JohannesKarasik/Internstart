import os
import json
import re
import time
import requests
from datetime import datetime
from serpapi import GoogleSearch
import random

def main():
    # --- Configuration ---
    QUERY_BASE = (
        'site:linkedin.com/jobs inurl:uk '
        '("@gmail.com" OR "@outlook.com" OR "@co.uk" OR "@hotmail.com" OR "@yahoo.com") '
        '("marketing" OR "digital marketing" OR "social media" OR "content marketing" OR "PR" OR "public relations" '
        'OR communications OR "email marketing" OR "copywriter" OR "brand manager" OR "advertising" OR "growth marketing" '
        'OR "marketing assistant" OR "marketing coordinator" OR "media buyer" OR "campaign manager" OR "community manager" '
        'OR "marketing executive" OR "account manager" OR "marketing intern" OR "performance marketing")'
    )

    API_KEY = os.getenv("SERPAPI_API_KEY") or "6ecc501d2af38d445f1766ba7f169eac80355198994c221128cde05ef76f9d28"
    print("🔍 Fetching up to 100 UK marketing listings from SerpAPI ...")

    base_params = {
        "engine": "google",
        "num": 10,
        "hl": "en",
        "gl": "uk",
        "location": "United Kingdom",
        "filter": "0",
        "tbs": "qdr:w",  # Only jobs from the past week
        "api_key": API_KEY,
    }

    all_results = []
    for i, start in enumerate(range(0, 100, 10)):
        # Slightly vary the query each page to avoid repetition
        random_term = random.choice(["apply", "hiring", "vacancy", "recruitment", "career"])
        params = base_params.copy()
        params["q"] = QUERY_BASE + f" {random_term} {i}"
        params["start"] = start

        print(f"📄 Fetching page {i+1} (start={start})...")
        try:
            data = GoogleSearch(params).get_dict()
        except Exception as e:
            print(f"⚠️ SerpAPI request failed: {e}")
            time.sleep(5)
            continue

        if "error" in data:
            print(f"⚠️ SerpAPI error: {data['error']}")
            break

        organic = data.get("organic_results", [])
        if not organic:
            print("⚠️ No organic results returned, stopping early.")
            break

        all_results.extend(organic)
        time.sleep(2)

    print(f"🌍 Total raw results fetched: {len(all_results)}")

    # --- Filter for marketing + email listings ---
    MARKETING_KEYWORDS = [
        "marketing", "seo", "sem", "ppc", "content", "copywriter", "advertising",
        "branding", "growth", "campaign", "communications", "pr", "public relations",
        "email", "media", "digital", "social", "brand", "community", "performance",
        "influencer", "affiliate", "creative", "ecommerce", "paid search",
        "account manager", "engagement", "customer acquisition"
    ]

    EXCLUDE_KEYWORDS = [
        "engineer", "developer", "roofer", "technician", "plumber",
        "construction", "warehouse", "driver", "nurse", "teacher",
        "chef", "accountant", "finance", "hr", "recruiter", "maintenance",
        "installer", "operator", "mechanic", "laborer", "caretaker",
        "electrician", "cleaner", "joiner", "welder", "foreman"
    ]

    filtered = []
    for r in all_results:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        link = r.get("link", "")

        combined = (title + " " + snippet).lower()

        # Must contain email mention
        if not re.search(r'@\w+\.', combined):
            continue

        # Must look like a marketing job
        if not any(mk in combined for mk in MARKETING_KEYWORDS):
            continue

        if any(ex in combined for ex in EXCLUDE_KEYWORDS):
            continue

        filtered.append({
            "title": title.strip(),
            "link": link.strip(),
            "snippet": snippet.strip(),
        })

    print(f"✅ {len(filtered)} listings contain emails & marketing relevance before closure check.")

    # --- Check that listings are still open ---
    CLOSED_PATTERNS = [
        "no longer accepting applications",
        "no longer taking applications",
        "no longer accepting applicants",
        "this job is no longer available",
        "applications are closed",
        "position filled",
        "you can no longer apply",
        "job has expired",
        "not accepting",
    ]

    open_listings = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/126.0 Safari/537.36",
        "Accept-Language": "en-GB,en;q=0.9",
    }

    print(f"🧠 Checking {len(filtered)} listings for closure text...")
    for job in filtered:
        try:
            html = requests.get(job["link"], headers=headers, timeout=8).text.lower()
            if any(p in html for p in CLOSED_PATTERNS):
                print(f"⛔ Closed: {job['title']}")
                continue
            open_listings.append(job)
            print(f"✅ Open: {job['title']}")
        except Exception as e:
            print(f"⚠️ Request failed: {e}")
        time.sleep(1)

        if len(open_listings) >= 100:
            break

    # --- Save to JSON ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"linkedin_uk_marketing_jobs_{timestamp}.json"
    output_path = os.path.join(os.path.dirname(__file__), filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(open_listings, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(open_listings)} open UK marketing listings to {filename}")
    return open_listings


if __name__ == "__main__":
    main()
