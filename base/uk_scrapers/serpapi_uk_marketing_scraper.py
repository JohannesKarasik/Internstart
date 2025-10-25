import os
import json
import re
from datetime import datetime
from serpapi import GoogleSearch

# 🧩 --- Configuration ---
QUERY = (
    'site:linkedin.com/jobs ('
    'intitle:marketing OR intitle:"digital marketing" OR intitle:"social media" OR intitle:SEO OR intitle:advertising OR '
    'intitle:content OR intitle:communications OR intitle:PR OR intitle:"public relations" OR intitle:brand OR '
    'intitle:"growth" OR intitle:"media" OR intitle:"creative" OR intitle:"copywriter" OR intitle:"campaign" OR '
    'intitle:"performance" OR intitle:"influencer" OR intitle:"paid media") '
    '("send your CV" OR "apply by email" OR "email your application") '
    '("@gmail.com" OR "@outlook.com" OR "@hotmail.com" OR "@company.co.uk" OR "@co.uk" OR "@") '
    '("United Kingdom" OR "UK") ("1 day ago" OR "24 hours ago")'
)


def main():
    """Fetch recent (past 24h) UK marketing jobs with visible emails (max 50)."""
    API_KEY = os.getenv("SERPAPI_API_KEY")
    if not API_KEY:
        raise EnvironmentError("❌ SERPAPI_API_KEY not found in environment variables.")

    print("🔍 Fetching up to 50 UK marketing listings from SerpAPI (past 24 hours)...")

    params = {
        "engine": "google",
        "q": QUERY,
        "num": 10,                # SerpAPI limit per page
        "hl": "en",
        "gl": "uk",
        "location": "United Kingdom",
        "filter": "0",
        "tbs": "qdr:d1",          # limit to last 24 hours
        "api_key": API_KEY,
    }

    all_results = []

    # 🌀 --- Paginate up to 5 pages (≈ 50 results max) ---
    for start in range(0, 50, 10):
        params["start"] = start
        print(f"📄 Fetching page starting at {start}...")
        try:
            search = GoogleSearch(params)
            data = search.get_dict()
        except Exception as e:
            print(f"⚠️ Request failed at start={start}: {e}")
            break

        results = data.get("organic_results", [])
        if not results:
            print("⏹️ No more results found.")
            break

        all_results.extend(results)

        # Stop early if we already have enough
        if len(all_results) >= 50:
            break

    print(f"🌍 Total raw results fetched: {len(all_results)}")

    # 🧹 --- Filter results with visible emails ---
    filtered = []
    for r in all_results:
        snippet = r.get("snippet", "")
        title = r.get("title", "")
        link = r.get("link", "")

        # Require an email
        if "@" not in snippet:
            continue

        # Clean up listing
        filtered.append({
            "title": title.strip(),
            "link": link.strip(),
            "snippet": snippet.strip(),
        })

    # Trim to 50 just in case
    filtered = filtered[:50]

    # 💾 --- Save results ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"linkedin_uk_marketing_jobs_{timestamp}.json"
    output_path = os.path.join(os.path.dirname(__file__), filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(filtered)} listings (past 24h, email-visible) to {filename}")


if __name__ == "__main__":
    main()
