# base/playwright_google_scraper.py

import json
import urllib.parse
import random
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time
import sys

QUERY = ('site:linkedin.com/jobs/denmark OR site:linkedin.com/jobs/view/ '
         '("send ansøgning" OR "send din ansøgning" OR "send dit CV" '
         'OR "ansøg via mail" OR "ansøg på mail" OR "send os din ansøgning" '
         'OR "@gmail.com" OR "@company.com")')
NUM_RESULTS = 50
TIME_FILTER = "tbs=qdr:m"

def build_url(query):
    encoded = urllib.parse.quote_plus(query)
    return f"https://www.google.dk/search?q={encoded}&num={NUM_RESULTS}&hl=da&gl=dk&{TIME_FILTER}"

def parse_google_html(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for g in soup.select("div.g"):
        h3 = g.select_one("h3")
        a = g.select_one("a[href]")
        snippet = ""
        snippet_tag = g.select_one("div.VwiC3b") or g.select_one("div.IsZvec") or g.select_one("span.aCOpRe")
        if snippet_tag:
            snippet = snippet_tag.get_text(" ", strip=True)
        if h3 and a:
            link = a["href"]
            title = h3.get_text(strip=True)
            if "linkedin.com/jobs" in link:
                results.append({"title": title, "url": link, "snippet": snippet})
    return results

def is_captcha(page):
    try:
        body_text = page.inner_text("body", timeout=2000)
        return ("Jeg er ikke en robot" in body_text or 
                "recaptcha" in body_text.lower() or 
                "unusual traffic" in body_text.lower())
    except:
        return False

def main():
    url = build_url(QUERY)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--start-maximized",
            ],
        )

        context = browser.new_context(
            locale="da-DK",
            viewport={"width": random.randint(1280, 1920), "height": random.randint(700, 1080)},
            user_agent=random.choice([
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            ]),
        )

        page = context.new_page()
        print("Navigating to:", url)
        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(2)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(3000)

        if is_captcha(page):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"captcha_{timestamp}.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"⚠️ CAPTCHA detected — screenshot saved to {screenshot_path}")
            browser.close()
            return

        html = page.content()
        with open("debug_google.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("💾 Saved raw HTML to debug_google.html for inspection")

        results = parse_google_html(html)
        browser.close()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_file = f"linkedin_denmark_jobs_{timestamp}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"✅ Saved {len(results)} listings to {output_file}")

if __name__ == "__main__":
    main()
