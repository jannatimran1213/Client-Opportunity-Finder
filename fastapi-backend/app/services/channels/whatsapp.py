"""
Module 6 - WhatsApp Cloud API integration (Meta Graph API).

Env: WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_API_VERSION, WHATSAPP_VERIFY_TOKEN,
WHATSAPP_APP_SECRET. Without a token the platform runs in "simulated" mode and returns a wa.me
click-to-chat link so the message can still be sent by hand.

Note (Meta rule): a free-form text is only delivered inside 24h of the contact's last message;
the first message to a new contact must be an approved template (send_template).
"""
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from app.core.config import settings


def configured() -> bool:
    return bool(settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID)


def normalize(number: str) -> str:
    return re.sub(r"\D", "", number or "")


def click_to_chat(number: str, text: str) -> str:
    return f"https://wa.me/{normalize(number)}?text={quote(text or '')}"


async def _post(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(url, json=payload, headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"})
    data = r.json() if r.content else {}
    if r.status_code >= 400:
        err = data.get("error", {})
        return {"success": False, "error": err.get("message") or r.text[:300], "code": err.get("code")}
    msg_id = (data.get("messages") or [{}])[0].get("id")
    return {"success": True, "message_id": msg_id}


async def send_text(to: str, body: str, preview_url: bool = True) -> Dict[str, Any]:
    return await _post({"messaging_product": "whatsapp", "recipient_type": "individual", "to": normalize(to),
                        "type": "text", "text": {"preview_url": preview_url, "body": body[:4096]}})


async def send_template(to: str, name: str, language: str = "en_US", params: Optional[List[str]] = None) -> Dict[str, Any]:
    template: Dict[str, Any] = {"name": name, "language": {"code": language}}
    if params:
        template["components"] = [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}]
    return await _post({"messaging_product": "whatsapp", "to": normalize(to), "type": "template", "template": template})


def parse_webhook(payload: Dict[str, Any]) -> Dict[str, list]:
    statuses, incoming = [], []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for s in value.get("statuses", []) or []:
                statuses.append({"id": s.get("id"), "status": s.get("status"), "recipient": s.get("recipient_id"),
                                 "errors": s.get("errors")})
            for m in value.get("messages", []) or []:
                incoming.append({"id": m.get("id"), "from": m.get("from"), "type": m.get("type"),
                                 "text": (m.get("text") or {}).get("body") or (m.get("button") or {}).get("text") or f"[{m.get('type')}]"})
    return {"statuses": statuses, "incoming": incoming}

