import requests
from bs4 import BeautifulSoup
import re
import json
import time

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
}

SEARCH_PHRASES = [
    '"send din ansøgning til" site:.dk',
    '"send din ansøgning på mail" site:.dk',
    '"send din ansøgning via e-mail" site:.dk',
    '"send your CV to" site:.dk',
    '"apply by emailing" site:.dk',
    '"send application to" site:.dk',
    '"email your resume to" site:.dk'
]


def get_duckduckgo_results(query, max_results=20):
    """Fetch search results from DuckDuckGo (plain HTML)."""
    url = f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    links = []
    for a in soup.select("a.result__a[href]"):
        href = a["href"]
        if href.startswith("http"):
            links.append(href)
    return links[:max_results]


def extract_emails_from_url(url):
    """Extract all visible emails from a web page."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if "text/html" not in r.headers.get("Content-Type", ""):
            return []
        text = r.text
        emails = re.findall(EMAIL_REGEX, text)
        # Filter out junk or generic emails
        filtered = [
            e for e in emails
            if not any(bad in e for bad in ["noreply", "no-reply", "info@", "support@", "kontakt@"])
        ]
        return list(set(filtered))
    except Exception as e:
        print(f"⚠️ Failed {url}: {e}")
        return []


def find_jobs_with_emails(pages_per_query=1):
    all_results = []
    for phrase in SEARCH_PHRASES:
        print(f"\n🔍 Searching for: {phrase}")
        links = get_duckduckgo_results(phrase, max_results=15 * pages_per_query)
        print(f"➡️ Found {len(links)} result links")

        for link in links:
            emails = extract_emails_from_url(link)
            if emails:
                print(f"✅ {link} → {emails}")
                all_results.append({"url": link, "emails": emails})
            time.sleep(1)  # polite crawling

    return all_results


if __name__ == "__main__":
    data = find_jobs_with_emails(pages_per_query=2)
    with open("email_jobs.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Done! Saved {len(data)} listings with emails to email_jobs.json")