from playwright.sync_api import sync_playwright
from django.conf import settings
from .models import ATSRoom, User
from .ats_filler import fill_dynamic_fields  # optional mop-up, left in import
import time, traceback, random, json, os, tempfile, re, difflib
from urllib.parse import urlparse
from datetime import datetime
from base.ai.field_interpreter import map_fields_to_answers
import unicodedata
import re


# ---------------- util ----------------

_PLACEHOLDER_SELECT_TEXTS = {
    "vælg", "select", "choose", "please select",
    "-- select --", "- select -", "vælg...", "(vælg)", "— vælg —", "choose..."
}
_PLACEHOLDER_SELECT_VALUES = {"", "0", "-1", "select", "vælg", "9999"}


def _norm(s):
    return (s or "").strip().lower()

def _select_is_unfilled(selected_text, selected_value):
    st = _norm(selected_text)
    sv = _norm(selected_value)
    return (not st and not sv) or (st in _PLACEHOLDER_SELECT_TEXTS) or (sv in _PLACEHOLDER_SELECT_VALUES)

def _best_option_match(options, want_text):
    if not options or not want_text:
        return None
    want = _norm(want_text)

    # exact
    for o in options:
        if _norm(o) == want:
            return o
    # startswith
    for o in options:
        if _norm(o).startswith(want):
            return o
    # substring
    for o in options:
        if want in _norm(o):
            return o
    # fuzzy
    best = None
    best_score = -1
    for o in options:
        s = difflib.SequenceMatcher(None, _norm(o), want).ratio()
        if s > best_score:
            best, best_score = o, s
    return best


# ---------------- AI leftovers with dropdown support ----------------

def _extract_dropdown_options(frame, query, nth):
    """Read visible option texts for a specific <select> using the same locator query/nth."""
    try:
        return frame.evaluate(
            """(a) => {
                const el = document.querySelectorAll(a.q)[a.n];
                if (!el || el.tagName.toLowerCase() !== 'select') return [];
                return [...el.options].map(o => (o.textContent || '').trim()).filter(Boolean).slice(0, 200);
            }""",
            {"q": query, "n": nth}
        ) or []
    except Exception:
        return []

# ---- tweak: make “share your application” count as an auto-YES
AUTO_YES_RE = re.compile(
    r"(privacy\s*policy|data\s*protection|consent|acknowledg(e|ement)|terms|gdpr|agree|"
    r"dele\s+din\s+ansøgning|må\s+dele\s+min\s+ansøgning)", re.I
)

AUTO_NO_RE  = re.compile(r"(currently\s*employ(ed)?\s*by|ever\s*been\s*employ(ed)?\s*by|subsidiar(y|ies)|conflict\s*of\s*interest)", re.I)

# ---- helpers for rule-based suggestions -------------------------------------

def _fallback_required_option(options):
    """Pick a safe option if AI skips a required select."""
    if not options:
        return None
    lower = [o.lower() for o in options]
    for want in ("andet", "other", "ikke relevant", "n/a"):
        for i, o in enumerate(lower):
            if want in o:
                return options[i]
    # first non-placeholder
    for o in options:
        if o and o.strip() and o.strip().lower() not in {"vælg", "select", "choose", "-- select --", "- select -"}:
            return o
    return options[0]

def _profile_get(profile: dict, *keys, default=None):
    """Safely pull nested values. Tries top-level first, then nested dict path hints."""
    if not profile:
        return default
    # direct hits
    for k in keys:
        if isinstance(k, str) and k in profile and profile.get(k):
            return profile[k]
    # nested: try common groups
    groups = ["employment", "education", "contact", "profile"]
    for g in groups:
        sub = profile.get(g) or {}
        for k in keys:
            if isinstance(k, str) and k in sub and sub.get(k):
                return sub[k]
    return default


# --- SELECT-LIKE helpers (add once, near other utils) -----------------------
SELECT_LIKE_TYPES = {"select", "combo", "md-select", "mat-select"}

def _select_like_set(frame, query, nth, label_text: str) -> bool:
    """Set a value on native <select> or custom select-like widgets."""
    try:
        return frame.evaluate(
            """(a) => {
              const el = document.querySelectorAll(a.q)[a.n];
              if (!el) return false;
              const want = (a.want || '').trim().toLowerCase();
              const tag  = (el.tagName || '').toLowerCase();
              const role = (el.getAttribute('role') || '').toLowerCase();
              const hasListbox = (el.getAttribute('aria-haspopup') || '').toLowerCase() === 'listbox';

              // Native <select>
              if (tag === 'select') {
                const opts = Array.from(el.options || []);
                const hit  = opts.find(o => (o.textContent||'').trim().toLowerCase() === want)
                          || opts.find(o => (o.textContent||'').trim().toLowerCase().includes(want));
                if (!hit) return false;
                el.value = hit.value;
                el.dispatchEvent(new Event('input',  {bubbles:true}));
                el.dispatchEvent(new Event('change', {bubbles:true}));
                return true;
              }

              // Generic open
              const open = () => { el.click(); };
              open();

              // Options can be rendered in overlays/portals:
              const root = document;
              const cand = [
                ...root.querySelectorAll('[role="option"]'),
                ...root.querySelectorAll('md-option'),
                ...root.querySelectorAll('.mat-option-text'),
                ...root.querySelectorAll('.select2-results__option'),
              ];

              const norm = s => (s||'').trim().toLowerCase();
              let best = null;
              for (const n of cand) {
                const t = norm(n.innerText || n.textContent);
                if (!t) continue;
                if (t === want) { best = n; break; }
                if (!best && t.startsWith(want)) best = n;
                if (!best && t.includes(want))   best = n;
              }
              if (!best) {
                // Escape the menu
                el.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true}));
                return false;
              }
              const clickNode = best.closest('[role="option"]') || best.closest('md-option') || best;
              clickNode.click();
              el.dispatchEvent(new Event('change', {bubbles:true}));
              return true;
            }""",
            {"q": query, "n": nth, "want": label_text or ""}
        ) or False
    except Exception:
        return False


def _extract_dropdown_options(frame, query, nth):
    """Return visible option texts for native and custom selects."""
    try:
        return frame.evaluate(
            """(a) => {
              const el = document.querySelectorAll(a.q)[a.n];
              if (!el) return [];
              const tag  = (el.tagName || '').toLowerCase();

              // Native <select>
              if (tag === 'select') {
                return Array.from(el.options || [])
                        .map(o => (o.textContent||'').trim())
                        .filter(Boolean).slice(0, 300);
              }

              // Open the menu
              el.click();

              const root = document;
              const texts = [
                ...root.querySelectorAll('[role="option"]'),
                ...root.querySelectorAll('md-option'),
                ...root.querySelectorAll('.mat-option-text'),
                ...root.querySelectorAll('.select2-results__option'),
              ]
              .map(n => (n.innerText || n.textContent || '').trim())
              .filter(Boolean);

              // Close (best effort)
              el.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true}));
              return Array.from(new Set(texts)).slice(0, 300);
            }""",
            {"q": query, "n": nth}
        ) or []
    except Exception:
        return []


