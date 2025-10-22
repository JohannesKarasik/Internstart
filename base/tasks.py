from playwright.sync_api import sync_playwright
from django.conf import settings
from .models import ATSRoom, User
import time

def apply_to_ats(room_id, user_id, resume_path, cover_letter_text=""):
    room = ATSRoom.objects.get(id=room_id)
    user = User.objects.get(id=user_id)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"🌐 Visiting: {room.apply_url}")

        page.goto(room.apply_url, timeout=60000)

        # 1️⃣ Handle consent popups
        try:
            consent = page.locator("button:has-text('I agree'), button:has-text('Accept')")
            if consent.count() > 0:
                consent.first.click()
                print("✅ Clicked consent button")
            else:
                checkbox = page.locator("input[type='checkbox'][id*='agree'], input[name*='consent']")
                if checkbox.count() > 0:
                    checkbox.first.check()
                    print("✅ Checked consent box")
        except Exception as e:
            print(f"⚠️ Consent handling failed: {e}")

        # 2️⃣ Fill user fields
        fields = {
            "first": user.first_name,
            "last": user.last_name,
            "email": user.email,
            "phone": getattr(user, "phone", ""),
            "linkedin": getattr(user, "linkedin", ""),
        }

        for key, value in fields.items():
            try:
                locator = page.locator(f"input[name*='{key}'], input[placeholder*='{key}']")
                if locator.count() > 0:
                    locator.first.fill(value)
                    print(f"✍️ Filled {key} field")
            except Exception as e:
                print(f"⚠️ Could not fill {key}: {e}")

        # 3️⃣ Upload resume
        try:
            file_input = page.locator("input[type='file']")
            if file_input.count() > 0:
                file_input.first.set_input_files(resume_path)
                print("📄 Uploaded resume")
        except Exception as e:
            print(f"⚠️ Resume upload failed: {e}")

        # 4️⃣ Fill cover letter if available
        try:
            textarea = page.locator("textarea")
            if textarea.count() > 0:
                textarea.first.fill(cover_letter_text or "Please find my resume attached.")
                print("💬 Filled cover letter")
        except Exception as e:
            print(f"⚠️ Could not fill cover letter: {e}")

        # 5️⃣ Click submit/apply
        try:
            page.locator("button:has-text('Submit'), button:has-text('Apply'), input[type='submit']").first.click()
            time.sleep(5)
            print("🚀 Submitted form")
        except Exception as e:
            print(f"⚠️ Could not click submit: {e}")

        # 6️⃣ Check success
        html = page.content().lower()
        browser.close()

        if "thank" in html or "confirmation" in html:
            print(f"✅ Application for {room.company_name} submitted successfully!")
            return True
        else:
            print(f"⚠️ Application submission for {room.company_name} could not be verified.")
            return False
