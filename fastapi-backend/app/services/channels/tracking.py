"""
Module 6 - Tracking Pixel Engine.

instrument_html() rewrites every http(s) link to a signed redirect (click tracking) and appends a
1x1 transparent GIF (open tracking). Links are HMAC-signed by SecurityManager so the redirect
endpoint can never be abused as an open redirect.
"""
import base64
import html as html_lib
import re
import secrets
from urllib.parse import quote

from app.core.config import settings
from app.core.security import security_manager

PIXEL_GIF = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


def tracking_base() -> str:
    return (settings.TRACKING_BASE_URL or settings.BACKEND_URL).rstrip("/")


def new_token() -> str:
    return secrets.token_urlsafe(16)


def click_url(token: str, url: str) -> str:
    sig = security_manager.sign(f"{token}|{url}")
    return f"{tracking_base()}/api/v1/track/c/{token}?u={quote(url, safe='')}&s={sig}"


def pixel_url(token: str) -> str:
    return f"{tracking_base()}/api/v1/track/o/{token}.gif"


def text_to_html(text: str) -> str:
    esc = html_lib.escape(text or "")
    esc = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', esc)
    return "<div style=\"font-family:Arial,sans-serif;font-size:14px;line-height:1.6;color:#222\">" + esc.replace("\n", "<br>") + "</div>"


def instrument_html(html: str, token: str, track_clicks: bool = True, track_opens: bool = True) -> str:
    if track_clicks:
        def repl(m):
            url = html_lib.unescape(m.group(2))
            if "/api/v1/track/" in url or not url.lower().startswith(("http://", "https://")):
                return m.group(0)
            return f'{m.group(1)}"{html_lib.escape(click_url(token, url))}"'
        html = re.sub(r'(<a\b[^>]*?\bhref=)["\']([^"\']+)["\']', repl, html, flags=re.I)
    if not track_opens:
        return html
    pixel = f'<img src="{pixel_url(token)}" width="1" height="1" alt="" style="display:none;border:0" />'
    if re.search(r"</body>", html, re.I):
        return re.sub(r"</body>", pixel + "</body>", html, count=1, flags=re.I)
    return html + pixel

