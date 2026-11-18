"""
Module 1 - Stripe integration over its REST API (no extra SDK needed).

Live mode needs STRIPE_SECRET_KEY + STRIPE_PRICE_PRO / STRIPE_PRICE_AGENCY (+ STRIPE_WEBHOOK_SECRET
for the webhook). Without a key the subscription engine runs in test/mock mode.
"""
from typing import Dict, Optional

import httpx

from app.core.config import settings

STRIPE_API = "https://api.stripe.com/v1"


async def create_checkout_session(*, price_id: str, workspace_id: str, plan: str, email: str,
                                  success_url: str, cancel_url: str, customer_id: Optional[str] = None) -> Dict:
    data = {
        "mode": "subscription",
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": workspace_id,
        "metadata[workspace_id]": workspace_id,
        "metadata[plan]": plan,
        "subscription_data[metadata][workspace_id]": workspace_id,
        "subscription_data[metadata][plan]": plan,
    }
    if customer_id:
        data["customer"] = customer_id
    else:
        data["customer_email"] = email
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(f"{STRIPE_API}/checkout/sessions", data=data, auth=(settings.STRIPE_SECRET_KEY, ""))
    if r.status_code >= 400:
        raise RuntimeError(r.json().get("error", {}).get("message", r.text))
    return r.json()


async def cancel_subscription(subscription_id: str) -> Dict:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(f"{STRIPE_API}/subscriptions/{subscription_id}",
                              data={"cancel_at_period_end": "true"}, auth=(settings.STRIPE_SECRET_KEY, ""))
    if r.status_code >= 400:
        raise RuntimeError(r.text)
    return r.json()


async def create_portal_session(customer_id: str, return_url: str) -> Dict:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(f"{STRIPE_API}/billing_portal/sessions",
                              data={"customer": customer_id, "return_url": return_url}, auth=(settings.STRIPE_SECRET_KEY, ""))
    if r.status_code >= 400:
        raise RuntimeError(r.text)
    return r.json()


def verify_webhook_signature(payload: bytes, sig_header: str, secret: str, tolerance: int = 300) -> bool:
    """Delegates to SecurityManager (Stripe v1 scheme: HMAC-SHA256 of "{timestamp}.{payload}")."""
    from app.core.security import security_manager
    return security_manager.verify_stripe_signature(payload, sig_header, secret, tolerance)

