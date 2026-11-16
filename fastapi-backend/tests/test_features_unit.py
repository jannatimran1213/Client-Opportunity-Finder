"""Offline unit tests for the 32-feature modules (no database, no network)."""
import asyncio
import time

import pytest

from app.core.security import SecurityError, SecurityManager, security_manager as sm
from app.services.builder.renderer import render_email, render_page
from app.services.builder.templates import TEMPLATES
from app.services.channels import tracking
from app.services.leads import dedupe
from app.services.leads.validation import validate_email, validate_phone
from app.services.website_audit.trust_leaks import detect_leaks
from app.services.billing.plans import PLANS, plan_limits, price_for


# ── [1] SecurityManager: the single security class ──
def test_security_manager_is_one_class():
    assert isinstance(sm, SecurityManager)
    from app.core import encryption, rbac
    assert encryption.encrypt("x") != "x"   # shims delegate to SecurityManager
    assert rbac.has_permission("owner", "billing:manage")


def test_passwords_and_jwt():
    h = sm.hash_password("Passw0rd!x")
    assert sm.verify_password("Passw0rd!x", h) and not sm.verify_password("wrong", h)
    tok = sm.create_access_token("user-1")
    assert sm.decode_access_token(tok)["sub"] == "user-1"
    assert sm.decode_access_token(tok + "x") is None


def test_rbac_matrix():
    assert sm.has_permission("owner", "billing:manage")
    assert not sm.has_permission("member", "billing:manage")
    assert sm.has_permission("viewer", "leads:read") and not sm.has_permission("viewer", "leads:write")
    assert not sm.can_assign_role("admin", "owner")


def test_tenant_isolation():
    class Obj:
        workspace_id = "ws-a"
    assert sm.assert_same_tenant(Obj(), "ws-a")
    with pytest.raises(SecurityError):
        sm.assert_same_tenant(Obj(), "ws-b")


def test_encryption_signing_sanitising():
    c = sm.encrypt("smtp-secret")
    assert c != "smtp-secret" and sm.decrypt(c) == "smtp-secret"
    sig = sm.sign("token|https://a.com")
    assert sm.verify_signature("token|https://a.com", sig) and not sm.verify_signature("token|https://evil.com", sig)
    assert "<script" not in sm.sanitize_html("<p>hi</p><script>alert(1)</script>")
    assert sm.sanitize_subdomain("My Cafe!!") == "my-cafe"
    assert not sm.is_safe_redirect_url("javascript:alert(1)")


def test_rate_limit():
    key = f"t{time.time()}"
    results = [sm.check_rate_limit(key, 3, 60)[0] for _ in range(4)]
    assert results == [True, True, True, False]


def test_plans():
    assert set(PLANS) == {"basic", "pro", "enterprise"}
    assert price_for("pro", "yearly") < price_for("pro", "monthly") * 12
    assert plan_limits("enterprise")["leads"] > plan_limits("basic")["leads"]


# ── [3] Lead Management ──
def test_dedupe():
    a = {"id": "1", "business_name": "Blue Cafe", "website": "https://www.bluecafe.com/", "city": "Lahore"}
    b = {"id": "2", "business_name": "Blue Cafe LLC", "website": "http://bluecafe.com", "city": "Lahore"}
    c = {"id": "3", "business_name": "Red Bistro", "website": "https://redbistro.pk", "city": "Lahore"}
    assert dedupe.norm_domain(a["website"]) == "bluecafe.com"
    groups = dedupe.find_duplicate_groups([a, b, c])
    assert len(groups) == 1 and {l["id"] for l in groups[0]["leads"]} == {"1", "2"}


def test_validation():
    assert validate_email("hello@gmail.com", check_mx=False)["status"] in ("valid", "unknown")
    assert validate_email("not-an-email", check_mx=False)["status"] == "invalid"
    assert validate_email("a@mailinator.com", check_mx=False)["status"] in ("invalid", "risky")
    p = validate_phone("0300 1234567", "Pakistan")
    assert p["status"] in ("valid", "unknown") and (p.get("e164") or "").startswith("+92")


# ── [4] Trust & Conversion Leak Detector ──
def test_trust_leaks():
    bare = "<html><body><h1>Hi</h1></body></html>"
    good = ('<html lang="en"><head><link rel="icon" href="/f.ico"></head><body><a href="tel:+971500000000">Call</a>'
            '<p>Address: 12 Main Street</p><a href="/privacy">Privacy</a><a href="/terms">Terms</a>'
            '<section>Testimonials: 5 stars</section><a href="/about">About us</a><a href="https://facebook.com/x">fb</a>'
            '<button>Book now</button><form></form><a href="https://wa.me/9715">WhatsApp</a><a href="mailto:a@b.com">mail</a>'
            '<p>Pricing from $49</p><script src="https://www.googletagmanager.com/gtag.js"></script></body></html>')
    bad = detect_leaks(bare, {}, is_https=False, ssl_valid=False, load_ms=5000, mobile_viewport=False)
    ok = detect_leaks(good, {}, is_https=True, ssl_valid=True, load_ms=800, mobile_viewport=True)
    assert bad["score"] < ok["score"] and bad["high_severity"] >= 3 and ok["leak_count"] <= 2


# ── [6] Tracking Pixel Engine ──
def test_tracking_instrumentation():
    tok = tracking.new_token()
    html = tracking.instrument_html('<p>See <a href="https://example.com/offer">offer</a></p>', tok)
    assert tracking.pixel_url(tok) in html
    assert "https://example.com/offer" not in html.split('href="')[1].split('"')[0] or "/track/c/" in html


# ── [8] Builder ──
def test_renderer_and_templates():
    assert len([t for t in TEMPLATES.values() if t["kind"] == "page"]) >= 8
    t = next(iter(TEMPLATES.values()))
    html = render_page(t["blocks"], t["theme"], title="Demo")
    assert html.startswith("<!DOCTYPE html>") and "Demo" in html
    assert "<script>alert" not in render_page([{"type": "text", "props": {"heading": "x", "body": "<script>alert(1)</script>"}}], {})
    assert "<table" in render_email([{"type": "text", "props": {"heading": "Hi", "body": "<p>Body</p>"}}], {})
