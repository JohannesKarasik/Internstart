import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import time

HEADERS = {
    "User-Agent": "InternstartBot/1.0 (+https://internstart.com)"
}

def crawl_jobs_from_page(url):
    """Collect potential job links from a company careers page."""
    print(f"🔍 Crawling: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return []
    
    soup = BeautifulSoup(r.text, "html.parser")
    jobs = []
    
    for link in soup.find_all("a", href=True):
        href = link["href"]
        # Only accept full Greenhouse job URLs
        if "greenhouse.io" in href and "/jobs/" in href:
            jobs.append(urljoin(url, href))
    return list(set(jobs))  # Remove duplicates


def is_public_apply_form(job_url):
    """
    Checks whether a job posting page has a public application form.
    Returns True if no login/account is needed.
    """
    try:
        r = requests.get(job_url, headers=HEADERS, timeout=10, allow_redirects=True)
        if r.status_code != 200:
            return False
        
        # Redirect to login or missing page
        if "login" in r.url.lower() or "404" in r.text.lower():
            return False
        
        soup = BeautifulSoup(r.text, "html.parser")
        form = soup.find("form")
        if not form:
            return False
        
        # CAPTCHA or JS-only tokens = skip
        if soup.find(class_="g-recaptcha") or "data-sitekey" in r.text:
            return False
        
        # Must have a POST action (true apply form)
        method = form.get("method", "get").lower()
        if method != "post":
            return False
        
        # Greenhouse open forms have "application_form" id or similar
        if "application" in form.get("id", "").lower():
            return True
        
        return True  # Default: assume open if we reach here

    except Exception as e:
        print(f"⚠️ Error probing {job_url}: {e}")
        return False


def find_public_jobs(company_url):
    """Find all valid, open job postings for one company."""
    job_links = crawl_jobs_from_page(company_url)
    public_jobs = []
    for job in job_links:
        if is_public_apply_form(job):
            print(f"✅ Open apply form: {job}")
            public_jobs.append(job)
        else:
            print(f"❌ Skipped (login or invalid): {job}")
        time.sleep(1)  # polite delay
    return public_jobs


def crawl_greenhouse_index(limit=5):
    """Get companies using Greenhouse and crawl a few of them."""
    base = "https://boards.greenhouse.io/"
    print("🌍 Fetching Greenhouse company boards...")
    r = requests.get(base, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")
    boards = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.startswith("/"):
            boards.append(urljoin(base, href))
    boards = list(set(boards))
    print(f"Found {len(boards)} company boards.")
    return boards[:limit]


if __name__ == "__main__":
    all_open_jobs = {}

    # Step 1: find some companies hosted on Greenhouse
    company_boards = crawl_greenhouse_index(limit=5)

    # Step 2: crawl each company’s board and detect open jobs
    for board_url in company_boards:
        print(f"\n🏢 Checking company board: {board_url}")
        open_jobs = find_public_jobs(board_url)
        if open_jobs:
            all_open_jobs[board_url] = open_jobs

    # Step 3: save results
    with open("open_jobs.json", "w", encoding="utf-8") as f:
        json.dump(all_open_jobs, f, indent=2, ensure_ascii=False)

    print("\n✅ Done! Results saved to open_jobs.json")