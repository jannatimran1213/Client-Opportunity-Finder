"""
Module 5 - AI Copywriter engine.

  Personalized Icebreakers ... icebreakers()
  Bulk Email Generation ...... generate_email() called per lead by the bulk endpoint
  Dynamic Reply Assistant .... reply_assistant()  (intent detection + suggested replies)
  Industry-Specific Content .. industry_content()

Every function uses the configured LLM when available and falls back to a deterministic
template engine (driven by the industry packs) when no API key is set or the LLM call fails.
"""
import random
import re
from typing import Any, Dict, List, Optional

from app.services.copywriter import llm
from app.services.copywriter.industries import CONTENT_TYPES, detect_industry, get_pack

SYSTEM = ("You are a senior B2B cold-outreach copywriter. Write short, specific, human messages. "
          "No hype, no emojis, no fake claims, no placeholders like [Name]. Use the facts provided.")


def _first(name: Optional[str]) -> str:
    return (name or "").split(" ")[0] if name else ""


def _facts(lead: Dict[str, Any], audit: Optional[Dict[str, Any]] = None) -> List[str]:
    facts = []
    if lead.get("city"):
        facts.append(f"based in {lead['city']}")
    if lead.get("website"):
        facts.append(f"website {lead['website']}")
    else:
        facts.append("no website found")
    a = audit or {}
    for key, label in (("speed_score", "page speed"), ("mobile_score", "mobile friendliness"),
                       ("security_score", "security"), ("overall_score", "overall site score"),
                       ("load_speed_score", "page speed"), ("responsiveness_score", "mobile friendliness"),
                       ("seo_score", "SEO")):
        v = a.get(key) if a.get(key) is not None else lead.get(key)
        if v is not None:
            facts.append(f"{label} {round(float(v))}/100")
    for t in (a.get("tech_stack") or [])[:4]:
        facts.append(f"uses {t.get('name') if isinstance(t, dict) else t}" + (f" {t.get('version')} (outdated)" if isinstance(t, dict) and t.get("outdated") else ""))
    for leak in (a.get("leaks") or [])[:3]:
        facts.append(f"website issue: {leak}")
    if lead.get("instagram") or lead.get("facebook"):
        facts.append("active on social media")
    return facts


def _weak_spot(lead: Dict[str, Any], audit: Optional[Dict[str, Any]]) -> Optional[str]:
    a = {**lead, **(audit or {})}
    if a.get("leaks"):
        return f"your site has an issue that costs enquiries: {a['leaks'][0].lower()}"
    if not a.get("website"):
        return "I couldn't find a website for you, so people searching online may be going to competitors"
    checks = [("mobile_score", "your site is hard to use on a phone"), ("responsiveness_score", "your site is hard to use on a phone"),
              ("speed_score", "your homepage takes a while to load"), ("load_speed_score", "your homepage takes a while to load"),
              ("security_score", "your site is missing some security basics browsers warn about"),
              ("ssl_score", "your site shows security warnings"), ("seo_score", "your site is hard to find on Google")]
    for key, text in checks:
        v = a.get(key)
        if v is not None and float(v) < 60:
            return text
    return None


# â”€â”€ AI deduction: audit data + company data + user's services -> pain point â”€â”€

def deduce_pain_point(lead: Dict[str, Any], audit: Optional[Dict[str, Any]], services: str = "") -> Dict[str, str]:
    weak = _weak_spot(lead, audit)
    pack = get_pack(detect_industry(lead.get("category"), lead.get("business_name")))
    service = (services or "").split(",")[0].strip() or pack["offers"][0]
    if weak:
        pain = f"{lead.get('business_name') or 'This business'} is losing customers because {weak.replace('your site', 'its site').replace('your ', 'its ')}."
    else:
        pain = f"Like most {pack['label'].lower()}, it likely struggles with {pack['pains'][0]}."
    return {"pain_point": pain, "recommended_service": service, "outcome": pack["outcome"]}


