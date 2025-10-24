import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import time
import random

def scrape_google_jobs(query, num_results=30):
    # Encode query for URL
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/search?q={encoded_query}&num={num_results}&tbs=qdr:m"  # past month filter

    headers = {
        "User-Agent": random.choice([
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/119.0",
        ])
    }

    print(f"🔍 Fetching Google results for query:\n{query}\n")

    res = requests.get(url, headers=headers)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    results = []

    for g in soup.select("div.g"):
        title_tag = g.select_one("h3")
        link_tag = g.select_one("a")
        snippet_tag = g.select_one("div.VwiC3b")

        if title_tag and link_tag:
            title = title_tag.get_text(strip=True)
            link = link_tag["href"]
            snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

            # Only LinkedIn job URLs
            if "linkedin.com/jobs" in link:
                results.append({
                    "title": title,
                    "url": link,
                    "snippet": snippet
                })

    return results


if __name__ == "__main__":
    query = '''site:linkedin.com/jobs/denmark OR site:linkedin.com/jobs/view/ ("send ansøgning" OR "send din ansøgning" OR "send dit CV" OR "ansøg via mail" OR "ansøg på mail" OR "send os din ansøgning")'''

    data = scrape_google_jobs(query)

    # Save JSON file
    output_file = "linkedin_denmark_jobs.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved {len(data)} job listings to {output_file}")