def _rule_based_value(label, options, user_profile, user):
    """Return a best-guess string for *this* field label from profile, else None."""
    L = _normalize_label(label or "")

    # Address block
    if "adresse" in L or "address" in L:
        return getattr(user, "address", None) \
            or _profile_get(user_profile, "address", "street", "address_line_1")
    if "postnummer" in L or "postal" in L or "zip" in L:
        return getattr(user, "postal_code", None) \
            or _profile_get(user_profile, "postal_code", "zip_code")
    if re.search(r"\bby\b", L) or "city" in L:  # city (Danish)
        return getattr(user, "city", None) \
            or _profile_get(user_profile, "city", "location")

    # Current position / employer
    if re.search(r"(nuværende\s+stilling|current\s*position|title\s*\(current\)|position)", L):
        return getattr(user, "occupation", None) \
            or _profile_get(user_profile, "current_position", "occupation")
    if re.search(r"(nuværende\s+arbejdsgiver|current\s*employer|company)", L):
        return getattr(user, "category", None) \
            or _profile_get(user_profile, "current_employer", "company")

    # Education – field of study
    if "fagområde" in L or "fagomraade" in L or "field of study" in L:
        return _profile_get(user_profile, "field_of_study")
    # Education – degree title
    if "titel" in L and "uddannelse" in L or "degree" in L:
        deg = _profile_get(user_profile, "highest_education_level", "degree", "highest_level") or ""
        deg = (deg.replace("Bachelor’s", "Bachelor")
                  .replace("Bachelor's", "Bachelor")
                  .replace("Master’s", "Master")
                  .replace("Master's", "Master")
                  .replace("PhD", "Ph.d.")
                  .replace("High School", "Gymnasial"))
        return deg

    # Years of experience
    if "totalt antal års arbejdserfaring" in L or "arbejdserfaring" in L or "experience" in L:
        yrs = _profile_get(user_profile, "years_experience")
        if yrs is None and str(_profile_get(user_profile, "under_education")).lower() in {"yes", "true", "1"}:
            yrs = 0
        if yrs is not None:
            if options:
                return f"{yrs} År"  # try to match "N År"
            return str(yrs)

    # Consent type wording (if our auto-YES didn’t catch it)
    if "må dele" in L or "dele din ansøgning" in L or "consent" in L:
        return "Ja"

    # Gender (if present in profile)
    if "køn" in L or "gender" in L:
        g = _profile_get(user_profile, "gender")
        return g

        # Salary expectations
    if "løn" in L or "salary" in L or "pay" in L or "wage" in L:
        sal = getattr(user, "expected_salary", None) or _profile_get(user_profile, "expected_salary")
        if sal:
            return str(sal)

    return None


# ---------------- misc helpers ----------------

