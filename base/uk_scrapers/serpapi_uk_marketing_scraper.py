import os
import json
import re
from datetime import datetime
from serpapi import GoogleSearch

# 🧩 --- Query: target UK jobs only ---
QUERY = (
    'site:linkedin.com/jobs ('
    'intitle:marketing OR intitle:"digital marketing" OR intitle:"social media" OR intitle:SEO OR intitle:advertising OR '
    'intitle:content OR intitle:communications OR intitle:PR OR intitle:"public relations" OR intitle:brand OR '
    'intitle:"growth" OR intitle:"media" OR intitle:"creative" OR intitle:"copywriter" OR intitle:"campaign" OR '
    'intitle:"performance" OR intitle:"influencer" OR intitle:"paid media") '
    '("send your CV" OR "apply by email" OR "email your application") '
    '("@gmail.com" OR "@outlook.com" OR "@hotmail.com" OR "@company.co.uk" OR "@co.uk" OR "@") '
    '("United Kingdom" OR "UK" OR "England" OR "London" OR "Manchester" OR "Birmingham" OR "Leeds" OR "Liverpool") '
    '("1 day ago" OR "24 hours ago")'
)


def main():
    """Fetch up to 50 LinkedIn UK marketing jobs (past 24h, email visible)."""
    API_KEY = os.getenv("SERPAPI_API_KEY")
    if not API_KEY:
        raise EnvironmentError("❌ SERPAPI_API_KEY not found in environment variables.")

    print("🔍 Fetching UK-only marketing listings from SerpAPI (past 24h)...")

    params = {
        "engine": "google",
        "q": QUERY,
        "num": 10,
        "hl": "en",
        "gl": "uk",
        "location": "United Kingdom",
        "filter": "0",
        "tbs": "qdr:d1",   # last 24 hours
        "api_key": API_KEY,
    }

    all_results = []

    # 🌀 paginate up to 5 pages (~50 listings)
    for start in range(0, 50, 10):
        params["start"] = start
        print(f"📄 Fetching page starting at {start}...")
        try:
            search = GoogleSearch(params)
            data = search.get_dict()
        except Exception as e:
            print(f"⚠️ Request failed on page {start//10 + 1}: {e}")
            break

        results = data.get("organic_results", [])
        if not results:
            print("⏹️ No more results found.")
            break

        all_results.extend(results)
        if len(all_results) >= 50:
            break

    print(f"🌍 Total raw results fetched: {len(all_results)}")

    # 🧹 --- Filter visible emails + confirm UK relevance ---
    filtered = []
    uk_keywords = ["uk", "united kingdom", "england", "scotland", "wales", "london", "manchester",
                   "birmingham", "leeds", "liverpool", ".co.uk"]

    for r in all_results:
        snippet = r.get("snippet", "").lower()
        title = r.get("title", "")
        link = r.get("link", "")

        # Require an email
        if "@" not in snippet:
            continue

        # Must clearly relate to UK
        if not any(k in snippet or k in link for k in uk_keywords):
            continue

        filtered.append({
            "title": title.strip(),
            "link": link.strip(),
            "snippet": snippet.strip(),
        })

    # Limit to 50 listings
    filtered = filtered[:50]

    # 💾 --- Save results ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"linkedin_uk_marketing_jobs_{timestamp}.json"
    output_path = os.path.join(os.path.dirname(__file__), filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(filtered)} UK listings (past 24h, email-visible) to {filename}")


if __name__ == "__main__":
    main()
