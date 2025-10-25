import os
import json
import re
import time
import requests
from datetime import datetime
from serpapi import GoogleSearch

def main():
    # 🧩 --- Configuration ---
    QUERY = (
        'site:linkedin.com/jobs inurl:uk '
        '("send your CV" OR "apply by email" OR "email your application") '
        '("@co.uk" OR "@gmail.com" OR "@outlook.com") '
        '(marketing OR "digital marketing" OR SEO OR "content marketing" OR "social media" OR PR OR "public relations" '
        'OR communications OR "email marketing" OR "copywriter" OR "brand manager" OR "advertising" OR "growth marketing" '
        'OR "marketing assistant" OR "marketing coordinator" OR "media buyer" OR "campaign manager" OR "community manager" '
        'OR "marketing executive" OR "account manager" OR "marketing intern" OR "performance marketing")'
    )

    API_KEY = os.getenv("SERPAPI_API_KEY")
    if not API_KEY:
        raise EnvironmentError("❌ SERPAPI_API_KEY not found in environment variables.")

    print("🔍 Fetching up to 30 UK marketing listings from SerpAPI ...")

    base_params = {
        "engine": "google",
        "q": QUERY,
        "num": 10,
        "hl": "en",
        "gl": "uk",
        "location": "United Kingdom",
        "filter": "0",
        "tbs": "qdr:w",
        "api_key": API_KEY,
    }

    all_results = []
    for start in range(0, 30, 10):
        params = base_params.copy()
        params["start"] = start
        print(f"📄 Fetching page starting at {start}...")
        try:
            data = GoogleSearch(params).get_dict()
        except Exception as e:
            print(f"⚠️ SerpAPI request failed: {e}")
            time.sleep(3)
            continue

        if "error" in data:
            print(f"⚠️ SerpAPI error: {data['error']}")
            break

        organic = data.get("organic_results", [])
        if not organic:
            break

        all_results.extend(organic)
        time.sleep(2)

    print(f"🌍 Total raw results fetched: {len(all_results)}")

    # 🎯 --- Keyword logic ---
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

    def is_marketing_job(title, snippet):
        """
        Returns True if title or snippet clearly indicates a marketing-related role.
        Filters out blue-collar, technical, or unrelated jobs.
        """
        title_lower = title.lower()
        snippet_lower = snippet.lower()

        # ❌ Exclude immediately if title contains irrelevant terms
        if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
            return False

        # ✅ Require at least one marketing term in title (strong signal)
        if any(mk in title_lower for mk in MARKETING_KEYWORDS):
            return True

        # ⚙️ Weak fallback: snippet mentions marketing keywords (but not excluded)
        if any(mk in snippet_lower for mk in MARKETING_KEYWORDS) and not any(ex in snippet_lower for ex in EXCLUDE_KEYWORDS):
            return True

        return False

    # 🧹 --- Filtering phase ---
    filtered = []
    for r in all_results:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        link = r.get("link", "")

        text = (title + " " + snippet).lower()
        if "@" not in snippet:
            continue
        if not ("uk" in text or "united kingdom" in text or "/uk/" in link.lower()):
            continue
        if not is_marketing_job(title, snippet):
            print(f"🚫 Skipped non-marketing: {title}")
            continue

        filtered.append({
            "title": title.strip(),
            "link": link.strip(),
            "snippet": snippet.strip(),
        })

    print(f"✅ Filtered down to {len(filtered)} marketing-relevant listings before closure check.")

    # 🔎 --- Remove closed listings ---
    CLOSED_PATTERNS = [
        "no longer accepting applications",
        "no longer taking applications",
        "no longer accepting applicants",
        "this job is no longer available",
        "applications are closed",
        "position filled",
        "you can no longer apply",
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
        time.sleep(1.0)

    open_listings = open_listings[:30]

    # 💾 --- Save to JSON ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"linkedin_uk_marketing_jobs_{timestamp}.json"
    output_path = os.path.join(os.path.dirname(__file__), filename)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(open_listings, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(open_listings)} open UK marketing listings to {filename}")
    return open_listings
