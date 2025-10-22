from playwright.sync_api import sync_playwright
from django.conf import settings
from .models import ATSRoom, User
from .ats_filler import fill_dynamic_fields   # 🧠 AI field filler
import time, traceback


def apply_to_ats(room_id, user_id, resume_path=None, cover_letter_text="", dry_run=True):
    """
    Automates applying to an ATS job listing.
    If dry_run=True, it will fill everything but NOT click submit.
    """

    room = ATSRoom.objects.get(id=room_id)
    user = User.objects.get(id=user_id)

    print(f"🌐 Starting ATS automation for: {room.company_name} ({room.apply_url})")
    print(f"🧪 Dry-run mode: {dry_run}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print(f"🌍 Visiting {room.apply_url} ...")
            page.goto(room.apply_url, timeout=60000)
            page.wait_for_timeout(3000)

            # 1️⃣ Handle cookie/consent popups
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

            # 2️⃣ Fill standard user fields
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

            # 3️⃣ 🧠 Fill dynamic fields with AI
            try:
                fill_dynamic_fields(page, user)
            except Exception as e:
                print(f"⚠️ AI dynamic field filling failed: {e}")
                traceback.print_exc()

            # 4️⃣ Upload resume if present
            try:
                file_input = page.locator("input[type='file']")
                if file_input.count() > 0 and resume_path:
                    file_input.first.set_input_files(resume_path)
                    print("📄 Uploaded resume")
            except Exception as e:
                print(f"⚠️ Resume upload failed: {e}")

            # 5️⃣ Cover letter fill
            try:
                textarea = page.locator("textarea")
                if textarea.count() > 0:
                    letter_text = cover_letter_text or (
                        "Dear Hiring Manager, I'm very interested in this opportunity and believe my background fits well."
                    )
                    textarea.first.fill(letter_text)
                    print("💬 Filled cover letter")
            except Exception as e:
                print(f"⚠️ Could not fill cover letter: {e}")

            # 6️⃣ DRY-RUN: Do NOT submit
            if dry_run:
                print("🧪 Dry run active — skipping submit.")
                screenshot_path = f"ats_preview_{room.company_name.replace(' ', '_')}.png"
                page.screenshot(path=screenshot_path, full_page=True)
                print(f"📸 Saved preview screenshot as {screenshot_path}")
                browser.close()
                return "dry-run"

            # 7️⃣ Otherwise, actually click submit
            try:
                submit_btn = page.locator("button:has-text('Submit'), button:has-text('Apply'), input[type='submit']")
                if submit_btn.count() > 0:
                    submit_btn.first.click()
                    time.sleep(5)
                    print("🚀 Submitted form")
                else:
                    print("⚠️ No submit button found.")
            except Exception as e:
                print(f"⚠️ Could not click submit: {e}")

            # 8️⃣ Verify success
            html = page.content().lower()
            browser.close()

            if "thank" in html or "confirmation" in html or "submitted" in html:
                print(f"✅ Application for {room.company_name} submitted successfully!")
                return True
            else:
                print(f"⚠️ Application submission for {room.company_name} could not be verified.")
                return False

        except Exception as e:
            print(f"❌ Fatal error during automation: {e}")
            traceback.print_exc()
            browser.close()
            return False