def write_temp_cover_letter_file(text, suffix=".txt"):
    fd, path = tempfile.mkstemp(prefix="cover_letter_", suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# ---------------- document upload helpers (single dropzone) ----------------

DOC_SYNONYMS = {
    "cv": {"cv", "curriculum vitae", "résumé", "resume"},
    "cover_letter": {
        "ansøgning", "ansoegning", "cover letter", "application",
        "motiveret ansøgning", "motivationsbrev", "motivationsbrev"
    },
}
# For select/category widgets (visible option text)
CATEGORY_SYNONYMS = {
    "cv": ["CV", "Resume", "Curriculum Vitae"],
    "cover_letter": ["Ansøgning", "Cover letter", "Application", "Motiveret ansøgning"],
}

UPLOAD_BUTTON_CANDIDATES = [
    "button:has-text('Upload' i)",
    "button:has-text('Vedhæft' i)",
    "button:has-text('Vælg & upload' i)",
    "input[type='submit'][value*='upload' i]",
    "input[type='button'][value*='upload' i]",
    "a:has-text('Upload' i)", "a:has-text('Vedhæft' i)"
]

def _uniq_keep_order(items):
    seen = set(); out = []
    for x in items:
        if x not in seen:
            seen.add(x); out.append(x)
    return out

def _normalize_label(s: str) -> str:
    """Lowercase, strip, remove diacritics, collapse spaces, and map Danish chars."""
    if not s:
        return ""
    s = str(s).strip().lower()
    # Preserve Danish forms, but also support ASCII fallbacks
    s = (s.replace("ø", "o")
          .replace("æ", "ae")
          .replace("å", "a"))
    # Remove any remaining diacritics
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    return s

def _parse_required_docs_from_text(txt: str):
    """Return ordered list like ['cv','cover_letter'] based on section text."""
    t = (txt or "").lower()
    hits = []
    if re.search(r"\bcv\b", t) or "curriculum vitae" in t or "résumé" in t or "resume" in t:
        hits.append("cv")
    if ("ansøgning" in t or "ansoegning" in t or "cover letter" in t or
        "application" in t or "motiveret ansøgning" in t or "motivationsbrev" in t):
        hits.append("cover_letter")
    return _uniq_keep_order(hits)

def _find_documents_section(context):
    # Prefer the container that holds the "Vælg & upload" button
    try:
        btn = context.locator(":is(button,a,input)[has-text('Vælg & upload')]")
        if btn.count():
            cont = btn.first.locator("xpath=ancestor::*[self::section or self::div][1]").first
            if cont and cont.is_visible():
                return cont, (cont.inner_text() or "").strip()
    except Exception:
        pass

    # Fallbacks (as before)
    for sel in [
        "section:has-text('Dokumenter')",
        "div:has-text('Dokumenter')",
        "section:has-text('Documents')",
        "div:has-text('Documents')",
        "section:has-text('Vedhæfte' i)",
        "div:has-text('Vedhæfte' i)",
    ]:
        try:
            loc = context.locator(sel)
            if loc.count() and loc.first.is_visible():
                txt = (loc.first.inner_text() or "").strip()
                return loc.first, txt
        except Exception:
            pass
    return context, (context.inner_text() or "")


# ---- fill policy ------------------------------------------------------------
FILL_ALL_MISSING = True

TEXT_LIKE_TYPES = {"text", "email", "tel", "number", "url", "search", "textarea"}

def _is_fillable_type(t: str) -> bool:
    t = (t or "").lower()
    return (t in TEXT_LIKE_TYPES) or (t in SELECT_LIKE_TYPES)

def _synth_value_for_text(label: str, ftype: str, user_profile: dict, user) -> str:
    L = _normalize_label(label or "")
    # sensible Danish defaults
    if "email" in L or "mail" in L:
        return getattr(user, "email", "") or "candidate@example.com"
    if "phone" in L or "mobil" in L or "tel" in L:
        raw = getattr(user, "phone_number", "") or "42424242"
        cc = (getattr(user, "country", "") or "DK").upper()
        dial = DIAL.get(cc, "+45")
        return raw if raw.startswith("+") else f"{dial} {raw}"
    if "postnummer" in L or "zip" in L or "postal" in L:
        return getattr(user, "postal_code", "") or "2100"
    if re.search(r"\bby\b", L) or "city" in L:
        return getattr(user, "city", "") or "København"
    if "adresse" in L or "address" in L:
        return getattr(user, "address", "") or "Testvej 1"
    if "stilling" in L or "position" in L or "title" in L:
        return _profile_get(user_profile, "current_position", "occupation") or "Ledig"
    if "arbejdsgiver" in L or "employer" in L or "company" in L:
        return _profile_get(user_profile, "current_employer", "company") or "Ingen"
    if ("løn" in L or "salary" in L or "compensation" in L):
        val = getattr(user, "expected_salary", None) or _profile_get(user_profile, "expected_salary")
        if ftype == "number":
            return re.sub(r"[^\d]", "", str(val or "0")) or "0"
        return str(val or "Efter aftale")
    if ("fagområde" in L) or ("field of study" in L):
        return _profile_get(user_profile, "field_of_study") or "Andet område"
    if ("titel" in L and "uddannelse" in L) or "degree" in L:
        return _profile_get(user_profile, "highest_education_level", "degree") or "Bachelor"

    # generic fallbacks
    if ftype == "email":  return "candidate@example.com"
    if ftype == "tel":    return "+45 42424242"
    if ftype == "number": return "1"
    return "N/A"

def _synth_value_for_select(label: str, options: list[str]) -> str | None:
    """Choose a reasonable option for any select when AI is silent."""
    if not options:
        return None
    L = _normalize_label(label or "")
    # consent / privacy → Yes / Ja if available
    if re.search(r"(consent|agree|gdpr|dele.*ansogning|må.*dele)", L):
        for want in ("Ja", "Yes"):
            for o in options:
                if want.lower() in o.lower(): return o
    # gender → "Andet" or similar neutral
    if re.search(r"k(ø|o)n|gender", L):
        for want in ("Foretrækker at undlade", "Andet", "Other"):
            for o in options:
                if want.lower() in o.lower(): return o
    # years of experience → the smallest available (often 0 or 1)
    if "erfaring" in L or "experience" in L:
        nums = []
        for o in options:
            m = re.search(r"(\d+)", o)
            if m: nums.append((int(m.group(1)), o))
        if nums:
            return sorted(nums, key=lambda x: x[0])[0][1]
    # degree / uddannelse → Bachelor/Master if present
    if "uddannelse" in L or "degree" in L:
        for want in ("Bachelor", "Master"):
            for o in options:
                if want.lower() in o.lower(): return o
    # heard about job → Andet/Other
    if "hvor har du hørt" in L or "how did you hear" in L or "kilde" in L:
        for want in ("Andet", "Other"):
            for o in options:
                if want.lower() in o.lower(): return o

    # otherwise pick first non-placeholder (or last resort first item)
    pick = _fallback_required_option(options)
    return pick or options[0]


def _find_upload_controls(context, section):
    """Locate the file input, the *documents* category select, and the upload button."""
    root = section or context

    def _loc_first(scope, sel):
        try:
            loc = scope.locator(sel)
            if loc.count() and loc.first.is_visible():
                return loc.first
        except Exception:
            pass
        return None

    # Prefer a container that actually holds the upload UI
    upload_btn = (_loc_first(root, ":is(button,a,input)[has-text('Vælg & upload')]")
                  or _loc_first(context, ":is(button,a,input)[has-text('Vælg & upload')]"))

    # File input (often hidden, but present in DOM)
    file_input = None
    for scope in (root, context):
        try:
            cand = scope.locator("input[type='file']")
            if cand.count():
                file_input = cand.first
                break
        except Exception:
            pass

    # Category select: pick the <select> whose options include CV/Ansøgning (or synonyms)
    category = None
    def _select_with_doc_options(scope):
        try:
            sels = scope.locator("select")
            for i in range(min(sels.count(), 10)):
                sel = sels.nth(i)
                try:
                    opts = sel.evaluate("(el)=>[...el.options].map(o=>(o.textContent||'').trim())")
                except Exception:
                    continue
                joined = " | ".join(opts).lower()
                if any(k in joined for k in ["cv","curriculum","resume","ansøgning","ansoegning","cover","application","motiveret"]):
                    return sel
        except Exception:
            pass
        return None

    category = _select_with_doc_options(root) or _select_with_doc_options(context)

    # Multiple files support?
    supports_multiple = False
    try:
        if file_input:
            ma = file_input.get_attribute("multiple")
            if ma and str(ma).lower() not in {"false","0",""}:
                supports_multiple = True
    except Exception:
        pass

    print(f"🔧 Upload controls → file_input={'yes' if file_input else 'no'}, "
          f"category={'yes' if category else 'no'}, "
          f"button={'yes' if upload_btn else 'no'}, "
          f"multiple={'yes' if supports_multiple else 'no'}")

    return {"file_input": file_input, "category": category, "upload_btn": upload_btn, "supports_multiple": supports_multiple}


def _ensure_file_input_visible(context):
    try:
        context.evaluate(
            """() => {
                const i = document.querySelector('input[type=file]');
                if (!i) return;
                i.style.display = 'block';
                i.style.visibility = 'visible';
                i.style.position = 'static';
                i.removeAttribute('hidden');
                i.classList?.remove('visually-hidden');
            }"""
        )
    except Exception:
        pass

def _make_temp_docx_or_txt(text: str, prefix: str = "application_"):
    """Prefer .docx (if python-docx installed); fallback to .txt."""
    try:
        from docx import Document  # type: ignore
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=".docx")
        os.close(fd)
        doc = Document()
        doc.add_paragraph(text)
        doc.save(path)
        return path
    except Exception:
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        return path

def _build_files_for_docs(user, resume_path, default_cover_letter_text=""):
    """Return dict like {'cv': '/path/to/cv.pdf', 'cover_letter': '/tmp/application_xxx.docx'}."""
    files = {}
    # CV
    if resume_path and os.path.exists(resume_path):
        files["cv"] = resume_path
    # Default application/cover letter file
    default_text = default_cover_letter_text or (
        f"Application\n\nCandidate: {getattr(user, 'full_name', '') or user.email}\n"
        "This is a default application document automatically attached by Internstart."
    )
    files["cover_letter"] = _make_temp_docx_or_txt(default_text, prefix="application_")
    return files

