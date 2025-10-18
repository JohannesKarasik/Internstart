import json
import re
import time
from playwright.sync_api import sync_playwright

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

def crawl_indeed_for_emails(query="software intern", location="denmark", pages=1):
    """Search Indeed for job listings and extract any emails from postings."""
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = browser.new_page()

        for page_num in range(pages):
            url = f"https://dk.indeed.com/jobs?q={query}&l={location}&start={page_num*10}"
            print(f"🔍 Searching: {url}")
            page.goto(url, timeout=30000)
            page.wait_for_timeout(3000)  # wait for dynamic content to load

            job_links = [
                a.get_attribute("href")
                for a in page.query_selector_all("a[data-jk]")
            ]
            job_links = [f"https://dk.indeed.com{l}" if l.startswith("/") else l for l in job_links]
            job_links = list(set(job_links))
            print(f"➡️ Found {len(job_links)} job links on page {page_num+1}")

            for job_url in job_links:
                try:
                    page.goto(job_url, timeout=30000)
                    page.wait_for_timeout(2000)
                    text = page.content()
                    emails = re.findall(EMAIL_REGEX, text)
                    # Filter only relevant job emails
                    emails = [
                        e for e in emails
                        if any(keyword in e for keyword in ["hr", "career", "jobs", "apply", "recruit", "talent"])
                    ]
                    if emails:
                        print(f"✅ {job_url} → {emails}")
                        results.append({"url": job_url, "emails": emails})
                except Exception as e:
                    print(f"⚠️ Error with {job_url}: {e}")
                time.sleep(1)

        browser.close()

    return results


if __name__ == "__main__":
    results = crawl_indeed_for_emails(query="software intern", location="Denmark", pages=2)
    with open("indeed_emails.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Done! Saved {len(results)} listings with email addresses to indeed_emails.json")