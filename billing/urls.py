from django.urls import path
from .views import (
    create_checkout_session,
    create_billing_portal,
    stripe_webhook,
    well_known_devtools,
)

urlpatterns = [
    # silence Chrome DevTools probe
    path(".well-known/appspecific/com.chrome.devtools.json", well_known_devtools),
    path("create-checkout-session/", create_checkout_session, name="create_checkout_session"),
    path("create-billing-portal/", create_billing_portal, name="create_billing_portal"),
    path("stripe/webhook/", stripe_webhook, name="stripe_webhook"),
]
