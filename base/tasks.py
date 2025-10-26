from playwright.sync_api import sync_playwright
from django.conf import settings
from .models import ATSRoom, User
from .ats_filler import fill_dynamic_fields   # 🧠 AI field filler (kept)
import time, traceback, random, json
from urllib.parse import urlparse
import os, tempfile
from datetime import datetime
import re

# --- helper: write a small temp text file (used if ATS only accepts file upload for CL) ---
def write_temp_cover_letter_file(text, suffix=".txt"):
    fd, path = tempfile.mkstemp(prefix="cover_letter_", suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# --- universal cookie/consent dismiss ---
def dismiss_privacy_overlays(page, timeout_ms=8000):
    import re, time as _time
    start = _time.time()

    known_selectors = [
        "#onetrust-accept-btn-handler",
        "button#onetrust-accept-btn-handler",
        "#CybotCookiebotDialogBodyLevelButtonAccept",
        "#CybotCookiebotDialogBodyButtonAccept",
        "button:has-text('Accept All')",
        "button:has-text('ACCEPT ALL')",
        "button:has-text('Allow all')",
        "button:has-text('Enable All')",
        "button:has-text('Enable all')",
        "button:has-text('Got it')",
        # Danish
        "button:has-text('Accepter alle')",
        "button:has-text('Tillad alle')",
        "button:has-text('Aktiver alle')",
        "button:has-text('OK')",
        "button:has-text('Forstået')",
        # generic fallbacks
        "button[aria-label*='accept' i]",
        "button:has-text('accept' i)",
        "[role='button']:has-text('accept' i)",
        "input[type='button'][value*='accept' i]",
        "input[type='submit'][value*='accept' i]",
    ]

    POSITIVE = re.compile(r"(accept|agree|allow|enable|ok|got it|continue|save.*(preferences|settings))", re.I)
    NEGATIVE = re.compile(r"(reject|deny|decline|manage|settings|preferences|options|custom|kun nødvendige|strictly necessary)", re.I)

    def try_click_in_frame(frame):
        for sel in known_selectors:
            try:
                btns = frame.locator(sel)
                if btns.count() > 0:
                    for i in range(min(btns.count(), 3)):
                        b = btns.nth(i)
                        if b.is_visible():
                            b.click(force=True)
                            return True
            except Exception:
                pass
        try:
            containers = frame.locator(":is([id*='cookie' i],[class*='cookie' i],[id*='consent' i],[class*='consent' i],[id*='gdpr' i],[class*='gdpr' i],div[role='dialog'], .modal, .overlay, .cmp-container)")
            btns = containers.locator(":is(button,[role='button'],a,input[type='button'],input[type='submit'])")
            n = btns.count()
            for i in range(n):
                el = btns.nth(i)
                if not el.is_visible():
                    continue
                txt = (el.inner_text() or el.get_attribute("value") or "").strip()
                if POSITIVE.search(txt) and not NEGATIVE.search(txt):
                    el.click(force=True)
                    return True
        except Exception:
            pass
        return False

    while (_time.time() - start) * 1000 < timeout_ms:
        clicked = False
        for fr in page.frames:
            try:
                if try_click_in_frame(fr):
                    clicked = True
            except Exception:
                continue
        if clicked:
            page.wait_for_timeout(500)
            continue
        page.wait_for_timeout(250)

    # last-resort close button
    try:
        xbtn = page.locator(":is(button,[role='button'],a)[aria-label*='close' i], :is(button,a):has-text('×')")
        if xbtn.count() > 0 and xbtn.first.is_visible():
            xbtn.first.click(force=True)
    except Exception:
        pass
# --- end consent helper ---


def _closest_dropdown_root(frame, label_for_id: str, label_id: str):
    """Find the clickable root for a custom dropdown using the label's for/id relationships."""
    # 1) Try the element referenced by label's 'for'
    try:
        el = frame.locator(f"#{label_for_id}")
        if el.count() and el.first.is_visible():
            return el.first
    except Exception:
        pass

    # 2) Try a sibling container commonly used by custom selects
    try:
        el = frame.locator(f"label[for='{label_for_id}']").locator("xpath=following-sibling::*[1]")
        if el.count() and el.first.is_visible():
            return el.first
    except Exception:
        pass

    # 3) Try anything bound to this label id via aria-labelledby
    try:
        el = frame.locator(f"[aria-labelledby='{label_id}']")
        if el.count() and el.first.is_visible():
            return el.first
    except Exception:
        pass

    # 4) Last resort: the nearest “shell” looking div under the same container
    try:
        wrapper = frame.locator(f"#{label_id}, label[for='{label_for_id}']").first
        if wrapper:
            el = wrapper.locator("xpath=ancestor::*[self::div or self::section][1]").locator(
                ".select__control, .select__container, .select-shell, [role='combobox'], [aria-haspopup='listbox'], div"
            )
            if el.count() and el.first.is_visible():
                return el.first
    except Exception:
        pass
    return None


def _click_and_choose_option(page, frame, want_text: str) -> bool:
    """
    After a dropdown is opened, pick an option by visible text.
    Search both inside the frame and in portals mounted on <body>.
    Retry for a short period because some menus mount with a delay.
    """
    selectors_menu = (
        ":is("
        "[role='listbox'], [role='menu'], "
        ".MuiPaper-root, .MuiPopover-paper, "
        ".select__menu, .dropdown-menu, "
        "[class*='menu' i], [class*='options' i], "
        "ul[role='listbox'], ul"
        ")"
    )
    selectors_opt = ":is([role='option'], [role='menuitem'], li, div, button, span)"

    want = (want_text or "").strip()
    deadline = time.time() + 2.5  # up to ~2.5s

    while time.time() < deadline:
        for scope in (frame, page):
            try:
                menu = scope.locator(selectors_menu)
                if menu.count():
                    opt = menu.locator(selectors_opt).filter(has_text=want).first
                    if opt and opt.is_visible():
                        opt.click(force=True)
                        try:
                            frame.wait_for_timeout(120)
                        except Exception:
                            pass
                        return True
            except Exception:
                pass
        try:
            frame.wait_for_timeout(120)
        except Exception:
            pass
    return False



def _set_custom_dropdown_by_label(page, frame, label_el, prefer_text: str) -> bool:
    """
    Using a <label> element, open and set its custom dropdown to prefer_text (e.g., 'Yes'/'No').
    Tries the inner input (type-ahead) path first, then the click-an-option path.
    """
    try:
        label_id  = label_el.get_attribute("id") or ""
        label_for = label_el.get_attribute("for") or ""
        root = _closest_dropdown_root(frame, label_for, label_id)
        if not root:
            return False

        # open/focus
        try:
            root.scroll_into_view_if_needed()
        except Exception:
            pass
        try:
            root.click(force=True)
            frame.wait_for_timeout(120)
        except Exception:
            return False

        # 1) TYPE-AHEAD PATH (most reliable for React/Remix selects)
        try:
            # find the real editable part inside the shell
            inp = root.locator("input, [contenteditable='true'], [role='combobox'] input, [role='textbox']").first
            if inp and inp.is_visible():
                try:
                    inp.fill("")           # clear any placeholder text
                except Exception:
                    pass
                inp.type(prefer_text, delay=20)
            else:
                # fallback: type on the root
                root.type(prefer_text, delay=20)

            # commit selection
            frame.keyboard.press("Enter")
            frame.wait_for_timeout(120)
            # blur to force React onBlur/onChange
            try:
                frame.keyboard.press("Tab")
                frame.wait_for_timeout(60)
            except Exception:
                pass
        except Exception:
            pass

        # 2) If text typing didn't visibly set it, try the click-an-option path
        if not _click_and_choose_option(page, frame, prefer_text):
            # may already be selected by Enter; that's fine
            pass

        # 3) verification: read visible text on the labelled shell
        try:
            committed = frame.evaluate("""
                (labId, want) => {
                  const root =
                    document.querySelector(`[aria-labelledby="${labId}"]`) ||
                    document.getElementById(labId)?.closest('.select__container') ||
                    document.getElementById(labId)?.parentElement;
                  if (!root) return false;
                  const txt = (root.innerText || '').toLowerCase();
                  return txt.includes((want || '').toLowerCase());
                }
            """, label_id, prefer_text)
        except Exception:
            committed = False

        if committed:
            return True

        # 4) last-resort: try to set the underlying labelled control directly
        try:
            ok = frame.evaluate("""
                (elId, want) => {
                  const el = document.getElementById(elId);
                  if (!el) return false;
                  const lower = (want || '').toLowerCase();

                  if (el.tagName && el.tagName.toLowerCase() === 'select') {
                    const opts = Array.from(el.options || []);
                    const m = opts.find(o => ((o.textContent||'').trim().toLowerCase() === lower) ||
                                             ((o.textContent||'').toLowerCase().includes(lower)));
                    if (m) {
                      el.value = m.value;
                      el.dispatchEvent(new Event('input', { bubbles: true }));
                      el.dispatchEvent(new Event('change', { bubbles: true }));
                      return true;
                    }
                  }
                  if (el.tagName && el.tagName.toLowerCase() === 'input') {
                    el.value = want;
                    el.setAttribute('value', want);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    return true;
                  }
                  return false;
                }
            """, label_for, prefer_text)
            if ok:
                return True
        except Exception:
            pass

        return False
    except Exception:
        return False




# ---------- Phase 1: Scan (inventory every field first) ----------
def _accessible_label(frame, el):
    try:
        return frame.evaluate(
            """
            (el) => {
              const byLabel = (el.labels && el.labels[0] && el.labels[0].innerText) || "";
              const aria    = el.getAttribute("aria-label") || "";
              const ph      = el.getAttribute("placeholder") || "";
              const byId    = (() => {
                 const ids = (el.getAttribute("aria-labelledby") || "").trim().split(/\\s+/).filter(Boolean);
                 return ids.map(id => (document.getElementById(id)?.innerText || "")).join(" ");
              })();
              const near = (() => {
                 const lab = el.closest("label");
                 if (lab) return lab.innerText || "";
                 const wrapper = el.closest("div, section, fieldset, .form-group, .field");
                 return wrapper ? (wrapper.querySelector("legend,h1,h2,h3,h4,span,small,label,.label,.title")?.innerText || "") : "";
              })();
              return [byLabel, aria, ph, byId, near].join(" ").replace(/\\s+/g," ").trim();
            }
            """,
            el,
        ) or ""
    except Exception:
        return ""


def scan_all_fields(page):
    """
    Build an inventory of all visible input-like fields across every frame.
    Returns a list of dicts with stable (query + nth) locators to re-find elements later.
    """
    selectors = [
        "input:not([type='hidden']):not([disabled])",
        "textarea:not([disabled])",
        "select:not([disabled])",
        "[contenteditable='true']",
    ]
    inventory = []
    frame_idx_map = {frame: idx for idx, frame in enumerate(page.frames)}

    total = 0
    for frame in page.frames:
        for query in selectors:
            loc = frame.locator(query)
            n = loc.count()
            for i in range(n):
                el = loc.nth(i)
                try:
                    if not el.is_visible():
                        continue
                    etype = (el.get_attribute("type") or "").lower()
                    label = _accessible_label(frame, el)
                    req = bool(el.get_attribute("required") or (el.get_attribute("aria-required") in ["true", True]))

                    # current value
                    curr = ""
                    try:
                        if query == "[contenteditable='true']":
                            curr = el.inner_text().strip()
                        else:
                            curr = el.input_value().strip()
                    except Exception:
                        pass

                    item = {
                        "frame_index": frame_idx_map[frame],
                        "query": query,
                        "nth": i,
                        "type": etype or ("contenteditable" if query == "[contenteditable='true']" else ""),
                        "name": el.get_attribute("name") or "",
                        "id": el.get_attribute("id") or "",
                        "placeholder": el.get_attribute("placeholder") or "",
                        "aria_label": el.get_attribute("aria-label") or "",
                        "label": label,
                        "required": req,
                        "current_value": curr,
                    }
                    inventory.append(item)
                    total += 1
                except Exception:
                    continue

    print(f"🧩 Field scan complete — detected {total} fields across {len(page.frames)} frames.")
    return inventory


def _country_human(code: str) -> str:
    return {
        "DK": "Denmark",
        "US": "United States",
        "UK": "United Kingdom",
        "FRA": "France",
        "GER": "Germany",
    }.get((code or "").upper(), "")


# --- NEW: smarter value resolver (uses label + name + id + placeholder + aria) ---
DIAL = {"DK": "+45", "US": "+1", "UK": "+44", "FRA": "+33", "GER": "+49"}


# --- Auto-Yes/No intent detection + helpers ---
AUTO_YES_RE = re.compile(
    r"(privacy\s*policy|data\s*protection|consent|acknowledg(e|ement)|"
    r"terms\s*(and\s*conditions)?|gdpr|policy\s*ack|read\s*the\s*privacy|"
    r"agree\s*to\s*the\s*policy)", re.I
)

AUTO_NO_RE = re.compile(
    r"(currently\s*employ(ed)?\s*by|ever\s*been\s*employ(ed)?\s*by|"
    r"previous(ly)?\s*employ(ed)?\s*by|worked\s*for\s*(us|this\s*company)|"
    r"subsidiar(y|ies)|conflict\s*of\s*interest)", re.I
)

def _yesno_preference(label_text: str) -> str:
    """Return 'Yes' or 'No' if the question clearly matches our intent, else ''."""
    L = (label_text or "").lower()
    if AUTO_YES_RE.search(L):
        return "Yes"
    if AUTO_NO_RE.search(L):
        return "No"
    return ""

def _select_by_label_text(frame, select_el, want_text: str) -> bool:
    """Choose an option in a <select> by visible text (exact or contains)."""
    try:
        return bool(frame.evaluate("""
            (el, want) => {
              if (!el || el.tagName.toLowerCase() !== 'select') return false;
              const w = (want || '').toLowerCase();
              const opts = Array.from(el.options || []);
              const exact = opts.find(o => (o.textContent||'').trim().toLowerCase() === w);
              const match = exact || opts.find(o => (o.textContent||'').toLowerCase().includes(w));
              if (match) {
                el.value = match.value;
                el.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
              }
              return false;
            }
        """, select_el, want_text))
    except Exception:
        return False


def _attrs_blob(label="", name="", id_="", placeholder="", aria_label="", type_=""):
    """Combine all useful attributes/labels into one lowercased string for matching."""
    return " ".join([
        str(label or ""),
        str(name or ""),
        str(id_ or ""),
        str(placeholder or ""),
        str(aria_label or ""),
        str(type_ or "")
    ]).lower().strip()

def _value_from_meta(user, meta_text: str):
    """Decide value using the combined metadata string."""
    L = (meta_text or "").lower()

    linkedin = (getattr(user, "linkedin_url", "") or "").strip()
    country_code = (getattr(user, "country", "") or "").upper()
    phone_raw = (getattr(user, "phone_number", "") or "").strip()
    country_h = _country_human(country_code)

    # Prefer phone with dial prefix when asked for phone/mobile/tel
    phone = phone_raw
    dial = DIAL.get(country_code, "")
    if any(k in L for k in ["phone", "mobile", "tel"]) and phone_raw and dial and not phone_raw.startswith("+"):
        phone = f"{dial} {phone_raw}"

    mapping = [
        (["first", "fname", "given", "forename"],          user.first_name or ""),
        (["last", "lname", "surname", "family"],           user.last_name or ""),
        (["email", "e-mail", "mail"],                      user.email or ""),
        (["phone", "mobile", "tel"],                       phone),
        (["linkedin", "profile url", "profile_url"],       linkedin),
        (["country", "nationality"],                       country_h),
        (["city", "town"],                                 getattr(user, "location", "") or ""),
        (["job title", "title", "position", "role"],       getattr(user, "occupation", "") or ""),
        (["company", "employer", "organization", "organisation", "current company"], getattr(user, "category", "") or ""),
    ]
    for keys, val in mapping:
        if any(k in L for k in keys) and val:
            return val

    # Generic URL → only if clearly LinkedIn
    if ("url" in L or "website" in L) and "linkedin" in L and linkedin:
        return linkedin

    return ""



def fill_from_inventory(page, user, inventory):
    """
    Re-find each scanned element via (frame_index, query, nth),
    decide the right value from user data, and fill it (no 'N/A' anywhere).
    """
    filled = 0
    frames = list(page.frames)
    for item in inventory:
        # Resolve frame & element
        try:
            frame = frames[item["frame_index"]]
            el = frame.locator(item["query"]).nth(item["nth"])
        except Exception:
            continue

        try:
            if not el.is_visible():
                continue

            # Current value
            curr = ""
            try:
                curr = (el.inner_text().strip() if item["query"] == "[contenteditable='true']"
                        else el.input_value().strip())
            except Exception:
                pass
            if curr and curr.upper() != "N/A":
                continue  # already has a real value

            # Build combined metadata & decide a value
            meta = _attrs_blob(
                label=item.get("label", ""),
                name=item.get("name", ""),
                id_=item.get("id", ""),
                placeholder=item.get("placeholder", ""),
                aria_label=item.get("aria_label", ""),
                type_=item.get("type", "")
            )
            val = _value_from_meta(user, meta)

            # If field currently has "N/A" but we now have a real value, clear first
            if val and curr.upper() == "N/A":
                try:
                    el.fill("")
                except Exception:
                    pass

            if not val:
                continue  # nothing appropriate to fill

            # Scroll & fill
            try:
                el.scroll_into_view_if_needed(timeout=2000)
            except Exception:
                pass

            is_select = False
            try:
                is_select = el.evaluate("el => el.tagName && el.tagName.toLowerCase() === 'select'")
            except Exception:
                pass

            if is_select:
                try:
                    el.select_option(label=val)
                except Exception:
                    frame.evaluate("""
                        (el, want) => {
                          const opts = Array.from(el.options || []);
                          const t = (want||'').toLowerCase();
                          const match = opts.find(o => (o.textContent||'').trim().toLowerCase()===t)
                                      || opts.find(o => (o.textContent||'').toLowerCase().includes(t));
                          if (match) { el.value = match.value; el.dispatchEvent(new Event('change',{bubbles:true})); }
                        }
                    """, el, val)
            else:
                el.fill(val)
                try: el.press("Tab")
                except Exception: pass
                try:
                    frame.evaluate("el => { el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }", el)
                except Exception:
                    pass

            print(f"✅ Filled “{meta[:60]}” → {val}")
            filled += 1

        except Exception:
            continue

    print(f"✅ Post-scan fill completed — filled {filled} fields from inventory.")
    return filled


def apply_to_ats(room_id, user_id, resume_path=None, cover_letter_text="", dry_run=True):
    """
    Robust ATS automation handler.
    Detects and fills dynamic, iframe-based forms (Workday, Lever, Greenhouse, etc.).
    If dry_run=True, it fills but does not submit.

    NEW FLOW:
      - Reveal form (consent + safe apply)
      - Detect iframe, scroll/expand
      - PHASE 1: Scan all fields -> inventory
      - PHASE 2: Fill from inventory
      - Required-completeness pass
      - Upload resume
      - Paste static cover letter ("test coverletter")
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

    # For saving inventories & screenshots
    log_dir = "/home/clinton/Internstart/media"
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_company = "".join(c if c.isalnum() else "_" for c in (room.company_name or "company"))

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

            # 1️⃣ Kill cookie/consent overlays globally (main page + iframes)
            dismiss_privacy_overlays(page)

            # Some pages need a reload after consent
            page.goto(room.apply_url, timeout=120000, wait_until="domcontentloaded")
            page.wait_for_load_state("load", timeout=20000)
            page.wait_for_timeout(2000)
            dismiss_privacy_overlays(page)

            # 2️⃣ Trigger “Apply” or open hidden form modals (SAFE)
            try:
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
                                dismiss_privacy_overlays(page, timeout_ms=5000)

                                after_url = page.url
                                after_field_count = page.locator("input, textarea, select").count()

                                if (after_url != before_url and after_field_count <= before_field_count):
                                    print("↩️ Navigation didn’t expose more fields; going back.")
                                    try:
                                        page.go_back(timeout=10000)
                                        page.wait_for_timeout(1000)
                                        dismiss_privacy_overlays(page, timeout_ms=3000)
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

            # Ensure nothing is blocking before we scan/fill
            dismiss_privacy_overlays(page, timeout_ms=3000)

            # 3️⃣ Detect iframe context (used later for uploads/CL)
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

            # 4️⃣ Wait for fields + expand + scroll to render dynamic inputs
            try:
                context.wait_for_selector("input, textarea, select", timeout=12000)
                print("⏳ Form fields detected and ready.")
            except Exception:
                print("⚠️ No visible fields yet; continuing with scan.")
            try:
                expanders = context.locator("button:has-text('Expand'), button:has-text('Show more'), div[role='button']")
                if expanders.count() > 0:
                    for i in range(min(expanders.count(), 3)):
                        expanders.nth(i).click()
                        page.wait_for_timeout(700)
                    print("📂 Expanded collapsible sections.")
            except Exception:
                pass
            try:
                for _ in range(0, 1800, 360):
                    page.mouse.wheel(0, 360)
                    page.wait_for_timeout(350 + random.randint(80, 220))
                print("🧭 Scrolled through page to reveal hidden inputs.")
            except Exception:
                pass

            # ========== PHASE 1: SCAN ==========
            inventory = scan_all_fields(page)

            # Save inventory snapshot (useful for debugging / dashboard)
            try:
                inv_path = os.path.join(log_dir, f"ats_field_inventory_{safe_company}_{ts}.json")
                with open(inv_path, "w", encoding="utf-8") as f:
                    json.dump(inventory, f, ensure_ascii=False, indent=2)
                print(f"📝 Saved field inventory → {inv_path}")
            except Exception as e:
                print(f"⚠️ Could not save inventory JSON: {e}")

            # ========== PHASE 2: FILL ==========
            try:
                fill_count = fill_from_inventory(page, user, inventory)
            except Exception as e:
                print(f"⚠️ Post-scan fill failed: {e}")
                fill_count = 0

            # 7️⃣ REQUIRED COMPLETENESS PASS — fill requireds still empty (N/A where needed)
            try:
                print("🧹 Running required-completeness pass (text/select/radio/checkbox/phone code)…")

                # Small helpers
                DIAL = {"DK": "+45", "US": "+1", "UK": "+44", "FRA": "+33", "GER": "+49"}
                user_cc = DIAL.get((getattr(user, "country", "") or "").upper(), "")

                PLACEHOLDER_WORDS = ["select", "vælg", "choose", "chose", "pick", "—", "-", "–", "please"]
                AVOID_CHECKBOX = ["newsletter", "marketing", "samarbejde", "marketingsføring", "updates", "promotion"]
                REQUIRED_MARKERS = ["*", "required", "obligatorisk", "påkrævet", "mandatory"]

                def looks_required(text: str) -> bool:
                    t = (text or "").lower()
                    return any(m in t for m in REQUIRED_MARKERS)

                def near_text(frame, el):
                    try:
                        return frame.evaluate("""
                        (el) => {
                            const lab  = (el.labels && el.labels[0]) ? el.labels[0].innerText : "";
                            const aria = el.getAttribute("aria-label") || "";
                            const ph   = el.getAttribute("placeholder") || "";
                            const byId = (() => {
                            const ids = (el.getAttribute("aria-labelledby") || "").split(/\\s+/).filter(Boolean);
                            return ids.map(id => (document.getElementById(id)?.innerText || "")).join(" ");
                            })();
                            const wrap = el.closest("label, .field, .form-group, .MuiFormControl-root, div, section, fieldset");
                            const near = wrap ? (wrap.querySelector("legend, label, h1, h2, h3, h4, span, .label, .title")?.innerText || "") : "";
                            const tr = el.closest("tr");
                            const leftCell = tr ? (tr.querySelector("td,th")?.innerText || "") : "";
                            return [lab, aria, ph, byId, near, leftCell].join(" ").replace(/\\s+/g," ").trim();
                        }
                        """, el) or ""
                    except Exception:
                        return ""


                # Phone code widgets
                for frame in page.frames:
                    if not user_cc:
                        break
                    try:
                        phone_rows = frame.locator("select, [role='combobox']").filter(has_text="+")
                        for i in range(min(6, phone_rows.count())):
                            sel = phone_rows.nth(i)
                            if not sel.is_visible():
                                continue
                            txt = near_text(frame, sel).lower()
                            if "phone" in txt or "mobil" in txt or "telefon" in txt:
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

                # Required text-like inputs
              # Required text-like inputs (NO 'N/A' writes; try metadata-based fill only)
                        for frame in page.frames:
                            try:
                                inputs = frame.locator("input:not([type='hidden']):not([disabled]), textarea:not([disabled])")
                                for i in range(inputs.count()):
                                    el = inputs.nth(i)
                                    try:
                                        if not el.is_visible():
                                            continue
                                        t = (el.get_attribute("type") or "").lower()
                                        if t in ["checkbox", "radio", "file"]:
                                            continue

                                        # current value
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

                                        # required?
                                        lbl = near_text(frame, el)
                                        req_attr = el.get_attribute("required") is not None or el.get_attribute("aria-required") in ["true", True]
                                        req_near = looks_required(lbl)
                                        if not (req_attr or req_near):
                                            continue

                                        # Build metadata blob and try to fill with a real value
                                        blob = _attrs_blob(
                                            label=lbl,
                                            name=el.get_attribute("name") or "",
                                            id_=el.get_attribute("id") or "",
                                            placeholder=el.get_attribute("placeholder") or "",
                                            aria_label=el.get_attribute("aria-label") or "",
                                            type_=t
                                        )

                                        # Hard guard: never overwrite these with placeholders
                                        if any(k in blob for k in ["first","fname","given","forename",
                                                                "last","lname","surname","family",
                                                                "email","e-mail","mail",
                                                                "phone","mobile","tel",
                                                                "linkedin"]):
                                            # Try to fill with real value only
                                            real = _value_from_meta(user, blob)
                                            if real:
                                                el.fill(real)
                                                try: el.press("Tab")
                                                except Exception: pass
                                                try:
                                                    frame.evaluate("el => { el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }", el)
                                                except Exception: pass
                                                print(f"🧩 Completed required field (guarded) → {real} ({lbl[:60]})")
                                            continue

                                        # Non-guarded required fields → try real value; if none, skip (no 'N/A')
                                        real = _value_from_meta(user, blob)
                                        if real:
                                            el.fill(real)
                                            try: el.press("Tab")
                                            except Exception: pass
                                            try:
                                                frame.evaluate("el => { el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }", el)
                                            except Exception: pass
                                            print(f"🧩 Completed required field → {real} ({lbl[:60]})")
                                        # else: leave blank; do NOT write 'N/A'
                                    except Exception:
                                        continue
                            except Exception:
                                pass

                            except Exception:
                                continue
                    except Exception:
                        pass


                # --- Custom dropdowns driven by <label for="..."> (auto Yes/No) ---
                try:
                    for frame in page.frames:
                        try:
                            labels = frame.locator("label[for]").all()
                        except Exception:
                            labels = []

                        for lab in labels:
                            try:
                                if not lab.is_visible():
                                    continue
                                q_text = (lab.inner_text() or "").strip()

                                # existing generic intent
                                pref = _yesno_preference(q_text)  # 'Yes' for privacy, 'No' for prior employment

                                qL = q_text.lower()
                                if ("ever been employed by ipg" in qL
                                        or "currently employed" in qL
                                        or "subsidiar" in qL):
                                    pref = "No"
                                # ▲▲ ADD THESE LINES HERE ▲▲

                                if not pref:
                                    continue

                                if _set_custom_dropdown_by_label(page, frame, lab, pref):
                                    print(f"🟢 Set custom dropdown via <label for=…> → {pref} ({q_text[:80]})")
                                    ok = _set_custom_dropdown_by_label(page, frame, lab, pref)
                                    if ok:
                                        # verify the visible value actually changed
                                        label_id  = lab.get_attribute("id") or ""
                                        label_for = lab.get_attribute("for") or ""
                                        committed = False
                                        try:
                                            committed = frame.evaluate("""
                                                (labId, want) => {
                                                const root =
                                                    document.querySelector(`[aria-labelledby="${labId}"]`) ||
                                                    (document.getElementById(labId)?.closest('.select__container'));
                                                const txt = root ? (root.innerText || '').toLowerCase() : '';
                                                return txt.includes((want || '').toLowerCase());
                                                }
                                            """, label_id, pref)
                                        except Exception:
                                            committed = False

                                        if not committed:
                                            # last-resort: set the underlying element the label points to
                                            try:
                                                committed = frame.evaluate("""
                                                    (elId, want) => {
                                                    const el = document.getElementById(elId);
                                                    if (!el) return false;
                                                    const lower = (want || '').toLowerCase();
                                                    if (el.tagName && el.tagName.toLowerCase() === 'select') {
                                                        const opts = Array.from(el.options || []);
                                                        const m = opts.find(o =>
                                                        ((o.textContent||'').trim().toLowerCase() === lower) ||
                                                        ((o.textContent||'').toLowerCase().includes(lower))
                                                        );
                                                        if (m) {
                                                        el.value = m.value;
                                                        el.dispatchEvent(new Event('input', {bubbles:true}));
                                                        el.dispatchEvent(new Event('change',{bubbles:true}));
                                                        return true;
                                                        }
                                                    }
                                                    if (el.tagName && el.tagName.toLowerCase() === 'input') {
                                                        el.value = want;
                                                        el.setAttribute('value', want);
                                                        el.dispatchEvent(new Event('input', {bubbles:true}));
                                                        el.dispatchEvent(new Event('change',{bubbles:true}));
                                                        return true;
                                                    }
                                                    return false;
                                                    }
                                                """, label_for, pref)
                                            except Exception:
                                                committed = False

                                        if committed:
                                            print(f"🟢 Confirmed dropdown set → {pref} ({q_text[:80]})")
                                        else:
                                            print(f"🟡 Dropdown click landed but value didn’t commit; fallback failed ({q_text[:80]})")

                            except Exception:
                                continue
                except Exception:
                    pass



                # --- Hard-case: IPG "ever/currently employed" combobox — force type+Enter + verify ---
                try:
                    for frame in page.frames:
                        # 1) Find the specific label
                        lab = frame.locator(
                            "label[for]",
                        ).filter(has_text=re.compile(r"are you currently employed|ever been employed.*ipg", re.I)).first
                        if not (lab and lab.is_visible()):
                            continue

                        lab_id  = (lab.get_attribute("id") or "")
                        lab_for = (lab.get_attribute("for") or "")

                        # 2) Find the clickable root/combobox near the label
                        root = None
                        # element referenced by label's "for"
                        if lab_for:
                            el = frame.locator(f"#{lab_for}")
                            if el.count() and el.first.is_visible():
                                root = el.first

                        # aria-labelledby binding
                        if not root and lab_id:
                            el = frame.locator(f"[aria-labelledby='{lab_id}']")
                            if el.count() and el.first.is_visible():
                                root = el.first

                        # common shells
                        if not root:
                            root = lab.locator("xpath=following::*[1]").locator(
                                ":is([role='combobox'], [aria-haspopup='listbox'], .select__control, .select-shell, .select__container)"
                            ).first

                        if not (root and root.is_visible()):
                            continue

                        # 3) Open and type "No", then Enter
                        try:
                            root.scroll_into_view_if_needed()
                        except Exception:
                            pass
                        root.click(force=True)
                        frame.wait_for_timeout(120)

                        # Some widgets need the inner input focused
                        try:
                            inner_input = root.locator("input[role='combobox'], input[aria-autocomplete='list']")
                            if inner_input.count() and inner_input.first.is_visible():
                                inner_input.first.fill("")  # clear any filter
                                inner_input.first.type("No", delay=20)
                            else:
                                root.type("No", delay=20)
                        except Exception:
                            root.type("No", delay=20)

                        frame.keyboard.press("Enter")
                        frame.wait_for_timeout(180)

                        # 4) Verify; if not committed, try portal click on the visible “No” option
                        committed = False
                        try:
                            committed = frame.evaluate("""
                                (labId) => {
                                const root =
                                    document.querySelector(`[aria-labelledby="${labId}"]`) ||
                                    (labId && document.getElementById(labId)?.closest('.select__container'));
                                const txt = (root && root.innerText) ? root.innerText.toLowerCase() : "";
                                return txt.includes("no");
                                }
                            """, lab_id)
                        except Exception:
                            committed = False

                        if not committed:
                            # Click the menu option wherever it was rendered (inside frame or in a body portal)
                            for scope in (frame, page):
                                menu = scope.locator(
                                    ":is([role='listbox'], [role='menu'], .select__menu, .dropdown-menu, "
                                    ".MuiPaper-root, .MuiPopover-paper, ul[role='listbox'], ul)"
                                )
                                opt = menu.locator(":is([role='option'], [role='menuitem'], li, div, button, span)").filter(has_text="No").first
                                if opt and opt.is_visible():
                                    opt.click(force=True)
                                    scope.wait_for_timeout(160)
                                    break

                        # 5) Final verify; log result
                        try:
                            committed = frame.evaluate("""
                                (labId) => {
                                const root =
                                    document.querySelector(`[aria-labelledby="${labId}"]`) ||
                                    (labId && document.getElementById(labId)?.closest('.select__container'));
                                const txt = (root && root.innerText) ? root.innerText.toLowerCase() : "";
                                return txt.includes("no");
                                }
                            """, lab_id)
                        except Exception:
                            committed = False

                        if committed:
                            print("🟢 Forced commit: IPG prior/current employment → No")
                        else:
                            print("🟡 Still not committed after force; will rely on later validation")
                except Exception as e:
                    print(f"⚠️ Hard-case handler failed: {e}")




                # Required selects (with auto Yes/No for policy/employment questions)
                for frame in page.frames:
                    try:
                        selects = frame.locator("select:not([disabled])")
                        for i in range(selects.count()):
                            sel = selects.nth(i)
                            try:
                                if not sel.is_visible():
                                    continue
                                has_val = frame.evaluate("(el) => !!el.value", sel)
                                if has_val:
                                    continue

                                lbl = near_text(frame, sel)
                                req_attr = sel.get_attribute("required") is not None or sel.get_attribute("aria-required") in ["true", True]
                                req_near = looks_required(lbl)
                                if not (req_attr or req_near):
                                    continue

                                # ➊ Prefer our auto Yes/No rules
                                pref = _yesno_preference(lbl)
                                if pref and _select_by_label_text(frame, sel, pref):
                                    print(f"✅ Auto-answered select → {pref} ({lbl[:80]})")
                                    continue

                                # ➋ Country heuristic (user model)
                                user_country_human = _country_human(getattr(user, "country", ""))
                                if "country" in lbl.lower() and user_country_human:
                                    try:
                                        sel.select_option(label=user_country_human)
                                        print(f"🌍 Completed required Country select → {user_country_human}")
                                        continue
                                    except Exception:
                                        pass

                                # ➌ Generic: choose first non-placeholder option
                                chose = frame.evaluate("""
                                    (el) => {
                                    const opts = Array.from(el.options || []);
                                    const good = opts.find(o => {
                                        const t = (o.textContent||'').trim();
                                        return t && !/^(select|vælg|choose|please|—|–|-|select\.\.\.)$/i.test(t);
                                    });
                                    if (good) { el.value = good.value; el.dispatchEvent(new Event('change',{bubbles:true})); return good.textContent.trim(); }
                                    return "";
                                    }
                                """, sel)
                                if chose:
                                    print(f"✅ Required select filled → {chose[:40]} ({lbl[:80]})")
                            except Exception:
                                continue
                    except Exception:
                        pass


                        # --- Fallback for custom dropdowns that are not <select> ---
                        try:
                            combos = frame.locator("[role='combobox'], [aria-haspopup='listbox']")
                            for i in range(min(30, combos.count())):
                                root = combos.nth(i)
                                if not root.is_visible():
                                    continue
                                lbl = near_text(frame, root)
                                pref = _yesno_preference(lbl)  # "Yes" for privacy; "No" for prior employment
                                if not pref:
                                    continue

                                # open the dropdown
                                try:
                                    root.click(force=True)
                                    frame.wait_for_timeout(150)
                                except Exception:
                                    continue

                                # pick option that contains our pref text
                                try:
                                    menu = frame.locator(":is([role='listbox'], .MuiPaper-root, .select__menu, .dropdown-menu, ul[role='listbox'])")
                                    opt  = menu.locator(f":is([role='option'], li, div):has-text('{pref}')").first
                                    if opt and opt.is_visible():
                                        opt.click(force=True)
                                        frame.wait_for_timeout(100)
                                        print(f"🟢 Set custom dropdown “{lbl[:80]}” → {pref}")
                                except Exception:
                                    # close if nothing chosen
                                    try: frame.keyboard.press("Escape")
                                    except Exception: pass
                        except Exception:
                            pass


                # Required radios (with auto Yes/No for policy/employment questions)
                for frame in page.frames:
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
                                if group.count() == 0:
                                    continue

                                # Is the group required?
                                any_req = False
                                for j in range(group.count()):
                                    g = group.nth(j)
                                    if g.get_attribute("required") is not None or g.get_attribute("aria-required") in ["true", True]:
                                        any_req = True
                                        break
                                if not any_req:
                                    continue

                                # Pull a group-level label/question
                                group_label = near_text(frame, r)
                                pref = _yesno_preference(group_label)

                                chosen = False
                                if pref:
                                    want = pref.lower()
                                    # Try to pick the radio whose nearby/sibling label contains Yes/No
                                    for j in range(group.count()):
                                        g = group.nth(j)
                                        try:
                                            lab = (frame.evaluate(
                                                "(el)=> el.closest('label, .radio, .form-check, td, th, div')?.innerText || ''", g
                                            ) or "").lower()
                                        except Exception:
                                            lab = ""
                                        if want in lab:
                                            g.check(force=True)
                                            print(f"🔘 Auto-answered radio → {pref} ({group_label[:80]})")
                                            chosen = True
                                            break

                                    # Fallback: check first visible if text labels not found
                                    if not chosen:
                                        for j in range(group.count()):
                                            g = group.nth(j)
                                            if g.is_visible():
                                                g.check(force=True)
                                                print(f"🔘 Radio fallback pick (pref {pref}) for group '{name}'")
                                                chosen = True
                                                break

                                # If no preference matched, leave to other passes (don’t guess)
                                if chosen:
                                    processed.add(name)
                            except Exception:
                                continue
                    except Exception:
                        pass


                # Required checkboxes (skip marketing)
                for frame in page.frames:
                    try:
                        checks = frame.locator("input[type='checkbox']:not([disabled])")
                        for i in range(checks.count()):
                            c = checks.nth(i)
                            try:
                                lbl = (c.get_attribute("aria-label") or "").lower()
                                req = c.get_attribute("required") is not None or c.get_attribute("aria-required") in ["true", True]
                                if not lbl:
                                    try:
                                        lbl = frame.evaluate("(el)=> el.closest('label,div,section,fieldset')?.innerText || ''", c).lower()
                                    except Exception:
                                        lbl = ""
                                is_marketing = any(w in lbl for w in ["newsletter", "marketing", "samarbejde", "marketingsføring", "updates", "promotion"])
                                if req and not is_marketing:
                                    c.check(force=True)
                                    print(f"☑️ Checked required checkbox ({lbl[:60]})")
                            except Exception:
                                continue
                    except Exception:
                        pass

                print("✅ Required-completeness pass finished.")
            except Exception as e:
                print(f"⚠️ Required-completeness pass failed: {e}")

            # 🧠 AI dynamic field filling (optional mop-up; still kept)
            try:
                fill_dynamic_fields(context, user)
            except Exception as e:
                print(f"⚠️ AI dynamic field filling failed: {e}")
                traceback.print_exc()

            # 9️⃣ Resume upload (robust for hidden inputs)
            try:
                if resume_path:
                    print(f"📎 Attempting to upload resume from: {resume_path}")

                    try:
                        all_buttons = context.locator("button, label")
                        attach_btn = all_buttons.filter(has_text="Attach")
                        manual_btn = all_buttons.filter(has_text="Enter manually")

                        if attach_btn.count() > 0:
                            print("🧠 Decision: Choosing 'Attach' option for resume upload.")
                            attach_btn.first.click()
                            page.wait_for_timeout(2500)
                        elif manual_btn.count() > 0:
                            print("⚠️ Only 'Enter manually' found — skipping upload.")
                        else:
                            print("⚠️ No resume option buttons found.")
                    except Exception as e:
                        print(f"⚠️ Could not click attach button: {e}")

                    file_input = None
                    for _ in range(10):
                        try:
                            for frame in page.frames:
                                locator = frame.locator("input[type='file']")
                                if locator.count() > 0:
                                    file_input = locator.first
                                    context = frame
                                    print("✅ Found file input (possibly hidden) in frame")
                                    break
                            if file_input:
                                break
                        except Exception:
                            pass
                        page.wait_for_timeout(1000)

                    if file_input:
                        try:
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
                                  }
                                }
                            """)
                            file_input.set_input_files(resume_path)
                            print("📄 Successfully uploaded resume via forced visibility fix.")
                        except Exception as e:
                            print(f"⚠️ Upload attempt failed even after unhide: {e}")
                    else:
                        print("⚠️ Could not find any input[type='file'] after retries.")

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

            # 🔟 Cover letter (STATIC): paste "test coverletter" or upload as file if needed
            try:
                letter_text = cover_letter_text or "test coverletter"

                inserted = False
                try:
                    manual_btn = context.locator(
                        ":is(button,label,a):has-text('Enter manually'), :is(button,label,a):has-text('Skriv manuelt')"
                    )
                    if manual_btn.count() > 0 and manual_btn.first.is_visible():
                        manual_btn.first.click()
                        page.wait_for_timeout(600)
                except Exception:
                    pass

                # textarea route
                try:
                    ta = context.locator(
                        "textarea[name*='cover' i], textarea[id*='cover' i], textarea[aria-label*='cover' i]"
                    )
                    if ta.count() == 0:
                        ta = context.locator("textarea")
                    for i in range(min(6, ta.count())):
                        el = ta.nth(i)
                        if el.is_visible():
                            el.fill(letter_text)
                            try: el.press("Tab")
                            except Exception: pass
                            print("💬 Pasted static cover letter into textarea.")
                            inserted = True
                            break
                except Exception:
                    pass

                # contenteditable route
                if not inserted:
                    try:
                        ce = context.locator("[contenteditable='true']")
                        for i in range(min(6, ce.count())):
                            el = ce.nth(i)
                            if el.is_visible():
                                el.click()
                                el.fill(letter_text)
                                print("💬 Pasted static cover letter into contenteditable.")
                                inserted = True
                                break
                    except Exception:
                        pass

                # file attach fallback
                if not inserted:
                    print("📎 No text field found — uploading static cover letter as file.")
                    file_path = write_temp_cover_letter_file(letter_text, suffix=".txt")

                    try:
                        attach_btn = context.locator(
                            ":is(button,label,a):has-text('Attach'), :is(button,label,a):has-text('Vedhæft')"
                        )
                        if attach_btn.count() > 0 and attach_btn.first.is_visible():
                            attach_btn.first.click()
                            page.wait_for_timeout(600)
                    except Exception:
                        pass

                    file_input = None
                    for frame in page.frames:
                        try:
                            fi = frame.locator("input[type='file']")
                            if fi.count() > 0:
                                file_input = fi.first
                                context = frame
                                break
                        except Exception:
                            continue

                    if file_input:
                        file_input.set_input_files(file_path)
                        print("📄 Uploaded static cover letter file.")
                    else:
                        print("⚠️ Could not locate cover letter file input.")
            except Exception as e:
                print(f"⚠️ Cover letter step failed: {e}")

            # 11️⃣ Dry run
            screenshot_path = os.path.join(log_dir, f"ats_preview_{safe_company}_{ts}.png")
            if dry_run:
                print("🧪 Dry run active — skipping submit.")
                try:
                    page.screenshot(path=screenshot_path, full_page=True)
                    print(f"📸 Saved preview screenshot as {screenshot_path}")
                except Exception as e:
                    print(f"⚠️ Could not save screenshot: {e}")
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
                err_shot = os.path.join(log_dir, f"error_screenshot_{safe_company}_{ts}.png")
                page.screenshot(path=err_shot, full_page=True)
                print(f"📸 Saved error screenshot for debugging → {err_shot}")
            except Exception:
                pass
            browser.close()
            return False
