import requests
from bs4 import BeautifulSoup
import re
import json
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

def search_indeed(query="software intern", location="denmark", pages=1):
    """Collect listing URLs from Indeed search results."""
    results = []
    base = "https://dk.indeed.com/jobs"
    for page in range(pages):
        params = {"q": query, "l": location, "start": page * 10}
        r = requests.get(base, headers=HEADERS, params=params, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for link in soup.select("a[data-jk]"):
            jk = link.get("data-jk")
            if jk:
                job_url = f"https://dk.indeed.com/viewjob?jk={jk}"
                results.append(job_url)
        time.sleep(1)
    return list(set(results))


def extract_email_from_job(url):
    """Open a job page and extract email addresses."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        emails = re.findall(EMAIL_REGEX, text)
        return list(set(emails))
    except Exception as e:
        print(f"⚠️ Error {url}: {e}")
        return []


def crawl_indeed_for_emails(query="intern", location="denmark", pages=1):
    job_links = search_indeed(query, location, pages)
    print(f"🔍 Found {len(job_links)} job listings")

    data = []
    for job in job_links:
        emails = extract_email_from_job(job)
        if emails:
            print(f"✅ {job} → {emails}")
            data.append({"url": job, "emails": emails})
        time.sleep(1)
    return data


if __name__ == "__main__":
    results = crawl_indeed_for_emails(query="software intern", location="Denmark", pages=2)

    with open("indeed_emails.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Done! Saved {len(results)} listings with email addresses to indeed_emails.json")