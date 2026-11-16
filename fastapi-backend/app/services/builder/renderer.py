"""
Module 8 - Drag-and-Drop Builder: block -> HTML renderer (pages and emails).

The visual editor (nextjs-frontend/app/builder/[id]/page.js) produces a list of blocks:
    [{"id": "...", "type": "hero", "props": {...}}, ...]
render_page() turns that into a standalone, responsive HTML document (used for live preview,
subdomain hosting and code export). All user text is escaped / sanitised by SecurityManager.
"""
from typing import Any, Dict, List

from app.core.security import security_manager as sm

DEFAULT_THEME = {"primary": "#6D5DF6", "background": "#ffffff", "text": "#1f2937", "muted": "#6b7280",
                 "surface": "#f8fafc", "font": "Inter", "radius": "14px"}

BLOCK_TYPES = {
    "hero": {"label": "Hero", "props": {"heading": "Your headline here", "subheading": "A short sentence about what you do.",
                                        "button_text": "Get started", "button_link": "#contact", "image": "", "align": "center"}},
    "text": {"label": "Text", "props": {"heading": "About us", "body": "<p>Tell visitors your story.</p>"}},
    "image": {"label": "Image", "props": {"src": "https://picsum.photos/seed/builder/1200/600", "alt": "", "caption": ""}},
    "features": {"label": "Features", "props": {"heading": "Why choose us", "items": [
        {"icon": "â˜…", "title": "Quality", "text": "Describe a benefit."},
        {"icon": "âš¡", "title": "Speed", "text": "Describe a benefit."},
        {"icon": "â™¥", "title": "Care", "text": "Describe a benefit."}]}},
    "gallery": {"label": "Gallery", "props": {"heading": "Gallery", "images": [
        "https://picsum.photos/seed/g1/600/400", "https://picsum.photos/seed/g2/600/400", "https://picsum.photos/seed/g3/600/400"]}},
    "testimonials": {"label": "Testimonials", "props": {"heading": "What clients say", "items": [
        {"quote": "Fantastic service, highly recommended.", "author": "Happy client"}]}},
    "pricing": {"label": "Pricing", "props": {"heading": "Pricing", "plans": [
        {"name": "Basic", "price": "$49", "features": ["Feature one", "Feature two"], "cta": "Choose"},
        {"name": "Pro", "price": "$99", "features": ["Everything in Basic", "Feature three"], "cta": "Choose"}]}},
    "cta": {"label": "Call to action", "props": {"heading": "Ready to start?", "text": "Book a free consultation today.",
                                                 "button_text": "Contact us", "button_link": "#contact"}},
    "contact": {"label": "Contact / Form", "props": {"heading": "Contact us", "email": "", "phone": "", "whatsapp": "",
                                                     "address": "", "show_form": True}},
    "map": {"label": "Map", "props": {"address": "Dubai, UAE"}},
    "video": {"label": "Video", "props": {"url": ""}},
    "button": {"label": "Button", "props": {"text": "Click here", "link": "#", "align": "center"}},
    "divider": {"label": "Divider", "props": {}},
    "spacer": {"label": "Spacer", "props": {"height": 40}},
    "footer": {"label": "Footer", "props": {"text": "Â© Your Business. All rights reserved."}},
}


def _e(v: Any) -> str:
    return sm.escape(v)


def _url(v: Any) -> str:
    v = str(v or "#")
    return _e(v) if (v.startswith(("http://", "https://", "#", "/", "mailto:", "tel:"))) else "#"


def _youtube_embed(url: str) -> str:
    import re
    m = re.search(r"(?:youtu\.be/|v=|embed/)([A-Za-z0-9_-]{6,})", url or "")
    return f"https://www.youtube.com/embed/{m.group(1)}" if m else ""


