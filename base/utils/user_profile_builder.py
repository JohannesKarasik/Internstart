# base/utils/user_profile_builder.py
from typing import Any, Dict

def _yn_str(val):
    """
    Normalizes booleans/strings to 'yes'/'no' for consistency.
    Returns None if unknown.
    """
    if val is True:  return "yes"
    if val is False: return "no"
    if val is None:  return None
    s = str(val).strip().lower()
    if s in {"yes", "ja", "true", "1"}:  return "yes"
    if s in {"no", "nej", "false", "0"}: return "no"
    return None

def build_user_profile(u) -> Dict[str, Any]:
    """
    Build a JSON-serializable dict of the user profile for ATS/AI.
    Keep keys stable; prefer primitive types only.
    """
    full_name = (u.full_name or f"{u.first_name or ''} {u.last_name or ''}".strip()).strip()

    profile: Dict[str, Any] = {
        # --- identity / meta ---
        "id": u.id,
        "date_joined": u.date_joined.isoformat() if getattr(u, "date_joined", None) else None,

        # --- flat fields (handy for simple matches) ---
        "full_name": full_name or None,
        "first_name": u.first_name or None,
        "last_name": u.last_name or None,
        "email": u.email or None,
        "phone_number": u.phone_number or None,
        "linkedin_url": u.linkedin_url or None,
        "country": u.country or None,
        "location": (u.location or None),
        "role": u.role or None,
        "category": u.category or None,
        "job_type": u.job_type or None,
        "gender": getattr(u, "gender", None),

        # legacy flat education keys (preserve for compatibility)
        "under_education": _yn_str(getattr(u, "under_education", None)),
        "highest_education_level": getattr(u, "highest_education_level", None),
        "field_of_study": getattr(u, "field_of_study", None),
        "current_education_name": getattr(u, "current_education_name", None),
    }

    # --- structured sections the AI will prefer ---
    profile["education"] = {
        "under_education": _yn_str(getattr(u, "under_education", None)),
        "highest_level": getattr(u, "highest_education_level", None),
        "field_of_study": getattr(u, "field_of_study", None),
        "institution": getattr(u, "current_education_name", None),
    }

    # NEW: employment enrichment
    profile["employment"] = {
        "currently_employed": getattr(u, "currently_employed", None),
        "current_position":   (getattr(u, "current_position", None) or u.occupation or None),
        "current_employer":   (getattr(u, "current_employer", None) or u.category or None),
        "years_experience":    getattr(u, "total_years_experience", None),  # integer years
        "occupation":          u.occupation or None,
        "category":            u.category or None,
        "job_type":            u.job_type or None,
    }

    profile["contact"] = {
        "email": u.email or None,
        "phone": u.phone_number or None,
        "linkedin": u.linkedin_url or None,
        "country": u.country or None,
        "location": (u.location or None),
    }

    profile["assets"] = {
        "resume": (u.resume.name if getattr(u, "resume", None) else None),
        "avatar": (u.avatar.name if getattr(u, "avatar", None) else None),
        "background": (u.background.name if getattr(u, "background", None) else None),
    }

    return profile
