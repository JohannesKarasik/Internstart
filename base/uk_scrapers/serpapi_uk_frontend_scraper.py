import os
import sys       # 🆕 add this line
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
            'site:linkedin.com/jobs inurl:uk '
            '("send your CV" OR "apply by email" OR "email your application" OR "send your application to") '
            '("@co.uk" OR "@gmail.com" OR "@outlook.com") '
            '("frontend developer" OR "front-end developer" OR "frontend engineer" OR "front-end engineer" '
            'OR "web developer" OR "react developer" OR "javascript developer" OR "vue developer" '
            'OR "next.js developer" OR "html css javascript" OR "ui developer" OR "frontend designer" '
            'OR "web designer" OR "frontend software engineer" OR "software engineer frontend" '
            'OR "front end developer" OR "front end engineer" OR "ui engineer" OR "react js developer")'
        )

        # 🔑 --- API Key ---
        API_KEY = os.getenv("SERPAPI_API_KEY")
        if not API_KEY:
            return {"error": "SERPAPI_API_KEY not found in environment variables."}

        print("🔍 Fetching up to 100 UK frontend developer listings from SerpAPI ...", file=sys.stderr)

        # 🌍 --- Base Search Parameters ---
        base_params = {
            "engine": "google",
            "q": QUERY,
            "num": 10,
            "hl": "en",
            "gl": "uk",
            "location": "United Kingdom",
            "filter": "0",
            "tbs": "qdr:m",  # past month for broader coverage
            "api_key": API_KEY,
        }

        # 🌀 --- Fetch up to 100 results (10 pages) ---
        all_results = []
        for start in range(0, 100, 10):
            params = base_params.copy()
            params["start"] = start
            print(f"📄 Fetching page starting at {start}...", file=sys.stderr)

            try:
                data = GoogleSearch(params).get_dict()
            except Exception as e:
                return {"error": f"SerpAPI request failed: {e}"}

            if "error" in data:
                return {"error": data["error"]}

            organic = data.get("organic_results", [])
            if not organic:
                print("⏹️ No more results found.", file=sys.stderr)
                break

            all_results.extend(organic)
            time.sleep(2)

        print(f"🌍 Total raw results fetched: {len(all_results)}", file=sys.stderr)

        # 🎯 --- Frontend filters ---
        FRONTEND_KEYWORDS = [
            "frontend", "front-end", "front end", "react", "vue", "nextjs", "next.js",
            "javascript", "typescript", "web developer", "ui developer", "ui engineer",
            "web designer", "html", "css", "sass", "tailwind", "bootstrap",
            "front-end engineer", "frontend engineer", "frontend developer",
            "react developer", "reactjs", "react.js", "angular", "svelte"
        ]

        EXCLUDE_KEYWORDS = [
            "marketing", "finance", "accountant", "auditor", "bookkeeper",
            "driver", "technician", "warehouse", "nurse", "teacher", "chef",
            "construction", "plumber", "operator", "retail", "sales",
            "customer service", "hospitality", "barista", "cleaner", "support",
            "electrician", "mechanic", "waiter"
        ]

        # 🧹 --- Filter results ---
        filtered = []
        for r in all_results:
            title = r.get("title", "") or ""
            snippet = r.get("snippet", "") or ""
            link = r.get("link", "") or ""

            if "@" not in snippet:
                continue

            text = (title + " " + snippet + " " + link).lower()

            if not any(x in text for x in [" uk ", "united kingdom", ".co.uk", "/uk/"]):
                continue

            if any(bad in text for bad in EXCLUDE_KEYWORDS):
                continue

            if not any(keyword in text for keyword in FRONTEND_KEYWORDS):
                continue

            filtered.append({
                "title": title.strip(),
                "link": link.strip(),
                "snippet": snippet.strip(),
            })

        print(f"✅ Filtered down to {len(filtered)} frontend listings before deduplication and closure check.", file=sys.stderr)

        # 🔁 --- Deduplication ---
        seen_emails = set()
        seen_links = set()
        seen_companies = set()

        def extract_email(text):
            match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
            return match.group(0).lower() if match else None

        def extract_company(title):
            match = re.search(r"at ([A-Za-z0-9&.,' -]+)", title)
            return match.group(1).strip().lower() if match else None

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

        for job in filtered:
            url = job["link"]
            snippet = job["snippet"].lower()
            title = job["title"]

            email = extract_email(snippet)
            company = extract_company(title)
            link_root = re.sub(r"\?.*$", "", url).strip().lower()

            if (email and email in seen_emails) or link_root in seen_links or (company and company in seen_companies):
                continue

            if email:
                seen_emails.add(email)
            seen_links.add(link_root)
            if company:
                seen_companies.add(company)

            try:
                resp = requests.get(url, headers=headers, timeout=5)
                html = resp.text.lower()
                if any(p in html for p in CLOSED_PATTERNS):
                    continue
                open_listings.append(job)
            except requests.RequestException:
                continue

            time.sleep(0.8)

        open_listings = open_listings[:100]

        # 💾 --- Save to JSON ---
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"linkedin_uk_frontend_jobs_{timestamp}.json"
        output_path = os.path.join(os.path.dirname(__file__), filename)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(open_listings, f, indent=2, ensure_ascii=False)

        print(f"✅ Saved {len(open_listings)} open UK frontend listings to {filename}", file=sys.stderr)
        return {"results": open_listings, "count": len(open_listings)}

    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, ensure_ascii=False))
