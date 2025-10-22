import json
from openai import OpenAI
from playwright.sync_api import Page

client = OpenAI()  # Uses OPENAI_API_KEY from environment

def fill_dynamic_fields(page: Page, user):
    """
    Extracts all visible form fields, sends them to OpenAI with user info,
    gets back suggested answers, and fills them into the form dynamically.
    """

    print("🧠 Starting intelligent field mapping...")

    # --- Step 1: Extract all input and label names ---
    elements = []
    for el in page.locator("input, textarea, select").all():
        try:
            label = page.evaluate(
                "(el) => el.labels?.[0]?.innerText || el.placeholder || el.name || ''",
                el
            )
            if label and len(label.strip()) > 1:
                elements.append(label.strip())
        except Exception:
            continue

    print(f"🧩 Found {len(elements)} form fields")

    if not elements:
        return

    # --- Step 2: Create user context ---
    user_context = {
        "full_name": f"{user.first_name} {user.last_name}",
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": getattr(user, "phone", None),
        "linkedin": getattr(user, "linkedin", None),
        "website": getattr(user, "website", None),
        "country": "Denmark",
        "citizenship": "Yes",
        "work_authorization": "Yes",
    }

    # --- Step 3: Ask OpenAI to generate answers ---
    prompt = f"""
You are helping an automated system fill out an online job application form.

Here is the user's information:
{json.dumps(user_context, indent=2)}

The form fields to fill are:
{json.dumps(elements, indent=2)}

For each field, return a JSON object where the key is the field label and the value is what should be entered.
If the field matches known user info (like name, email, phone, etc.), use that info.
If it's something else (like 'Why are you interested in this job?' or 'Do you have permission to work in the country?'), create a logical, short answer.

Output only a valid JSON object, nothing else.
"""

    print("🧠 Sending field list to OpenAI...")
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    ai_output = response.output[0].content[0].text.strip()
    print("--- RAW AI RESPONSE ---")
    print(ai_output)
    print("-----------------------")

    try:
        field_values = json.loads(ai_output)
    except json.JSONDecodeError:
        print("⚠️ Failed to parse AI output as JSON.")
        return

    # --- Step 4: Fill each field dynamically ---
    for label, value in field_values.items():
        if not value:
            continue

        try:
            selector = f"input[placeholder*='{label}'], input[name*='{label.lower()}'], textarea[placeholder*='{label}'], textarea[name*='{label.lower()}']"
            field = page.locator(selector)

            if field.count() > 0:
                field.first.fill(str(value))
                print(f"✍️ Filled '{label}' with '{value}'")
                continue

            # Try dropdowns
            select = page.locator("select")
            if select.count() > 0:
                for s in select.all():
                    options = s.locator("option").all_texts()
                    for opt in options:
                        if str(value).lower() in opt.lower():
                            s.select_option(label=opt)
                            print(f"🔽 Selected '{opt}' for '{label}'")
                            break

        except Exception as e:
            print(f"⚠️ Could not fill field '{label}': {e}")

    print("✅ Field filling complete.")