# â”€â”€ Icebreakers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _template_icebreakers(lead, audit, industry, count):
    name = lead.get("business_name") or "your business"
    city = lead.get("city") or "your area"
    pack = get_pack(industry)
    weak = _weak_spot(lead, audit)
    options = [
        f"I came across {name} while looking at {pack['label'].lower()} in {city} and liked what you've built.",
        f"Noticed {name} is one of the better-reviewed names in {city}, so I took a quick look at your online presence.",
        f"Quick one: I was on {lead.get('website') or name}'s page from my phone this morning and had a thought.",
        f"Most {pack['label'].lower()} in {city} I speak with mention {pack['pains'][0]}; curious if that's true for {name} too.",
    ]
    if weak:
        options.insert(0, f"I was looking at {name} online and noticed {weak}. It's an easy fix.")
    tech = [t.get("name") for t in (audit or {}).get("tech_stack", []) if isinstance(t, dict)]
    if tech:
        options.append(f"I saw {name} runs on {tech[0]}; I've helped a few {pack['label'].lower()} get more out of that setup.")
    return options[:count]


async def icebreakers(lead: Dict[str, Any], audit: Optional[Dict[str, Any]] = None, count: int = 3,
                      tone: str = "friendly") -> Dict[str, Any]:
    industry = detect_industry(lead.get("category"), lead.get("business_name"))
    if llm.available():
        try:
            data = await llm.chat_json(SYSTEM, (
                f"Write {count} different one-sentence personalised icebreakers (opening lines) for a cold email to "
                f"'{lead.get('business_name')}', a {get_pack(industry)['label']} business. Tone: {tone}. "
                f"Facts: {'; '.join(_facts(lead, audit))}. Each under 30 words, reference a real fact. "
                'Return {"icebreakers": ["...", "..."]}'))
            lines = [s.strip() for s in data.get("icebreakers", []) if s.strip()][:count]
            if lines:
                return {"icebreakers": lines, "source": "llm", "industry": industry, "deduction": deduce_pain_point(lead, audit)}
        except Exception:
            pass
    return {"icebreakers": _template_icebreakers(lead, audit, industry, count), "source": "template", "industry": industry,
            "deduction": deduce_pain_point(lead, audit)}


# â”€â”€ Emails (single + bulk) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _template_email(lead, audit, industry, sender, tone, icebreaker=None, channel="email"):
    pack = get_pack(industry)
    name = lead.get("business_name") or "your business"
    sender_name = sender.get("name") or "Our team"
    company = sender.get("company") or ""
    opener = icebreaker or _template_icebreakers(lead, audit, industry, 1)[0]
    weak = _weak_spot(lead, audit)
    problem = f"From a quick check, {weak}." if weak else f"Many {pack['label'].lower()} we work with struggle with {pack['pains'][1]}."
    offer = f"We help businesses like {name} with {pack['offers'][0]} and {pack['offers'][1]}, which usually means {pack['outcome']}."
    sign = f"{sender_name}" + (f"\n{company}" if company else "")
    if channel == "whatsapp":
        body = f"Hi! {opener} {problem} {offer} {pack['cta']}"
        return {"subject": None, "body": body[:900]}
    if channel == "linkedin":
        body = f"Hi, {opener} I help {pack['label'].lower()} get {pack['outcome']}. Happy to connect."
        return {"subject": None, "body": body[:300]}
    subjects = [f"Quick idea for {name}", f"{name}: {pack['outcome']}", f"Question about {name}'s website"]
    body = f"Hi {name} team,\n\n{opener}\n\n{problem} {offer}\n\n{pack['cta']}\n\nBest regards,\n{sign}"
    return {"subject": random.Random(name).choice(subjects), "body": body}


async def generate_email(lead: Dict[str, Any], audit: Optional[Dict[str, Any]] = None, sender: Optional[Dict[str, str]] = None,
                         tone: str = "professional", channel: str = "email", industry: Optional[str] = None,
                         extra_instructions: str = "") -> Dict[str, Any]:
    sender = sender or {}
    industry = industry or detect_industry(lead.get("category"), lead.get("business_name"))
    pack = get_pack(industry)
    if llm.available():
        try:
            limits = {"email": "120-170 words with a subject line", "linkedin": "under 300 characters, no subject",
                      "whatsapp": "under 80 words, no subject, conversational"}[channel if channel in ("email", "linkedin", "whatsapp") else "email"]
            data = await llm.chat_json(SYSTEM, (
                f"Write a {channel} outreach message ({limits}) to '{lead.get('business_name')}' "
                f"({pack['label']}). Tone: {tone}. Facts: {'; '.join(_facts(lead, audit))}. "
                f"Typical pains: {', '.join(pack['pains'])}. What we offer: {', '.join(pack['offers'])}. "
                f"Sender: {sender.get('name', '')} from {sender.get('company', '')} ({sender.get('services', '')}). "
                f"End with a soft call to action. {extra_instructions} "
                'Return {"subject": "...", "body": "..."}'))
            if data.get("body"):
                return {"subject": data.get("subject"), "body": data["body"], "source": "llm", "industry": industry}
        except Exception:
            pass
    return {**_template_email(lead, audit, industry, sender, tone, channel=channel), "source": "template", "industry": industry}


