import json
import os
import re
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _extract_json(text: str):
    """
    Try to pull a JSON object from the model output reliably.
    Accepts either a raw JSON object or JSON fenced in code blocks.
    """
    if not text:
        return None
    text = text.strip()

    # Remove common markdown fences if present
    if text.startswith("```"):
        # strip first fence
        text = re.sub(r"^```(?:json)?\s*", "", text)
        # strip trailing fence
        text = re.sub(r"\s*```$", "", text)

    # First attempt: direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Fallback: greedy object capture
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def map_fields_to_answers(fields, user_profile):
    """
    Use AI to decide what values should go in each ATS field.

    Args:
        fields (list): items like
            {
              "field_id": "42",
              "label": "Highest education level",
              "type": "select" | "text" | "radio" | "checkbox" | "contenteditable",
              "options": ["Bachelor", "Master", "PhD"]   # may be absent
            }
        user_profile (dict): loaded from user JSON file.

    Returns:
        dict: {"field_id": <answer or {"value": "..."} or "skip">}
    """

    if not fields or not user_profile:
        return {}

    # ---- Prompt with strict rules about options & format ----
    prompt = f"""
You fill job-application forms **precisely** using the user's profile.

UserProfile JSON:
{json.dumps(user_profile, indent=2, ensure_ascii=False)}

TASK
For each field below, provide the best value using the profile. If unknown, return "skip".

CRITICAL RULES
- If a field includes an "options" array, your answer MUST be EXACTLY one of those option strings (case & accents must match).
- Prefer localized answers that appear in "options" when present (e.g., Danish labels like "Vælg" are placeholders and should not be chosen).
- For yes/no questions: if options are localized, select the localized option; otherwise use "Yes" or "No".
- Phone country-code selects: choose the option that matches the user's dial code (e.g., "+45").
- Dates: if the form asks for a date but none is available, return "skip".
- Never invent employers, dates, or degrees not present in the profile.

OUTPUT FORMAT
- Return ONLY a single JSON object mapping field_id -> answer.
- Answer may be a plain string, e.g. {{"42": "Bachelor"}}
  OR an object with a "value" key, e.g. {{"42": {{"value": "Bachelor"}}}}.
- Do NOT include explanations.

FIELDS (each item has field_id, label, type, and may include options):
{json.dumps(fields, indent=2, ensure_ascii=False)}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise form-filling agent. "
                        "Always return a single JSON object with field_id -> answer. "
                        "When options are provided, select exactly one of them."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        raw = response.choices[0].message.content.strip()
        data = _extract_json(raw)
        if not isinstance(data, dict):
            print("⚠️ Could not parse model output:", raw)
            return {}

        # Optional light normalization: ensure values are strings or dicts
        cleaned = {}
        for k, v in data.items():
            # Accept "skip" as-is
            if isinstance(v, str):
                cleaned[str(k)] = v.strip()
            elif isinstance(v, dict):
                # keep only 'value' if present
                if "value" in v and isinstance(v["value"], str):
                    cleaned[str(k)] = {"value": v["value"].strip()}
                else:
                    # unknown dict shape -> stringify just in case
                    cleaned[str(k)] = json.dumps(v, ensure_ascii=False)
            else:
                # numbers/bools -> stringify
                cleaned[str(k)] = str(v)

        return cleaned

    except Exception as e:
        print(f"❌ AI field mapping failed: {e}")
        return {}
