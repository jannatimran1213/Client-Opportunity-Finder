"""
Module 4 - Advanced Audit.

  Speed & Security Audit ...... measure_speed() + security checks from SecurityManager
  Tech Stack Detection ........ detect_tech_stack()   (fingerprints in HTML, headers, cookies, scripts)
  Mobile Friendliness Score ... mobile_friendliness() (+ Google PageSpeed mobile score when PAGESPEED_API_KEY set)
  Competitor Benchmarking ..... benchmark()            (side-by-side ranking + gap insights)
"""
import asyncio
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings
from app.core.security import security_manager

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"

# name -> (category, list of regexes checked against html, header patterns "header:regex", cookie names)
TECH_SIGNATURES: Dict[str, Dict[str, Any]] = {
    "WordPress": {"cat": "CMS", "html": [r"wp-content/", r"wp-includes/", r'name="generator" content="WordPress']},
    "WooCommerce": {"cat": "E-commerce", "html": [r"woocommerce", r"wc-ajax"]},
    "Shopify": {"cat": "E-commerce", "html": [r"cdn\.shopify\.com", r"Shopify\.theme"], "headers": [r"x-shopify-stage:"]},
    "Wix": {"cat": "Website builder", "html": [r"static\.wixstatic\.com", r"wix-code"], "headers": [r"x-wix-request-id:"]},
    "Squarespace": {"cat": "Website builder", "html": [r"static1\.squarespace\.com", r"Squarespace"]},
    "Webflow": {"cat": "Website builder", "html": [r"webflow\.js", r'data-wf-page', r"assets\.website-files\.com"]},
    "Joomla": {"cat": "CMS", "html": [r'content="Joomla', r"/media/jui/"]},
    "Drupal": {"cat": "CMS", "html": [r"Drupal\.settings", r"/sites/default/files", r'content="Drupal'], "headers": [r"x-drupal-cache:"]},
    "Magento": {"cat": "E-commerce", "html": [r"Mage\.Cookies", r"/static/version\d+/", r"magento"]},
    "Ghost": {"cat": "CMS", "html": [r'content="Ghost']},
    "Next.js": {"cat": "JS framework", "html": [r"/_next/static", r"__NEXT_DATA__"], "headers": [r"x-powered-by:\s*next\.js"]},
    "Nuxt.js": {"cat": "JS framework", "html": [r"/_nuxt/", r"__NUXT__"]},
    "React": {"cat": "JS framework", "html": [r"react(\.production)?\.min\.js", r"data-reactroot", r"__REACT_DEVTOOLS"]},
    "Vue.js": {"cat": "JS framework", "html": [r"vue(\.runtime)?(\.global)?(\.prod)?\.js", r"data-v-[0-9a-f]{8}"]},
    "Angular": {"cat": "JS framework", "html": [r"ng-version=", r"angular(\.min)?\.js"]},
    "Gatsby": {"cat": "JS framework", "html": [r"___gatsby"]},
    "jQuery": {"cat": "JS library", "html": [r"jquery[.-](\d|min)", r"jquery\.js"]},
    "Bootstrap": {"cat": "UI framework", "html": [r"bootstrap(\.min)?\.(css|js)"]},
    "Tailwind CSS": {"cat": "UI framework", "html": [r"tailwind", r'class="[^"]*\b(?:px|py|mt|mb)-\d+[^"]*\b(?:flex|grid)\b']},
    "Elementor": {"cat": "Page builder", "html": [r"elementor"]},
    "Divi": {"cat": "Page builder", "html": [r"et_pb_", r"Divi"]},
    "Google Analytics": {"cat": "Analytics", "html": [r"google-analytics\.com/analytics\.js", r"gtag\(", r"googletagmanager\.com/gtag/js"]},
    "Google Tag Manager": {"cat": "Tag manager", "html": [r"googletagmanager\.com/gtm\.js", r"GTM-[A-Z0-9]+"]},
    "Meta Pixel": {"cat": "Marketing", "html": [r"connect\.facebook\.net/.+/fbevents\.js", r"fbq\("]},
    "Hotjar": {"cat": "Analytics", "html": [r"static\.hotjar\.com", r"hjSettings"]},
    "HubSpot": {"cat": "Marketing", "html": [r"js\.hs-scripts\.com", r"hs-analytics"]},
    "Mailchimp": {"cat": "Marketing", "html": [r"chimpstatic\.com", r"list-manage\.com"]},
    "Intercom": {"cat": "Live chat", "html": [r"widget\.intercom\.io", r"intercomSettings"]},
    "Tawk.to": {"cat": "Live chat", "html": [r"embed\.tawk\.to"]},
    "WhatsApp Chat": {"cat": "Live chat", "html": [r"wa\.me/", r"api\.whatsapp\.com"]},
    "Stripe": {"cat": "Payments", "html": [r"js\.stripe\.com"]},
    "PayPal": {"cat": "Payments", "html": [r"paypal\.com/sdk", r"paypalobjects"]},
    "reCAPTCHA": {"cat": "Security", "html": [r"google\.com/recaptcha", r"g-recaptcha"]},
    "Cloudflare": {"cat": "CDN", "headers": [r"server:\s*cloudflare", r"cf-ray:"]},
    "Vercel": {"cat": "Hosting", "headers": [r"server:\s*vercel", r"x-vercel-id:"]},
    "Netlify": {"cat": "Hosting", "headers": [r"server:\s*netlify", r"x-nf-request-id:"]},
    "Amazon CloudFront": {"cat": "CDN", "headers": [r"x-amz-cf-id:", r"via:.*cloudfront"]},
    "Nginx": {"cat": "Web server", "headers": [r"server:\s*nginx"]},
    "Apache": {"cat": "Web server", "headers": [r"server:\s*apache"]},
    "LiteSpeed": {"cat": "Web server", "headers": [r"server:\s*litespeed"]},
    "Microsoft IIS": {"cat": "Web server", "headers": [r"server:\s*microsoft-iis"]},
    "PHP": {"cat": "Language", "headers": [r"x-powered-by:\s*php"], "cookies": ["PHPSESSID"]},
    "ASP.NET": {"cat": "Language", "headers": [r"x-aspnet-version:", r"x-powered-by:\s*asp\.net"], "cookies": ["ASP.NET_SessionId"]},
    "Font Awesome": {"cat": "Font", "html": [r"font-?awesome"]},
    "Google Fonts": {"cat": "Font", "html": [r"fonts\.googleapis\.com"]},
}


