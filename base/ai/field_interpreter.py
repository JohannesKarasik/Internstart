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


def _normalize_label_text(label: str) -> str:
    """
    Clean weird labels like:
      "[Key candidate.appFormPerson.personality.applicationText not found]"
    into something GPT understands.
    """
    if not label:
        return ""

    raw = str(label).strip()

    # If the raw already hints at the essay field, normalize to a friendly alias.
    if re.search(r"(application\s*text|applicationtext|cover\s*letter|motivation|"
                 r"motivationsbrev|ans(ø|oe)gning|personal(ity)?\s*(statement|profile)?)",
                 raw, re.I):
        return "application text"

    # Common "required" noise
    if raw.lower() in {"nødvendig", "obligatorisk", "required", "necessary"}:
        return ""

    # Special-case: salvage inside "[Key ... not found]" without dropping the useful token
    m = re.search(r"\[([^]]+)\]", raw)
    if m:
        inside = m.group(1)
        # remove leading "key" and trailing "not found"
        inside = re.sub(r"^\s*key\s+", "", inside, flags=re.I)
        inside = re.sub(r"\s*not\s*found\s*$", "", inside, flags=re.I)
        # make human
        inside = re.sub(r"[._]", " ", inside)
        inside = re.sub(r"([a-z])([A-Z])", r"\1 \2", inside)
        inside = re.sub(r"\s+", " ", inside).strip().lower()

        # If the salvaged text contains our essay hints, collapse to alias
        if re.search(r"(application\s*text|applicationtext|cover\s*letter|motivation|"
                     r"motivationsbrev|ans(ø|oe)gning)", inside, re.I):
            return "application text"
        return inside or raw

    # Generic humanization
    txt = re.sub(r"([a-z])([A-Z])", r"\1 \2", raw)
    txt = re.sub(r"[\[\]{}()/_.\-]+", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()



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
    Handles both short structured fields and essay/motivation fields in separate passes.
    """
    if not fields:
        return {}

    user_profile = user_profile or {}

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

    # --- Normalize all field labels before sending to GPT ---
    normalized_fields = []
    for f in fields:
        norm_label = (
            _normalize_label_text(f.get("label", ""))
            or _normalize_label_text(f.get("aria_label", ""))
            or f.get("label", "")
        )
        norm_field = dict(f)
        norm_field["label"] = norm_label.strip()
        normalized_fields.append(norm_field)

    # --- Split essay vs non-essay fields ---
    essay_fields = [f for f in normalized_fields if f.get("kind") == "essay"]
    short_fields = [f for f in normalized_fields if f.get("kind") != "essay"]

    answers = {}

    # ================================
    # 🧩 PASS 1 — Non-essay fields
    # ================================
    if short_fields:
        user_prompt_short = f"""
        You are filling out a job application form on behalf of a user based on their profile.

        🧩 Input:
        - Each field includes a label, type, and "kind" (semantic meaning like essay, phone, email, etc.).
        - You must fill **every single field** — never skip any.
        - If you don’t know the answer, make up a realistic value that fits the label.

        🌍 Language:
        - Understand and respond in Danish or English depending on the field label.
        - Match the field’s language (Danish label → Danish answer, English label → English answer).

        🧠 Formatting rules by kind:
        - kind="skills": Return 3–6 comma-separated skills, e.g. "Python, Marketing, Communication".
        - kind="phone": Return a valid phone number with country code, e.g. "+45 42424242".
        - kind="email": Return a valid email, e.g. "kasperchristensen@mail.com".
        - kind="salary": Use "Efter aftale" (Danish) or "Negotiable" (English).
        - kind="yesno": If it sounds like consent/policy/sharing → "Ja"/"Yes"; if about employment restrictions → "Nej"/"No".
        - kind="address": Use "Testvej 1".
        - kind="city": Use "København".
        - kind="zip": Use "2100".
        - kind="country": Use "Danmark" or "Denmark".
        - kind="first_name": "Kasper"
        - kind="last_name": "Christensen"
        - Default (unknown kind): Generate a short, context-appropriate value.

        🎯 Output:
        Return one JSON object where each key is a field_id and each value is the best answer.

        🧾 UserProfile:
        {json.dumps(user_profile, ensure_ascii=False, indent=2)}

        Fields to fill:
        {json.dumps(short_fields, ensure_ascii=False, indent=2)}

        Return **only** valid JSON like this:
        {{"field_id": "answer", ...}}
        """

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": base_system_prompt.strip()},
                    {"role": "user", "content": user_prompt_short.strip()},
                ],
                temperature=0.4,
            )
            text = (response.choices[0].message.content or "").strip()
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                answers.update(json.loads(match.group(0)))
            else:
                print("⚠️ Could not parse non-essay block:", text)
        except Exception as e:
            print(f"❌ Non-essay AI block failed: {e}")

    # ================================
    # 🧠 PASS 2 — Essay fields
    # ================================
    if essay_fields:
        essay_prompt = f"""
        You are a writing assistant for job applications.

        For each of the following fields, write 4–7 fluent sentences (≈80–150 words)
        in the label’s language. Each should read like a short motivational paragraph.

        Include:
        - Why the user is interested in the position
        - Relevant experience or strengths
        - A professional and positive tone

        Never include numbers, phone codes, or countries here.

        🧾 UserProfile:
        {json.dumps(user_profile, ensure_ascii=False, indent=2)}

        Fields:
        {json.dumps(essay_fields, ensure_ascii=False, indent=2)}

        Return JSON with each field_id as key and its essay text as value.
        """

        try:
            essay_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a writing assistant for job applications."},
                    {"role": "user", "content": essay_prompt.strip()},
                ],
                temperature=0.7,
            )
            essay_text = (essay_response.choices[0].message.content or "").strip()
            match = re.search(r"\{.*\}", essay_text, re.DOTALL)
            if match:
                answers.update(json.loads(match.group(0)))
            else:
                print("⚠️ Could not parse essay block:", essay_text)
        except Exception as e:
            print(f"❌ Essay AI block failed: {e}")

    # ✅ Final merged result
    return answers
