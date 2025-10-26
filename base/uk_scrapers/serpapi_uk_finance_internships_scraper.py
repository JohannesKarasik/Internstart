import os
import json
import re
import time
import requests
from datetime import datetime
from serpapi import GoogleSearch


def main():
    try:
        # 🎯 --- Search Query (Finance Internships) ---
        QUERY = (
            'site:linkedin.com/jobs '
            '("finance intern" OR "financial analyst intern" OR "accounting intern" OR "investment intern" OR '
            '"finance internship" OR "corporate finance intern" OR "banking intern" OR "treasury intern" OR '
            '"financial services intern" OR "audit intern" OR "tax intern") '
            '("send your CV" OR "apply by email" OR "email your application") '
            'intext:@ "United Kingdom"'
        )

        # 🔑 --- API Key ---
        API_KEY = os.getenv("SERPAPI_API_KEY")
        if not API_KEY:
            return {"error": "SERPAPI_API_KEY not found in environment variables."}

        print("🔍 Fetching LinkedIn finance internship listings with potential emails...")

        # 🌍 --- Base search parameters ---
        base_params = {
            "engine": "google",
            "q": QUERY,
            "num": 10,
            "hl": "en",
            "gl": "uk",
            "location": "United Kingdom",
            "filter": "0",
            "tbs": "qdr:m",
            "api_key": API_KEY,
        }

        # 🌀 --- Fetch up to 100 results ---
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
                print("⏹️ No more results.")
                break

            all_results.extend(organic)
            time.sleep(1.5)

        print(f"🌍 Total raw results fetched: {len(all_results)}")

        EMAIL_PATTERN = re.compile(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            re.IGNORECASE,
        )

        CLOSED_REGEX = re.compile(
            r"(no\s*longer\s*(accepting|taking)\s*(applications|applicants))|"
            r"(applications\s*(are)?\s*closed)|"
            r"(job\s*(is)?\s*(closed|expired|unavailable))|"
            r"(position\s*(has\s*been)?\s*filled)",
            re.IGNORECASE,
        )

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            "Accept-Language": "en-GB,en;q=0.9",
        }

        results = []
        closed_skipped = 0

        for r in all_results:
            title = r.get("title", "").strip()
            link = r.get("link", "").strip()
            snippet = r.get("snippet", "").strip()

            if "intern" not in title.lower():
                continue

            print(f"🔎 Scanning {link} ...")
            emails_found = set()

            try:
                resp = requests.get(link, headers=headers, timeout=10)
                html_raw = resp.text.lower()

                # 🧹 Clean HTML from tags/spaces
                html_clean = re.sub(r"<[^>]+>", " ", html_raw)
                html_clean = re.sub(r"\s+", " ", html_clean).strip()

                # 🚫 Skip hidden/archived listings
                if "this job is no longer available" in html_clean or "this job has expired" in html_clean:
                    closed_skipped += 1
                    print(f"🚫 Archived/expired: {title}")
                    continue

                # ⛔ Skip closed listings (regex handles all variants)
                if CLOSED_REGEX.search(html_clean):
                    closed_skipped += 1
                    print(f"⛔ Closed listing: {title}")
                    continue

                # ✉️ Extract emails
                emails_found.update(EMAIL_PATTERN.findall(html_clean))

            except Exception as e:
                print(f"⚠️ Failed to fetch {link}: {e}")
                continue

            if not emails_found:
                continue

            results.append({
                "title": title,
                "link": link,
                "emails": list(emails_found),
                "snippet": snippet,
            })
            time.sleep(1)

        print(f"✅ Found {len(results)} open internship listings with emails.")
        print(f"🚫 Skipped {closed_skipped} closed/expired jobs.")

        # 💾 --- Save results ---
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"linkedin_uk_finance_internships_{timestamp}.json"
        output_path = os.path.join(os.path.dirname(__file__), filename)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"💾 Saved {len(results)} open finance internships with emails to {filename}")
        return {"count": len(results), "results": results, "skipped_closed": closed_skipped}

    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, ensure_ascii=False))
