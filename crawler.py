import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def crawl_jobs_from_page(url):
    r = requests.get(url, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")
    jobs = []
    for link in soup.find_all("a", href=True):
        if any(x in link["href"] for x in ["jobs", "apply", "careers"]):
            jobs.append(urljoin(url, link["href"]))
    return jobs

if __name__ == "__main__":
    test_url = "https://example.com/careers"
    found_jobs = crawl_jobs_from_page(test_url)
    print(f"Found {len(found_jobs)} job links:")
    for job in found_jobs:
        print(job)