import requests
from bs4 import BeautifulSoup
import re
import json
import time

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

def find_jobs_with_emails(query, pages=2):
    results = []
    for page in range(pages):
        start = page * 10
        url = f"https://www.google.com/search?q={query}&start={start}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")

        # Extract all visible result links
        for a in soup.select("a[href]"):
            href = a["href"]
            if href.startswith("/url?q="):
                target_url = href.split("/url?q=")[1].split("&")[0]
                # Visit the target page
                try:
                    page_r = requests.get(target_url, headers=headers, timeout=8)
                    text = page_r.text
                    emails = re.findall(EMAIL_REGEX, text)
                    # Filter relevant emails
                    relevant = [
                        e for e in emails
                        if any(x in e for x in ["hr", "career", "jobs", "apply", "recruit", "work"])
                    ]
                    if relevant:
                        print(f"✅ {target_url} → {relevant}")
                        results.append({"url": target_url, "emails": relevant})
                except Exception as e:
                    print(f"⚠️ Skipped {target_url}: {e}")
                time.sleep(1)

    return results

if __name__ == "__main__":
    data = find_jobs_with_emails('"send your CV to" site:.dk', pages=2)
    with open("email_jobs.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Done! Saved {len(data)} listings with emails to email_jobs.json")