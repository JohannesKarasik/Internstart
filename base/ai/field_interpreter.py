import json, os
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def map_fields_to_answers(fields, user_profile):
    """
    fields: list of {"field_id": ..., "label": ...}
    user_profile: dict loaded from JSON
    """
    prompt = f"""
You are an assistant filling job application forms.

User data:
{json.dumps(user_profile, indent=2)}

Below are form fields. Respond in JSON with the best value for each field, or "skip" if no data fits.
Fields:
{json.dumps(fields, indent=2)}
Return JSON mapping of field_id -> answer.
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    try:
        text = resp.choices[0].message.content
        return json.loads(text)
    except Exception as e:
        print("⚠️ Parse error:", e)
        return {}
