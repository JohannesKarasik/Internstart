# base/ai/field_interpreter.py
import json
import os
import re
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Light-weight synonym/translation hints the model can use when matching to Danish options.
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

FEW_SHOT = [
    # --- Select with options (field of study) ---
    {
        "user": {
            "under_education": "yes",
            "field_of_study": "Marketing",
            "highest_education_level": "Bachelor’s Degree"
        },
        "fields": [{
            "field_id": "A",
            "label": "Fagområde for uddannelse",
            "type": "select",
            "options": ["IT", "Markedsføring", "Andet område"],
            "required": True
        }],
        "answer": {"A": "Markedsføring"}
    },
    # --- Degree title select ---
    {
        "user": {"highest_education_level": "Bachelor’s Degree"},
        "fields": [{
            "field_id": "B",
            "label": "Titel på uddannelse",
            "type": "select",
            "options": ["Bachelor", "Kandidat", "Ph.d.", "Andet"],
            "required": True
        }],
        "answer": {"B": "Bachelor"}
    },
    # --- Years of experience select (still studying → 0 År) ---
    {
        "user": {"under_education": "yes"},
        "fields": [{
            "field_id": "C",
            "label": "Totalt antal års arbejdserfaring",
            "type": "select",
            "options": ["0 År", "1 År", "2-3 År", "4+ År"],
            "required": True
        }],
        "answer": {"C": "0 År"}
    },
    # --- Consent style yes/no select ---
    {
        "user": {},
        "fields": [{
            "field_id": "D",
            "label": "Venligst besvar, om vi må dele din ansøgning",
            "type": "select",
            "options": ["Ja", "Nej"],
            "required": True
        }],
        "answer": {"D": "Ja"}
    }
]


def _few_shot_block():
    # Render few-shot examples inside the prompt as guidance.
    chunks = []
    for ex in FEW_SHOT:
        chunks.append(
            "Example\n"
            f"UserProfile:\n{json.dumps(ex['user'], ensure_ascii=False, indent=2)}\n"
            f"Fields:\n{json.dumps(ex['fields'], ensure_ascii=False, indent=2)}\n"
            f"Answer:\n{json.dumps(ex['answer'], ensure_ascii=False)}\n"
        )
    return "\n".join(chunks)


def map_fields_to_answers(fields, user_profile):
    """
    Use AI to decide what values should go in each ATS field.

    Args:
        fields (list): each item may contain:
          {
            "field_id": str,
            "label": str,
            "type": "text"|"select"|... (optional),
            "options": [str, ...]    (for select),
            "required": bool         (optional)
          }
        user_profile (dict): loaded from user JSON file.

    Returns:
        dict: {"field_id": "answer"} where the answer is EITHER:
              - a free-text string for text inputs, or
              - EXACTLY one string from the field's `options` (for selects).
              Use "skip" only when not required and no safe answer exists.
    """
    if not fields or not user_profile:
        return {}

    # Provide the model with locale and synonym hints so it can align English profile values to Danish options.
    prompt = f"""
Du er en assistent, der udfylder DANSKE jobansøgningsskemaer (locale: da-DK).
Brug kun oplysningerne i UserProfile til at besvare felter. 
Hvis et felt har "options", SKAL svaret være PRÆCIS én streng fra den liste.
Hvis intet passer og feltet er required, vælg en neutral mulighed som "Andet/Other".
Undgå "skip" på required felter. På ikke-required felter må du returnere "skip" når der reelt ikke er data.

Oversættelses-/synonymer-hints (hjælp til at mappe engelske udtryk fra profilen til danske valgmuligheder):
{json.dumps(HINTS, ensure_ascii=False, indent=2)}

Nogle retningslinjer:
- “Bachelor’s Degree” → “Bachelor”; “Master’s Degree” → “Kandidat”; “PhD” → “Ph.d.”
- “Marketing” kan matche “Markedsføring” eller lignende.
- Hvis UserProfile siger at brugeren stadig studerer, og der spørges om år af erfaring, så vælg “0 År” hvis det findes.
- Samtykke-/delingsfelter bør som udgangspunkt være “Ja”, medmindre UserProfile siger andet.
- Returnér KUN gyldig JSON uden kommentarer, forklaringer eller tekst før/efter.

UserProfile:
{json.dumps(user_profile, ensure_ascii=False, indent=2)}

Fields to fill (each item may include options for selects):
{json.dumps(fields, ensure_ascii=False, indent=2)}

{_few_shot_block()}

Returnér KUN JSON-objektet: {{"field_id": "answer", ...}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You fill Danish ATS forms strictly. "
                        "When a field provides options, return exactly one of those options as the value. "
                        "Prefer the closest semantic match; for required selects, never return 'skip'—choose a safe fallback like 'Andet'."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,  # keep it deterministic
        )

        text = (response.choices[0].message.content or "").strip()

        # Parse JSON (with a defensive fallback)
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group(0))
            print("⚠️ Could not parse model output:", text)
            return {}

    except Exception as e:
        print(f"❌ AI field mapping failed: {e}")
        return {}
