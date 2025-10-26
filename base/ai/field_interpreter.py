import json
import os
import re
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def map_fields_to_answers(fields, user_profile):
    """
    Use AI to decide what values should go in each ATS field.

    Args:
        fields (list): [{"field_id": ..., "label": ...}]
        user_profile (dict): loaded from user JSON file.

    Returns:
        dict: {"field_id": "answer"}
    """

    if not fields or not user_profile:
        return {}

    prompt = f"""
You are a precise assistant filling out job application forms.

Here is the user's data:
{json.dumps(user_profile, indent=2, ensure_ascii=False)}

Below are the fields extracted from an application form.

For each field, decide what should be entered based on the user's information.
If there is no relevant data, respond with "skip".

Return ONLY valid JSON in this format:
{{"field_id": "answer", ...}}
Do NOT include explanations or commentary.

Fields:
{json.dumps(fields, indent=2, ensure_ascii=False)}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You fill job application forms using user data. "
                        "Always respond with clean JSON only, mapping each field id to an answer."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        text = response.choices[0].message.content.strip()

        # Attempt to parse JSON cleanly
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            print("⚠️ Could not parse model output:", text)
            return {}

    except Exception as e:
        print(f"❌ AI field mapping failed: {e}")
        return {}