def _select_category_value(page, context, category_locator, want_label: str) -> bool:
    label = (want_label or "").strip()

    # Try robust native <select> path first (substring / case-insensitive)
    try:
        tag = (category_locator.evaluate("el => (el.tagName||'').toLowerCase()") or "")
    except Exception:
        tag = ""

    if tag == "select":
        try:
            opts = category_locator.evaluate("(el)=>[...el.options].map(o=>({t:(o.textContent||'').trim(), v:o.value}))")
            def norm(s):
                return re.sub(r"\s+", " ", s or "").strip().lower()
            want = norm(label)
            idx = next((i for i,o in enumerate(opts)
                        if norm(o["t"]) == want or norm(o["t"]).startswith(want) or want in norm(o["t"])), -1)
            if idx >= 0:
                category_locator.evaluate(
                    "(el,i)=>{el.selectedIndex=i; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));}",
                    idx
                )
                return True

            # Try synonyms if not found
            syns = CATEGORY_SYNONYMS.get("cv" if "cv" in want.lower() else "cover_letter", [])
            for alt in syns:
                want_alt = norm(alt)
                idx = next((i for i,o in enumerate(opts)
                            if norm(o["t"]) == want_alt or want_alt in norm(o["t"])), -1)
                if idx >= 0:
                    category_locator.evaluate(
                        "(el,i)=>{el.selectedIndex=i; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));}",
                        idx
                    )
                    return True
        except Exception:
            pass

    # Custom widget fallback: click, type, Enter
    try:
        category_locator.click(force=True)
        context.wait_for_timeout(120)
        inner = category_locator.locator("input[role='combobox'], input[aria-autocomplete='list'], input[type='text']").first
        target = inner if (inner and inner.is_visible()) else category_locator
        try:
            if target == inner:
                target.fill("")
            target.type(label, delay=18)
        except Exception:
            pass
        _safe_press(page, target, "Enter"); _safe_press(page, target, "Tab")
        return True
    except Exception:
        pass

    # Last resort: click in the open menu
    try:
        menu = context.locator(":is([role='listbox'], .select2-results__options, .MuiPaper-root, ul[role='listbox'])")
        if menu.count():
            opt = menu.locator(":is([role='option'], li, div, span, button)").filter(has_text=label).first
            if opt and opt.is_visible():
                opt.click(force=True)
                return True
    except Exception:
        pass

    return False


def _wait_file_list_contains(section, filename_base: str, category_hint: str = "", timeout_ms: int = 4000):
    """Best-effort verification that the table/list shows our uploaded entry."""
    end = time.time() + (timeout_ms / 1000.0)
    pat = re.compile(re.escape(filename_base), re.I)
    cat = category_hint.lower()
    while time.time() < end:
        try:
            txt = (section.inner_text() or "")
            ok_name = bool(pat.search(txt))
            ok_cat  = (cat in txt.lower()) if cat else True
            if ok_name and ok_cat:
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False

def _wait_file_list_contains(section, filename_base: str, timeout_ms: int = 5000):
    end = time.time() + (timeout_ms / 1000.0)
    pat = re.compile(re.escape(filename_base), re.I)
    while time.time() < end:
        try:
            txt = (section.inner_text() or "")
            if pat.search(txt):
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False

def upload_docs_via_controls(page, context, section, controls: dict, required_docs, files_map):
    uploaded = []

    # If there is no category and the input supports multiple, batch upload
    if not controls.get("category") and controls.get("supports_multiple"):
        paths = [files_map[d] for d in required_docs if files_map.get(d)]
        if paths:
            _ensure_file_input_visible(context)
            controls["file_input"].set_input_files(paths)
            if controls.get("upload_btn") and controls["upload_btn"].is_visible():
                controls["upload_btn"].click(force=True)
            b = os.path.basename(paths[0])
            _wait_file_list_contains(section or context, b)
        return {"uploaded": required_docs[:], "missing": []}

    # Upload sequentially; RE-FIND controls each time because ATS UIs often re-render
    for doc in required_docs:
        path = files_map.get(doc)
        if not path or not os.path.exists(path):
            print(f"⚠️ Missing file for {doc}")
            continue

        # Re-acquire the current, live controls inside the section
        fresh = _find_upload_controls(context, section)
        file_input  = fresh.get("file_input")
        category    = fresh.get("category")
        upload_btn  = fresh.get("upload_btn")

        if not file_input:
            print("⚠️ No live file input; attempting to click upload button to reveal it …")
            if upload_btn and upload_btn.is_visible():
                upload_btn.click(force=True)
                context.wait_for_timeout(300)
            fresh = _find_upload_controls(context, section)
            file_input = fresh.get("file_input")
            category   = category or fresh.get("category")
            upload_btn = upload_btn or fresh.get("upload_btn")
            if not file_input:
                print("❌ Still no file input; skipping this document.")
                continue

        want_label = CATEGORY_SYNONYMS["cv"][0] if doc == "cv" else CATEGORY_SYNONYMS["cover_letter"][0]
        ok_cat = True
        if category:
            ok_cat = _select_category_value(page, context, category, want_label)
            print(f"{'✅' if ok_cat else '⚠️'} Category set → {want_label}")

        _ensure_file_input_visible(context)
        try:
            file_input.set_input_files(path)
        except Exception:
            # Node may have been re-rendered; re-find once more
            fresh = _find_upload_controls(context, section)
            file_input = fresh.get("file_input")
            if not file_input:
                print("⚠️ File input disappeared; cannot continue.")
                continue
            file_input.set_input_files(path)

        if upload_btn and upload_btn.is_visible():
            try:
                upload_btn.click(force=True)
            except Exception:
                pass

        base = os.path.basename(path)

        # Prefer toast/notification if present
        try:
            notif = context.locator(":is(.alert,.toast,.notification):has-text('blev uploadet')")
            if notif.count():
                notif.first.wait_for(state="visible", timeout=3000)
        except Exception:
            pass

        if _wait_file_list_contains(section or context, base):
            print(f"🗂️ Uploaded {doc} → {base}")
            uploaded.append(doc)
        else:
            context.wait_for_timeout(1500)
            if _wait_file_list_contains(section or context, base):
                print(f"🗂️ Uploaded (delayed confirm) {doc} → {base}")
                uploaded.append(doc)
            else:
                print(f"⚠️ Could not verify upload row for {doc} ({base})")

        try:
            context.wait_for_timeout(300)
        except Exception:
            pass

    missing = [d for d in required_docs if d not in uploaded]
    return {"uploaded": uploaded, "missing": missing}


