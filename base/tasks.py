from playwright.sync_api import sync_playwright
from django.conf import settings
from .models import ATSRoom, User
from .ats_filler import fill_dynamic_fields   # 🧠 AI field filler
import time, traceback, random

def apply_to_ats(room_id, user_id, resume_path=None, cover_letter_text="", dry_run=True):
    """
    Robust ATS automation handler.
    Detects and fills dynamic, iframe-based forms (Workday, Lever, Greenhouse, etc.).
    If dry_run=True, it fills but does not submit.
    """

    room = ATSRoom.objects.get(id=room_id)
    user = User.objects.get(id=user_id)

    print(f"🌐 Starting ATS automation for: {room.company_name} ({room.apply_url})")
    print(f"🧪 Dry-run mode: {dry_run}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
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
                    page.wait_for_timeout(2000)
            except Exception as e:
                print(f"⚠️ Consent handling failed: {e}")

            # 2️⃣ Trigger “Apply” or open hidden form modals
            try:
                buttons = page.locator("button, a")
                trigger_words = [
                    "apply", "continue", "start application",
                    "next", "get started", "begin", "proceed"
                ]
                for word in trigger_words:
                    matches = buttons.filter(has_text=word)
                    if matches.count() > 0:
                        matches.first.click()
                        print(f"🖱️ Clicked '{word}' button to open form")
                        page.wait_for_timeout(5000)
                        break
            except Exception as e:
                print(f"⚠️ Could not trigger application form: {e}")

            # 3️⃣ Detect iframe context
            context = page
            try:
                for frame in page.frames:
                    if frame == page.main_frame:
                        continue
                    try:
                        count = frame.locator("input, textarea, select").count()
                        if count > 3:
                            context = frame
                            print(f"🔄 Switched context to ATS iframe containing form ({count} elements detected)")
                            break
                    except Exception:
                        continue
            except Exception as e:
                print(f"⚠️ Could not detect iframe: {e}")

            # 4️⃣ Wait for form fields (handle React render delays)
            try:
                context.wait_for_selector("input, textarea, select", timeout=12000)
                print("⏳ Form fields detected and ready.")
            except Exception:
                print("⚠️ No visible fields yet; continuing with scan.")

            # 5️⃣ Expand collapsed / hidden sections (Workday, Lever, etc.)
            try:
                expanders = context.locator("button:has-text('Expand'), button:has-text('Show more'), div[role='button']")
                if expanders.count() > 0:
                    for i in range(min(expanders.count(), 3)):
                        expanders.nth(i).click()
                        page.wait_for_timeout(1000)
                    print("📂 Expanded collapsible sections.")
            except Exception:
                pass

            # 6️⃣ Scroll slowly to ensure all elements render
            try:
                for y in range(0, 2000, 400):
                    page.mouse.wheel(0, 400)
                    page.wait_for_timeout(400 + random.randint(100, 300))
                print("🧭 Scrolled through page to reveal hidden inputs.")
            except Exception:
                pass

            # 7️⃣ Fill deterministic user fields
            fields = {
                "first": user.first_name,
                "last": user.last_name,
                "email": user.email,
                "phone": getattr(user, "phone", ""),
                "linkedin": getattr(user, "linkedin", ""),
            }

            for key, value in fields.items():
                try:
                    locator = context.locator(
                        f"input[name*='{key}'], input[placeholder*='{key}'], input[id*='{key}']"
                    )
                    if locator.count() > 0:
                        locator.first.fill(value)
                        print(f"✍️ Filled {key} field")
                except Exception as e:
                    print(f"⚠️ Could not fill {key}: {e}")

            # 8️⃣ 🧠 AI dynamic field filling
            try:
                fill_dynamic_fields(context, user)
            except Exception as e:
                print(f"⚠️ AI dynamic field filling failed: {e}")
                traceback.print_exc()

            # 9️⃣ Upload resume
            try:
                file_input = context.locator("input[type='file']")
                if file_input.count() > 0 and resume_path:
                    file_input.first.set_input_files(resume_path)
                    print("📄 Uploaded resume")
            except Exception as e:
                print(f"⚠️ Resume upload failed: {e}")

            # 🔟 Cover letter fill
            try:
                textarea = context.locator("textarea")
                if textarea.count() > 0:
                    letter_text = cover_letter_text or (
                        "Dear Hiring Manager,\n\nI'm very interested in this opportunity and believe my background fits well."
                    )
                    textarea.first.fill(letter_text)
                    print("💬 Filled cover letter")
            except Exception as e:
                print(f"⚠️ Could not fill cover letter: {e}")

            # 11️⃣ Dry run — skip submit safely
            screenshot_path = f"/home/clinton/Internstart/media/ats_preview_{room.company_name.replace(' ', '_')}.png"
            if dry_run:
                print("🧪 Dry run active — skipping submit.")
                # always screenshot from page (even if using frame context)
                page.screenshot(path=screenshot_path, full_page=True)
                print(f"📸 Saved preview screenshot as {screenshot_path}")
                browser.close()
                return "dry-run"

            # 12️⃣ Submit
            try:
                submit_btn = context.locator("button:has-text('Submit'), button:has-text('Apply'), input[type='submit']")
                if submit_btn.count() > 0:
                    submit_btn.first.click()
                    print("🚀 Submitted form")
                    time.sleep(5)
                else:
                    print("⚠️ No submit button found.")
            except Exception as e:
                print(f"⚠️ Could not click submit: {e}")

            # 13️⃣ Success verification
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
            try:
                page.screenshot(path=f"/home/clinton/Internstart/media/error_screenshot.png", full_page=True)
                print("📸 Saved error screenshot for debugging.")
            except Exception:
                pass
            browser.close()
            return False
