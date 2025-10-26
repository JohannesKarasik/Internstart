from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from base.utils.user_profile_builder import build_user_profile
import json, os

User = get_user_model()

@receiver(post_save, sender=User)
def generate_user_profile_json(sender, instance, **kwargs):
    profile = build_user_profile(instance)
    path = f"/home/clinton/Internstart/media/user_profiles/{instance.id}.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    print(f"🧾 Saved user profile JSON → {path}")