def handle_document_uploads(page, context, user, resume_path, cover_letter_text, log_dir, safe_company, ts):
    """Orchestrator: detect requirements, find controls, build files, upload."""
    try:
        # If we were accidentally passed a Frame as 'page', normalize:
        # (We always call with page=Page, context=Page/Frame, but keep this safe.)
        real_page = page
        if hasattr(page, "page"):  # e.g., a Frame accidentally passed as 'page'
            try:
                real_page = page.page
            except Exception:
                real_page = context if not hasattr(context, "page") else context.page

        section, sec_text = _find_documents_section(context)
        required = _parse_required_docs_from_text(sec_text)
        if not required:
            # If we cannot parse, assume at least CV if file input exists
            controls = _find_upload_controls(context, section)
            if controls.get("file_input"):
                required = ["cv"]  # minimal default
            else:
                print("ℹ️ No documents section or file input detected.")
                return {"uploaded": [], "missing": []}

        print(f"📎 Detected required docs: {required}")

        controls = _find_upload_controls(context, section)
        files    = _build_files_for_docs(user, resume_path, cover_letter_text or "Default application text.")
        summary  = upload_docs_via_controls(real_page, context, section, controls, required, files)

        # Section screenshot for logs
        try:
            shot = os.path.join(log_dir, f"documents_section_{safe_company}_{ts}.png")
            context.screenshot(path=shot)
            print(f"📸 Saved documents-section screenshot → {shot}")
        except Exception:
            pass

        print(f"📦 Upload summary: {summary}")
        return summary
    except Exception as e:
        print(f"⚠️ Document upload flow failed: {e}")
        return {"uploaded": [], "missing": []}


def _safe_press(page, target_locator, key: str):
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


