import os
import json
import stripe
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

# ✅ Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# ✅ Stripe price IDs for each tier (replace with your real IDs)
PRICE_IDS = {
    "starter": os.getenv("STRIPE_PRICE_STARTER", "price_starter_test"),
    "pro": os.getenv("STRIPE_PRICE_PRO", "price_pro_test"),
    "elite": os.getenv("STRIPE_PRICE_ELITE", "price_elite_test"),
}

# ✅ Swipe limits per plan
SWIPE_LIMITS = {
    "starter": 50,
    "pro": 200,
    "elite": 500,
}


def well_known_devtools(_request):
    """Return empty JSON to satisfy Chrome DevTools probes."""
    return JsonResponse({}, status=200)


# =====================================
# 🔹 CREATE CHECKOUT SESSION
# =====================================
@login_required
def create_checkout_session(request):
    """Creates a Stripe Checkout Session for subscription signup."""
    if not settings.STRIPE_SECRET_KEY:
        return JsonResponse({"error": "Stripe key not configured"}, status=400)

    # Get plan tier from request
    try:
        if "application/json" in request.content_type:
            body = json.loads(request.body.decode("utf-8"))
            tier = (body or {}).get("tier", "").lower()
        else:
            tier = (request.POST.get("tier") or request.GET.get("tier") or "").lower()
    except Exception as e:
        return JsonResponse({"error": f"Invalid JSON: {e}"}, status=400)

    if tier not in PRICE_IDS:
        return JsonResponse({"error": f"Invalid tier '{tier}'"}, status=400)

    # Ensure Stripe customer exists
    try:
        res = stripe.Customer.list(email=request.user.email, limit=1)
        customer = res.data[0].id if res.data else stripe.Customer.create(
            email=request.user.email,
            metadata={"django_user_id": str(request.user.id)},
        ).id
    except Exception as e:
        return JsonResponse({"error": f"Customer error: {e}"}, status=400)

    # Create checkout session
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer,
            line_items=[{"price": PRICE_IDS[tier], "quantity": 1}],
            allow_promotion_codes=True,
            success_url=settings.STRIPE_SUCCESS_URL,
            cancel_url=settings.STRIPE_CANCEL_URL,
            subscription_data={"metadata": {"django_user_id": str(request.user.id), "tier": tier}},
            client_reference_id=str(request.user.id),
        )
        return JsonResponse({"url": session.url})
    except Exception as e:
        return JsonResponse({"error": f"Checkout error: {e}"}, status=400)


# =====================================
# 🔹 BILLING PORTAL
# =====================================
@login_required
def create_billing_portal(request):
    """Creates a Stripe Billing Portal session for managing subscription."""
    try:
        res = stripe.Customer.list(email=request.user.email, limit=1)
        customer = res.data[0].id if res.data else stripe.Customer.create(
            email=request.user.email,
            metadata={"django_user_id": str(request.user.id)},
        ).id

        portal = stripe.billing_portal.Session.create(
            customer=customer,
            return_url=settings.STRIPE_PORTAL_RETURN_URL,
        )
        return JsonResponse({"url": portal.url})
    except Exception as e:
        return JsonResponse({"error": f"Portal error: {e}"}, status=400)


# =====================================
# 🔹 APPLY SUBSCRIPTION LOCALLY
# =====================================
def _apply_subscription(user_id, tier=None, status="active"):
    """Update User subscription info and reset swipe usage."""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return

    if tier in SWIPE_LIMITS:
        user.subscription_tier = tier
        user.subscription_status = status
        user.swipes_used = 0  # reset usage when subscribing/renewing
        user.save()
    else:
        # If canceled or invalid tier, mark as inactive
        user.subscription_status = "canceled"
        user.save()


# =====================================
# 🔹 STRIPE WEBHOOK
# =====================================
@csrf_exempt
def stripe_webhook(request):
    """Handles Stripe webhook events for subscription lifecycle."""
    payload = request.body
    sig_header = request.headers.get("Stripe-Signature", "")
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception:
        return HttpResponse(status=400)

    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})

    # ✅ New checkout completed
    if event_type == "checkout.session.completed":
        session = data
        user_id = session.get("client_reference_id")
        sub_id = session.get("subscription")

        if user_id and sub_id:
            sub = stripe.Subscription.retrieve(sub_id)
            price_id = sub["items"]["data"][0]["price"]["id"]
            tier = next((k for k, v in PRICE_IDS.items() if v == price_id), None)
            if tier:
                _apply_subscription(user_id, tier, "active")

    # ✅ Subscription created or updated (renewal)
    elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
        sub = data
        user_id = sub.get("metadata", {}).get("django_user_id")
        price_id = sub["items"]["data"][0]["price"]["id"]
        tier = next((k for k, v in PRICE_IDS.items() if v == price_id), None)
        if user_id and tier:
            _apply_subscription(user_id, tier, sub.get("status", "active"))

    # ✅ Subscription canceled
    elif event_type == "customer.subscription.deleted":
        sub = data
        user_id = sub.get("metadata", {}).get("django_user_id")
        if user_id:
            _apply_subscription(user_id, None, "canceled")

    return HttpResponse(status=200)

def landing_page(request):
    return render(request, "landing_page.html", {
        "google_maps_key": settings.GOOGLE_MAPS_KEY
    })