def render_block(block: Dict[str, Any], site_slug: str = "") -> str:
    t = block.get("type")
    p = {**BLOCK_TYPES.get(t, {}).get("props", {}), **(block.get("props") or {})}
    if t == "hero":
        bg = f"background-image:linear-gradient(rgba(0,0,0,.45),rgba(0,0,0,.45)),url('{_url(p['image'])}');color:#fff" if p.get("image") else ""
        return (f'<section class="hero align-{_e(p.get("align"))}" style="{bg}"><div class="wrap">'
                f'<h1>{_e(p["heading"])}</h1><p class="lead">{_e(p["subheading"])}</p>'
                + (f'<a class="btn" href="{_url(p["button_link"])}">{_e(p["button_text"])}</a>' if p.get("button_text") else "")
                + "</div></section>")
    if t == "text":
        return f'<section class="wrap block"><h2>{_e(p["heading"])}</h2><div class="rich">{sm.sanitize_html(p["body"])}</div></section>'
    if t == "image":
        cap = f"<figcaption>{_e(p['caption'])}</figcaption>" if p.get("caption") else ""
        return f'<figure class="wrap block"><img src="{_url(p["src"])}" alt="{_e(p["alt"])}" loading="lazy">{cap}</figure>'
    if t == "features":
        items = "".join(f'<div class="card"><div class="icon">{_e(i.get("icon"))}</div><h3>{_e(i.get("title"))}</h3><p>{_e(i.get("text"))}</p></div>'
                        for i in p.get("items") or [])
        return f'<section class="wrap block"><h2>{_e(p["heading"])}</h2><div class="grid">{items}</div></section>'
    if t == "gallery":
        imgs = "".join(f'<img src="{_url(s)}" alt="" loading="lazy">' for s in p.get("images") or [])
        return f'<section class="wrap block"><h2>{_e(p["heading"])}</h2><div class="gallery">{imgs}</div></section>'
    if t == "testimonials":
        items = "".join(f'<blockquote class="card">â€œ{_e(i.get("quote"))}â€<cite>{_e(i.get("author"))}</cite></blockquote>' for i in p.get("items") or [])
        return f'<section class="wrap block"><h2>{_e(p["heading"])}</h2><div class="grid">{items}</div></section>'
    if t == "pricing":
        plans = "".join(
            f'<div class="card price"><h3>{_e(pl.get("name"))}</h3><div class="amount">{_e(pl.get("price"))}</div><ul>'
            + "".join(f"<li>{_e(f)}</li>" for f in pl.get("features") or [])
            + f'</ul><a class="btn" href="#contact">{_e(pl.get("cta") or "Choose")}</a></div>' for pl in p.get("plans") or [])
        return f'<section class="wrap block"><h2>{_e(p["heading"])}</h2><div class="grid">{plans}</div></section>'
    if t == "cta":
        return (f'<section class="cta"><div class="wrap"><h2>{_e(p["heading"])}</h2><p>{_e(p["text"])}</p>'
                f'<a class="btn light" href="{_url(p["button_link"])}">{_e(p["button_text"])}</a></div></section>')
    if t == "contact":
        lines = []
        if p.get("email"):
            lines.append(f'<p>âœ‰ <a href="mailto:{_e(p["email"])}">{_e(p["email"])}</a></p>')
        if p.get("phone"):
            lines.append(f'<p>â˜Ž <a href="tel:{_e(p["phone"])}">{_e(p["phone"])}</a></p>')
        if p.get("whatsapp"):
            import re
            lines.append(f'<p><a class="btn wa" href="https://wa.me/{re.sub(r"[^0-9]", "", str(p["whatsapp"]))}">Chat on WhatsApp</a></p>')
        if p.get("address"):
            lines.append(f"<p>âŒ– {_e(p['address'])}</p>")
        form = ""
        if p.get("show_form"):
            action = f"/api/v1/sites/{_e(site_slug)}/contact" if site_slug else "#"
            form = (f'<form class="form" method="post" action="{action}">'
                    '<input name="name" placeholder="Your name" required><input name="email" type="email" placeholder="Email" required>'
                    '<input name="phone" placeholder="Phone"><textarea name="message" rows="4" placeholder="How can we help?"></textarea>'
                    '<button class="btn" type="submit">Send message</button></form>')
        return f'<section id="contact" class="wrap block"><h2>{_e(p["heading"])}</h2><div class="two">{"".join(lines) or "<p></p>"}{form}</div></section>'
    if t == "map":
        from urllib.parse import quote
        return (f'<section class="wrap block"><iframe class="map" loading="lazy" title="map" '
                f'src="https://maps.google.com/maps?q={quote(str(p.get("address") or ""))}&output=embed"></iframe></section>')
    if t == "video":
        src = _youtube_embed(p.get("url"))
        return f'<section class="wrap block"><div class="video"><iframe src="{_e(src)}" allowfullscreen title="video"></iframe></div></section>' if src else ""
    if t == "button":
        return f'<div class="wrap block align-{_e(p.get("align"))}"><a class="btn" href="{_url(p["link"])}">{_e(p["text"])}</a></div>'
    if t == "divider":
        return '<hr class="wrap divider">'
    if t == "spacer":
        return f'<div style="height:{int(p.get("height") or 40)}px"></div>'
    if t == "footer":
        return f'<footer><div class="wrap">{_e(p["text"])}</div></footer>'
    return ""


