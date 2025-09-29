from django.shortcuts import render  # (unused, but harmless; remove if you prefer)
import os
import json

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib.auth import get_user_model

import stripe
from base.models import DailySwipeQuota  # 👈 import your quota model

User = get_user_model()

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Map your plan slugs to Stripe Price IDs (TEST mode to begin with)
PRICE_IDS = {
    "starter": os.getenv("STRIPE_PRICE_STARTER", "price_123StarterTEST"),
    "pro":     os.getenv("STRIPE_PRICE_PRO",     "price_123ProTEST"),
    "vip":     os.getenv("STRIPE_PRICE_VIP",     "price_123VipTEST"),
}

# Map Stripe Price IDs back to tiers & daily swipe limits
PRICE_LIMITS = {
    PRICE_IDS["starter"]: {"tier": "starter", "daily_swipes": 10},
    PRICE_IDS["pro"]: {"tier": "pro", "daily_swipes": 25},
    PRICE_IDS["vip"]: {"tier": "vip", "daily_swipes": 40},
}


def well_known_devtools(_request):
    """Return empty JSON to satisfy Chrome/DevTools probe."""
    return JsonResponse({}, status=200)


@login_required
def create_checkout_session(request):
    """
    Create a Stripe Checkout Session for subscriptions.
    """
    if not getattr(settings, "STRIPE_SECRET_KEY", "").startswith(("sk_test_", "sk_live_")):
        return JsonResponse({"error": "Stripe secret key not configured"}, status=400)

    tier = None
    try:
        if request.content_type and "application/json" in request.content_type:
            body = json.loads((request.body or b"{}").decode("utf-8"))
            tier = (body or {}).get("tier")
        else:
            tier = request.POST.get("tier") or request.GET.get("tier")
    except Exception as e:
        return JsonResponse({"error": f"Invalid JSON: {e}"}, status=400)

    tier = (tier or "pro").strip().lower()
    price_id = PRICE_IDS.get(tier)
    if not price_id:
        return JsonResponse(
            {"error": f"Unknown tier '{tier}'. Use one of: {', '.join(PRICE_IDS.keys())}"},
            status=400,
        )

    try:
        res = stripe.Customer.list(email=request.user.email, limit=1)
        customer = res.data[0].id if res.data else stripe.Customer.create(
            email=request.user.email, metadata={"django_user_id": str(request.user.id)}
        ).id
    except Exception as e:
        return JsonResponse({"error": f"Customer error: {e}"}, status=400)

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer=customer,
            allow_promotion_codes=True,
            success_url=settings.STRIPE_SUCCESS_URL,
            cancel_url=settings.STRIPE_CANCEL_URL,
            subscription_data={
                "metadata": {"django_user_id": str(request.user.id), "tier": tier},
            },
            client_reference_id=str(request.user.id),
        )
        return JsonResponse({"url": session.url})
    except Exception as e:
        return JsonResponse({"error": f"Checkout error: {e}"}, status=400)


@login_required
def create_billing_portal(request):
    """
    Create a Billing Portal session so users can update payment method,
    change plan, or cancel.
    """
    try:
        res = stripe.Customer.list(email=request.user.email, limit=1)
        customer = res.data[0].id if res.data else stripe.Customer.create(
            email=request.user.email, metadata={"django_user_id": str(request.user.id)}
        ).id
        portal = stripe.billing_portal.Session.create(
            customer=customer,
            return_url=settings.STRIPE_PORTAL_RETURN_URL,
        )
        return JsonResponse({"url": portal.url})
    except Exception as e:
        return JsonResponse({"error": f"Portal error: {e}"}, status=400)


# --- Helper to apply subscription locally ---
def _apply_subscription(user_id, price_id):
    """Update User + DailySwipeQuota based on Stripe price_id."""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return

    if price_id and price_id in PRICE_LIMITS:
        tier_info = PRICE_LIMITS[price_id]
        # update user model
        user.subscription_tier = tier_info["tier"]
        user.save()

        # update today's quota
        quota, _ = DailySwipeQuota.objects.get_or_create(user=user, date=timezone.localdate())
        quota.limit = tier_info["daily_swipes"]
        quota.save()
    else:
        # fallback to free
        user.subscription_tier = "free"
        user.save()
        quota, _ = DailySwipeQuota.objects.get_or_create(user=user, date=timezone.localdate())
        quota.limit = 5
        quota.save()


@csrf_exempt
def stripe_webhook(request):
    """
    Handle Stripe webhook events.
    """
    payload = request.body
    sig = request.headers.get("Stripe-Signature", "")
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, endpoint_secret)
    except Exception:
        return HttpResponse(status=400)

    et = event.get("type")
    data = event.get("data", {}).get("object", {})

    if et == "checkout.session.completed":
        session = data
        user_id = session.get("client_reference_id")
        if user_id:
            # need to fetch subscription to get price
            sub_id = session.get("subscription")
            if sub_id:
                sub = stripe.Subscription.retrieve(sub_id)
                price_id = sub["items"]["data"][0]["price"]["id"]
                _apply_subscription(user_id, price_id)

    elif et in ("customer.subscription.created", "customer.subscription.updated"):
        sub = data
        user_id = sub.get("metadata", {}).get("django_user_id")
        price_id = sub["items"]["data"][0]["price"]["id"]
        if user_id:
            _apply_subscription(user_id, price_id)

    elif et == "customer.subscription.deleted":
        sub = data
        user_id = sub.get("metadata", {}).get("django_user_id")
        if user_id:
            _apply_subscription(user_id, None)

    return HttpResponse(status=200)