# â”€â”€ Reply assistant â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

INTENT_RULES = [
    ("unsubscribe", r"\b(unsubscribe|remove me|stop (emailing|messaging)|not contact)\b"),
    ("out_of_office", r"\b(out of (the )?office|on leave|on vacation|auto.?reply|away until)\b"),
    ("meeting", r"\b(call|meet|meeting|schedule|calendar|zoom|teams|available|tomorrow|next week)\b"),
    ("pricing", r"\b(price|pricing|cost|how much|quote|rates?|budget|fee)\b"),
    ("not_interested", r"\b(not interested|no thanks|no thank you|we('re| are) (good|fine|covered)|already have)\b"),
    ("interested", r"\b(interested|sounds good|tell me more|let'?s talk|send (me )?(more|details)|yes)\b"),
    ("question", r"\?"),
]


def detect_intent(message: str) -> Dict[str, str]:
    text = (message or "").lower()
    for intent, pat in INTENT_RULES:
        if re.search(pat, text):
            sentiment = "negative" if intent in ("unsubscribe", "not_interested") else "neutral" if intent in ("out_of_office", "question") else "positive"
            return {"intent": intent, "sentiment": sentiment}
    return {"intent": "other", "sentiment": "neutral"}


def _template_replies(intent: str, sender: Dict[str, str], context: Dict[str, Any]) -> List[Dict[str, str]]:
    who = sender.get("name") or "Best regards"
    link = sender.get("booking_link") or ""
    biz = context.get("business_name") or "your business"
    t = {
        "interested": [("Book a call", f"Great to hear! The easiest next step is a 15-minute call so I can understand {biz}'s goals. "
                        f"{'You can pick a time here: ' + link if link else 'Would Tuesday or Wednesday afternoon work?'}\n\n{who}"),
                       ("Send details", f"Thanks for getting back to me. I'll put together a short proposal for {biz} with examples and a clear price. "
                        f"Is there anything specific you'd like me to include?\n\n{who}")],
        "pricing": [("Give a range", f"Good question. Most projects like this fall into a few packages depending on scope. "
                     f"If you can share what matters most to you, I'll send an exact quote for {biz} today.\n\n{who}"),
                    ("Offer a call", f"Happy to share pricing. It depends on a couple of details, so a quick 10-minute call is the fastest way to give you an accurate number. When suits you?\n\n{who}")],
        "meeting": [("Confirm time", f"Perfect, let's do it. {('Here is my calendar: ' + link) if link else 'Please share a time that works and I will send an invite.'}\n\nLooking forward to it,\n{who}"),
                    ("Propose slots", f"Thank you! I'm free Tuesday 11:00 or Thursday 15:00. Which works better for you?\n\n{who}")],
        "question": [("Answer + CTA", f"Thanks for the question. Happy to explain in detail, and I can also show a quick example for {biz}. "
                      f"Would a short call or a written summary be more helpful?\n\n{who}")],
        "not_interested": [("Polite close", f"Understood, thanks for letting me know. If anything changes, feel free to reach out anytime.\n\nAll the best,\n{who}"),
                           ("Leave door open", f"No problem at all. Would it be okay if I checked back in a few months?\n\n{who}")],
        "out_of_office": [("Follow up later", f"Thanks, I'll follow up when you're back.\n\n{who}")],
        "unsubscribe": [("Confirm removal", f"Done, you won't hear from me again. Apologies for the interruption.\n\n{who}")],
        "other": [("Acknowledge", f"Thanks for your reply. Could you tell me a little more so I can help in the best way?\n\n{who}")],
    }
    return [{"label": l, "body": b} for l, b in t.get(intent, t["other"])]


