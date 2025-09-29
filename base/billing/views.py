# billing/views.py
import os
import json
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
import stripe

stripe.api_key = settings.STRIPE_SECRET_KEY

# Map your three tiers to Stripe Price IDs (test mode first)
# e.g. grab these from Dashboard > Prices (test data)
PRICE_IDS = {
    "starter":  os.getenv("STRIPE_PRICE_STARTER",  "price_123StarterTEST"),
    "pro":      os.getenv("STRIPE_PRICE_PRO",      "price_123ProTEST"),
    "vip":      os.getenv("STRIPE_PRICE_VIP",      "price_123VipTEST"),
}

@login_required
def create_checkout_session(request):
    """
    Creates a Stripe Checkout Session for subscriptions.
    Expects JSON: { "tier": "starter" | "pro" | "vip" }
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
        tier = body.get("tier")
        price_id = PRICE_IDS.get(tier)
        if not price_id:
            return JsonResponse({"error": "Unknown tier"}, status=400)

        # Ensure the Stripe customer exists (attach Django user id as metadata)
        customer = None
        if request.user.is_authenticated and hasattr(request.user, "email"):
            # Try to find by email; in production you’d store customer id on the user model
            res = stripe.Customer.list(email=request.user.email, limit=1)
            customer = res.data[0].id if res.data else None
            if not customer:
                customer = stripe.Customer.create(
                    email=request.user.email,
                    metadata={"django_user_id": str(request.user.id)}
                ).id

        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer=customer,
            allow_promotion_codes=True,  # lets you test with coupons (100% off)
            success_url=settings.STRIPE_SUCCESS_URL,
            cancel_url=settings.STRIPE_CANCEL_URL,
            subscription_data={
                # For “test without paying”, you can also add a trial period:
                # "trial_period_days": 7,
                "metadata": {"django_user_id": str(request.user.id), "tier": tier},
            },
            client_reference_id=str(request.user.id),
        )
        return JsonResponse({"url": session.url})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@login_required
def create_billing_portal(request):
    """
    Customer self-serve portal (change plan, cancel, update card).
    """
    # Look up / create customer by email (or pull from your DB)
    res = stripe.Customer.list(email=request.user.email, limit=1)
    customer = res.data[0].id if res.data else stripe.Customer.create(
        email=request.user.email,
        metadata={"django_user_id": str(request.user.id)}
    ).id

    portal = stripe.billing_portal.Session.create(
        customer=customer,
        return_url=settings.STRIPE_PORTAL_RETURN_URL,
    )
    return JsonResponse({"url": portal.url})

@csrf_exempt
def stripe_webhook(request):
    """
    Handle Stripe webhook events (test + live).
    Update your local subscription state here.
    """
    payload = request.body
    sig = request.headers.get("Stripe-Signature", "")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig, endpoint_secret)
    except Exception as e:
        return HttpResponse(status=400)

    # Handle events you care about
    if event["type"] in ("checkout.session.completed",):
        # Subscription created/paid
        session = event["data"]["object"]
        # TODO: mark user as active subscriber using session["client_reference_id"]
        #       and session["subscription"]
        pass

    if event["type"] in ("customer.subscription.updated", "customer.subscription.created"):
        sub = event["data"]["object"]
        # TODO: store sub["status"], sub["current_period_end"], sub["items"]["data"][0]["price"]["id"], etc.
        pass

    if event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        # TODO: mark local subscription inactive
        pass

    return HttpResponse(status=200)
