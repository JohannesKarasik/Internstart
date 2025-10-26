from playwright.sync_api import sync_playwright
from django.conf import settings
from .models import ATSRoom, User
from .ats_filler import fill_dynamic_fields  # 🧠 optional mop-up
import time, traceback, random, json, os, tempfile, re
from urllib.parse import urlparse
from datetime import datetime
from base.ai.field_interpreter import map_fields_to_answers



# ---------- helpers ----------

def _ai_fill_leftovers(page, user):
    """Debug AI field mapping — logs what fields are being detected, which are unfilled, and what is sent to AI."""
    try:
        profile_path = f"/home/clinton/Internstart/media/user_profiles/{user.id}.json"
        if not os.path.exists(profile_path):
            print(f"⚠️ No profile JSON found for user {user.id} at {profile_path}")
            return 0

        with open(profile_path, "r", encoding="utf-8") as f:
            user_profile = json.load(f)

        # 1️⃣ Scan all fields
        inv = scan_all_fields(page)
        print(f"🔍 DEBUG: total scanned fields = {len(inv)}")

        # Log a preview of what scan_all_fields() actually sees
        for i, fdata in enumerate(inv[:10]):  # show first 10 fields
            print(f"   [{i}] label='{fdata.get('label')}' placeholder='{fdata.get('placeholder')}' value='{fdata.get('current_value')}'")

        # 2️⃣ Collect only unfilled fields
        fields_to_ai = []
        for i, fdata in enumerate(inv):
            val = fdata.get("current_value") or ""
            label = fdata.get("label") or fdata.get("placeholder") or fdata.get("aria_label") or fdata.get("name") or ""
            if not val.strip():  # empty fields only
                fields_to_ai.append({
                    "field_id": f"{fdata['frame_index']}_{fdata['nth']}",
                    "label": label
                })

        print(f"🔍 DEBUG: {len(fields_to_ai)} unfilled fields found")

        # Show 5 examples of what will be sent to GPT
        for i, f in enumerate(fields_to_ai[:5]):
            print(f"   → {f}")

        # 3️⃣ If none found, skip
        if not fields_to_ai:
            print("🤖 AI pass: sending 0 fields for interpretation… (No unfilled fields detected)")
            return 0

        # 4️⃣ Send to AI
        print(f"🤖 AI pass: sending {len(fields_to_ai)} fields for interpretation…")
        answers = map_fields_to_answers(fields_to_ai, user_profile)

        print("============== 🧠 AI RAW OUTPUT ==============")
        print(json.dumps(answers, indent=2, ensure_ascii=False))
        print("=============================================")

        # 5️⃣ Try filling the AI’s answers
        filled = 0
        frames = list(page.frames)
        for fdata in inv:
            fid = f"{fdata['frame_index']}_{fdata['nth']}"
            val = answers.get(fid)
            if not val or val.lower() == "skip":
                continue

            fr = frames[fdata["frame_index"]]
            el = fr.locator(fdata["query"]).nth(fdata["nth"])
            if not el.is_visible():
                continue

            try:
                el.scroll_into_view_if_needed(timeout=1500)
                el.fill(val)
                fr.evaluate("el=>{el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));}", el)
                print(f"✅ AI filled “{fdata.get('label','(no label)')[:60]}” → {val}")
                filled += 1
            except Exception as e:
                print(f"⚠️ Could not fill field {fid}: {e}")

        print(f"🤖 AI pass completed — filled {filled} fields.")
        return filled

    except Exception as e:
        print(f"⚠️ AI leftovers pass failed: {e}")
        return 0