async def _fetch(url: str, ua: str = UA, timeout: float = 15.0) -> Dict[str, Any]:
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": ua}) as client:
        async with client.stream("GET", url) as resp:
            ttfb = time.perf_counter() - start
            body = b""
            async for chunk in resp.aiter_bytes():
                body += chunk
                if len(body) > 6_000_000:
                    break
            total = time.perf_counter() - start
            return {"status": resp.status_code, "final_url": str(resp.url), "headers": dict(resp.headers),
                    "cookies": list(resp.cookies.keys()), "html": body.decode(resp.encoding or "utf-8", errors="ignore"),
                    "bytes": len(body), "ttfb": ttfb, "total": total,
                    "redirects": [str(r.url) for r in resp.history]}


def detect_tech_stack(html: str, headers: Dict[str, str], cookies: List[str]) -> List[Dict[str, str]]:
    header_blob = "\n".join(f"{k.lower()}: {v.lower()}" for k, v in (headers or {}).items())
    found = []
    for name, sig in TECH_SIGNATURES.items():
        hit = None
        for pat in sig.get("html", []):
            if re.search(pat, html or "", re.I):
                hit = "html"
                break
        if not hit:
            for pat in sig.get("headers", []):
                if re.search(pat, header_blob, re.I):
                    hit = "headers"
                    break
        if not hit and any(c in (cookies or []) for c in sig.get("cookies", [])):
            hit = "cookies"
        if hit:
            found.append({"name": name, "category": sig["cat"], "evidence": hit})
    gen = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', html or "", re.I)
    if gen and not any(gen.group(1).lower().startswith(f["name"].lower()) for f in found):
        found.append({"name": gen.group(1)[:60], "category": "Generator", "evidence": "meta"})
    return found


# Latest-major baselines used to flag outdated software (a sales opportunity for web developers)
VERSION_RULES = {
    "WordPress": (r'content=["\']WordPress\s*([\d.]+)|ver=([\d.]+)[^"\']*wp-(?:includes|emoji)', (6, 4)),
    "jQuery": (r"jquery[.-]?([0-9]+\.[0-9]+(?:\.[0-9]+)?)(?:\.min)?\.js|jquery\.js\?ver=([\d.]+)", (3, 5)),
    "Bootstrap": (r"bootstrap(?:@|/|\.min\.css\?ver=|-)([0-9]+\.[0-9]+(?:\.[0-9]+)?)", (5, 0)),
    "PHP": (r"php/([\d.]+)", (8, 1)),
    "Nginx": (r"nginx/([\d.]+)", (1, 22)),
    "Apache": (r"apache/([\d.]+)", (2, 4)),
}


