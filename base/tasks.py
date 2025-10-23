from playwright.sync_api import sync_playwright
from django.conf import settings
from .models import ATSRoom, User
from .ats_filler import fill_dynamic_fields   # 🧠 AI field filler
import time, traceback, random
from urllib.parse import urlparse


def apply_to_ats(room_id, user_id, resume_path=None, cover_letter_text="", dry_run=True):
    """
    Robust ATS automation handler.
    Detects and fills dynamic, iframe-based forms (Workday, Lever, Greenhouse, etc.).
    If dry_run=True, it fills but does not submit.
    """

    room = ATSRoom.objects.get(id=room_id)
    user = User.objects.get(id=user_id)

    # ✅ Automatically pull resume from user model if not provided
    if not resume_path:
        try:
            if hasattr(user, "resume") and user.resume:
                resume_path = user.resume.path  # local filesystem path
                print(f"📄 Loaded resume from user model: {resume_path}")
            else:
                print("⚠️ User has no resume uploaded in their profile.")
        except Exception as e:
            print(f"⚠️ Could not load resume from user model: {e}")

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
            page.goto(room.apply_url, timeout=120000, wait_until="domcontentloaded")
            page.wait_for_load_state("load", timeout=20000)
            page.wait_for_timeout(4000)
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

            # 2️⃣ Trigger “Apply” or open hidden form modals (SAFE)
            try:
                # If we already see inputs, don't click anything.
                existing_fields = page.locator("input, textarea, select").count()
                if existing_fields >= 3:
                    print("🛑 Form fields already visible; skipping any 'apply' clicks.")
                else:
                    print("🔎 Looking for a SAFE apply/continue trigger...")

                    trigger_words = [
                        "apply", "continue", "start application", "start your application",
                        "next", "get started", "begin", "proceed"
                    ]
                    block_words = [
                        "quick apply", "jobindex", "linkedin", "indeed", "glassdoor", "xing",
                        "external", "login", "log ind", "sign in", "create account"
                    ]

                    candidates = page.locator("button, a")

                    def looks_blocked(txt: str) -> bool:
                        t = (txt or "").lower()
                        return any(b in t for b in block_words)

                    def looks_allowed(txt: str) -> bool:
                        t = (txt or "").lower()
                        return any(w in t for w in trigger_words)

                    url_host = urlparse(page.url).netloc

                    safe_clicked = False
                    for i in range(candidates.count()):
                        el = candidates.nth(i)
                        try:
                            if not el.is_visible():
                                continue
                            text = (el.inner_text() or "").strip()
                            if not looks_allowed(text) or looks_blocked(text):
                                continue

                            in_form = el.evaluate("e => !!e.closest('form')")
                            href = (el.get_attribute("href") or "").strip()
                            same_origin = True
                            if href.startswith("http"):
                                same_origin = (urlparse(href).netloc == url_host)
                            is_submit_type = (el.get_attribute("type") or "").lower() == "submit"

                            if in_form or is_submit_type or (same_origin and not href.lower().startswith("mailto:")):
                                before_url = page.url
                                before_field_count = page.locator("input, textarea, select").count()
                                el.click()
                                print(f"🖱️ Safely clicked '{text[:40]}'")
                                page.wait_for_timeout(1500)

                                after_url = page.url
                                after_field_count = page.locator("input, textarea, select").count()

                                # If we navigated but didn't get more fields, go back.
                                if (after_url != before_url and after_field_count <= before_field_count):
                                    print("↩️ Navigation didn’t expose more fields; going back.")
                                    try:
                                        page.go_back(timeout=10000)
                                        page.wait_for_timeout(1000)
                                    except Exception:
                                        pass
                                    continue

                                safe_clicked = True
                                break
                        except Exception:
                            continue

                    if not safe_clicked:
                        print("⚠️ No safe apply/continue trigger found; proceeding without clicking.")
            except Exception as e:
                print(f"⚠️ Safe apply trigger failed: {e}")


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

            # 5️⃣ Expand collapsed / hidden sections
            try:
                expanders = context.locator("button:has-text('Expand'), button:has-text('Show more'), div[role='button']")
                if expanders.count() > 0:
                    for i in range(min(expanders.count(), 3)):
                        expanders.nth(i).click()
                        page.wait_for_timeout(1000)
                    print("📂 Expanded collapsible sections.")
            except Exception:
                pass

            # 6️⃣ Scroll to render dynamic fields
            try:
                for y in range(0, 2000, 400):
                    page.mouse.wheel(0, 400)
                    page.wait_for_timeout(400 + random.randint(100, 300))
                print("🧭 Scrolled through page to reveal hidden inputs.")
            except Exception:
                pass

            # 7️⃣ Fill deterministic fields
            fields = {
                "first": user.first_name,
                "last": user.last_name,
                "email": user.email,
                "phone": getattr(user, "phone_number", ""),
            }

            for key, value in fields.items():
                if not value:
                    continue
                try:
                    locator = context.locator(
                        f"input[name*='{key}'], input[placeholder*='{key}'], input[id*='{key}']"
                    )
                    if locator.count() > 0:
                        locator.first.fill(value)
                        print(f"✍️ Filled {key} field")
                except Exception as e:
                    print(f"⚠️ Could not fill {key}: {e}")

                # ✅ LinkedIn URL — sourced automatically from user model
                try:
                    # Pull LinkedIn URL from user model like resume
                    linkedin_url = getattr(user, "linkedin_url", "") or ""
                    if linkedin_url:
                        print(f"🔗 Loaded LinkedIn URL from user profile: {linkedin_url}")
                    else:
                        print("⚠️ No LinkedIn URL found in user model.")

                    # First attempt — fill any visible LinkedIn/Profile/URL fields
                    linkedin_fields = context.locator(
                        "input[name*='linkedin'], input[id*='linkedin'], input[placeholder*='linkedin'], "
                        "input[aria-label*='linkedin'], input[placeholder*='profile'], input[aria-label*='profile'], "
                        "input[name*='url'], input[id*='url']"
                    )
                    if linkedin_fields.count() > 0:
                        linkedin_fields.first.fill(linkedin_url or "N/A")
                        print("🔗 Filled LinkedIn URL field (initial pass).")
                    else:
                        print("⚠️ No LinkedIn field visible yet — will retry globally after resume upload.")

                except Exception as e:
                    print(f"⚠️ LinkedIn pre-fill failed: {e}")


            # 7.1️⃣ Country field (dropdown or input)
            try:
                user_country = getattr(user, "country", "") or ""
                if user_country:
                    country_map = {
                        "DK": "Denmark",
                        "US": "United States",
                        "UK": "United Kingdom",
                        "FRA": "France",
                        "GER": "Germany",
                    }
                    country_name = country_map.get(user_country, user_country)
                    print(f"🧩 Looking for country field to fill with '{country_name}'")

                    # Handle normal Greenhouse dropdowns
                    container = context.locator(".select__container")
                    if container.count() > 0:
                        container.first.click()
                        page.wait_for_timeout(1000)
                        menu = page.locator(".select__menu, .select__menu-list")
                        if menu.count() > 0:
                            option = menu.locator(f"text={country_name}")
                            if option.count() > 0:
                                option.first.click()
                                print(f"🌍 Selected country from Greenhouse menu: {country_name}")
                                page.mouse.click(10, 10)
                                page.wait_for_timeout(1000)
                            else:
                                print(f"⚠️ Could not find '{country_name}' in dropdown.")
                        else:
                            print("⚠️ No .select__menu found after opening dropdown.")
                    else:
                        # Handle <select> or text fields (skip phone country widgets)
                        select = context.locator("select[name*='country'], select[id*='country']")
                        if select.count() > 0:
                            options = select.first.locator("option")
                            for i in range(options.count()):
                                text = options.nth(i).inner_text().strip().lower()
                                if country_name.lower() in text:
                                    value = options.nth(i).get_attribute("value")
                                    select.first.select_option(value=value)
                                    print(f"🌍 Selected country from <select>: {country_name}")
                                    break
                        else:
                            # Try text input (not phone prefix)
                            country_inputs = context.locator("input[placeholder*='Country'], input[aria-label*='Country']")
                            for i in range(country_inputs.count()):
                                el = country_inputs.nth(i)
                                parent = el.evaluate("el => el.closest('div')?.innerText || ''")
                                if "+" in parent or "Phone" in parent:
                                    continue
                                el.fill(country_name)
                                print(f"🌍 Filled standalone country text field: {country_name}")
                                break
                            else:
                                print("⚠️ No valid country field found.")
            except Exception as e:
                print(f"⚠️ Could not select country: {e}")


            # 7.2️⃣ REQUIRED COMPLETENESS PASS — fill every remaining required field
            try:
                print("🧹 Running required-completeness pass (text/select/radio/checkbox/phone code)…")

                # Small helpers
                DIAL = {"DK": "+45", "US": "+1", "UK": "+44", "FRA": "+33", "GER": "+49"}
                user_cc = DIAL.get((getattr(user, "country", "") or "").upper(), "")

                PLACEHOLDER_WORDS = ["select", "vælg", "choose", "chose", "pick", "—", "-", "–", "please"]
                AVOID_CHECKBOX = ["newsletter", "marketing", "samarbejde", "marketingsføring", "updates", "promotion"]
                REQUIRED_MARKERS = ["*", "required", "obligatorisk", "påkrævet", "mandatory"]

                def is_placeholder(text: str) -> bool:
                    t = (text or "").strip().lower()
                    return (t == "" or any(w in t for w in PLACEHOLDER_WORDS))

                def near_text(frame, el):
                    try:
                        return frame.evaluate("""
                            (el) => {
                            const lab = (el.labels && el.labels[0]) ? el.labels[0].innerText : "";
                            const byId = (() => {
                                const ids = (el.getAttribute("aria-labelledby") || "").split(/\s+/).filter(Boolean);
                                return ids.map(id => (document.getElementById(id)?.innerText || "")).join(" ");
                            })();
                            const aria = el.getAttribute("aria-label") || "";
                            const ph   = el.getAttribute("placeholder") || "";
                            const wrap = el.closest("label, .field, .form-group, .MuiFormControl-root, div, section");
                            const near = wrap ? (wrap.querySelector("legend, label, span, small, .label, .title")?.innerText || "") : "";
                            return [lab, byId, aria, ph, near].join(" ").replace(/\\s+/g," ").trim();
                            }
                        """, el) or ""
                    except Exception:
                        return ""

                def looks_required(text: str) -> bool:
                    t = (text or "").lower()
                    return any(m in t for m in REQUIRED_MARKERS)

                # Scan every frame for still-empty required fields
                for frame in page.frames:
                    # --- Phone country split widgets (select with +code next to phone input) ---
                    if user_cc:
                        try:
                            phone_rows = frame.locator("select, [role='combobox']").filter(has_text="+")
                            for i in range(min(6, phone_rows.count())):
                                sel = phone_rows.nth(i)
                                if not sel.is_visible():
                                    continue
                                # heuristic: sibling/nearby contains 'phone' text
                                txt = near_text(frame, sel).lower()
                                if "phone" in txt or "mobil" in txt or "telefon" in txt:
                                    # try exact option match, then contains
                                    try:
                                        sel.select_option(label=user_cc)
                                    except Exception:
                                        frame.evaluate("""
                                            (el, want) => {
                                            const opts = Array.from((el.tagName==='SELECT' ? el.options : []));
                                            const match = opts.find(o => (o.textContent||'').trim()===want)
                                                        || opts.find(o => (o.textContent||'').includes(want));
                                            if (match) { el.value = match.value; el.dispatchEvent(new Event('change',{bubbles:true})); }
                                            }
                                        """, sel, user_cc)
                                    print(f"📞 Selected phone country code {user_cc}")
                                    break
                        except Exception:
                            pass

                    # --- Required text-like fields ---
                    try:
                        inputs = frame.locator("input:not([type='hidden']):not([disabled]), textarea:not([disabled])")
                        for i in range(inputs.count()):
                            el = inputs.nth(i)
                            try:
                                if not el.is_visible():
                                    continue
                                t = (el.get_attribute("type") or "").lower()
                                if t in ["checkbox", "radio", "file"]:
                                    continue  # handled below

                                curr = ""
                                try:
                                    curr = el.input_value().strip()
                                except Exception:
                                    try:
                                        curr = el.inner_text().strip()
                                    except Exception:
                                        curr = ""

                                if curr and curr.upper() != "N/A":
                                    continue

                                lbl = near_text(frame, el)
                                req_attr = el.get_attribute("required") is not None or el.get_attribute("aria-required") in ["true", True]
                                req_near = looks_required(lbl)
                                if not (req_attr or req_near):
                                    continue  # only mop up requireds

                                # Don't auto-fill emails/phones here (those were handled earlier)
                                L = lbl.lower()
                                if any(k in L for k in ["email", "e-mail", "mail"]):
                                    continue
                                if any(k in L for k in ["phone", "mobil", "telefon", "tel"]):
                                    continue
                                if "linkedin" in L:
                                    continue  # already handled by dedicated logic

                                # Last resort: drop N/A so the field isn’t left blank
                                el.fill("N/A")
                                try: el.press("Tab")
                                except Exception: pass
                                frame.evaluate("el => { el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }", el)
                                print(f"🧩 Required text field had no value → set 'N/A' ({lbl[:60]})")
                            except Exception:
                                continue
                    except Exception:
                        pass

                    # --- Required <select> dropdowns ---
                    try:
                        selects = frame.locator("select:not([disabled])")
                        for i in range(selects.count()):
                            sel = selects.nth(i)
                            try:
                                if not sel.is_visible():
                                    continue

                                # already has value?
                                has_val = frame.evaluate("(el) => !!el.value", sel)
                                if has_val:
                                    continue

                                lbl = near_text(frame, sel)
                                req_attr = sel.get_attribute("required") is not None or sel.get_attribute("aria-required") in ["true", True]
                                req_near = looks_required(lbl)
                                if not (req_attr or req_near):
                                    continue

                                # If label hints 'country' and we know the user's country text, try that first
                                user_country_human = {
                                    "DK": "Denmark",
                                    "US": "United States",
                                    "UK": "United Kingdom",
                                    "FRA": "France",
                                    "GER": "Germany",
                                }.get((getattr(user, "country", "") or "").upper(), "")

                                if "country" in lbl.lower() and user_country_human:
                                    try:
                                        sel.select_option(label=user_country_human)
                                        print(f"🌍 Completed required Country select → {user_country_human}")
                                        continue
                                    except Exception:
                                        pass

                                # Otherwise choose the first non-placeholder option
                                chose = frame.evaluate("""
                                    (el) => {
                                    const opts = Array.from(el.options || []);
                                    const good = opts.find(o => {
                                        const t = (o.textContent||'').trim();
                                        return t && !/select|vælg|choose|please|—|–|-/i.test(t);
                                    });
                                    if (good) { el.value = good.value; el.dispatchEvent(new Event('change',{bubbles:true})); return good.textContent.trim(); }
                                    return "";
                                    }
                                """, sel)
                                if chose:
                                    print(f"✅ Required select filled → {chose[:40]} ({lbl[:40]})")
                            except Exception:
                                continue
                    except Exception:
                        pass

                    # --- Radio groups (pick a safe default if required) ---
                    try:
                        radios = frame.locator("input[type='radio']:not([disabled])")
                        processed = set()
                        for i in range(radios.count()):
                            r = radios.nth(i)
                            try:
                                name = r.get_attribute("name") or f"__idx{i}"
                                if name in processed:
                                    continue
                                group = frame.locator(f"input[type='radio'][name='{name}']")
                                # required?
                                any_req = False
                                for j in range(group.count()):
                                    g = group.nth(j)
                                    if g.get_attribute("required") is not None or g.get_attribute("aria-required") in ["true", True]:
                                        any_req = True; break
                                if not any_req:
                                    continue
                                # pick the first visible option
                                for j in range(group.count()):
                                    g = group.nth(j)
                                    if g.is_visible():
                                        g.check(force=True)
                                        print(f"🔘 Checked required radio group '{name}'")
                                        break
                                processed.add(name)
                            except Exception:
                                continue
                    except Exception:
                        pass

                    # --- Checkboxes (required only; avoid marketing/newsletters) ---
                    try:
                        checks = frame.locator("input[type='checkbox']:not([disabled])")
                        for i in range(checks.count()):
                            c = checks.nth(i)
                            try:
                                lbl = near_text(frame, c).lower()
                                req = c.get_attribute("required") is not None or c.get_attribute("aria-required") in ["true", True] or looks_required(lbl)
                                if not req:
                                    continue
                                if any(w in lbl for w in AVOID_CHECKBOX):
                                    print(f"🚫 Skipping nonessential checkbox: {lbl[:50]}")
                                    continue
                                c.check(force=True)
                                print(f"☑️ Checked required checkbox ({lbl[:60]})")
                            except Exception:
                                continue
                    except Exception:
                        pass

                print("✅ Required-completeness pass finished.")
            except Exception as e:
                print(f"⚠️ Required-completeness pass failed: {e}")

            

            # ✅ EXTRA: Global scan for any unfilled fields (outside iframe or below form)
            # 🔁 LinkedIn URL from user (single source)
            linkedin_url = (getattr(user, "linkedin_url", "") or "").strip()

            # 🚫 REMOVE the old "Global scan" that filled "N/A" before this point.

            # 🌐 UNIVERSAL ACCESSIBLE-NAME FIELD SCANNER (dynamic, user-only)
            try:
                print("🌐 Running dynamic universal field scanner (accessible-name aware)...")

                def _country_human(code: str) -> str:
                    return {
                        "DK": "Denmark",
                        "US": "United States",
                        "UK": "United Kingdom",
                        "FRA": "France",
                        "GER": "Germany",
                    }.get((code or "").upper(), "")

                user_data = {
                    "first_name": user.first_name or "",
                    "last_name": user.last_name or "",
                    "email": user.email or "",
                    "phone": getattr(user, "phone_number", "") or "",
                    "linkedin": linkedin_url,
                    "country": _country_human(getattr(user, "country", "")),
                    "city": getattr(user, "location", "") or "",
                    "occupation": getattr(user, "occupation", "") or "",
                    "company": getattr(user, "category", "") or "",
                }

                # Helper that returns an element's best label using several strategies
                def accessible_label(frame, el):
                    try:
                        return frame.evaluate(
                            """
                            (el) => {
                            const byLabel = (el.labels && el.labels[0] && el.labels[0].innerText) || "";
                            const aria = el.getAttribute("aria-label") || "";
                            const ph = el.getAttribute("placeholder") || "";
                            const byId = (() => {
                                const ids = (el.getAttribute("aria-labelledby") || "").trim().split(/\s+/).filter(Boolean);
                                return ids.map(id => (document.getElementById(id)?.innerText || "")).join(" ");
                            })();
                            // Nearby header/text container as fallback
                            const near = (() => {
                                const lab = el.closest("label");
                                if (lab) return lab.innerText || "";
                                const wrapper = el.closest("div, section, fieldset");
                                return wrapper ? (wrapper.querySelector("legend,h1,h2,h3,h4,span,small,label")?.innerText || "") : "";
                            })();
                            return [byLabel, aria, ph, byId, near].join(" ").replace(/\\s+/g, " ").trim();
                            }
                            """,
                            el,
                        ) or ""
                    except Exception:
                        return ""

                # Mapping predicate → user value, ordered by specificity
                def value_for(label: str, el_type: str) -> str:
                    L = label.lower()

                    if "first" in L or "given" in L or "forename" in L:
                        return user_data["first_name"]
                    if "last" in L or "surname" in L or "family name" in L:
                        return user_data["last_name"]
                    if "email" in L or el_type == "email":
                        return user_data["email"]
                    if "phone" in L or "mobile" in L or "tel" in L or el_type == "tel":
                        return user_data["phone"]
                    if "linkedin" in L or ("profile" in L and "url" in L) or ("url" in L and "linkedin" in L):
                        return user_data["linkedin"]
                    if "country" in L:
                        return user_data["country"]
                    if "city" in L or "town" in L:
                        return user_data["city"]
                    if "job title" in L or ("title" in L and "job" in L) or "position" in L or "role" in L:
                        return user_data["occupation"]
                    if "company" in L or "employer" in L or "organization" in L or "organisation" in L:
                        return user_data["company"]

                    # generic URL fields: only fill if clearly LinkedIn
                    if ("url" in L or "website" in L) and "linkedin" in L:
                        return user_data["linkedin"]

                    return ""

                filled = 0

                # Scan inputs, textareas, selects, and React comboboxes
                selectors = [
                    "input:not([type='hidden']):not([disabled])",
                    "textarea:not([disabled])",
                    "select:not([disabled])",
                    "[role='combobox'] input",   # common for react-select & MUI
                ]

                for frame in page.frames:
                    print(f"🔎 Scanning frame: {frame.name or 'main'}")
                    for sel in selectors:
                        loc = frame.locator(sel)
                        n = loc.count()
                        for i in range(n):
                            el = loc.nth(i)
                            try:
                                if not el.is_visible():
                                    continue

                                # Determine element type & current value
                                etype = (el.get_attribute("type") or "").lower()
                                curr = ""
                                try:
                                    curr = el.input_value().strip()
                                except Exception:
                                    try:
                                        curr = el.inner_text().strip()
                                    except Exception:
                                        curr = ""

                                # Skip if already non-empty and not "N/A"
                                if curr and curr.upper() != "N/A":
                                    continue

                                # Build best label
                                label = accessible_label(frame, el)
                                if not label:
                                    # last-ditch: use name/id
                                    label = " ".join(filter(None, [
                                        el.get_attribute("name") or "",
                                        el.get_attribute("id") or "",
                                        etype
                                    ])).strip()

                                # Decide value from user data
                                val = value_for(label, etype)

                                # If field currently says "N/A" but we have a user value, clear then fill
                                if (not val) and curr.upper() == "N/A":
                                    # we don't want to leave N/A anywhere; clear it
                                    try:
                                        el.fill("")
                                    except Exception:
                                        pass
                                    continue

                                if not val:
                                    continue  # nothing to fill from user

                                # Scroll into view + fill + commit (helps controlled inputs)
                                try:
                                    el.scroll_into_view_if_needed(timeout=2000)
                                except Exception:
                                    pass

                                if el.evaluate("el => el.tagName.toLowerCase() === 'select'"):
                                    # select dropdown: choose matching option
                                    # primarily used for Country etc.
                                    try:
                                        # exact text match first
                                        el.select_option(label=val)
                                    except Exception:
                                        # fallback: partial match (lowercase contains)
                                        frame.evaluate(
                                            """
                                            (el, want) => {
                                            const opts = Array.from(el.options || []);
                                            const target = opts.find(o => (o.textContent||'').trim().toLowerCase() === want.toLowerCase())
                                                        || opts.find(o => (o.textContent||'').toLowerCase().includes(want.toLowerCase()));
                                            if (target) el.value = target.value;
                                            el.dispatchEvent(new Event('change', {bubbles:true}));
                                            }
                                            """,
                                            el,
                                            val,
                                        )
                                else:
                                    # text-like fields
                                    el.fill(val)
                                    try:
                                        el.press("Tab")
                                    except Exception:
                                        pass
                                    # fire input/change for frameworks
                                    try:
                                        frame.evaluate(
                                            "el => { el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }",
                                            el,
                                        )
                                    except Exception:
                                        pass

                                print(f"✅ Filled “{label[:60]}” → {val}")
                                filled += 1

                            except Exception:
                                continue

                print(f"✅ Dynamic universal scanner filled {filled} fields.")

                # 🔁 Robust LinkedIn retry anywhere (after dynamic fill & any late-render)
                if linkedin_url:
                    try:
                        print("🔎 Extra LinkedIn scan across all frames...")
                        for frame in page.frames:
                            ln = frame.locator(
                                "input[name*='linkedin' i], input[id*='linkedin' i], input[placeholder*='linkedin' i], "
                                "input[aria-label*='linkedin' i], input[name*='profile' i][name*='url' i], "
                                "input[id*='profile' i][id*='url' i]"
                            )
                            if ln.count() > 0:
                                for j in range(ln.count()):
                                    el = ln.nth(j)
                                    if el.is_visible():
                                        cur = ""
                                        try:
                                            cur = el.input_value().strip()
                                        except Exception:
                                            pass
                                        if not cur or cur.upper() == "N/A":
                                            el.fill(linkedin_url)
                                            try:
                                                el.press("Tab")
                                            except Exception:
                                                pass
                                            print("🔗 LinkedIn field filled via extra scan.")
                                            break
                    except Exception:
                        pass

            except Exception as e:
                print(f"⚠️ Dynamic universal field scanner failed: {e}")


            # 🧠 AI dynamic field filling
            try:
                fill_dynamic_fields(context, user)
            except Exception as e:
                print(f"⚠️ AI dynamic field filling failed: {e}")
                traceback.print_exc()

            # Resume upload + rest of function unchanged...



            # 9️⃣ Resume upload (Greenhouse robust fix for visually-hidden inputs)
            try:
                if resume_path:
                    print(f"📎 Attempting to upload resume from: {resume_path}")

                    # 🧠 Step 1: Prefer "Attach" button if available
                    try:
                        all_buttons = context.locator("button, label")
                        attach_btn = all_buttons.filter(has_text="Attach")
                        manual_btn = all_buttons.filter(has_text="Enter manually")

                        if attach_btn.count() > 0:
                            print("🧠 AI decision: Choosing 'Attach' option for resume upload.")
                            attach_btn.first.click()
                            page.wait_for_timeout(2500)
                        elif manual_btn.count() > 0:
                            print("⚠️ Only 'Enter manually' found — skipping upload.")
                        else:
                            print("⚠️ No resume option buttons found.")
                    except Exception as e:
                        print(f"⚠️ Could not click attach button: {e}")

                    # 🕵️ Step 2: Find <input type="file"> even if hidden
                    file_input = None
                    for i in range(10):  # retry 10s
                        try:
                            for frame in page.frames:
                                locator = frame.locator("input[type='file']")
                                if locator.count() > 0:
                                    file_input = locator.first
                                    context = frame
                                    print(f"✅ Found file input (possibly hidden) in frame after {i+1}s")
                                    break
                            if file_input:
                                break
                        except Exception:
                            pass
                        page.wait_for_timeout(1000)

                    # 🧱 Step 3: Force unhide input and upload
                    if file_input:
                        try:
                            # Force visibility using direct JS
                            frame = context
                            frame.evaluate("""
                                () => {
                                    const input = document.querySelector('input[type=file]');
                                    if (input) {
                                        input.style.display = 'block';
                                        input.style.visibility = 'visible';
                                        input.style.position = 'static';
                                        input.style.width = '200px';
                                        input.style.height = '40px';
                                        input.classList.remove('visually-hidden');
                                        input.removeAttribute('hidden');
                                        console.log("🎯 File input forcibly unhidden.");
                                    } else {
                                        console.warn("⚠️ No file input found in DOM for unhide.");
                                    }
                                }
                            """)
                            # Set file
                            file_input.set_input_files(resume_path)
                            print("📄 Successfully uploaded resume via forced visibility fix.")
                        except Exception as e:
                            print(f"⚠️ Upload attempt failed even after unhide: {e}")
                    else:
                        print("⚠️ Could not find any input[type='file'] after retries.")

                    # ✅ Step 4: Verify attachment (text or filename visible)
                    try:
                        uploaded = context.locator("text=.docx, text=.pdf, text=Attached, text=uploaded")
                        if uploaded.count() > 0:
                            print("✅ Resume visibly uploaded on page.")
                        else:
                            print("⚠️ Could not visually verify upload (might still be attached internally).")
                    except Exception:
                        pass

            except Exception as e:
                print(f"⚠️ Resume upload failed: {e}")



            # 🔍 UNIVERSAL FIELD SCANNER (fills all visible input-like fields dynamically from user data)
            try:
                print("🌐 Running user-based universal field scan (no static values)...")

                selectors = [
                    "input:not([type='hidden']):not([disabled])",
                    "textarea:not([disabled])",
                    "div[contenteditable='true']"
                ]
                filled_fields = []

                for frame in page.frames:
                    print(f"🔎 Scanning frame: {frame.name or 'main'}")

                    for selector in selectors:
                        elements = frame.locator(selector)
                        count = elements.count()

                        for i in range(count):
                            el = elements.nth(i)
                            try:
                                if not el.is_visible():
                                    continue

                                # --- Collect identifiers ---
                                attrs = {
                                    "name": el.get_attribute("name") or "",
                                    "id": el.get_attribute("id") or "",
                                    "placeholder": el.get_attribute("placeholder") or "",
                                    "aria": el.get_attribute("aria-label") or "",
                                }
                                nearby = el.evaluate("""
                                    el => {
                                        const label = el.closest('label');
                                        const parent = el.closest('div');
                                        return (label?.innerText || parent?.innerText || '').toLowerCase();
                                    }
                                """)
                                joined = " ".join([attrs["name"], attrs["id"], attrs["placeholder"], attrs["aria"], nearby]).lower()

                                # Skip filled fields
                                current_val = (
                                    el.inner_text().strip()
                                    if selector == "div[contenteditable='true']"
                                    else el.input_value().strip()
                                )
                                if current_val:
                                    continue

                                # --- Smart mapping from user model ---
                                fill_value = None

                                if any(k in joined for k in ["first", "fname", "given"]):
                                    fill_value = user.first_name
                                elif any(k in joined for k in ["last", "lname", "surname", "family"]):
                                    fill_value = user.last_name
                                elif "email" in joined:
                                    fill_value = user.email
                                elif any(k in joined for k in ["phone", "mobile", "tel"]):
                                    fill_value = getattr(user, "phone_number", "")
                                elif any(k in joined for k in ["linkedin", "profile", "url"]):
                                    fill_value = getattr(user, "linkedin_url", "")
                                elif "country" in joined:
                                    # Convert DK → Denmark etc.
                                    country_map = dict(
                                        DK="Denmark",
                                        US="United States",
                                        UK="United Kingdom",
                                        FRA="France",
                                        GER="Germany",
                                    )
                                    fill_value = country_map.get(getattr(user, "country", ""), "")
                                elif any(k in joined for k in ["city"]):
                                    fill_value = getattr(user, "location", "")
                                elif any(k in joined for k in ["job", "title", "position", "role"]):
                                    fill_value = getattr(user, "occupation", "")
                                elif any(k in joined for k in ["company", "employer"]):
                                    fill_value = getattr(user, "category", "")

                                # Skip if no value found in user model
                                if not fill_value:
                                    continue

                                # Fill dynamically
                                el.fill(str(fill_value))
                                filled_fields.append((joined[:70], fill_value))
                                print(f"✅ Filled '{joined[:60]}' → {fill_value}")

                            except Exception:
                                continue

                print(f"✅ Universal field scan complete. Dynamically filled {len(filled_fields)} fields.")
            except Exception as e:
                print(f"⚠️ Universal field scan failed: {e}")





            # 🔟 Cover letter fill — skip captcha fields
            try:
                textareas = context.locator("textarea[name*='cover'], textarea[id*='cover'], textarea[placeholder*='cover']")
                if textareas.count() == 0:
                    textareas = context.locator("textarea")
                if textareas.count() > 0:
                    letter_text = cover_letter_text or (
                        "Dear Hiring Manager,\n\nI'm very interested in this opportunity and believe my background fits well."
                    )
                    for i in range(textareas.count()):
                        el = textareas.nth(i)
                        try:
                            if "captcha" not in el.get_attribute("name", "").lower():
                                el.fill(letter_text)
                                print("💬 Filled cover letter")
                                break
                        except Exception:
                            continue
            except Exception as e:
                print(f"⚠️ Could not fill cover letter: {e}")

            # 11️⃣ Dry run
            screenshot_path = f"/home/clinton/Internstart/media/ats_preview_{room.company_name.replace(' ', '_')}.png"
            if dry_run:
                print("🧪 Dry run active — skipping submit.")
                page.screenshot(path=screenshot_path, full_page=True)
                print(f"📸 Saved preview screenshot as {screenshot_path}")
                browser.close()
                return "dry-run"

            # 12️⃣ Submit form
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

            # 13️⃣ Verify success
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
