import json
from django.forms.models import model_to_dict

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

    return profile
