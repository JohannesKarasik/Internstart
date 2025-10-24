# base/playwright_google_scraper.py
import json
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time
import sys

QUERY = ('site:linkedin.com/jobs/denmark OR site:linkedin.com/jobs/view/ '
         '("send ansøgning" OR "send din ansøgning" OR "send dit CV" '
         'OR "ansøg via mail" OR "ansøg på mail" OR "send os din ansøgning")')
NUM_RESULTS = 50
TIME_FILTER = "tbs=qdr:m"  # past month

def build_url(query, num=NUM_RESULTS):
    encoded = urllib.parse.quote_plus(query)
    # hl=da (language), gl=dk (geolocation)
    return f"https://www.google.com/search?q={encoded}&num={num}&hl=da&gl=dk&{TIME_FILTER}"

def parse_google_html(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    # google's search results block
    for g in soup.select("div.g"):
        h3 = g.select_one("h3")
        a = g.select_one("a[href]")
        # snippet tag varies — try a few
        snippet = ""
        snippet_tag = g.select_one("div.VwiC3b") or g.select_one("span.aCOpRe") or g.select_one("div.IsZvec")
        if snippet_tag:
            snippet = snippet_tag.get_text(" ", strip=True)
        if h3 and a:
            link = a["href"]
            title = h3.get_text(strip=True)
            if "linkedin.com/jobs" in link:
                results.append({"title": title, "url": link, "snippet": snippet})
    return results

def is_captcha(page):
    # very simple detection: google captcha contains 'Jeg er ikke en robot' or reCAPTCHA elements
    text = page.inner_text("body", timeout=2000) if page else ""
    return "Jeg er ikke en robot" in text or "Our systems have detected unusual traffic" in text or "recaptcha" in text.lower()

def main():
    url = build_url(QUERY)
    with sync_playwright() as p:
        # Use chromium; set headless=False if you want to watch (may require DISPLAY)
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(locale="da-DK", user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ))
        page = context.new_page()
        print("Navigating to:", url)
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(1.2)  # give scripts on page a moment

        if is_captcha(page):
            # save screenshot for debugging and exit
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"captcha_{ts}.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print("⚠️ CAPTCHA detected — saved screenshot to", screenshot_path, file=sys.stderr)
            browser.close()
            return

        html = page.content()
        results = parse_google_html(html)

        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_file = f"linkedin_denmark_jobs_{timestamp}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"✅ Saved {len(results)} listings to {output_file}")
        browser.close()

if __name__ == "__main__":
    main()
