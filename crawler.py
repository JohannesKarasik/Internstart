import re, json, time, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# -------------------------------- CONFIG -------------------------------- #
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
}
EMAIL_STD = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

OBF_PAIRS = [
    (r"\s*\[\s*at\s*\]|\s*\(\s*at\s*\)\s*|\s+at\s+", "@"),
    (r"\s*\[\s*dot\s*\]|\s*\(\s*dot\s*\)\s*|\s+dot\s+", "."),
    (r"\s*\{\s*at\s*\}\s*", "@"),
    (r"\s*\{\s*dot\s*\}\s*", "."),
]

POS = ("apply", "application", "email your resume", "send your resume",
       "send cv", "cover letter", "job", "internship", "position")
NEG = ("support@", "sales@", "press@", "media@", "privacy@", "legal@", "contact@", "info@")

SOURCES = {
    # Minimal, high-yield public sources with emails allowed
    "hn": "https://news.ycombinator.com/item?id=42389642",  # example "Who's Hiring" thread
    "reddit": "https://www.reddit.com/r/forhire/",
    "mit": "https://math.mit.edu/about/employment/",
    "harvard": "https://academicpositions.harvard.edu/",
}

# -------------------------------- UTILITIES -------------------------------- #
def fetch_html(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if "text/html" not in r.headers.get("Content-Type", ""):
            return ""
        return r.text
    except Exception as e:
        print(f"⚠️  Failed to fetch {url}: {e}")
        return ""

def extract_emails(text):
    std = set(EMAIL_STD.findall(text))
    deob = text
    for pat, repl in OBF_PAIRS:
        deob = re.sub(pat, repl, deob, flags=re.I)
    std |= set(EMAIL_STD.findall(deob))
    return list(std)

def score_email(email, text, window=200):
    """Higher = more likely to be application email"""
    idx = text.lower().find(email.lower().split("@")[0])
    if idx == -1: idx = text.lower().find(email.lower())
    start = max(0, idx - window)
    end = min(len(text), idx + window)
    ctx = text[start:end].lower()
    score = 0
    score += sum(1 for w in POS if w in ctx) * 2
    score -= sum(1 for w in NEG if w in email.lower() or w in ctx) * 2
    return score, text[start:end].strip()

# -------------------------------- CRAWLERS -------------------------------- #
def crawl_hn():
    """Parse Hacker News 'Who’s Hiring' thread for emails."""
    html = fetch_html(SOURCES["hn"])
    soup = BeautifulSoup(html, "html.parser")
    posts = soup.find_all("span", class_="commtext")
    results = []
    for post in posts:
        text = post.get_text(" ", strip=True)
        for email in extract_emails(text):
            s, ctx = score_email(email, text)
            if s > 1:
                results.append({
                    "source": "HackerNews",
                    "url": SOURCES["hn"],
                    "email": email,
                    "context": ctx,
                    "score": s,
                })
    return results

def crawl_reddit():
    """Collect top r/forhire posts for visible emails."""
    url = SOURCES["reddit"]
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    posts = [a["href"] for a in soup.select("a[href*='/r/forhire/comments/']")]
    results = []
    for p in posts[:10]:
        full = urljoin(url, p)
        text = fetch_html(full)
        for email in extract_emails(text):
            s, ctx = score_email(email, text)
            if s > 1:
                results.append({
                    "source": "Reddit",
                    "url": full,
                    "email": email,
                    "context": ctx,
                    "score": s,
                })
        time.sleep(1)
    return results

def crawl_university(name, url):
    """Generic small-site crawler for career pages."""
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    links = [urljoin(url, a["href"]) for a in soup.select("a[href]")]
    results = []
    for link in links:
        if not any(x in link.lower() for x in ["job", "career", "position", "employment"]):
            continue
        text = fetch_html(link)
        for email in extract_emails(text):
            s, ctx = score_email(email, text)
            if s > 1:
                results.append({
                    "source": name,
                    "url": link,
                    "email": email,
                    "context": ctx,
                    "score": s,
                })
        time.sleep(1)
    return results

# -------------------------------- MAIN -------------------------------- #
def main():
    print("🌎 Starting U.S. Email Job Crawler...\n")

    all_results = []
    all_results += crawl_hn()
    all_results += crawl_reddit()
    all_results += crawl_university("MIT", SOURCES["mit"])
    all_results += crawl_university("Harvard", SOURCES["harvard"])

    # Deduplicate
    uniq = {}
    for r in all_results:
        key = (r["email"], r["url"])
        if key not in uniq:
            uniq[key] = r
    data = list(uniq.values())

    with open("email_jobs_us.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Done! Saved {len(data)} email-based job listings to email_jobs_us.json")

# ---------------------------------------------------------------------- #
if __name__ == "__main__":
    main()