def css(theme: Dict[str, Any]) -> str:
    th = {**DEFAULT_THEME, **(theme or {})}
    return f"""
:root{{--p:{th['primary']};--bg:{th['background']};--tx:{th['text']};--mu:{th['muted']};--sf:{th['surface']};--r:{th['radius']}}}
*{{box-sizing:border-box}}body{{margin:0;font-family:'{th['font']}',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--tx);line-height:1.6}}
img{{max-width:100%;display:block;border-radius:var(--r)}}a{{color:var(--p)}}
.wrap{{max-width:1100px;margin:0 auto;padding:0 20px}}.block{{padding:56px 20px}}
h1{{font-size:clamp(2rem,5vw,3.4rem);line-height:1.1;margin:0 0 16px}}h2{{font-size:clamp(1.5rem,3.5vw,2.2rem);margin:0 0 24px}}
.hero{{padding:96px 0;background:linear-gradient(135deg,var(--p),#111827);color:#fff;background-size:cover;background-position:center}}
.hero .lead{{font-size:1.2rem;opacity:.9;max-width:640px}}.align-center{{text-align:center}}.align-center .lead{{margin:0 auto 28px}}
.btn{{display:inline-block;background:var(--p);color:#fff;padding:14px 26px;border-radius:999px;text-decoration:none;font-weight:700;border:0;cursor:pointer;font-size:1rem}}
.hero .btn{{background:#fff;color:var(--p)}}.btn.light{{background:#fff;color:var(--p)}}.btn.wa{{background:#25D366}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px}}
.card{{background:var(--sf);border-radius:var(--r);padding:24px;margin:0}}.card h3{{margin:8px 0}}.icon{{font-size:1.8rem;color:var(--p)}}
blockquote.card{{font-style:italic}}cite{{display:block;margin-top:12px;font-style:normal;font-weight:700;color:var(--mu)}}
.price .amount{{font-size:2rem;font-weight:800;color:var(--p)}}.price ul{{padding-left:18px}}
.gallery{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}
.cta{{background:var(--p);color:#fff;text-align:center;padding:64px 0}}
.two{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:28px}}
.form{{display:grid;gap:12px}}.form input,.form textarea{{padding:12px 14px;border:1px solid #d1d5db;border-radius:10px;font:inherit}}
.map{{width:100%;height:340px;border:0;border-radius:var(--r)}}.video{{position:relative;padding-top:56.25%}}.video iframe{{position:absolute;inset:0;width:100%;height:100%;border:0;border-radius:var(--r)}}
.divider{{border:0;border-top:1px solid #e5e7eb}}figcaption{{color:var(--mu);font-size:.9rem;margin-top:8px}}
footer{{background:#111827;color:#9ca3af;padding:28px 0;text-align:center;font-size:.9rem}}
@media(max-width:640px){{.block{{padding:40px 16px}}.hero{{padding:64px 0}}}}
"""


