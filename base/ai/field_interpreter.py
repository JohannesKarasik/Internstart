# base/ai/field_interpreter.py
import json
import os
import re
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Synonym / translation hints ---
HINTS = {
    "education_levels": {
        "bachelor": ["bachelor", "bachelorgrad", "ba", "b.sc.", "b.eng."],
        "master": ["kandidat", "master", "cand."],
        "phd": ["ph.d.", "phd"],
        "high_school": ["gymnasial", "high school", "studentereksamen"],
        "other": ["andet", "other", "n/a"]
    },
    "fields_of_study": {
        "marketing": ["marketing", "markedsføring", "kommunikation", "marketing & kommunikation"],
        "computer_science": ["datalogi", "computer science", "software", "it"],
        "business": ["business", "økonomi", "finance", "finans", "erhvervsøkonomi"],
        "design": ["design", "grafisk design", "ux", "ui"],
        "other": ["andet", "other", "n/a"]
    },
    "yes": ["ja", "yes"],
    "no": ["nej", "no"]
}

# --- Few-shot examples ---
FEW_SHOT = [
    {
        "user": {"field_of_study": "Marketing", "highest_education_level": "Bachelor’s Degree"},
        "fields": [{
            "field_id": "A",
            "label": "Fagområde for uddannelse",
            "type": "select",
            "options": ["IT", "Markedsføring", "Andet område"],
        }],
        "answer": {"A": "Markedsføring"}
    },
    {
        "user": {"highest_education_level": "Bachelor’s Degree"},
        "fields": [{
            "field_id": "B",
            "label": "Titel på uddannelse",
            "type": "select",
            "options": ["Bachelor", "Kandidat", "Ph.d.", "Andet"],
        }],
        "answer": {"B": "Bachelor"}
    },
    {
        "user": {"under_education": "yes"},
        "fields": [{
            "field_id": "C",
            "label": "Totalt antal års arbejdserfaring",
            "type": "select",
            "options": ["0 År", "1 År", "2-3 År", "4+ År"],
        }],
        "answer": {"C": "0 År"}
    },
    {
        "user": {},
        "fields": [{
            "field_id": "D",
            "label": "Venligst besvar, om vi må dele din ansøgning",
            "type": "select",
            "options": ["Ja", "Nej"],
        }],
        "answer": {"D": "Ja"}
    }
]


def _few_shot_block():
    """Render example blocks inside the prompt for few-shot learning."""
    parts = []
    for ex in FEW_SHOT:
        parts.append(
            "Example:\n"
            f"UserProfile:\n{json.dumps(ex['user'], ensure_ascii=False, indent=2)}\n"
            f"Fields:\n{json.dumps(ex['fields'], ensure_ascii=False, indent=2)}\n"
            f"Answer:\n{json.dumps(ex['answer'], ensure_ascii=False)}\n"
        )
    return "\n".join(parts)


def map_fields_to_answers(fields, user_profile, system_prompt=None):
    """
    Use AI to decide what values should go in each ATS field dynamically.
    The model is robust to unpredictable labels and multi-language forms (Danish/English).

    Args:
        fields (list): each field may include:
          {
            "field_id": str,
            "label": str,
            "type": "text"|"select"|...,
            "options": [str, ...],
            "required": bool
          }
        user_profile (dict): loaded from JSON for this user.
        system_prompt (str, optional): custom system prompt to override default behavior.

    Returns:
        dict: {"field_id": "answer"} where answers are:
              - free-text strings for text inputs, or
              - exact strings from `options` for selects.
    """
    if not fields:
        return {}
    user_profile = user_profile or {}


    # Default system prompt if none provided
    base_system_prompt = system_prompt or """
    You are an AI assistant that fills job application forms using a user's profile.
    Match each field label to the most relevant piece of information.

    Guidelines:
    - Understand both Danish and English labels (e.g. "stilling" = "position", "arbejdsgiver" = "employer").
    - If a label mentions "Nuværende stilling" or "Current position", use the user's current job title.
    - If a label mentions "Nuværende arbejdsgiver" or "Current employer", use the user's current company.
    - If a label mentions "løn", "salary", or "expected pay", use the user's expected salary.
    - If it asks about "experience" or "arbejdserfaring", use years of experience.
    - For gender ("køn"), use the user's gender if available.
    - For consent or sharing fields, default to "Ja"/"Yes" if uncertain.
    - Always return an answer for *every* field, even if inferred.
    - Only skip if the field truly has no relevant information.
    - Translate and normalize appropriately.
    """

    # Combine structured hints + few-shot + user data
    user_prompt = f"""
    You are filling out a job application form on behalf of a user based on their profile.

    🧩 Input:
    - You receive a list of fields with labels, IDs, types, and possible options.
    - You must fill **every single field** — never skip any.
    - If you don’t know the answer, generate a natural, realistic value that matches the field label and context.

    🌍 Language:
    - Understand and respond correctly in both Danish and English.
    - Match the field’s language: if the label is Danish, answer in Danish; if English, answer in English.

    🎯 Objective:
    Provide one value per field ID in valid JSON format.

    💡 Rules:
    1. **Always provide a value** for every field_id — even if you must make one up.
    2. **For select or dropdown fields**:
    - The answer **must exactly match** one of the available options.
    - If none fit, pick a neutral or generic one like “Other”, “Andet”, or the first option that makes sense.
    3. **For text fields**:
    - Use realistic short answers: names, emails, phone numbers, cities, companies, etc.
    - If the label is unknown, infer from common job application logic (example: “info.middleName” → a realistic middle name like “Peter”).
    4. **For Yes/No questions**:
    - If it sounds like consent, policy, or agreement → “Yes” / “Ja”.
    - If it sounds like prior employment restriction → “No” / “Nej”.
    5. **For salary or pay** → “Efter aftale” (Danish) or “Negotiable” (English).
    6. **For address** → “Testvej 1”, city → “København”, zip → “2100”.
    7. **For first name** → use user’s name if known, else “Test”.
    8. **For last name** → use user’s surname if known, else “User”.
    9. **If completely unsure**, make up a short but realistic answer based on the field label type.
    10. **Return only valid JSON** — no markdown, no explanations, no comments.

    Examples:
    - Label: “info.firstName” → “Kasper”
    - Label: “City” → “Copenhagen”
    - Label: “Expected Salary” → “Efter aftale”
    - Label: “How did you hear about us?” → “LinkedIn”
    - Label: “Address Line 1” → “Testvej 1”
    - Label: “Email” → “kasperchristensen@mail.com”
    - Label: “Skills” → “Python, Marketing, Communication”

    Now fill out the following fields based on the user profile.

    UserProfile:
    {json.dumps(user_profile, ensure_ascii=False, indent=2)}

    Fields to fill:
    {json.dumps(fields, ensure_ascii=False, indent=2)}

    Return **only** a JSON object like this:
    {{"field_id": "answer", ...}}
    """


    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": base_system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            temperature=0.4,  # deterministic output
        )

        text = (response.choices[0].message.content or "").strip()

        # Parse JSON safely
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        print("⚠️ Could not parse model output, returning empty:", text)
        return {f["field_id"]: "" for f in fields}

    except Exception as e:
        print(f"❌ AI field mapping failed: {e}")
        return {}
