"""
Trust & Conversion Leak Detector  (Minahil Fatima's module in the OrbiScout proposal)
+ Search-engine indexing checks (SEO & Responsiveness Analysis).

A "leak" is anything on a prospect's site that makes visitors distrust it or leave without
contacting the business. Each leak has a category (trust | conversion), a severity, the
business impact in plain words and the fix - ready to drop into an outreach email.
"""
import asyncio
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx

SEVERITY_POINTS = {"high": 15, "medium": 8, "low": 4}


def _has(html: str, pattern: str) -> bool:
    return bool(re.search(pattern, html or "", re.I | re.S))


def _visible_text(html: str) -> str:
    h = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html or "", flags=re.I | re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))


def detect_leaks(html: str, headers: Dict[str, str], *, is_https: bool, ssl_valid: bool, load_ms: int,
                 mobile_viewport: bool, broken_links: int = 0, mixed_content: int = 0) -> Dict[str, Any]:
    text = _visible_text(html)
    year = datetime.utcnow().year
    leaks: List[Dict[str, str]] = []

    def leak(cat, sev, title, impact, fix):
        leaks.append({"category": cat, "severity": sev, "title": title, "impact": impact, "fix": fix})

    # â”€â”€ Trust signals â”€â”€
    if not is_https or not ssl_valid:
        leak("trust", "high", "Browser shows 'Not secure'", "Visitors see a security warning and leave before reading anything.",
             "Install a free SSL certificate and redirect all traffic to https://")
    if mixed_content:
        leak("trust", "medium", f"{mixed_content} insecure (http://) resources on an https page", "Padlock breaks; some browsers block images/scripts.",
             "Serve every image, script and stylesheet over https")
    if not _has(html, r'href=["\']tel:') and not re.search(r"\+?\d[\d\s().-]{8,}\d", text):
        leak("trust", "high", "No phone number visible", "Local customers want to call; no number makes the business look unreachable.",
             "Show a click-to-call phone number in the header and footer")
    if not _has(html, r"(street|road|rd\.|avenue|ave\.|building|floor|suite|p\.?o\.? box|\b\d{5}\b|address)"):
        leak("trust", "medium", "No physical address", "An address proves the business is real and helps local SEO.",
             "Add the full address (and a map) to the contact section/footer")
    if not _has(html, r"(privacy|datenschutz|privacy-policy)"):
        leak("trust", "medium", "No privacy policy", "Forms without a privacy policy reduce trust and can break GDPR/PDPL rules.",
             "Publish a privacy policy page and link it in the footer")
    if not _has(html, r"(terms|conditions)"):
        leak("trust", "low", "No terms & conditions page", "Missing legal pages look unprofessional to business buyers.",
             "Add a terms & conditions page")
    if not _has(html, r"(testimonial|review|rated|stars?|â˜…|trustpilot|google reviews|what (our )?(clients|customers) say)"):
        leak("trust", "high", "No reviews or testimonials", "Social proof is the #1 trust factor; without it visitors pick a competitor.",
             "Add 3-5 real testimonials or embed Google reviews")
    if not _has(html, r"(about[- ]us|/about|our story|who we are|our team)"):
        leak("trust", "low", "No 'About us' information", "People buy from people; an anonymous site converts worse.",
             "Add an About section with the team / story")
    years = [int(y) for y in re.findall(r"(?:Â©|&copy;|copyright)\s*(?:\d{4}\s*[-â€“]\s*)?(\d{4})", html or "", re.I)]
    if years and max(years) < year - 1:
        leak("trust", "medium", f"Copyright says {max(years)}", "An old year signals the business may be closed or the site abandoned.",
             "Update the footer year (or make it automatic)")
    if not _has(html, r'rel=["\'](shortcut )?icon'):
        leak("trust", "low", "No favicon", "The browser tab shows a blank icon, which looks unfinished.", "Add a favicon")
    if broken_links:
        leak("trust", "medium", f"{broken_links} broken link(s) on the homepage", "Dead links frustrate visitors and hurt SEO.",
             "Fix or remove links that return 404")
    if not _has(html, r"(facebook\.com|instagram\.com|linkedin\.com|twitter\.com|x\.com/|tiktok\.com|youtube\.com)"):
        leak("trust", "low", "No social media links", "Visitors check social pages to confirm a business is active.",
             "Link active social profiles in the footer")

    # â”€â”€ Conversion leaks â”€â”€
    cta = _has(html, r"<(a|button)[^>]*>[^<]{0,40}(contact|call|book|get (a )?(quote|started)|request|order|buy|schedule|enquire|inquire|appointment|sign up|whatsapp)[^<]{0,40}</(a|button)>")
    if not cta:
        leak("conversion", "high", "No clear call-to-action", "Visitors don't know what to do next, so they leave.",
             "Add one obvious button above the fold, e.g. 'Book a free consultation'")
    if not _has(html, r"<form\b"):
        leak("conversion", "medium", "No contact / enquiry form", "Many visitors won't call; without a form those leads are lost.",
             "Add a short 3-field enquiry form")
    if not _has(html, r"(wa\.me/|api\.whatsapp\.com|whatsapp|tawk\.to|intercom|crisp\.chat|livechat|tidio|zendesk|drift\.com)"):
        leak("conversion", "medium", "No WhatsApp or live chat", "Mobile visitors expect instant chat; it can double enquiries.",
             "Add a floating WhatsApp / chat button")
    if not _has(html, r'href=["\']mailto:'):
        leak("conversion", "low", "No clickable email", "Visitors who prefer email have to copy-paste.", "Add a mailto: link")
    if not mobile_viewport:
        leak("conversion", "high", "Not mobile-friendly (no viewport tag)", "Over 60% of visitors are on phones; the page is tiny and hard to use.",
             "Add a responsive viewport tag and a mobile layout")
    if load_ms and load_ms > 3000:
        leak("conversion", "high", f"Slow page ({load_ms/1000:.1f}s)", "53% of mobile visitors leave if a page takes over 3 seconds.",
             "Compress images, enable caching/CDN, remove unused scripts")
    elif load_ms and load_ms > 2000:
        leak("conversion", "medium", f"Page could be faster ({load_ms/1000:.1f}s)", "Every extra second reduces conversions by ~7%.",
             "Optimise images and enable compression")
    if not _has(html, r"(price|pricing|packages|plans|from \$|aed|pkr|usd|Â£|â‚¬)"):
        leak("conversion", "low", "No pricing information", "Visitors who can't see a starting price often won't enquire.",
             "Show starting prices or packages")
    if not _has(html, r"(googletagmanager|google-analytics|gtag\(|fbq\(|clarity\.ms|hotjar|plausible)"):
        leak("conversion", "low", "No analytics / tracking", "The business can't measure where leads come from.",
             "Install Google Analytics 4 or a privacy-friendly alternative")

    penalty = sum(SEVERITY_POINTS[l["severity"]] for l in leaks)
    trust_pen = sum(SEVERITY_POINTS[l["severity"]] for l in leaks if l["category"] == "trust")
    conv_pen = penalty - trust_pen
    return {
        "score": max(0, 100 - penalty),
        "trust_score": max(0, 100 - trust_pen * 1.4),
        "conversion_score": max(0, 100 - conv_pen * 1.4),
        "leak_count": len(leaks),
        "high_severity": sum(1 for l in leaks if l["severity"] == "high"),
        "leaks": sorted(leaks, key=lambda l: -SEVERITY_POINTS[l["severity"]]),
    }


