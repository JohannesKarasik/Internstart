import json
from django.forms.models import model_to_dict
from datetime import datetime, date

def safe_json(obj):
    """Handle non-serializable types like datetime."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)

def build_user_profile(user):
    """Convert user model into structured profile JSON."""
    profile = model_to_dict(user, exclude=["password", "last_login", "groups", "user_permissions"])

    # Normalize nested structures
    profile["education"] = {
        "under_education": user.under_education,
        "highest_level": user.highest_education_level,
        "field_of_study": user.field_of_study,
        "institution": user.current_education_name,
    }

    profile["contact"] = {
        "email": user.email,
        "phone": user.phone_number,
        "linkedin": user.linkedin_url,
        "country": user.country,
        "location": user.location,
    }

    profile["employment"] = {
        "occupation": user.occupation,
        "category": user.category,
        "job_type": user.job_type,
    }

    # Use safe JSON encoding for all values
    return json.loads(json.dumps(profile, default=safe_json))
