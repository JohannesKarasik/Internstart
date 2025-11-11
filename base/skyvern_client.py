# base/skyvern_client.py
import os
import requests


SKYVERN_API_KEY = os.getenv("SKYVERN_API_KEY")
SKYVERN_API_URL = "https://api.skyvern.com/v1/run/tasks"

def fill_job_application(user, job_url, resume_url=None):
    prompt = f"""
    Go to {job_url}.
    Fill out the job application form using the following candidate details:

    Name: {user.full_name}
    Email: {user.email}
    Phone: {user.phone}
    LinkedIn: {user.linkedin_url}
    Address: {user.address}

    If there's a question about work authorization, select 'Yes'.
    If asked for a cover letter, write a short and professional paragraph about
    why this candidate is a good fit for the role based on their resume.

    Upload the resume from: {resume_url or user.resume_url}

    After filling in all required fields, click Submit.
    Confirm that the application was submitted successfully.
    """

    payload = {
        "prompt": prompt,
        "url": job_url,
        "engine": "skyvern-2.0",
        "proxy_location": "RESIDENTIAL_GB",
        "max_steps": 25,
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": SKYVERN_API_KEY,
    }

    response = requests.post(SKYVERN_API_URL, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()