def add_versions(tech: List[Dict[str, Any]], html: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    blob = (html or "")[:400000] + "\n" + "\n".join(f"{k}: {v}" for k, v in (headers or {}).items())
    for t in tech:
        rule = VERSION_RULES.get(t["name"])
        if not rule:
            continue
        m = re.search(rule[0], blob, re.I)
        ver = next((g for g in (m.groups() if m else []) if g), None)
        if ver:
            t["version"] = ver
            try:
                parts = tuple(int(x) for x in ver.split(".")[:2])
                t["outdated"] = parts < rule[1]
                if t["outdated"]:
                    t["note"] = f"{t['name']} {ver} is outdated (current major >= {'.'.join(map(str, rule[1]))}) - security & speed risk"
            except ValueError:
                pass
    return tech


def _resource_counts(html: str) -> Dict[str, int]:
    return {
        "scripts": len(re.findall(r"<script[^>]+src=", html, re.I)),
        "stylesheets": len(re.findall(r'<link[^>]+rel=["\']stylesheet', html, re.I)),
        "images": len(re.findall(r"<img\b", html, re.I)),
        "lazy_images": len(re.findall(r'<img[^>]+loading=["\']lazy', html, re.I)),
        "inline_scripts": len(re.findall(r"<script(?![^>]*src=)[^>]*>", html, re.I)),
        "iframes": len(re.findall(r"<iframe\b", html, re.I)),
    }


def speed_score(ttfb: float, total: float, size_bytes: int, res: Dict[str, int], compressed: bool, cached: bool) -> float:
    s = 100.0
    s -= min(30, max(0, (ttfb - 0.2) * 25))           # server response
    s -= min(25, max(0, (total - 1.0) * 8))           # full HTML download
    s -= min(20, max(0, (size_bytes / 1024 - 300) / 50))  # HTML weight above 300 KB
    s -= min(10, max(0, res["scripts"] - 15) * 0.7)  # too many scripts
    s -= min(5, max(0, res["stylesheets"] - 6))
    s -= 0 if compressed else 6
    s -= 0 if cached else 4
    if res["images"] > 8 and res["lazy_images"] == 0:
        s -= 4
    return round(max(0, min(100, s)), 1)


def mobile_friendliness(html: str, mobile_html: Optional[str] = None) -> Dict[str, Any]:
    h = html or ""
    checks = []

    def add(name, ok, weight, tip):
        checks.append({"check": name, "passed": bool(ok), "weight": weight, "tip": None if ok else tip})

    viewport = re.search(r'<meta[^>]+name=["\']viewport["\'][^>]+content=["\']([^"\']+)', h, re.I)
    vp = viewport.group(1).lower() if viewport else ""
    add("Viewport meta tag", bool(viewport), 25, "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">")
    add("Responsive width (device-width)", "device-width" in vp, 10, "Viewport should use width=device-width")
    add("Zoom not disabled", not ("user-scalable=no" in vp or "maximum-scale=1" in vp.replace(" ", "")), 5,
        "Allow pinch-zoom (remove user-scalable=no) for accessibility")
    media_q = len(re.findall(r"@media[^{]*(max|min)-width", h, re.I))
    frameworks = bool(re.search(r"bootstrap|tailwind|foundation|bulma|elementor|wix|squarespace|shopify|webflow", h, re.I))
    add("Responsive CSS (media queries / framework)", media_q > 0 or frameworks or 'rel="stylesheet"' in h, 15,
        "Use CSS media queries or a responsive framework")
    fixed = re.findall(r'width\s*[:=]\s*["\']?(\d{4,})px', h, re.I)
    add("No fixed-width layouts > 1000px", not any(int(x) > 1000 for x in fixed), 10, "Replace fixed pixel widths with % / max-width")
    small_fonts = re.findall(r"font-size\s*:\s*([0-9.]+)px", h, re.I)
    tiny = [f for f in small_fonts if float(f) < 12]
    add("Readable font sizes (>= 12px)", len(tiny) <= 2, 10, "Use at least 14-16px body text on mobile")
    add("Tap-to-call / mobile contact link", bool(re.search(r'href=["\'](tel:|https://wa\.me|whatsapp:)', h, re.I)), 10,
        "Add a tap-to-call or WhatsApp button for mobile visitors")
    add("No Flash / legacy plugins", not re.search(r"\.swf|<object|<embed", h, re.I), 5, "Remove Flash/embed plugins")
    imgs = len(re.findall(r"<img\b", h, re.I))
    responsive_imgs = len(re.findall(r"<img[^>]+(srcset=|sizes=)", h, re.I)) + len(re.findall(r"<picture", h, re.I))
    add("Responsive images (srcset / picture)", imgs == 0 or responsive_imgs > 0, 10, "Serve responsive images with srcset")
    if mobile_html is not None:
        add("Mobile version loads", len(mobile_html) > 500, 0, "Mobile user-agent got an empty page")
    total = sum(c["weight"] for c in checks) or 1
    score = round(100 * sum(c["weight"] for c in checks if c["passed"]) / total, 1)
    return {"score": score, "checks": checks, "tips": [c["tip"] for c in checks if c["tip"]]}


async def pagespeed_mobile(url: str) -> Optional[Dict[str, Any]]:
    if not settings.PAGESPEED_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                            params={"url": url, "strategy": "mobile", "key": settings.PAGESPEED_API_KEY})
        data = r.json()
        lh = data.get("lighthouseResult", {})
        perf = lh.get("categories", {}).get("performance", {}).get("score")
        audits = lh.get("audits", {})
        return {"performance": round(perf * 100) if perf is not None else None,
                "lcp": audits.get("largest-contentful-paint", {}).get("displayValue"),
                "cls": audits.get("cumulative-layout-shift", {}).get("displayValue"),
                "tbt": audits.get("total-blocking-time", {}).get("displayValue")}
    except Exception:
        return None


async def run_advanced_audit(url: str) -> Dict[str, Any]:
    url = security_manager.normalize_url(url)
    host = urlparse(url).netloc.split(":")[0]
    loop = asyncio.get_event_loop()

    fetch_task = asyncio.create_task(_fetch(url))
    mobile_task = asyncio.create_task(_fetch(url, MOBILE_UA))
    ssl_task = loop.run_in_executor(None, security_manager.inspect_ssl, host)
    http_task = asyncio.create_task(_fetch("http://" + host + "/", timeout=8))
    psi_task = asyncio.create_task(pagespeed_mobile(url))

    try:
        page = await fetch_task
    except Exception as e:
        for t in (mobile_task, http_task, psi_task):
            t.cancel()
        return {"url": url, "error": f"Could not load site: {e}", "overall_score": 0}
    mobile, http_page, psi = await asyncio.gather(mobile_task, http_task, psi_task, return_exceptions=True)
    ssl_info = await ssl_task
    html = page["html"]
    headers = page["headers"]

    # â”€â”€ Speed â”€â”€
    res = _resource_counts(html)
    compressed = (headers.get("content-encoding") or "").lower() in ("gzip", "br", "deflate", "zstd")
    cached = bool(headers.get("cache-control") or headers.get("etag") or headers.get("last-modified"))
    s_score = speed_score(page["ttfb"], page["total"], page["bytes"], res, compressed, cached)
    speed = {"score": s_score, "ttfb_ms": round(page["ttfb"] * 1000), "load_ms": round(page["total"] * 1000),
             "html_kb": round(page["bytes"] / 1024, 1), "compression": headers.get("content-encoding") or "none",
             "caching": cached, "resources": res, "redirects": len(page["redirects"]), "status_code": page["status"],
             "tips": [t for t, bad in [
                 ("Enable gzip/brotli compression", not compressed),
                 ("Add Cache-Control / ETag headers", not cached),
                 ("Reduce server response time (TTFB > 600 ms)", page["ttfb"] > 0.6),
                 ("Reduce number of script files", res["scripts"] > 15),
                 ("Lazy-load images below the fold", res["images"] > 8 and res["lazy_images"] == 0),
                 ("Page HTML is heavy (> 300 KB)", page["bytes"] > 300 * 1024),
             ] if bad]}

    # â”€â”€ Security (SecurityManager) â”€â”€
    is_https = page["final_url"].startswith("https://")
    redirects_to_https = isinstance(http_page, dict) and http_page.get("final_url", "").startswith("https://")
    headers_audit = security_manager.audit_security_headers(headers)
    mixed = len(re.findall(r'(?:src|href)=["\']http://', html, re.I)) if is_https else 0
    sec_score = security_manager.security_score(is_https=is_https, redirects_to_https=redirects_to_https,
                                                ssl_info=ssl_info, headers_audit=headers_audit, mixed_content=mixed)
    security = {"score": sec_score, "https": is_https, "http_redirects_to_https": redirects_to_https,
                "ssl": ssl_info, "headers": headers_audit, "mixed_content_links": mixed,
                "tips": headers_audit["recommendations"] + ([] if is_https else ["Serve the site over HTTPS"]) +
                        ([] if redirects_to_https else ["Redirect http:// to https://"]) +
                        (["Renew the SSL certificate soon"] if (ssl_info.get("days_left") or 99) < 21 else [])}

    # â”€â”€ Tech stack (with versions / outdated software) â”€â”€
    tech = add_versions(detect_tech_stack(html, headers, page["cookies"]), html, headers)

    # â”€â”€ Mobile â”€â”€
    mob = mobile_friendliness(html, mobile.get("html") if isinstance(mobile, dict) else None)
    if isinstance(psi, dict) and psi.get("performance") is not None:
        mob["pagespeed_mobile"] = psi
        mob["score"] = round(0.6 * mob["score"] + 0.4 * psi["performance"], 1)

    # â”€â”€ SEO indexing checks + Trust & Conversion Leak Detector â”€â”€
    from app.services.website_audit.trust_leaks import count_broken_links, detect_leaks, indexing_checks
    seo, broken = await asyncio.gather(indexing_checks(html, headers, page["final_url"]),
                                       count_broken_links(html, page["final_url"]))
    viewport = any(c["check"] == "Viewport meta tag" and c["passed"] for c in mob["checks"])
    leaks = detect_leaks(html, headers, is_https=is_https, ssl_valid=bool(ssl_info.get("valid")),
                         load_ms=speed["load_ms"], mobile_viewport=viewport, broken_links=broken, mixed_content=mixed)

    overall = round(0.2 * s_score + 0.2 * sec_score + 0.2 * mob["score"] + 0.2 * seo["score"] + 0.2 * leaks["score"], 1)
    opportunities = [l["title"] for l in leaks["leaks"] if l["severity"] == "high"]
    opportunities += [t["note"] for t in tech if t.get("outdated")]
    if not seo["indexable"]:
        opportunities.insert(0, "Site is hidden from Google (noindex / robots.txt)")
    return {"url": url, "final_url": page["final_url"], "overall_score": overall, "speed": speed,
            "security": security, "tech_stack": tech, "mobile": mob, "seo": seo, "trust": leaks,
            "opportunities": opportunities[:8]}


async def benchmark(target_url: str, competitor_urls: List[str]) -> Dict[str, Any]:
    urls = [target_url] + [u for u in competitor_urls if u][:5]
    reports = await asyncio.gather(*[run_advanced_audit(u) for u in urls], return_exceptions=True)
    rows = []
    for u, r in zip(urls, reports):
        if isinstance(r, Exception) or r.get("error"):
            rows.append({"url": u, "error": str(r) if isinstance(r, Exception) else r.get("error"), "overall_score": 0,
                         "is_target": u == target_url})
            continue
        rows.append({"url": r["url"], "is_target": u == target_url, "overall_score": r["overall_score"],
                     "speed": r["speed"]["score"], "security": r["security"]["score"], "mobile": r["mobile"]["score"],
                     "seo": r["seo"]["score"], "trust": r["trust"]["score"], "load_ms": r["speed"]["load_ms"], "tech": [t["name"] for t in r["tech_stack"]]})
    ranking = sorted(rows, key=lambda x: x.get("overall_score") or 0, reverse=True)
    for i, r in enumerate(ranking, 1):
        r["rank"] = i
    target = next((r for r in rows if r["is_target"]), None)
    comps = [r for r in rows if not r["is_target"] and not r.get("error")]
    insights = []
    if target and comps and not target.get("error"):
        for metric, label in (("speed", "speed"), ("security", "security"), ("mobile", "mobile friendliness"),
                              ("seo", "search indexing"), ("trust", "trust & conversion")):
            avg = sum(c[metric] for c in comps) / len(comps)
            best = max(comps, key=lambda c: c[metric])
            diff = round(target[metric] - avg, 1)
            if diff < 0:
                insights.append(f"{label.capitalize()} is {abs(diff)} points below the competitor average ({round(avg)}). "
                                f"Best: {urlparse(best['url']).netloc} at {best[metric]}.")
            elif diff < 1:
                insights.append(f"{label.capitalize()} is level with the competitor average ({round(avg)}).")
            else:
                insights.append(f"{label.capitalize()} beats the competitor average by {diff} points.")
        comp_tech = {t for c in comps for t in c["tech"]}
        missing = sorted(comp_tech - set(target["tech"]))
        interesting = [t for t in missing if t in ("Google Analytics", "Meta Pixel", "WhatsApp Chat", "Google Tag Manager",
                                                   "HubSpot", "Intercom", "Tawk.to", "Stripe", "reCAPTCHA", "Cloudflare")]
        if interesting:
            insights.append("Competitors use tools you don't: " + ", ".join(interesting))
        insights.append(f"Overall rank: #{target['rank']} of {len(rows)}")
    return {"target_url": target_url, "ranking": ranking, "insights": insights}