async def count_broken_links(html: str, base_url: str, limit: int = 15) -> int:
    links = []
    for href in re.findall(r'<a[^>]+href=["\']([^"\'#]+)["\']', html or "", re.I):
        if href.startswith(("mailto:", "tel:", "javascript:", "whatsapp:")):
            continue
        full = urljoin(base_url, href)
        if urlparse(full).netloc == urlparse(base_url).netloc and full not in links:
            links.append(full)
    links = links[:limit]
    if not links:
        return 0

    async with httpx.AsyncClient(timeout=6, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (OrbiScout audit)"}) as c:
        async def check(u):
            try:
                r = await c.head(u)
                if r.status_code in (405, 403):
                    r = await c.get(u)
                return r.status_code >= 400
            except Exception:
                return True
        results = await asyncio.gather(*[check(u) for u in links])
    return sum(1 for r in results if r)


async def indexing_checks(html: str, headers: Dict[str, str], final_url: str) -> Dict[str, Any]:
    """Search-engine indexing configuration: robots.txt, sitemap, noindex, canonical, metadata, structured data."""
    origin = f"{urlparse(final_url).scheme}://{urlparse(final_url).netloc}"
    checks: List[Dict[str, Any]] = []

    def add(name, ok, weight, tip, detail=None):
        checks.append({"check": name, "passed": bool(ok), "weight": weight, "detail": detail, "tip": None if ok else tip})

    robots_txt, sitemap_ok, sitemap_url = None, False, None
    async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (OrbiScout audit)"}) as c:
        try:
            r = await c.get(origin + "/robots.txt")
            robots_txt = r.text if r.status_code == 200 and "html" not in r.headers.get("content-type", "") else None
        except Exception:
            pass
        m = re.search(r"sitemap:\s*(\S+)", robots_txt or "", re.I)
        sitemap_url = m.group(1) if m else origin + "/sitemap.xml"
        try:
            r = await c.get(sitemap_url)
            sitemap_ok = r.status_code == 200 and ("<urlset" in r.text or "<sitemapindex" in r.text)
        except Exception:
            pass
    blocks_all = bool(robots_txt and re.search(r"user-agent:\s*\*\s*(?:\n[^\n]*)*?\ndisallow:\s*/\s*(\n|$)", robots_txt, re.I))
    meta_robots = re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']+)', html, re.I)
    x_robots = {k.lower(): v for k, v in headers.items()}.get("x-robots-tag", "")
    noindex = "noindex" in ((meta_robots.group(1) if meta_robots else "") + x_robots).lower()
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title_t = re.sub(r"\s+", " ", title.group(1)).strip() if title else ""
    desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', html, re.I)
    desc_t = desc.group(1).strip() if desc else ""
    h1s = len(re.findall(r"<h1\b", html, re.I))

    add("Page is indexable (no noindex)", not noindex, 20, "Remove 'noindex' from the meta robots tag / X-Robots-Tag header",
        detail=(meta_robots.group(1) if meta_robots else x_robots) or "index")
    add("robots.txt present", robots_txt is not None, 8, "Add a robots.txt file")
    add("robots.txt does not block the whole site", not blocks_all, 15, "robots.txt has 'Disallow: /' - Google can't crawl the site")
    add("XML sitemap found", sitemap_ok, 10, "Create sitemap.xml and submit it in Google Search Console", detail=sitemap_url)
    add("Canonical URL", _has(html, r'rel=["\']canonical'), 7, "Add <link rel=\"canonical\"> to avoid duplicate-content issues")
    add("Title tag (10-65 chars)", 10 <= len(title_t) <= 65, 10, "Write a 50-60 character title with the main keyword + city", detail=title_t[:80])
    add("Meta description (50-160 chars)", 50 <= len(desc_t) <= 160, 8, "Write a 120-155 character meta description", detail=desc_t[:160])
    add("Exactly one H1", h1s == 1, 6, "Use one H1 heading that says what the business does", detail=f"{h1s} found")
    add("HTML lang attribute", _has(html, r"<html[^>]+lang="), 4, "Add lang=\"en\" (or the right language) to <html>")
    add("Structured data (schema.org)", _has(html, r"application/ld\+json|itemtype=[\"']https?://schema\.org"), 6, "Add LocalBusiness JSON-LD so Google shows rich results")
    add("Open Graph tags (social previews)", _has(html, r'property=["\']og:(title|image)'), 6, "Add og:title / og:image for nice link previews on WhatsApp & social")
    total = sum(c["weight"] for c in checks)
    score = round(100 * sum(c["weight"] for c in checks if c["passed"]) / total, 1)
    return {"score": score, "indexable": not noindex and not blocks_all, "checks": checks,
            "tips": [c["tip"] for c in checks if c["tip"]]}