async def reply_assistant(message: str, context: Optional[Dict[str, Any]] = None, sender: Optional[Dict[str, str]] = None,
                          history: Optional[List[Dict[str, str]]] = None, instruction: str = "") -> Dict[str, Any]:
    context, sender = context or {}, sender or {}
    detected = detect_intent(message)
    next_action = {"interested": "Schedule a meeting", "meeting": "Create the meeting in Schedule Meeting",
                   "pricing": "Send a quote", "question": "Answer and propose a call", "not_interested": "Mark lead as lost",
                   "out_of_office": "Create a follow-up for next week", "unsubscribe": "Stop all outreach to this lead",
                   "other": "Reply and qualify"}[detected["intent"]]
    if llm.available():
        try:
            convo = "\n".join(f"{h.get('role', 'them')}: {h.get('content', '')}" for h in (history or [])[-6:])
            data = await llm.chat_json(SYSTEM, (
                f"A prospect ({context.get('business_name', 'a business')}) replied to our outreach.\n"
                f"Earlier conversation:\n{convo}\nTheir latest reply:\n{message}\n"
                f"Detected intent: {detected['intent']}. {instruction}\n"
                f"Write 2 alternative replies signed by {sender.get('name', 'the sender')}. "
                'Return {"intent": "...", "sentiment": "...", "replies": [{"label": "...", "body": "..."}]}'))
            if data.get("replies"):
                return {"intent": data.get("intent") or detected["intent"], "sentiment": data.get("sentiment") or detected["sentiment"],
                        "suggested_replies": data["replies"][:3], "next_action": next_action, "source": "llm"}
        except Exception:
            pass
    return {**detected, "suggested_replies": _template_replies(detected["intent"], sender, context),
            "next_action": next_action, "source": "template"}


# â”€â”€ Industry content â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def industry_content(industry: str, content_type: str, lead: Optional[Dict[str, Any]] = None,
                           sender: Optional[Dict[str, str]] = None, tone: str = "professional") -> Dict[str, Any]:
    pack = get_pack(industry)
    lead, sender = lead or {}, sender or {}
    label = CONTENT_TYPES.get(content_type, content_type)
    if llm.available():
        try:
            data = await llm.chat_json(SYSTEM, (
                f"Write a {label} for the {pack['label']} industry. Tone: {tone}. "
                f"Prospect: {lead.get('business_name', 'a typical business')} {lead.get('city', '')}. "
                f"Industry pains: {', '.join(pack['pains'])}. Our offers: {', '.join(pack['offers'])}. Outcome: {pack['outcome']}. "
                f"Sender: {sender.get('name', '')} {sender.get('company', '')}. "
                'Return {"title": "...", "body": "..."}'))
            if data.get("body"):
                return {"title": data.get("title") or label, "body": data["body"], "source": "llm", "industry": industry}
        except Exception:
            pass
    # Without a specific prospect the copy is a reusable template with {{business_name}} placeholders
    name = lead.get("business_name") or "{{business_name}}"
    if not lead:
        lead = {"business_name": name, "city": "{{city}}", "website": "{{website}}", "category": industry}
    if content_type == "landing_copy":
        body = (f"HEADLINE: {pack['outcome'].capitalize()}\n"
                f"SUB-HEADLINE: {pack['offers'][0].capitalize()} built for {pack['label'].lower()}.\n\n"
                + "\n".join(f"- {o.capitalize()}" for o in pack["offers"]) + f"\n\nCTA: {pack['cta']}")
    elif content_type == "social_post":
        body = (f"Running {pack['label'].lower()}? The #1 thing we hear is {pack['pains'][0]}.\n"
                f"Here's what works: {pack['offers'][0]}, {pack['offers'][1]} and {pack['offers'][2]}.\n"
                f"Result: {pack['outcome']}. DM us to see how.")
    elif content_type == "follow_up":
        body = (f"Hi {name} team,\n\nJust floating my earlier note back to the top of your inbox. "
                f"We recently helped another {pack['label'].lower().rstrip('s')} get {pack['outcome']}.\n\n{pack['cta']}\n\n{sender.get('name', '')}")
    else:
        channel = {"linkedin_note": "linkedin", "whatsapp": "whatsapp"}.get(content_type, "email")
        body = _template_email(lead, None, industry, sender, tone, channel=channel)["body"]
    return {"title": label, "body": body, "source": "template", "industry": industry}

