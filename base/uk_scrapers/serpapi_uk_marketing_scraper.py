import os
import json
from datetime import datetime
from serpapi import GoogleSearch
import re

# 🔑 --- API Key ---
API_KEY = os.getenv("SERPAPI_API_KEY")
if not API_KEY:
    raise EnvironmentError("❌ SERPAPI_API_KEY not found in environment variables.")

print("🔍 Fetching LinkedIn marketing jobs (last 3 days, with visible emails) ...")

# 🌍 --- LinkedIn Search Parameters (using SerpAPI LinkedIn engine)
params = {
    "engine": "linkedin_jobs",
    "q": "marketing",  # keyword
    "location": "United Kingdom",
    "time": "past_72_hours",  # <-- ensures freshness
    "api_key": API_KEY,
    "count": 20,  # number of jobs to fetch
}

# 🌀 --- Perform search ---
search = GoogleSearch(params)
data = search.get_dict()

if "error" in data:
    print(f"⚠️ SerpAPI error: {data['error']}")
    results = []
else:
    results = data.get("jobs_results", []) or []
    print(f"📄 Fetched {len(results)} fresh LinkedIn results...")

# 🧹 --- Filter only listings that include visible emails
filtered = []
for job in results:
    description = job.get("description", "")
    if "@" not in description:
        continue

    # Extract email
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", description)
    email = email_match.group(0) if email_match else None

    filtered.append({
        "title": job.get("title"),
        "company": job.get("company_name"),
        "link": job.get("link"),
        "location": job.get("location"),
        "email": email,
        "snippet": description[:250] + "..." if description else "",
    })

# 💾 --- Save to JSON
timestamp = datetime.now().strftime("%Y%m%d_%H%M")
filename = f"linkedin_marketing_fresh_{timestamp}.json"
output_path = os.path.join(os.path.dirname(__file__), filename)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(filtered, f, indent=2, ensure_ascii=False)

print(f"✅ Saved {len(filtered)} listings (past 3 days, with visible emails) to {filename}")
