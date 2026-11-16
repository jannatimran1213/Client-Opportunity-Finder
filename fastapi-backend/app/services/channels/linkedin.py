"""
Module 6 - LinkedIn Automation (assisted mode).

LinkedIn's User Agreement does not allow bots to send connection requests or messages, and its
official APIs don't offer messaging to normal apps. So this module automates everything around
the click: it finds/stores profile URLs, writes the personalised note (<= 300 chars), queues tasks
with a daily safety limit (LINKEDIN_DAILY_LIMIT) and tracks status. A team member opens each task,
the note is copied to the clipboard, and they press "Connect"/"Send" on LinkedIn themselves.
"""
from typing import Optional
from urllib.parse import quote

CONNECT_NOTE_LIMIT = 300


def search_url(business_name: str, city: Optional[str] = None) -> str:
    q = f"{business_name} {city or ''}".strip()
    return f"https://www.linkedin.com/search/results/companies/?keywords={quote(q)}"


def fill_template(template: str, lead: dict, sender: dict) -> str:
    values = {
        "first_name": (lead.get("contact_name") or "").split(" ")[0] or "there",
        "business_name": lead.get("business_name") or "your company",
        "city": lead.get("city") or "your city",
        "category": (lead.get("category") or "business").replace("_", " "),
        "sender_name": sender.get("name") or "",
        "company": sender.get("company") or "",
    }
    out = template
    for k, v in values.items():
        out = out.replace("{" + k + "}", v)
    return out


DEFAULT_TEMPLATES = {
    "connect": "Hi {first_name}, I came across {business_name} in {city} and liked your work. I help {category} businesses get more clients online. Would be great to connect. - {sender_name}",
    "message": "Thanks for connecting, {first_name}! I had a quick look at {business_name}'s website and have 2-3 ideas that could bring in more enquiries. Open to a short call this week?",
    "follow_up": "Hi {first_name}, just following up on my last note. Happy to share those ideas for {business_name} in a 10-minute call if useful.",
}


def compose(action: str, lead: dict, sender: dict, template: Optional[str] = None) -> str:
    text = fill_template(template or DEFAULT_TEMPLATES.get(action, DEFAULT_TEMPLATES["connect"]), lead, sender)
    return text[:CONNECT_NOTE_LIMIT] if action == "connect" else text

