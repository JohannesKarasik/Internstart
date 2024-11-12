from django import template
from django.utils import timezone  # Import timezone from Django

register = template.Library()

@register.filter
def custom_timesince(value):
    now = timezone.now()

    # Ensure 'value' is timezone-aware
    if timezone.is_naive(value):
        value = timezone.make_aware(value)

    # Calculate the difference between now and the post time
    diff = now - value
    minutes = diff.total_seconds() // 60
    hours = minutes // 60
    days = hours // 24

    if minutes < 60:
        return f"{int(minutes)} minute{'s' if int(minutes) != 1 else ''} ago"
    elif hours < 24:
        return f"{int(hours)} hour{'s' if int(hours) != 1 else ''} ago"
    elif days < 7:  # If it's less than a week, show number of days
        return f"{int(days)} day{'s' if int(days) != 1 else ''} ago"
    else:
        return value.strftime("%b %d, %Y")