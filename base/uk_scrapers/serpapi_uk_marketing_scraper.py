import os
import json
import re
import time
import requests
from datetime import datetime
from serpapi import GoogleSearch

def main():
    try:
        # 🧩 --- Configuration ---
        QUERY = (
            'site:uk.linkedin.com/jobs '
            '("send your CV" OR "apply by email" OR "email your application" OR "send your application to" OR "email your CV to") '
            '("@gmail.com" OR "@outlook.com" OR "@co.uk" OR "@yahoo.co.uk") '
            '("finance" OR "financial analyst" OR "accountant" OR "bookkeeper" OR "auditor" OR "tax consultant" OR '
            '"investment analyst" OR "banking" OR "treasury analyst" OR "finance manager" OR "FP&A" OR '
            '"financial planning" OR "CFO" OR "finance director" OR "finance assistant" OR "payroll" OR '
            '"financial advisor" OR "compliance" OR "risk analyst") '
            'intext:"@" intext:("send your CV" OR "apply by email" OR "email your application") '
            '-"linkedin.com/company" -"linkedin.com/learning" -"linkedin.com/pulse" -"courses" -"insights" '
            '-filetype:jpg -filetype:png -filetype:webp'
        )

        API_KEY = os.getenv("SERPAPI_API_KEY")
        if not API_KEY:
            return {"error": "SERPAPI_API_KEY not found in environment variables."}

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

            try:
                data = GoogleSearch(params).get_dict()
            except Exception as e:
                return {"error": f"SerpAPI request failed: {e}"}

            if "error" in data:
                return {"error": data["error"]}

            organic = data.get("organic_results", [])
            if not organic:
                break

            all_results.extend(organic)
            time.sleep(2)

        FINANCE_TITLE_RE = re.compile(
            r"""(?ix)
            \b(
              finance|financial|analyst|accountant|accounting|
              bookkeeper|auditor|tax|treasury|banking|
              cfo|fp&a|controller|payroll|advisor|compliance|risk
            )\b
            """,
            re.IGNORECASE,
        )

        EXCLUDE_TITLE_RE = re.compile(
            r"""(?ix)
            \b(marketing|sales|technician|developer|engineer|teacher|driver|
               cleaner|warehouse|nurse|chef|plumber|construction|laborer|
               labourer|mechanic|operator|installer|waiter|barista|cook
              )\b
            """,
            re.IGNORECASE,
        )

        filtered = []
        for r in all_results:
            title = r.get("title", "") or ""
            snippet = r.get("snippet", "") or ""
            link = r.get("link", "") or ""

            if "@" not in snippet:
                continue

            if not link.startswith("https://uk.linkedin.com/jobs"):
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
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            "Accept-Language": "en-GB,en;q=0.9",
        }

        for job in filtered:
            url = job["link"]
            try:
                resp = requests.get(url, headers=headers, timeout=8)
                html = resp.text.lower()

                if any(p in html for p in CLOSED_PATTERNS):
                    continue

                open_listings.append(job)

            except requests.RequestException:
                continue

            time.sleep(0.8)

        open_listings = open_listings[:30]

        # 💾 --- Save to JSON (for local debugging) ---
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"linkedin_uk_finance_jobs_{timestamp}.json"
        output_path = os.path.join(os.path.dirname(__file__), filename)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(open_listings, f, indent=2, ensure_ascii=False)

        return {"results": open_listings, "count": len(open_listings)}

    except Exception as e:
        # Fallback to valid JSON error message
        return {"error": f"Unexpected error: {str(e)}"}


if __name__ == "__main__":
    result = main()
    # ✅ Always output valid JSON, no matter what happens
    print(json.dumps(result, indent=2, ensure_ascii=False))