# ---------------- dropdown helpers ----------------

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
                    """(a)=>{const r=document.querySelector(`[aria-labelledby~="${a.labId}"]`)
                       || (document.getElementById(a.labId)?.closest('.select__container,.select-shell,[role="combobox"],div'));
                       const t=(r?.innerText||'').toLowerCase(); return t.includes((a.w||'').toLowerCase());}""",
                    {"labId": lab_id, "w": want}
                )
                if committed: return True
            except Exception:
                pass

            if _click_and_choose_option(page, frame, want) or _click_and_choose_option(page, page, want):
                try:
                    committed = frame.evaluate(
                        """(a)=>{const r=document.querySelector(`[aria-labelledby~="${a.labId}"]`)
                           || (document.getElementById(a.labId)?.closest('.select__container,.select-shell,[role="combobox"],div'));
                           const t=(r?.innerText||'').toLowerCase(); return t.includes((a.w||'').toLowerCase());}""",
                        {"labId": lab_id, "w": want}
                    )
                    if committed: return True
                except Exception:
                    pass

        if lab_for:
            try:
                ok = frame.evaluate(
                    """(a)=>{const el=document.getElementById(a.id); if(!el) return false;
                        const tag=(el.tagName||'').toLowerCase();
                        if (tag==='select'){const o=[...el.options||[]];
                          const m=o.find(x=>(x.textContent||'').trim().toLowerCase()===(a.w||'').toLowerCase())
                                  || o.find(x=>(x.textContent||'').toLowerCase().includes((a.w||'').toLowerCase()));
                          if(!m) return false; el.value=m.value;}
                        else {el.value=a.w; el.setAttribute('value',a.w);}
                        el.dispatchEvent(new Event('input',{bubbles:true}));
                        el.dispatchEvent(new Event('change',{bubbles:true}));
                        return true;}""",
                    {"id": lab_for, "w": want}
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


# ---------------- scan & baseline fill ----------------

DIAL = {"DK": "+45", "US": "+1", "UK": "+44", "FRA": "+33", "GER": "+49"}

def _yesno_preference(label_text: str) -> str:
    L = (label_text or "").lower()
    if AUTO_YES_RE.search(L): return "Yes"
    if AUTO_NO_RE.search(L):  return "No"
    return ""

def _accessible_label(frame, el):
    try:
        return frame.evaluate(
            """(el) => {
              const txt = n => ((n && (n.innerText || n.textContent)) || '').trim();
              const byIds = (el.getAttribute('aria-labelledby') || '')
                  .trim().split(/\\s+/).map(id => txt(document.getElementById(id))).join(' ');

              const described = (el.getAttribute('aria-describedby') || '')
                  .trim().split(/\\s+/).map(id => txt(document.getElementById(id))).join(' ');

              const lab = (el.labels && el.labels[0] && txt(el.labels[0])) || '';
              const aria = el.getAttribute('aria-label') || '';
              const ph = el.getAttribute('placeholder') || '';

              let near = '';
              const wrap = el.closest('div,section,fieldset,td,tr,.form-group,.field,.form__group') || el.parentElement;

              if (wrap) {
                // Common label-like elements near the field
                let cand = wrap.querySelector('label,[for],legend,th,td,span,small,p,strong,b');
                near = txt(cand);
                // If still empty, walk up and across siblings
                if (!near) {
                  let prev = el.previousElementSibling;
                  for (let i = 0; i < 10 && !near && prev; i++) {
                    near = txt(prev);
                    prev = prev.previousElementSibling;
                  }
                }
                if (!near) {
                  // Search upwards for any row/cell headers with text
                  let up = wrap.parentElement;
                  for (let i = 0; i < 4 && !near && up; i++) {
                    let headerish = up.querySelector('label,th,td,span,strong,b,p');
                    near = txt(headerish);
                    up = up.parentElement;
                  }
                }
              }

              return [lab, aria, ph, byIds, described, near].join(' ').replace(/\\s+/g,' ').trim();
            }""",
            el
        ) or ""
    except Exception:
        return ""



def scan_all_fields(page):
    # Broader net: native inputs + common select-like widgets
    selectors = [
        "input:not([type='hidden']):not([disabled])",
        "textarea:not([disabled])",
        "select:not([disabled])",
        "[contenteditable='true']",

        # select-like
        "[role='combobox']:not([aria-disabled='true'])",
        "[aria-haspopup='listbox']:not([aria-disabled='true'])",
        "md-select:not([disabled])",
        "mat-select:not([disabled])",
        ".select2-selection[role='combobox']",
        ".choices__inner",
    ]

    inventory, frame_idx = [], {fr: i for i, fr in enumerate(page.frames)}
    total = 0
    for fr in page.frames:
        for q in selectors:
            loc = fr.locator(q)
            for i in range(loc.count()):
                el = loc.nth(i)
                try:
                    if not el.is_visible():
                        continue

                    tag  = el.evaluate("el => (el.tagName||'').toLowerCase()")
                    role = (el.get_attribute("role") or "").lower()
                    ah   = (el.get_attribute("aria-haspopup") or "").lower()

                    # classify type
                    if tag == "select":
                        et = "select"
                    elif tag == "md-select":
                        et = "md-select"
                    elif tag == "mat-select":
                        et = "mat-select"
                    elif role == "combobox" or ah == "listbox" or "choices__inner" in (el.get_attribute("class") or "") or "select2-selection" in (el.get_attribute("class") or ""):
                        et = "combo"
                    else:
                        et = (el.get_attribute("type") or "text").lower()

                    # read current value
                    current_val = ""
                    try:
                        if q == "[contenteditable='true']":
                            current_val = (el.inner_text() or "").strip()
                        elif et in SELECT_LIKE_TYPES and tag != "select":
                            # many custom selects keep "selected text" inside the element
                            current_val = (el.inner_text() or el.get_attribute("aria-label") or "").strip()
                        else:
                            current_val = (el.input_value() or "").strip()
                    except Exception:
                        pass

                    # selected text (native select only here; custom handled above)
                    selected_text = ""
                    if et == "select":
                        try:
                            selected_text = fr.evaluate(
                                """(a) => {
                                   const e = document.querySelectorAll(a.q)[a.n];
                                   if (!e) return '';
                                   const o = e.options[e.selectedIndex];
                                   return (o && o.textContent || '').trim();
                                }""",
                                {"q": q, "n": i}
                            ) or ""
                        except Exception:
                            selected_text = ""

                    required = False
                    try:
                        required = bool(
                            el.get_attribute("required") or
                            (el.get_attribute("aria-required") in ["true", True]) or
                            (el.get_attribute("ng-required") is not None)   # Angular
                        )
                    except Exception:
                        pass

                    inventory.append({
                        "frame_index": frame_idx[fr],
                        "query": q,
                        "nth": i,
                        "type": et or "text",
                        "name": el.get_attribute("name") or "",
                        "id": el.get_attribute("id") or "",
                        "placeholder": el.get_attribute("placeholder") or "",
                        "aria_label": el.get_attribute("aria-label") or "",
                        "label": _accessible_label(fr, el),
                        "required": required,
                        "current_value": current_val,
                        "selected_text": selected_text,
                    })
                    total += 1
                except Exception:
                    pass

    print(f"🧩 Field scan complete — detected {total} fields across {len(page.frames)} frames.")
    for i, f in enumerate(inventory):
        print(
            f"   [{i:02d}] frame={f['frame_index']} nth={f['nth']} type='{f.get('type')}' "
            f"id='{(f.get('id') or '')[:40]}' name='{(f.get('name') or '')[:40]}' "
            f"label='{(f.get('label') or '')[:80]}' selected='{f.get('selected_text')}' "
            f"value='{(f.get('current_value') or '')[:80]}' req={f.get('required')}"
        )
    return inventory


def _country_human(code: str) -> str:
    return {"DK":"Denmark","US":"United States","UK":"United Kingdom","FRA":"France","GER":"Germany"}.get((code or "").upper(), "")

def _attrs_blob(**kw):
    return " ".join([str(kw.get(k,"") or "") for k in ["label","name","id_","placeholder","aria_label","type_"]]).lower().strip()






def _value_from_meta(user, meta: str):
    L = _normalize_label(meta or "")
    linkedin = (getattr(user,"linkedin_url","") or "").strip()
    cc = (getattr(user,"country","") or "").upper()
    phone_raw = (getattr(user,"phone_number","") or "").strip()
    phone = f"{DIAL.get(cc,'')} {phone_raw}".strip() if any(k in L for k in ["phone","mobile","tel"]) and phone_raw and not phone_raw.startswith("+") else phone_raw

    # Make a clean numeric salary in case the input is type="number"
    def _numify_salary(x):
        s = str(x or "").strip()
        # accept things like "45.000 kr" or "45,000"
        digits = re.sub(r"[^\d]", "", s)
        return digits or s

    mapping = [
        (["first","fname","given","forename"], user.first_name or ""),
        (["last","lname","surname","family"],  user.last_name or ""),
        (["email","e-mail","mail"],            user.email or ""),
        (["phone","mobile","tel"],             phone),
        (["linkedin","profile url","profile_url"], linkedin),
        (["country","nationality","land"],     _country_human(cc)),
        (["city","town","by"],                 getattr(user,"location","") or ""),
        (["job title","title","position","role"], getattr(user,"occupation","") or ""),
        (["company","employer","organization","organisation","current company"], getattr(user,"category","") or ""),

        # Salary (include ASCII and English/Danish variants)
        ([
          "løn", "lon", "lonforventning", "lønforventning",
          "salary", "expected salary", "expected pay", "desired salary",
          "compensation", "expected compensation", "kompensation"
        ], _numify_salary(getattr(user, "expected_salary", ""))),
    ]

    for keys, val in mapping:
        # compare on normalized label
        if any(k in L for k in keys) and val:
            return val

    if ("url" in L or "website" in L) and "linkedin" in L and linkedin:
        return linkedin
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
            if curr and curr.upper()!="N/A":
                continue

            meta = _attrs_blob(
                label=it.get("label",""), name=it.get("name",""), id_=it.get("id",""),
                placeholder=it.get("placeholder",""), aria_label=it.get("aria_label",""),
                type_=it.get("type","")
            )
            val = _value_from_meta(user, meta)
            if not val: 
                continue

            try: el.scroll_into_view_if_needed(timeout=1500)
            except Exception: pass

            is_select_like = (it.get("type") in SELECT_LIKE_TYPES)

            if is_select_like:
                ok = False
                if it.get("type") == "select":
                    try:
                        el.select_option(label=val)
                        ok = True
                    except Exception:
                        pass
                if not ok:  # custom select-like or fallback
                    ok = _select_like_set(fr, it["query"], it["nth"], val)

                if not ok:
                    # last-chance: try matching against options we can see
                    try:
                        opts = _extract_dropdown_options(fr, it["query"], it["nth"])
                        pick = _best_option_match(opts, val)
                        if pick:
                            ok = _select_like_set(fr, it["query"], it["nth"], pick)
                    except Exception:
                        pass

                if not ok:
                    continue  # couldn’t set this control
            else:
                fr.evaluate(
                    """(a)=>{const el=document.querySelectorAll(a.q)[a.n]; if(!el) return;
                        if (el.isContentEditable){ el.innerText=a.v; } else { el.value=a.v; }
                        el.dispatchEvent(new Event('input',{bubbles:true}));
                        el.dispatchEvent(new Event('change',{bubbles:true}));}""",
                    {"q": it["query"], "n": it["nth"], "v": val}
                )


            print(f"✅ Filled “{meta[:60]}” → {val}")
            filled += 1
        except Exception:
            pass
    print(f"✅ Post-scan fill completed — filled {filled} fields from inventory.")
    return filled


# ---------------- AI mop-up with rule-based + required fallbacks ----------------

def _ai_fill_leftovers(page, user):
    try:
        profile_path = f"/home/clinton/Internstart/media/user_profiles/{user.id}.json"
        if not os.path.exists(profile_path):
            print(f"⚠️ No profile JSON found for user {user.id} at {profile_path}")
            return 0

        with open(profile_path, "r", encoding="utf-8") as f:
            user_profile = json.load(f)

        inv = scan_all_fields(page)
        print(f"🔍 DEBUG: total scanned fields = {len(inv)}")
        for i, fdata in enumerate(inv[:12]):
            print(f"   [{i}] type='{fdata.get('type')}' label='{fdata.get('label')}' "
                  f"selected='{fdata.get('selected_text')}' value='{fdata.get('current_value')}'")

        frames = list(page.frames)

        # 1) RULE-BASED PREFILL before AI
        prefilled = 0
        already_filled_fids = set()
        for fdata in inv:
            q, n, ftype = fdata["query"], fdata["nth"], fdata.get("type")
            label = fdata.get("label") or fdata.get("placeholder") or fdata.get("aria_label") or fdata.get("name") or ""
            curr = (fdata.get("current_value") or "").strip()
            fid = f"{fdata['frame_index']}_{fdata['nth']}"

            # skip if something is already entered
            if curr:
                continue

            options = []
            if ftype == "select":
                try:
                    fr = frames[fdata["frame_index"]]
                    options = _extract_dropdown_options(fr, q, n)
                except Exception:
                    options = []

            suggested = _rule_based_value(label, options, user_profile, user)

            if suggested:
                try:
                    fr = frames[fdata["frame_index"]]
                    if ftype == "select":
                        pick = _best_option_match(options, suggested)
                        if not pick:  # if still nothing, try a reasonable fallback
                            pick = _fallback_required_option(options) if fdata.get("required") else None
                        if pick:
                            try:
                                fr.locator(q).nth(n).select_option(label=pick)
                            except Exception:
                                fr.evaluate(
                                    """(a) => {
                                        const el = document.querySelectorAll(a.q)[a.n];
                                        if (!el) return;
                                        const want = (a.labelText || '').trim().toLowerCase();
                                        const opt = [...el.options].find(o =>
                                            (o.textContent || '').trim().toLowerCase() === want
                                        ) || [...el.options].find(o =>
                                            (o.textContent || '').toLowerCase().includes(want)
                                        );
                                        if (opt) {
                                            el.value = opt.value;
                                            el.dispatchEvent(new Event('input',{bubbles:true}));
                                            el.dispatchEvent(new Event('change',{bubbles:true}));
                                        }
                                    }""",
                                    {"q": q, "n": n, "labelText": pick}
                                )
                            print(f"✅ RB selected “{label[:70]}” → {pick}")
                            prefilled += 1
                            already_filled_fids.add(fid)
                    else:
                        fr.evaluate(
                            """(a)=>{
                                const el = document.querySelectorAll(a.q)[a.n];
                                if (!el) return;
                                if (el.isContentEditable) { el.innerText = a.v; }
                                else { el.value = a.v; }
                                el.dispatchEvent(new Event('input',{bubbles:true}));
                                el.dispatchEvent(new Event('change',{bubbles:true}));
                            }""",
                            {"q": q, "n": n, "v": str(suggested)}
                        )
                        print(f"✅ RB filled “{label[:70]}” → {suggested}")
                        prefilled += 1
                        already_filled_fids.add(fid)
                except Exception as e:
                    print(f"⚠️ RB could not fill {fid}: {e}")

        # 2) Build payload for AI (exclude what we already prefilled)
        fields_to_ai = []
        select_audit = []
        force_regex = re.compile(r"(stilling|position|arbejdsgiver|employer)", re.I)
        for fdata in inv:
            fid = f"{fdata['frame_index']}_{fdata['nth']}"
            if fid in already_filled_fids:
                continue

            ftype = fdata.get("type") or ""
            label = (fdata.get("label") or fdata.get("placeholder") or
                     fdata.get("aria_label") or fdata.get("name") or "")
            val = (fdata.get("current_value") or "").strip()
            required = bool(fdata.get("required"))

            if ftype == "select":
                sel_text = fdata.get("selected_text") or ""
                unfilled = _select_is_unfilled(sel_text, val)
                if unfilled:
                    fr = frames[fdata["frame_index"]]
                    options = _extract_dropdown_options(fr, fdata["query"], fdata["nth"])
                    fields_to_ai.append({
                        "field_id": fid, "label": label, "type": "select",
                        "required": required, "options": options
                    })
                    select_audit.append(
                        f"   SELECT label='{label}' selected='{sel_text}' value='{val}' → unfilled=True"
                    )
            else:
                if not val or force_regex.search(label):
                    fields_to_ai.append({
                        "field_id": fid, "label": label, "type": ftype or "text",
                        "required": required
                    })

        print("🔎 DEBUG (select audit):")
        for line in select_audit[:25]:
            print(line)
        print(f"🔍 DEBUG: {len(fields_to_ai)} unfilled fields for AI")

        if not fields_to_ai:
            print("🤖 AI pass: sending 0 fields for interpretation… (No unfilled fields detected)")
            return prefilled

        # 3) Ask AI
        print(f"🤖 AI pass: sending {len(fields_to_ai)} fields for interpretation…")
        answers = map_fields_to_answers(fields_to_ai, user_profile)
        print("============== 🧠 AI RAW OUTPUT ==============")
        try:
            print(json.dumps(answers, indent=2, ensure_ascii=False))
        except Exception:
            print(answers)
        print("=============================================")

        # 4) Apply AI answers (with required fallback for selects)
        applied = 0
        frames = list(page.frames)
        for fdata in inv:
            fid = f"{fdata['frame_index']}_{fdata['nth']}"
            if fid in already_filled_fids:
                continue
            ans = answers.get(fid)
            if ans is None or str(ans).lower() == "skip":
                # if it's a required select, try a safe fallback
                if fdata.get("type") == "select" and fdata.get("required"):
                    fr = frames[fdata["frame_index"]]
                    opts = _extract_dropdown_options(fr, fdata["query"], fdata["nth"])
                    pick = _fallback_required_option(opts)
                    if pick:
                        try:
                            fr.locator(fdata["query"]).nth(fdata["nth"]).select_option(label=pick)
                        except Exception:
                            fr.evaluate(
                                """(a) => {
                                    const el = document.querySelectorAll(a.q)[a.n];
                                    if (!el) return;
                                    const want = (a.labelText || '').trim().toLowerCase();
                                    const opt = [...el.options].find(o =>
                                        (o.textContent || '').trim().toLowerCase() === want
                                    ) || [...el.options].find(o =>
                                        (o.textContent || '').toLowerCase().includes(want)
                                    );
                                    if (opt) {
                                        el.value = opt.value;
                                        el.dispatchEvent(new Event('input',{bubbles:true}));
                                        el.dispatchEvent(new Event('change',{bubbles:true}));
                                    }
                                }""",
                                {"q": fdata["query"], "n": fdata["nth"], "labelText": pick}
                            )
                        print(f"✅ Fallback selected “{fdata.get('label','(no label)')[:70]}” → {pick}")
                        applied += 1
                continue

            fr = frames[fdata["frame_index"]]
            if fdata.get("type") == "select":
                opts = _extract_dropdown_options(fr, fdata["query"], fdata["nth"])
                pick = _best_option_match(opts, str(ans)) or _fallback_required_option(opts)
                if not pick:
                    print(f"⚠️ No option match for “{fdata.get('label','(no label)')}” ← {ans}")
                    continue
                try:
                    fr.locator(fdata["query"]).nth(fdata["nth"]).select_option(label=pick)
                except Exception:
                    fr.evaluate(
                        """(a) => {
                            const el = document.querySelectorAll(a.q)[a.n];
                            if (!el) return;
                            const want = (a.labelText || '').trim().toLowerCase();
                            const opt = [...el.options].find(o =>
                                (o.textContent || '').trim().toLowerCase() === want
                            ) || [...el.options].find(o =>
                                (o.textContent || '').toLowerCase().includes(want)
                            );
                            if (opt) {
                                el.value = opt.value;
                                el.dispatchEvent(new Event('input',{bubbles:true}));
                                el.dispatchEvent(new Event('change',{bubbles:true}));
                            }
                        }""",
                        {"q": fdata["query"], "n": fdata["nth"], "labelText": pick}
                    )
                print(f"✅ AI selected “{fdata.get('label','(no label)')[:70]}” → {pick}")
            else:
                fr.evaluate(
                    """(a)=>{
                        const el = document.querySelectorAll(a.q)[a.n];
                        if (!el) return;
                        if (el.isContentEditable) { el.innerText = a.v; }
                        else { el.value = a.v; }
                        el.dispatchEvent(new Event('input',{bubbles:true}));
                        el.dispatchEvent(new Event('change',{bubbles:true}));
                    }""",
                    {"q": fdata["query"], "n": fdata["nth"], "v": str(ans)}
                )
                print(f"✅ AI filled “{fdata.get('label','(no label)')[:70]}” → {ans}")
            applied += 1

        total = prefilled + applied
        print(f"🤖 AI pass completed — filled {total} fields.")
        return total

    except Exception as e:
        print(f"⚠️ AI leftovers pass failed: {e}")
        return 0


# ---------------- special yes/no forcings ----------------

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
            return frame.evaluate("""(a)=>{const r=document.querySelector(`[aria-labelledby~="${a.labId}"]`)
                       || (document.getElementById(a.labId)?.closest('.select__container,.select-shell,[role="combobox"],div'));
                       const t=(r?.innerText||'').toLowerCase(); return t.includes('no');}""",
                       {"labId": lab_id})
        except Exception:
            return False

    if committed(): return True
    if _click_and_choose_option(page, frame, "No") or _click_and_choose_option(page, page, "No"):
        return committed()
    if lab_for:
        try:
            ok = frame.evaluate("""(a)=>{const el=document.getElementById(a.id); if(!el) return false;
                 if (el.tagName.toLowerCase()==='select'){const m=[...el.options||[]].find(o=>/\\bno\\b/i.test(o.textContent||'')); if(!m) return false; el.value=m.value;}
                 else {el.value='No'; el.setAttribute('value','No');}
                 el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); return true;}""",
                 {"id": lab_for})
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


# ---------------- main ----------------

def apply_to_ats(room_id, user_id, resume_path=None, cover_letter_text="", dry_run=True, screenshot_delay_sec=3):
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

            context = page
            try:
                for fr in page.frames:
                    if fr == page.main_frame: continue
                    if fr.locator("input, textarea, select").count() > 3:
                        context = fr
                        print("🔄 Switched to ATS iframe")
                        break
            except Exception:
                pass

            try: context.wait_for_selector("input, textarea, select", timeout=12000)
            except Exception: pass
            try:
                for _ in range(6):
                    page.mouse.wheel(0, 420)
                    page.wait_for_timeout(220 + random.randint(0,120))
            except Exception: pass

            inv = scan_all_fields(page)
            try:
                with open(os.path.join(log_dir, f"ats_field_inventory_{safe_company}_{ts}.json"), "w", encoding="utf-8") as f:
                    json.dump(inv, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

            fill_from_inventory(page, user, inv)

            _force_privacy_yes_if_needed(page, context)
            if _force_ipg_employment_no(page, context):
                print("🟢 IPG employment → No (forced & verified)")
            else:
                print("🟡 IPG employment not confirmed — continuing; ATS validation may catch it")

            try:
                _ai_fill_leftovers(page, user)
            except Exception as e:
                print(f"⚠️ AI leftovers pass failed: {e}")


            # ---- NEW: document uploads (CV + default "application") ----
            try:
                print("📎 Document upload flow: starting …")
                upload_summary = handle_document_uploads(
                    page=page,                # pass the real Page object
                    context=context,          # page or frame we’re working inside
                    user=user,
                    resume_path=resume_path,
                    cover_letter_text=cover_letter_text or "Default application text.",
                    log_dir=log_dir,
                    safe_company=safe_company,
                    ts=ts
                )
                print(f"📦 Document upload flow summary: {upload_summary}")
            except Exception as e:
                print(f"⚠️ Document upload flow error: {e}")
            # -------------------------------------------------------------






            screenshot_path = os.path.join(log_dir, f"ats_preview_{safe_company}_{ts}.png")
            if dry_run:
                print("🧪 Dry run — skipping submit")
                delay_ms = max(int(screenshot_delay_sec * 1000), 0)
                if delay_ms:
                    print(f"⏱️ Waiting {screenshot_delay_sec}s before screenshot…")
                    page.wait_for_timeout(delay_ms)
                try:
                    page.screenshot(path=screenshot_path, full_page=True)
                    print(f"📸 Saved preview → {screenshot_path}")
                except Exception:
                    pass
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
