import requests, re, json, time
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

SEARCH_QUERIES = [
    '"send your resume to" site:craigslist.org',
    '"apply by emailing" site:startup.jobs',
    '"send your CV to" site:angel.co',
    '"apply via email" site:weworkremotely.com',
]

def duck_search(query, max_results=10):
    """Return a list of result URLs from DuckDuckGo Lite."""
    url = f"https://lite.duckduckgo.com/lite/?q={query.replace(' ', '+')}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")
    links = [a["href"] for a in soup.select("a[href^='http']")]
    return links[:max_results]

def extract_emails(url):
    """Extract likely job-application emails from a page."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if "text/html" not in r.headers.get("Content-Type", ""):
            return []
        text = r.text
        emails = re.findall(EMAIL_REGEX, text)
        context_matches = []
        for e in emails:
            snippet_start = text.lower().find(e.lower().split("@")[0])
            snippet = text[snippet_start-150:snippet_start+150].lower()
            if any(word in snippet for word in ["resume", "apply", "cv", "job", "position"]):
                context_matches.append(e)
        return list(set(context_matches))
    except Exception as e:
        print(f"⚠️ {url}: {e}")
        return []

def crawl_email_jobs():
    results = []
    for query in SEARCH_QUERIES:
        print(f"\n🔍 Searching: {query}")
        urls = duck_search(query)
        print(f"➡️ Found {len(urls)} links")
        for u in urls:
            emails = extract_emails(u)
            if emails:
                print(f"✅ {u} → {emails}")
                results.append({"url": u, "emails": emails})
            time.sleep(1)
    return results

if __name__ == "__main__":
    print("🌎 Starting improved U.S. email job crawler...\n")
    data = crawl_email_jobs()
    with open("email_jobs_us.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"\n✅ Done! Found {len(data)} listings with emails → email_jobs_us.json")