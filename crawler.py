import requests
from bs4 import BeautifulSoup
import re
import json
import time

# --- CONFIG ---
EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
}

# U.S.-focused search phrases
SEARCH_PHRASES = [
    '"send your resume to" site:.com',
    '"apply by emailing" site:.com',
    '"send application to" site:.com',
    '"email your resume to" site:.com',
    '"send your CV to" site:.us',
    '"apply via email" site:.com',
    '"email applications to" site:.com'
]

# --- SCRAPER FUNCTIONS ---

def get_bing_results(query, max_results=20):
    """Fetch search results from Bing (plain HTML)."""
    url = f"https://www.bing.com/search?q={query.replace(' ', '+')}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    links = []
    for a in soup.select("li.b_algo h2 a[href]"):
        href = a["href"]
        if href.startswith("http"):
            links.append(href)
    return links[:max_results]


def extract_emails_from_url(url):
    """Extract visible emails from a webpage."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if "text/html" not in r.headers.get("Content-Type", ""):
            return []
        text = r.text
        emails = re.findall(EMAIL_REGEX, text)
        # Filter out generic or irrelevant emails
        filtered = [
            e for e in emails
            if not any(bad in e for bad in [
                "noreply", "no-reply", "info@", "support@", "contact@", "sales@", "help@"
            ])
        ]
        return list(set(filtered))
    except Exception as e:
        print(f"⚠️ Failed {url}: {e}")
        return []


def find_jobs_with_emails(pages_per_query=1):
    """Search the web for job pages containing email addresses."""
    all_results = []
    for phrase in SEARCH_PHRASES:
        print(f"\n🔍 Searching for: {phrase}")
        links = get_bing_results(phrase, max_results=15 * pages_per_query)
        print(f"➡️ Found {len(links)} result links")

        for link in links:
            emails = extract_emails_from_url(link)
            if emails:
                print(f"✅ {link} → {emails}")
                all_results.append({"url": link, "emails": emails})
            time.sleep(1)  # polite crawling
    return all_results


# --- MAIN EXECUTION ---

if __name__ == "__main__":
    print("🌎 Starting U.S. Email Job Crawler...")
    data = find_jobs_with_emails(pages_per_query=2)
    with open("email_jobs_us.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Done! Saved {len(data)} listings with emails to email_jobs_us.json")