def write_temp_cover_letter_file(text, suffix=".txt"):
    fd, path = tempfile.mkstemp(prefix="cover_letter_", suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path

def _safe_press(page, target_locator, key: str):
    """Press a key on a target if possible; else fall back to page.keyboard."""
    try:
        if target_locator:
            target_locator.press(key)
            return True
    except Exception:
        pass
    try:
        page.keyboard.press(key)
        return True
    except Exception:
        return False

def dismiss_privacy_overlays(page, timeout_ms=8000):
    import time as _t
    start = _t.time()
    known = [
        "#onetrust-accept-btn-handler", "button#onetrust-accept-btn-handler",
        "#CybotCookiebotDialogBodyLevelButtonAccept", "#CybotCookiebotDialogBodyButtonAccept",
        "button:has-text('Accept All')", "button:has-text('Allow all')",
        "button:has-text('Enable All')", "button:has-text('Got it')",
        "button:has-text('Accepter alle')", "button:has-text('Tillad alle')",
        "button:has-text('Aktiver alle')", "button:has-text('OK')", "button:has-text('Forstået')",
        "button[aria-label*='accept' i]", "button:has-text('accept' i)",
        "[role='button']:has-text('accept' i)", "input[type='button'][value*='accept' i]",
        "input[type='submit'][value*='accept' i]"
    ]
    while (_t.time() - start) * 1000 < timeout_ms:
        clicked = False
        for fr in page.frames:
            try:
                for sel in known:
                    loc = fr.locator(sel)
                    if loc.count() and loc.first.is_visible():
                        loc.first.click(force=True)
                        clicked = True
                        break
            except Exception:
                pass
        if clicked:
            page.wait_for_timeout(400)
            continue
        page.wait_for_timeout(250)
    try:
        xbtn = page.locator(":is(button,[role='button'],a)[aria-label*='close' i], :is(button,a):has-text('×')")
        if xbtn.count() and xbtn.first.is_visible():
            xbtn.first.click(force=True)
    except Exception:
        pass

# ---------- dropdown helpers ----------
def _closest_dropdown_root(frame, label_for_id: str, label_id: str):
    try:
        if label_for_id:
            el = frame.locator(f"#{label_for_id}")
            if el.count() and el.first.is_visible():
                return el.first
    except Exception: pass
    try:
        if label_id:
            el = frame.locator(f"[aria-labelledby~='{label_id}']")
            if el.count() and el.first.is_visible():
                return el.first
    except Exception: pass
    try:
        if label_for_id:
            el = frame.locator(f"label[for='{label_for_id}'] + .select-shell, label[for='{label_for_id}'] + * .select-shell")
            if el.count() and el.first.is_visible():
                return el.first
        if label_id:
            el = frame.locator(f"#{label_id} + .select-shell, #{label_id} + * .select-shell")
            if el.count() and el.first.is_visible():
                return el.first
    except Exception: pass
    try:
        base = frame.locator(f"#{label_id}") if label_id else frame.locator(f"label[for='{label_for_id}']")
        if base.count():
            wr = base.first.locator("xpath=ancestor::*[self::div or self::section][1]")
            el = wr.locator(".select-shell, .select__container, .select__control, [role='combobox'], [aria-haspopup='listbox']")
            if el.count() and el.first.is_visible():
                return el.first
    except Exception: pass
    return None

def _click_and_choose_option(page, scope, text: str) -> bool:
    try:
        menu = scope.locator(
            ":is([role='listbox'], [role='menu'], .select__menu, .dropdown-menu, .MuiPaper-root, .MuiPopover-paper, ul[role='listbox'])"
        )
        if not menu.count():
            return False
        opt = menu.locator(":is([role='option'], [role='menuitem'], li, div, button, span)").filter(has_text=text).first
        if opt and opt.is_visible():
            opt.click(force=True)
            return True
    except Exception:
        pass
    return False

def _set_custom_dropdown_by_label(page, frame, label_el, want_text: str) -> bool:
    try:
        lab_id  = label_el.get_attribute("id") or ""
        lab_for = label_el.get_attribute("for") or ""
        root = _closest_dropdown_root(frame, lab_for, lab_id)
        if not root:
            return False

        want = (want_text or "").strip()

        for _ in range(3):
            try: root.scroll_into_view_if_needed()
            except Exception: pass
            try:
                root.click(force=True)
                frame.wait_for_timeout(120)
            except Exception:
                continue

            try:
                inner = root.locator("input[role='combobox'], input[aria-autocomplete='list'], input[type='text']").first
                if inner and inner.is_visible():
                    inner.fill("")
                    inner.type(want, delay=18)
                    _safe_press(page, inner, "Enter")
                    _safe_press(page, inner, "Tab")
                else:
                    root.type(want, delay=18)
                    _safe_press(page, root, "Enter")
                    _safe_press(page, root, "Tab")
            except Exception:
                pass

            try:
                committed = frame.evaluate(
                    """(labId,w)=>{const r=document.querySelector(`[aria-labelledby~="${labId}"]`)
                                   || (document.getElementById(labId)?.closest('.select__container,.select-shell,[role="combobox"],div'));
                                   const t=(r?.innerText||'').toLowerCase(); return t.includes((w||'').toLowerCase());}""",
                    lab_id, want
                )
                if committed: return True
            except Exception:
                pass

            if _click_and_choose_option(page, frame, want) or _click_and_choose_option(page, page, want):
                try:
                    committed = frame.evaluate(
                        """(labId,w)=>{const r=document.querySelector(`[aria-labelledby~="${labId}"]`)
                                       || (document.getElementById(labId)?.closest('.select__container,.select-shell,[role="combobox"],div'));
                                       const t=(r?.innerText||'').toLowerCase(); return t.includes((w||'').toLowerCase());}""",
                        lab_id, want
                    )
                    if committed: return True
                except Exception:
                    pass

        if lab_for:
            try:
                ok = frame.evaluate(
                    """(id,w)=>{const el=document.getElementById(id); if(!el) return false;
                        const tag=(el.tagName||'').toLowerCase();
                        if (tag==='select'){const o=[...el.options||[]];
                          const m=o.find(x=>(x.textContent||'').trim().toLowerCase()===(w||'').toLowerCase())
                                  || o.find(x=>(x.textContent||'').toLowerCase().includes((w||'').toLowerCase()));
                          if(!m) return false; el.value=m.value;}
                        else {el.value=w; el.setAttribute('value',w);}
                        el.dispatchEvent(new Event('input',{bubbles:true}));
                        el.dispatchEvent(new Event('change',{bubbles:true}));
                        return true;}""",
                    lab_for, want
                )
                if ok:
                    try: label_el.click(force=True)
                    except Exception: pass
                    frame.wait_for_timeout(80)
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False

# ---------- metadata + scan/fill ----------
DIAL = {"DK": "+45", "US": "+1", "UK": "+44", "FRA": "+33", "GER": "+49"}

AUTO_YES_RE = re.compile(r"(privacy\s*policy|data\s*protection|consent|acknowledg(e|ement)|terms|gdpr|agree)", re.I)
AUTO_NO_RE  = re.compile(r"(currently\s*employ(ed)?\s*by|ever\s*been\s*employ(ed)?\s*by|subsidiar(y|ies)|conflict\s*of\s*interest)", re.I)

def _yesno_preference(label_text: str) -> str:
    L = (label_text or "").lower()
    if AUTO_YES_RE.search(L): return "Yes"
    if AUTO_NO_RE.search(L):  return "No"
    return ""

def _accessible_label(frame, el):
    try:
        return frame.evaluate(
            """(el)=>{const lab=(el.labels&&el.labels[0]&&el.labels[0].innerText)||'';
                      const aria=el.getAttribute('aria-label')||'';
                      const ph=el.getAttribute('placeholder')||'';
                      const byId=(el.getAttribute('aria-labelledby')||'').trim().split(/\s+/)
                         .map(id=>document.getElementById(id)?.innerText||'').join(' ');
                      const near=el.closest('label')?.innerText
                        || el.closest('div,section,fieldset,.form-group,.field')
                             ?.querySelector('legend,h1,h2,h3,h4,span,small,label,.label,.title')?.innerText || '';
                      return [lab,aria,ph,byId,near].join(' ').replace(/\s+/g,' ').trim();}""",
            el
        ) or ""
    except Exception:
        return ""

def scan_all_fields(page):
    selectors = [
        "input:not([type='hidden']):not([disabled])",
        "textarea:not([disabled])",
        "select:not([disabled])",
        "[contenteditable='true']",
    ]
    inventory, frame_idx = [], {fr: i for i, fr in enumerate(page.frames)}
    total = 0
    for fr in page.frames:
        for q in selectors:
            loc = fr.locator(q)
            for i in range(loc.count()):
                el = loc.nth(i)
                try:
                    if not el.is_visible(): continue
                    et = (el.get_attribute("type") or "").lower()
                    curr = ""
                    try:
                        curr = el.inner_text().strip() if q == "[contenteditable='true']" else el.input_value().strip()
                    except Exception: pass
                    inventory.append({
                        "frame_index": frame_idx[fr], "query": q, "nth": i, "type": et,
                        "name": el.get_attribute("name") or "", "id": el.get_attribute("id") or "",
                        "placeholder": el.get_attribute("placeholder") or "",
                        "aria_label": el.get_attribute("aria-label") or "",
                        "label": _accessible_label(fr, el),
                        "required": bool(el.get_attribute("required") or (el.get_attribute("aria-required") in ["true", True])),
                        "current_value": curr,
                    })
                    total += 1
                except Exception:
                    pass
    print(f"🧩 Field scan complete — detected {total} fields across {len(page.frames)} frames.")
    return inventory

def _country_human(code: str) -> str:
    return {"DK":"Denmark","US":"United States","UK":"United Kingdom","FRA":"France","GER":"Germany"}.get((code or "").upper(), "")

def _attrs_blob(**kw):
    return " ".join([str(kw.get(k,"") or "") for k in ["label","name","id_","placeholder","aria_label","type_"]]).lower().strip()

def _value_from_meta(user, meta: str):
    L = (meta or "").lower()
    linkedin = (getattr(user,"linkedin_url","") or "").strip()
    cc = (getattr(user,"country","") or "").upper()
    phone_raw = (getattr(user,"phone_number","") or "").strip()
    phone = f"{DIAL.get(cc,'')} {phone_raw}".strip() if any(k in L for k in ["phone","mobile","tel"]) and phone_raw and not phone_raw.startswith("+") else phone_raw
    mapping = [
        (["first","fname","given","forename"], user.first_name or ""),
        (["last","lname","surname","family"],  user.last_name or ""),
        (["email","e-mail","mail"],            user.email or ""),
        (["phone","mobile","tel"],             phone),
        (["linkedin","profile url","profile_url"], linkedin),
        (["country","nationality"],            _country_human(cc)),
        (["city","town"],                      getattr(user,"location","") or ""),
        (["job title","title","position","role"], getattr(user,"occupation","") or ""),
        (["company","employer","organization","organisation","current company"], getattr(user,"category","") or ""),
    ]
    for keys,val in mapping:
        if any(k in L for k in keys) and val: return val
    if ("url" in L or "website" in L) and "linkedin" in L and linkedin: return linkedin
    return ""

def fill_from_inventory(page, user, inventory):
    filled = 0
    frames = list(page.frames)
    for it in inventory:
        try:
            fr = frames[it["frame_index"]]
            el = fr.locator(it["query"]).nth(it["nth"])
            if not el.is_visible(): continue
            try:
                curr = el.inner_text().strip() if it["query"]=="[contenteditable='true']" else el.input_value().strip()
            except Exception:
                curr = ""
            if curr and curr.upper()!="N/A": continue

            meta = _attrs_blob(
                label=it.get("label",""), name=it.get("name",""), id_=it.get("id",""),
                placeholder=it.get("placeholder",""), aria_label=it.get("aria_label",""),
                type_=it.get("type","")
            )
            val = _value_from_meta(user, meta)
            if not val: continue

            try: el.scroll_into_view_if_needed(timeout=1500)
            except Exception: pass

            is_select = False
            try: is_select = el.evaluate("el => el.tagName && el.tagName.toLowerCase()==='select'")
            except Exception: pass

            if is_select:
                try: el.select_option(label=val)
                except Exception:
                    fr.evaluate("""(el,w)=>{const o=[...el.options||[]];const t=(w||'').toLowerCase();
                                    const m=o.find(x=>(x.textContent||'').trim().toLowerCase()===t)
                                         || o.find(x=>(x.textContent||'').toLowerCase().includes(t));
                                    if(m){el.value=m.value; el.dispatchEvent(new Event('change',{bubbles:true}));}}""", el, val)
            else:
                el.fill(val)
                try: el.press("Tab")
                except Exception: pass
                try: fr.evaluate("el=>{el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));}", el)
                except Exception: pass

            print(f"✅ Filled “{meta[:60]}” → {val}")
            filled += 1
        except Exception:
            pass
    print(f"✅ Post-scan fill completed — filled {filled} fields from inventory.")
    return filled

# ---------- special Yes/No forcings ----------
def _force_ipg_employment_no(page, frame) -> bool:
    lab = frame.locator("label[for]").filter(has_text=re.compile(r"are you currently employed|ever been employed.*ipg", re.I)).first
    if not (lab and lab.is_visible()): return False
    lab_id  = lab.get_attribute("id") or ""
    lab_for = lab.get_attribute("for") or ""
    root = _closest_dropdown_root(frame, lab_for, lab_id)
    if not root: return False

    try: root.scroll_into_view_if_needed()
    except Exception: pass
    try: root.click(force=True); frame.wait_for_timeout(120)
    except Exception: pass

    inner = root.locator("input[role='combobox'], input[aria-autocomplete='list'], input[type='text']").first
    try:
        if inner and inner.is_visible():
            inner.fill(""); inner.type("No", delay=18)
            _safe_press(page, inner, "Enter"); _safe_press(page, inner, "Tab")
        else:
            root.type("No", delay=18)
            _safe_press(page, root, "Enter"); _safe_press(page, root, "Tab")
    except Exception:
        pass

    def committed():
        try:
            return frame.evaluate("""(labId)=>{const r=document.querySelector(`[aria-labelledby~="${labId}"]`)
                       || (document.getElementById(labId)?.closest('.select__container,.select-shell,[role="combobox"],div'));
                       const t=(r?.innerText||'').toLowerCase(); return t.includes('no');}""", lab_id)
        except Exception:
            return False

    if committed(): return True
    if _click_and_choose_option(page, frame, "No") or _click_and_choose_option(page, page, "No"):
        return committed()
    if lab_for:
        try:
            ok = frame.evaluate("""(id)=>{const el=document.getElementById(id); if(!el) return False;
                 if (el.tagName.toLowerCase()==='select'){const m=[...el.options||[]].find(o=>/\\bno\\b/i.test(o.textContent||'')); if(!m) return false; el.value=m.value;}
                 else {el.value='No'; el.setAttribute('value','No');}
                 el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); return true;}""",
                 lab_for)
            if ok:
                try: lab.click(force=True)
                except Exception: pass
                frame.wait_for_timeout(80)
                return committed()
        except Exception:
            pass
    return False

def _force_privacy_yes_if_needed(page, frame):
    labels = []
    try:
        labels = frame.locator("label[for]").all()
    except Exception:
        return 0
    changed = 0
    for lab in labels:
        try:
            if not lab.is_visible(): continue
            txt = (lab.inner_text() or "").strip()
            pref = _yesno_preference(txt)
            if not pref: continue
            ok = _set_custom_dropdown_by_label(page, frame, lab, pref)
            if ok:
                print(f"🟢 Set '{txt[:70]}' → {pref}")
                changed += 1
        except Exception:
            pass
    return changed

# ---------- main ----------
def apply_to_ats(room_id, user_id, resume_path=None, cover_letter_text="", dry_run=True, screenshot_delay_sec=3):
    """
    screenshot_delay_sec: wait this many seconds before the dry-run screenshot,
    so attachments/labels have time to render.
    """
    room = ATSRoom.objects.get(id=room_id)
    user = User.objects.get(id=user_id)

    if not resume_path:
        try:
            if hasattr(user, "resume") and user.resume:
                resume_path = user.resume.path
                print(f"📄 Loaded resume from user model: {resume_path}")
        except Exception as e:
            print(f"⚠️ Could not load resume from user model: {e}")

    print(f"🌐 Starting ATS automation for: {room.company_name} ({room.apply_url})")
    print(f"🧪 Dry-run mode: {dry_run}")

    log_dir = "/home/clinton/Internstart/media"
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_company = "".join(c if c.isalnum() else "_" for c in (room.company_name or "company"))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page()

        try:
            print(f"🌍 Visiting {room.apply_url} ...")
            page.goto(room.apply_url, timeout=120000, wait_until="domcontentloaded")
            page.wait_for_load_state("load", timeout=20000)
            page.wait_for_timeout(1200)
            dismiss_privacy_overlays(page)

            # try clicking a safe "Apply"
            try:
                if page.locator("input, textarea, select").count() < 3:
                    buttons = page.locator("button, a")
                    for i in range(buttons.count()):
                        b = buttons.nth(i)
                        if not b.is_visible(): continue
                        t = (b.inner_text() or "").lower()
                        if any(w in t for w in ["apply","start application","start your application","continue","get started","begin","proceed"]) \
                           and not any(bad in t for bad in ["quick apply","linkedin","indeed","glassdoor","jobindex","login","sign in","create account","external"]):
                            b.click()
                            print(f"🖱️ Safely clicked '{(t or '')[:40]}'")
                            page.wait_for_timeout(1200)
                            break
            except Exception:
                pass

            dismiss_privacy_overlays(page, timeout_ms=3000)

            # choose context (iframe hosting the form)
            context = page
            try:
                for fr in page.frames:
                    if fr == page.main_frame: continue
                    if fr.locator("input, textarea, select").count() > 3:
                        context = fr
                        print("🔄 Switched to ATS iframe")
                        break
            except Exception: pass

            # reveal fields
            try: context.wait_for_selector("input, textarea, select", timeout=12000)
            except Exception: pass
            try:
                for _ in range(6):
                    page.mouse.wheel(0, 420)
                    page.wait_for_timeout(220 + random.randint(0,120))
            except Exception: pass

            # scan + fill
            inv = scan_all_fields(page)
            try:
                with open(os.path.join(log_dir, f"ats_field_inventory_{safe_company}_{ts}.json"), "w", encoding="utf-8") as f:
                    json.dump(inv, f, ensure_ascii=False, indent=2)
            except Exception: pass

            fill_from_inventory(page, user, inv)

            # force Yes/No type questions (privacy → Yes; employment → No)
            _force_privacy_yes_if_needed(page, context)
            if _force_ipg_employment_no(page, context):
                print("🟢 IPG employment → No (forced & verified)")
            else:
                print("🟡 IPG employment not confirmed — continuing; ATS validation may catch it")

            # AI mop-up
            try:
                ai_filled = _ai_fill_leftovers(page, inv, user)
                print(f"🤖 AI filled {ai_filled} additional fields.")
            except Exception as e:
                print(f"⚠️ AI leftovers pass failed: {e}")

            # resume upload
            try:
                if resume_path:
                    print(f"📎 Uploading resume: {resume_path}")
                    try:
                        btn = context.locator(":is(button,label,a):has-text('Attach')")
                        if btn.count() and btn.first.is_visible():
                            btn.first.click(); page.wait_for_timeout(800)
                    except Exception: pass
                    file_input = None
                    for fr in page.frames:
                        try:
                            fi = fr.locator("input[type='file']")
                            if fi.count():
                                file_input = fi.first; context = fr; break
                        except Exception: pass
                    if file_input:
                        try:
                            context.evaluate("""()=>{const i=document.querySelector('input[type=file]'); if(!i) return;
                                i.style.display='block'; i.style.visibility='visible'; i.style.position='static';
                                i.removeAttribute('hidden'); i.classList?.remove('visually-hidden'); }""")
                        except Exception: pass
                        file_input.set_input_files(resume_path)
                        print("✅ Resume uploaded")
            except Exception as e:
                print(f"⚠️ Resume upload failed: {e}")

            # cover letter
            try:
                letter = cover_letter_text or "test coverletter"
                inserted = False
                ta = context.locator("textarea[name*='cover' i], textarea[id*='cover' i], textarea[aria-label*='cover' i]")
                if not ta.count(): ta = context.locator("textarea")
                for i in range(min(6, ta.count())):
                    t = ta.nth(i)
                    if t.is_visible():
                        t.fill(letter); inserted = True; print("💬 Cover letter pasted"); break
                if not inserted:
                    ce = context.locator("[contenteditable='true']")
                    for i in range(min(6, ce.count())):
                        c = ce.nth(i)
                        if c.is_visible():
                            c.click(); c.fill(letter); inserted = True; print("💬 Cover letter pasted (contenteditable)"); break
                if not inserted:
                    print("📎 Uploading cover letter as file fallback")
                    fp = write_temp_cover_letter_file(letter)
                    file_input = None
                    for fr in page.frames:
                        try:
                            fi = fr.locator("input[type='file']")
                            if fi.count(): file_input = fi.first; context = fr; break
                        except Exception: pass
                    if file_input: file_input.set_input_files(fp)
            except Exception as e:
                print(f"⚠️ Cover letter step failed: {e}")

            # dry run or submit
            screenshot_path = os.path.join(log_dir, f"ats_preview_{safe_company}_{ts}.png")
            if dry_run:
                print("🧪 Dry run — skipping submit")
                # NEW: wait a bit so uploads/labels render before screenshot
                delay_ms = max(int(screenshot_delay_sec * 1000), 0)
                if delay_ms:
                    print(f"⏱️ Waiting {screenshot_delay_sec}s before screenshot…")
                    page.wait_for_timeout(delay_ms)
                try:
                    page.screenshot(path=screenshot_path, full_page=True)
                    print(f"📸 Saved preview → {screenshot_path}")
                except Exception: pass
                browser.close()
                return "dry-run"

            try:
                sb = context.locator("button:has-text('Submit'), button:has-text('Apply'), input[type='submit']")
                if sb.count(): sb.first.click(); print("🚀 Submitted"); time.sleep(5)
                else: print("⚠️ No submit button found")
            except Exception as e:
                print(f"⚠️ Submit failed: {e}")

            html = page.content().lower()
            browser.close()
            if any(k in html for k in ["thank", "confirmation", "submitted", "successfully", "application received"]):
                print(f"✅ Application for {room.company_name} submitted successfully!")
                return True
            print(f"⚠️ Submission for {room.company_name} not verified")
            return False

        except Exception as e:
            print(f"❌ Fatal error: {e}")
            traceback.print_exc()
            try:
                err_shot = os.path.join(log_dir, f"error_screenshot_{safe_company}_{ts}.png")
                page.screenshot(path=err_shot, full_page=True)
                print(f"📸 Saved error screenshot → {err_shot}")
            except Exception:
                pass
            browser.close()
            return False
