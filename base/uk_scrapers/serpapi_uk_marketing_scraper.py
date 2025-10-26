import os
import json
import time
import requests
from datetime import datetime
from serpapi import GoogleSearch


def main():
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

    print("🔍 Fetching UK marketing listings from SerpAPI ...")

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
    for start in range(0, 40, 10):  # 4 pages → safer but larger
        params = base_params.copy()
        params["start"] = start
        print(f"📄 Fetching page starting at {start}...")

        try:
            data = GoogleSearch(params).get_dict()
        except Exception as e:
            print(f"⚠️ SerpAPI exception: {e}")
            time.sleep(3)
            continue

        if not isinstance(data, dict):
            print("⚠️ Non-dict response from SerpAPI (HTML or malformed). Skipping page.")
            time.sleep(2)
            continue

        if "error" in data:
            print(f"⚠️ SerpAPI error: {data['error']}")
            if "limit" in data["error"].lower():
                print("⏳ Rate limit reached — stopping early.")
                break
            time.sleep(2)
            continue

        organic = data.get("organic_results")
        if not organic:
            print("⚠️ No organic results found for this page.")
            continue

        all_results.extend(organic)
        time.sleep(2)

    print(f"🌍 Total raw results fetched: {len(all_results)}")

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
        title_lower = title.lower()
        snippet_lower = snippet.lower()

        if any(ex in title_lower for ex in EXCLUDE_KEYWORDS):
            return False
        if any(mk in title_lower for mk in MARKETING_KEYWORDS):
            return True
        if any(mk in snippet_lower for mk in MARKETING_KEYWORDS):
            return True
        return False

    filtered = []
    for r in all_results:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        link = r.get("link", "")

        if not title or "@" not in snippet:
            continue
        if not is_marketing_job(title, snippet):
            continue

        filtered.append({
            "title": title.strip(),
            "link": link.strip(),
            "snippet": snippet.strip(),
        })

    print(f"✅ Filtered {len(filtered)} marketing listings before closure check.")

    CLOSED_PATTERNS = [
        "no longer accepting applications",
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
    }

    for job in filtered[:50]:  # cap for speed
        try:
            html = requests.get(job["link"], headers=headers, timeout=6).text.lower()
            if any(p in html for p in CLOSED_PATTERNS):
                continue
            open_listings.append(job)
        except Exception as e:
            print(f"⚠️ Skipped due to request error: {e}")
            continue
        time.sleep(0.8)

    print(f"✅ Found {len(open_listings)} open listings.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"linkedin_uk_marketing_jobs_{timestamp}.json"
    output_path = os.path.join(os.path.dirname(__file__), filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(open_listings, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(open_listings)} listings to {filename}")
    return open_listings


if __name__ == "__main__":
    results = main()
    print(json.dumps(results, ensure_ascii=False))
