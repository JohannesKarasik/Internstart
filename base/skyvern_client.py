import os
import requests

SKYVERN_API_KEY = os.getenv("SKYVERN_API_KEY")
SKYVERN_API_URL = "https://api.skyvern.com/v1/run/tasks"

def run_skyvern_task(prompt, url=None, proxy="RESIDENTIAL_GB", engine="skyvern-2.0", webhook=None):
    """
    Run a Skyvern automation task.
    - prompt: string describing what to do
    - url: starting URL (optional)
    - proxy: e.g. RESIDENTIAL_GB for UK
    - engine: skyvern-2.0 (default)
    - webhook: optional callback URL
    """
    payload = {
        "prompt": prompt,
        "url": url,
        "engine": engine,
        "proxy_location": proxy,
        "max_steps": 20,
    }
    if webhook:
        payload["webhook_url"] = webhook

    headers = {
        "Content-Type": "application/json",
        "x-api-key": SKYVERN_API_KEY,
    }

    res = requests.post(SKYVERN_API_URL, json=payload, headers=headers)
    if res.status_code != 200:
        raise Exception(f"Skyvern error {res.status_code}: {res.text}")
    return res.json()
