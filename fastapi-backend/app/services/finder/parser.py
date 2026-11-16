"""
Module 2 - Data Parser & Extraction.

Turns raw HTML/text into structured lead data: emails, phones, WhatsApp numbers, social
profiles, schema.org (JSON-LD) business details, page title/description and contact pages.
Reuses the proprietary scraper's extractors (app/services/scraping/website_scraper.py).
"""
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from app.services.scraping.website_scraper import (
    ScrapedContacts, _extract_emails, _extract_phones, _extract_social, _is_valid_email, _pick_best_email, _pick_best_phone,
)

WHATSAPP_RE = re.compile(r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=|whatsapp://send\?phone=)(\+?\d{7,15})", re.I)
CONTACT_HINTS = ("contact", "about", "team", "reach", "location", "impressum", "kontakt")


def _jsonld_blocks(html: str) -> List[dict]:
    blocks = []
    for raw in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.I | re.S):
        try:
            data = json.loads(raw.strip())
        except Exception:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        blocks.extend(i for i in items if isinstance(i, dict))
    return blocks


def _business_from_jsonld(blocks: List[dict]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for b in blocks:
        t = b.get("@type")
        types = t if isinstance(t, list) else [t]
        if not any(isinstance(x, str) and (x.endswith("Business") or x in (
            "Organization", "LocalBusiness", "Restaurant", "Dentist", "Store", "Hotel", "MedicalClinic",
            "LegalService", "RealEstateAgent", "AutoRepair", "HealthClub", "BeautySalon", "Corporation")) for x in types):
            continue
        out.setdefault("name", b.get("name"))
        out.setdefault("type", types[0])
        out.setdefault("telephone", b.get("telephone"))
        out.setdefault("email", (b.get("email") or "").replace("mailto:", "") or None)
        addr = b.get("address")
        if isinstance(addr, dict):
            out.setdefault("address", ", ".join(str(addr.get(k)) for k in (
                "streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry") if addr.get(k)))
            out.setdefault("city", addr.get("addressLocality"))
        elif isinstance(addr, str):
            out.setdefault("address", addr)
        if b.get("openingHours"):
            out.setdefault("opening_hours", b.get("openingHours"))
        if b.get("priceRange"):
            out.setdefault("price_range", b.get("priceRange"))
        rating = b.get("aggregateRating")
        if isinstance(rating, dict):
            out.setdefault("rating", rating.get("ratingValue"))
            out.setdefault("review_count", rating.get("reviewCount"))
        same = b.get("sameAs")
        if same:
            out.setdefault("same_as", same if isinstance(same, list) else [same])
    return {k: v for k, v in out.items() if v}


def _meta(html: str, name: str) -> Optional[str]:
    m = re.search(rf'<meta[^>]+(?:name|property)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']*)', html, re.I)
    if not m:
        m = re.search(rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:name|property)=["\']{re.escape(name)}["\']', html, re.I)
    return m.group(1).strip() if m else None


def parse_content(content: str, base_url: Optional[str] = None) -> Dict[str, Any]:
    """Extract every contact signal we can find in an HTML page (or plain text)."""
    content = content or ""
    is_html = "<" in content and ">" in content
    contacts = ScrapedContacts()
    emails = sorted(e for e in _extract_emails(content) if _is_valid_email(e))
    phones = sorted(_extract_phones(content))
    _extract_social(content, contacts)
    domain = urlparse(base_url).netloc.replace("www.", "") if base_url else None

    title = None
    description = None
    contact_pages: List[str] = []
    jsonld: Dict[str, Any] = {}
    if is_html:
        m = re.search(r"<title[^>]*>(.*?)</title>", content, re.I | re.S)
        title = re.sub(r"\s+", " ", m.group(1)).strip() if m else None
        description = _meta(content, "description") or _meta(content, "og:description")
        jsonld = _business_from_jsonld(_jsonld_blocks(content))
        for href, text in re.findall(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', content, re.I | re.S):
            label = re.sub(r"<[^>]+>", "", text).lower()
            if any(h in href.lower() or h in label for h in CONTACT_HINTS):
                full = urljoin(base_url, href) if base_url else href
                if full not in contact_pages and full.startswith("http"):
                    contact_pages.append(full)

    whatsapp = sorted(set(WHATSAPP_RE.findall(content)))
    socials = {k: getattr(contacts, k) for k in ("facebook", "instagram", "twitter", "linkedin", "youtube", "tiktok") if getattr(contacts, k)}
    if jsonld.get("email") and jsonld["email"] not in emails:
        emails.insert(0, jsonld["email"])
    return {
        "emails": emails,
        "best_email": _pick_best_email(emails, domain) if emails else None,
        "phones": phones,
        "best_phone": jsonld.get("telephone") or (_pick_best_phone(phones) if phones else None),
        "whatsapp": whatsapp,
        "socials": socials,
        "title": title,
        "description": description,
        "business": jsonld,
        "contact_pages": contact_pages[:10],
    }

