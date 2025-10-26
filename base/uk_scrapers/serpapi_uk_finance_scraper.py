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
        '("send your CV" OR "apply by email" OR "email your application" OR "send your application to") '
        '("@co.uk" OR "@gmail.com" OR "@outlook.com") '
        '(accounting OR finance OR "financial analyst" OR "financial controller" OR "investment analyst" '
        'OR "accountant" OR "bookkeeper" OR "auditor" OR "tax consultant" OR "banking" OR "treasury analyst" '
        'OR "finance manager" OR "FP&A" OR "financial planning" OR "CFO" OR "finance director" '
        'OR "finance assistant" OR "payroll" OR "financial advisor" OR "compliance" OR "risk analyst")'
    )

    # 🔑 --- API Key ---
    API_KEY = os.getenv("SERPAPI_API_KEY")
    if not API_KEY:
        raise EnvironmentError("❌ SERPAPI_API_KEY not found in environment variables.")

    print("🔍 Fetching up to 30 UK finance listings from SerpAPI ...")

    # 🌍 --- Base Search Parameters ---
    base_params = {
        "engine": "google",
        "q": QUERY,
        "num": 10,
        "hl": "en",
        "gl": "uk",
        "location": "United Kingdom",
        "filter": "0",
        "tbs": "qdr:w",  # past week
        "api_key": API_KEY,
    }

    # 🌀 --- Fetch up to 30 results (3 pages) ---
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
            print("⏹️ No more results found.")
            break

        all_results.extend(organic)
        time.sleep(2)

    print(f"🌍 Total raw results fetched: {len(all_results)}")

    # 🎯 --- Finance title filters ---
    FINANCE_TITLE_RE = re.compile(
        r"""(?ix)
        \b(
           finance|financial|accounting|accountant|auditor|analyst|
           controller|treasury|banking|investment|payroll|cfo|
           "fp&a"|tax|risk|compliance|credit|wealth|equity|treasurer|
           advisor|consultant|bookkeeping|fund|portfolio
        )\b
        """,
        re.IGNORECASE,
    )

    # Exclude titles that are clearly not finance
    EXCLUDE_TITLE_RE = re.compile(
        r"""(?ix)
        \b(
           marketing|developer|engineer|technician|nurse|teacher|chef|sales|
           social\s+media|copywriter|pr|public\s+relations|construction|
           warehouse|driver|operator|designer|ux|ui|graphics|customer\s+service
        )\b
        """,
        re.IGNORECASE,
    )

    # 🧹 --- Filter results (EMAIL + UK + TITLE must match finance keywords) ---
    filtered = []
    for r in all_results:
        title = r.get("title", "") or ""
        snippet = r.get("snippet", "") or ""
        link = r.get("link", "") or ""

        # Must contain email
        if "@" not in snippet:
            continue

        # Must be UK
        text = (title + " " + snippet + " " + link).lower()
        if not (" uk " in f" {text} " or "united kingdom" in text or ".co.uk" in text or "/uk/" in link):
            continue

        # Must have finance-related keyword in title
        if not FINANCE_TITLE_RE.search(title):
            print(f"🚫 Non-finance title (skipped): {title}")
            continue

        # Exclude unrelated jobs
        if EXCLUDE_TITLE_RE.search(title):
            print(f"🚫 Excluded non-finance role: {title}")
            continue

        filtered.append({
            "title": title.strip(),
            "link": link.strip(),
            "snippet": snippet.strip(),
        })

    print(f"✅ Filtered down to {len(filtered)} finance titles before closure check.")

    # 🔎 --- Remove closed listings (page check) ---
    CLOSED_PATTERNS = [
        "no longer accepting applications",
        "this job is no longer available",
        "applications are closed",
        "position filled",
    ]

    open_listings = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36"
        ),
        "Accept-Language": "en-GB,en;q=0.9",
    }

    print(f"🧠 Checking {len(filtered)} listings for closure text...")
    for job in filtered:
        url = job["link"]
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            html = resp.text.lower()

            if any(p in html for p in CLOSED_PATTERNS):
                print(f"⛔ Closed: {job['title']}")
                continue

            open_listings.append(job)
            print(f"✅ Open: {job['title']}")

        except requests.RequestException as e:
            print(f"⚠️ Request failed for {url}: {e}")
            continue

        time.sleep(1.0)

    open_listings = open_listings[:30]

    # 💾 --- Save to JSON ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"linkedin_uk_finance_jobs_{timestamp}.json"
    output_path = os.path.join(os.path.dirname(__file__), filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(open_listings, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(open_listings)} open UK finance listings to {filename}")

    return open_listings

if __name__ == "__main__":
    main()
