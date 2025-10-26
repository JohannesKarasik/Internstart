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
        '("finance intern" OR "financial analyst intern" OR "accounting intern" OR '
        '"investment intern" OR "banking intern" OR "audit intern" OR "tax intern" OR '
        '"corporate finance intern" OR "treasury intern" OR "financial services intern" OR '
        '"finance internship")'
    )

    # 🔑 --- API Key ---
    API_KEY = os.getenv("SERPAPI_API_KEY")
    if not API_KEY:
        raise EnvironmentError("❌ SERPAPI_API_KEY not found in environment variables.")

    print("🔍 Fetching UK finance internships from SerpAPI ...")

    # 🌍 --- Base Search Parameters ---
    base_params = {
        "engine": "google",
        "q": QUERY,
        "num": 10,  # 10 results per page
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

    # 🎯 --- Title filters ---
    FINANCE_TITLE_RE = re.compile(
        r"""(?ix)
        \b(intern(ship)?|finance|financial|accounting|audit|tax|banking|investment|treasury|analyst|corporate)\b
        """,
        re.IGNORECASE,
    )

    EXCLUDE_TITLE_RE = re.compile(
        r"""(?ix)
        \b(marketing|developer|engineer|designer|sales|construction|chef|teacher|healthcare|nurse|technician)\b
        """,
        re.IGNORECASE,
    )

    # 🧹 --- Filter results (must show @ in snippet and match finance terms) ---
    filtered = []
    for r in all_results:
        title = r.get("title", "") or ""
        snippet = r.get("snippet", "") or ""
        link = r.get("link", "") or ""

        if "@" not in snippet:
            continue
        if "intern" not in title.lower():
            continue

        text = (title + " " + snippet + " " + link).lower()
        if not ("uk" in text or "united kingdom" in text or "/uk/" in link.lower() or ".co.uk" in text):
            continue
        if not FINANCE_TITLE_RE.search(title):
            continue
        if EXCLUDE_TITLE_RE.search(title):
            continue

        filtered.append({
            "title": title.strip(),
            "link": link.strip(),
            "snippet": snippet.strip(),
        })

    print(f"✅ Filtered down to {len(filtered)} finance internship titles before closure check.")

    # 🔎 --- Remove closed listings ---
    CLOSED_PATTERNS = [
        "no longer accepting applications",
        "no longer taking applications",
        "no longer accepting applicants",
        "this job is no longer available",
        "applications are closed",
        "position filled",
        "you can no longer apply",
        "job has expired",
        "job is closed",
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
    filename = f"linkedin_uk_finance_internships_{timestamp}.json"
    output_path = os.path.join(os.path.dirname(__file__), filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(open_listings, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(open_listings)} open UK finance internships to {filename}")

    return open_listings


if __name__ == "__main__":
    main()
