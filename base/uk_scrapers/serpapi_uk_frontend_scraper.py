import os
import json
import re
import time
import requests
from datetime import datetime
from serpapi import GoogleSearch


def main():
    try:
        QUERY = (
            'site:linkedin.com/jobs '
            '("frontend developer" OR "react developer" OR "software engineer") '
            '("send your CV" OR "apply by email" OR "email your application") '
            '"@" "United Kingdom"'
        )

        API_KEY = os.getenv("SERPAPI_API_KEY")
        if not API_KEY:
            return {"error": "SERPAPI_API_KEY not found in environment variables."}

        print("🔍 Fetching LinkedIn frontend/software jobs (with potential emails)...")

        # --- SerpAPI base params ---
        base_params = {
            "engine": "google",
            "q": QUERY,
            "num": 10,
            "hl": "en",
            "gl": "uk",
            "location": "United Kingdom",
            "filter": "0",
            "tbs": "qdr:m",  # Past month
            "api_key": API_KEY,
        }

        all_results = []
        for start in range(0, 100, 10):
            params = base_params.copy()
            params["start"] = start
            print(f"📄 Fetching page starting at {start}...")

            try:
                data = GoogleSearch(params).get_dict()
            except Exception as e:
                return {"error": f"SerpAPI request failed: {e}"}

            organic = data.get("organic_results", [])
            if not organic:
                break

            all_results.extend(organic)
            time.sleep(1.5)

        print(f"🌍 Total raw results fetched: {len(all_results)}")

        EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.IGNORECASE)
        FRONTEND_TERMS = ["frontend", "react", "javascript", "typescript", "software", "developer"]

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            "Accept-Language": "en-GB,en;q=0.9",
        }

        results = []
        for r in all_results:
            title = r.get("title", "")
            link = r.get("link", "")
            snippet = r.get("snippet", "")

            text = (title + " " + snippet).lower()
            if not any(term in text for term in FRONTEND_TERMS):
                continue

            print(f"🔎 Scanning {link} ...")
            emails_found = set()

            try:
                resp = requests.get(link, headers=headers, timeout=10)
                html = resp.text
                emails_found.update(EMAIL_PATTERN.findall(html))
            except Exception as e:
                print(f"⚠️ Failed to fetch {link}: {e}")
                continue

            if not emails_found:
                continue

            results.append({
                "title": title.strip(),
                "link": link.strip(),
                "emails": list(emails_found),
                "snippet": snippet.strip(),
            })
            time.sleep(1)

        print(f"✅ Found {len(results)} job pages with actual emails in HTML.")

        # --- Save output ---
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"linkedin_uk_frontend_emails_full_{timestamp}.json"
        output_path = os.path.join(os.path.dirname(__file__), filename)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"✅ Saved {len(results)} jobs with extracted emails to {filename}")
        return {"count": len(results), "results": results}

    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, ensure_ascii=False))
