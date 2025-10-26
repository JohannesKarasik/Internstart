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
            'site:linkedin.com/jobs inurl:uk '
            '("send your CV" OR "apply by email" OR "email your application" OR "send your application to") '
            '("@co.uk" OR "@gmail.com" OR "@outlook.com") '
            '(accounting OR finance OR "financial analyst" OR "financial controller" OR "investment analyst" '
            'OR "accountant" OR "bookkeeper" OR "auditor" OR "audit assistant" OR "assistant accountant" '
            'OR "tax consultant" OR "tax assistant" OR "banking" OR "treasury analyst" OR "finance manager" '
            'OR "financial planning" OR "FP&A" OR "finance director" OR "CFO" OR "financial services" '
            'OR "credit analyst" OR "financial advisor" OR "compliance" OR "risk analyst" '
            'OR "mortgage advisor" OR "insurance" OR "corporate finance" OR "fund accountant" '
            'OR "payroll" OR "bookkeeping" OR "reconciliation" OR "controller" OR "treasurer" '
            'OR "accounting assistant" OR "audit trainee" OR "finance graduate" OR "financial administrator")'
        )

        # 🔑 --- API Key ---
        API_KEY = os.getenv("SERPAPI_API_KEY")
        if not API_KEY:
            return {"error": "SERPAPI_API_KEY not found in environment variables."}

        print("🔍 Fetching up to 100 UK finance listings from SerpAPI ...")

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
            print(f"📄 Fetching page starting at {start}...")

            try:
                data = GoogleSearch(params).get_dict()
            except Exception as e:
                return {"error": f"SerpAPI request failed: {e}"}

            if "error" in data:
                return {"error": data["error"]}

            organic = data.get("organic_results", [])
            if not organic:
                print("⏹️ No more results found.")
                break

            all_results.extend(organic)
            time.sleep(2)

        print(f"🌍 Total raw results fetched: {len(all_results)}")

        # 🎯 --- Finance filters ---
        FINANCE_KEYWORDS = [
            "finance", "financial", "accounting", "accountant", "auditor", "audit",
            "analyst", "controller", "treasury", "banking", "investment", "payroll",
            "cfo", "fp&a", "tax", "risk", "compliance", "credit", "wealth", "equity",
            "treasurer", "advisor", "consultant", "bookkeeping", "fund", "portfolio",
            "mortgage", "insurance", "corporate finance", "reconciliation",
            "finance assistant", "assistant accountant", "financial administrator",
            "audit trainee", "finance graduate", "financial services"
        ]

        EXCLUDE_KEYWORDS = [
            "marketing", "developer", "engineer", "technician", "nurse", "teacher",
            "chef", "sales", "recruiter", "designer", "social media", "pr",
            "construction", "warehouse", "driver", "operator", "customer service",
            "hospitality", "bartender", "barista", "retail", "cleaner", "graphic",
            "web", "it ", "software", "frontend", "backend"
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

            if not any(fin in text for fin in FINANCE_KEYWORDS):
                continue

            filtered.append({
                "title": title.strip(),
                "link": link.strip(),
                "snippet": snippet.strip(),
            })

        print(f"✅ Filtered down to {len(filtered)} finance-related listings before deduplication and closure check.")

        # 🔁 --- Deduplication (email, link, company) ---
        seen_emails = set()
        seen_links = set()
        seen_companies = set()

        def extract_email(text):
            match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
            return match.group(0).lower() if match else None

        def extract_company(title):
            match = re.search(r"at ([A-Za-z0-9&.,' -]+)", title)
            return match.group(1).strip().lower() if match else None

        # 🔎 --- Check open jobs ---
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
                resp = requests.get(url, headers=headers, timeout=8)
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
        filename = f"linkedin_uk_finance_jobs_{timestamp}.json"
        output_path = os.path.join(os.path.dirname(__file__), filename)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(open_listings, f, indent=2, ensure_ascii=False)

        print(f"✅ Saved {len(open_listings)} open UK finance listings to {filename}")
        return {"results": open_listings, "count": len(open_listings)}

    except Exception as e:
        # Always return valid JSON error
        return {"error": f"Unexpected error: {str(e)}"}


if __name__ == "__main__":
    result = main()
    # ✅ Always output valid JSON
    print(json.dumps(result, indent=2, ensure_ascii=False))