def render_page(blocks: List[Dict[str, Any]], theme: Dict[str, Any], title: str = "Page", site_slug: str = "",
                inline_css: bool = True, description: str = "") -> str:
    body = "\n".join(render_block(b, site_slug) for b in blocks or [])
    th = {**DEFAULT_THEME, **(theme or {})}
    font = th["font"].replace(" ", "+")
    style = f"<style>{css(theme)}</style>" if inline_css else '<link rel="stylesheet" href="styles.css">'
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{_e(title)}</title><meta name="description" content="{_e(description or title)}">'
            f'<link href="https://fonts.googleapis.com/css2?family={font}:wght@400;600;800&display=swap" rel="stylesheet">'
            f'{style}</head><body>\n{body}\n' + ('' if inline_css else '<script src="script.js"></script>') + '</body></html>')


def render_email(blocks: List[Dict[str, Any]], theme: Dict[str, Any], title: str = "Email") -> str:
    """Email-safe rendering: single 600px table, inline styles, no forms/iframes."""
    th = {**DEFAULT_THEME, **(theme or {})}
    rows = []
    for b in blocks or []:
        t = b.get("type")
        p = {**BLOCK_TYPES.get(t, {}).get("props", {}), **(b.get("props") or {})}
        td = 'style="padding:24px 32px;font-family:Arial,sans-serif;color:%s;font-size:15px;line-height:1.6"' % th["text"]
        if t == "hero":
            rows.append(f'<tr><td style="background:{th["primary"]};color:#fff;padding:40px 32px;font-family:Arial,sans-serif;text-align:center">'
                        f'<h1 style="margin:0 0 10px;font-size:28px">{_e(p["heading"])}</h1><p style="margin:0 0 20px">{_e(p["subheading"])}</p>'
                        + (f'<a href="{_url(p["button_link"])}" style="background:#fff;color:{th["primary"]};padding:12px 22px;border-radius:24px;text-decoration:none;font-weight:bold">{_e(p["button_text"])}</a>' if p.get("button_text") else "")
                        + "</td></tr>")
        elif t == "text":
            rows.append(f'<tr><td {td}><h2 style="margin:0 0 12px;font-size:20px">{_e(p["heading"])}</h2>{sm.sanitize_html(p["body"])}</td></tr>')
        elif t == "image":
            rows.append(f'<tr><td style="padding:0 32px"><img src="{_url(p["src"])}" alt="{_e(p["alt"])}" width="536" style="width:100%;border-radius:8px;display:block"></td></tr>')
        elif t in ("button", "cta"):
            text, link = (p.get("text"), p.get("link")) if t == "button" else (p.get("button_text"), p.get("button_link"))
            head = f'<h2 style="margin:0 0 8px">{_e(p["heading"])}</h2><p>{_e(p["text"])}</p>' if t == "cta" else ""
            rows.append(f'<tr><td {td} align="center">{head}<a href="{_url(link)}" style="background:{th["primary"]};color:#fff;padding:12px 24px;border-radius:24px;text-decoration:none;font-weight:bold">{_e(text)}</a></td></tr>')
        elif t == "features":
            items = "".join(f'<p><b>{_e(i.get("icon"))} {_e(i.get("title"))}</b><br>{_e(i.get("text"))}</p>' for i in p.get("items") or [])
            rows.append(f'<tr><td {td}><h2 style="margin:0 0 12px;font-size:20px">{_e(p["heading"])}</h2>{items}</td></tr>')
        elif t == "divider":
            rows.append('<tr><td style="padding:0 32px"><hr style="border:0;border-top:1px solid #e5e7eb"></td></tr>')
        elif t == "spacer":
            rows.append(f'<tr><td style="height:{int(p.get("height") or 24)}px"></td></tr>')
        elif t == "footer":
            rows.append(f'<tr><td style="padding:20px 32px;color:#9ca3af;font-size:12px;font-family:Arial,sans-serif;text-align:center">{_e(p["text"])}</td></tr>')
        elif t == "testimonials":
            items = "".join(f'<p style="font-style:italic">â€œ{_e(i.get("quote"))}â€ <b>- {_e(i.get("author"))}</b></p>' for i in p.get("items") or [])
            rows.append(f'<tr><td {td}>{items}</td></tr>')
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{_e(title)}</title></head>'
            f'<body style="margin:0;background:#f3f4f6"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 8px">'
            f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff;border-radius:12px;overflow:hidden">'
            + "".join(rows) + "</table></td></tr></table></body></html>")

