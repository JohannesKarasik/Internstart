from playwright.sync_api import sync_playwright
from django.conf import settings
from .models import ATSRoom, User
from .ats_filler import fill_dynamic_fields   # 🧠 AI field filler
import time, traceback


def apply_to_ats(room_id, user_id, resume_path=None, cover_letter_text="", dry_run=True):
    """
    Automates applying to an ATS job listing.
    Ensures hidden/dynamic forms (SmartRecruiters, Workday, Greenhouse, Lever, etc.)
    are opened and all fields are detected before filling.
    If dry_run=True, it fills everything but does NOT click submit.
    """

    room = ATSRoom.objects.get(id=room_id)
    user = User.objects.get(id=user_id)

    print(f"🌐 Starting ATS automation for: {room.company_name} ({room.apply_url})")
    print(f"🧪 Dry-run mode: {dry_run}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page()

        try:
            print(f"🌍 Visiting {room.apply_url} ...")
            page.goto(room.apply_url, timeout=90000, wait_until="networkidle")
            page.wait_for_timeout(4000)

            # 1️⃣ Handle cookie/consent popups
            try:
                consent = page.locator("button:has-text('I agree'), button:has-text('Accept'), button:has-text('OK')")
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

            # 2️⃣ Try to open any application modal / form first
            try:
                buttons = page.locator("button, a")
                trigger_words = ["apply", "continue", "start application", "next", "get started", "begin", "proceed"]
                for word in trigger_words:
                    matches = buttons.filter(has_text=word)
                    if matches.count() > 0:
                        matches.first.click()
                        print(f"🖱️ Clicked '{word}' button to open form")
                        page.wait_for_timeout(5000)
                        break
            except Exception as e:
                print(f"⚠️ Could not trigger application form: {e}")

            # 3️⃣ Check for and switch to iframe forms if present
            try:
                for frame in page.frames:
                    try:
                        inner_inputs = frame.locator("input, textarea, select")
                        if inner_inputs.count() > 3:  # heuristic threshold
                            page = frame
                            print("🔄 Switched context to ATS iframe containing form")
                            break
                    except Exception:
                        continue
            except Exception as e:
                print(f"⚠️ Could not detect iframe: {e}")

            page.wait_for_timeout(3000)

            # 4️⃣ Fill standard user fields (deterministic fields first)
            fields = {
                "first": user.first_name,
                "last": user.last_name,
                "email": user.email,
                "phone": getattr(user, "phone", ""),
                "linkedin": getattr(user, "linkedin", ""),
            }

            for key, value in fields.items():
                try:
                    locator = page.locator(f"input[name*='{key}'], input[placeholder*='{key}'], input[id*='{key}']")
                    if locator.count() > 0:
                        locator.first.fill(value)
                        print(f"✍️ Filled {key} field")
                except Exception as e:
                    print(f"⚠️ Could not fill {key}: {e}")

            # 5️⃣ 🧠 AI dynamic field filling (after ensuring everything is loaded)
            try:
                fill_dynamic_fields(page, user)
            except Exception as e:
                print(f"⚠️ AI dynamic field filling failed: {e}")
                traceback.print_exc()

            # 6️⃣ Upload resume if available
            try:
                file_input = page.locator("input[type='file']")
                if file_input.count() > 0 and resume_path:
                    file_input.first.set_input_files(resume_path)
                    print("📄 Uploaded resume")
            except Exception as e:
                print(f"⚠️ Resume upload failed: {e}")

            # 7️⃣ Fill cover letter if textarea exists
            try:
                textarea = page.locator("textarea")
                if textarea.count() > 0:
                    letter_text = cover_letter_text or (
                        "Dear Hiring Manager,\n\nI'm very interested in this opportunity and believe my background fits well."
                    )
                    textarea.first.fill(letter_text)
                    print("💬 Filled cover letter")
            except Exception as e:
                print(f"⚠️ Could not fill cover letter: {e}")

            # 8️⃣ DRY-RUN: Stop before submitting
            if dry_run:
                print("🧪 Dry run active — skipping submit.")
                screenshot_path = f"ats_preview_{room.company_name.replace(' ', '_')}.png"
                page.screenshot(path=screenshot_path, full_page=True)
                print(f"📸 Saved preview screenshot as {screenshot_path}")
                browser.close()
                return "dry-run"

            # 9️⃣ Click Submit / Apply button
            try:
                submit_btn = page.locator("button:has-text('Submit'), button:has-text('Apply'), input[type='submit']")
                if submit_btn.count() > 0:
                    submit_btn.first.click()
                    print("🚀 Submitted form")
                    time.sleep(5)
                else:
                    print("⚠️ No submit button found.")
            except Exception as e:
                print(f"⚠️ Could not click submit: {e}")

            # 🔟 Verify success
            html = page.content().lower()
            browser.close()

            if any(kw in html for kw in ["thank", "confirmation", "submitted", "successfully", "application received"]):
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
