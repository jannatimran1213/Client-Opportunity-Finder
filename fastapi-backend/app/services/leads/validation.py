"""
Module 3 - Validation Filter: email (syntax, disposable, role, MX), phone (E.164) and website reachability.
"""
import asyncio
import re
import socket
from typing import Any, Dict, Optional

import httpx

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
DISPOSABLE = {"mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com", "yopmail.com",
              "trashmail.com", "getnada.com", "sharklasers.com", "temp-mail.org", "dispostable.com", "fakeinbox.com"}
ROLE_PREFIXES = {"noreply", "no-reply", "donotreply", "postmaster", "abuse", "webmaster", "hostmaster"}
PLACEHOLDER = re.compile(r"(example\.(com|org)|yourdomain|domain\.com|email\.com|test@|user@)", re.I)

COUNTRY_CODES = {
    "pakistan": "92", "pk": "92", "uae": "971", "united arab emirates": "971", "ae": "971",
    "usa": "1", "us": "1", "united states": "1", "canada": "1", "uk": "44", "united kingdom": "44", "gb": "44",
    "india": "91", "saudi arabia": "966", "sa": "966", "qatar": "974", "oman": "968", "bahrain": "973",
    "kuwait": "965", "australia": "61", "germany": "49", "france": "33", "turkey": "90", "egypt": "20",
}


def _mx_lookup(domain: str) -> Optional[bool]:
    try:
        import dns.resolver  # dnspython
        try:
            answers = dns.resolver.resolve(domain, "MX", lifetime=4)
            return len(answers) > 0
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            try:
                socket.gethostbyname(domain)
                return True  # implicit MX (A record)
            except Exception:
                return False
        except Exception:
            return None
    except ImportError:
        try:
            socket.gethostbyname(domain)
            return True
        except Exception:
            return False


def validate_email(email: Optional[str], check_mx: bool = True) -> Dict[str, Any]:
    if not email:
        return {"status": "missing", "reason": "No email"}
    email = email.strip().lower()
    if not EMAIL_RE.match(email) or ".." in email:
        return {"status": "invalid", "reason": "Bad email format"}
    local, domain = email.split("@", 1)
    if PLACEHOLDER.search(email):
        return {"status": "invalid", "reason": "Placeholder address"}
    if domain in DISPOSABLE:
        return {"status": "invalid", "reason": "Disposable email domain"}
    if local in ROLE_PREFIXES:
        return {"status": "risky", "reason": "No-reply / system mailbox"}
    if check_mx:
        mx = _mx_lookup(domain)
        if mx is False:
            return {"status": "invalid", "reason": "Domain has no mail server (MX)"}
        if mx is None:
            return {"status": "unknown", "reason": "DNS lookup timed out"}
    if local in {"info", "contact", "hello", "sales", "office", "admin", "support"}:
        return {"status": "valid", "reason": "Valid (generic inbox)"}
    return {"status": "valid", "reason": "Valid format and mail server"}


def validate_phone(phone: Optional[str], country: Optional[str] = None) -> Dict[str, Any]:
    if not phone:
        return {"status": "missing", "e164": None, "reason": "No phone"}
    raw = phone.strip()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("00"):
        digits = digits[2:]
        raw = "+" + digits
    if raw.startswith("+"):
        e164 = "+" + digits
    else:
        cc = COUNTRY_CODES.get((country or "").strip().lower())
        local = digits[1:] if digits.startswith("0") else digits
        e164 = f"+{cc}{local}" if cc else ("+" + digits if len(digits) > 10 else None)
    n = len(re.sub(r"\D", "", e164 or digits))
    if n < 8 or n > 15 or len(set(digits)) == 1:
        return {"status": "invalid", "e164": None, "reason": "Wrong number of digits"}
    return {"status": "valid", "e164": e164, "reason": "Valid" if e164 else "Valid (country code unknown)"}


async def validate_website(url: Optional[str], timeout: float = 8.0) -> Dict[str, Any]:
    if not url:
        return {"status": "missing", "http_code": None}
    if not url.startswith("http"):
        url = "https://" + url
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True,
                                     headers={"User-Agent": "Mozilla/5.0 (LeadValidator)"}) as c:
            r = await c.get(url)
        return {"status": "reachable" if r.status_code < 400 else "unreachable", "http_code": r.status_code,
                "final_url": str(r.url)}
    except Exception as e:
        return {"status": "unreachable", "http_code": None, "error": str(e)[:120]}


async def validate_lead(lead: Dict[str, Any], check_website: bool = True, check_mx: bool = True) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()
    email_res = await loop.run_in_executor(None, validate_email, lead.get("email"), check_mx)
    phone_res = validate_phone(lead.get("phone"), lead.get("country"))
    web_res = await validate_website(lead.get("website")) if check_website else {"status": "skipped", "http_code": None}
    score = 0
    score += {"valid": 40, "risky": 20, "unknown": 15}.get(email_res["status"], 0)
    score += 30 if phone_res["status"] == "valid" else 0
    score += 30 if web_res["status"] == "reachable" else 0
    return {"email": email_res, "phone": phone_res, "website": web_res, "score": score}

