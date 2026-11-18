"""
Module 7 - Set Reminders & Notifications: the reminder dispatcher.

process_due_reminders() delivers every reminder whose time has come:
  in_app   -> a Notification row (bell icon in the app header)
  email    -> Resend (platform mail) if configured, else falls back to in_app
  whatsapp -> WhatsApp Cloud API if configured, else falls back to in_app
It runs every REMINDER_LOOP_SECONDS inside the API process (see app/main.py) and can also be
triggered by a cron job via POST /api/v1/meetings/reminders/run-due.
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.meeting import FollowUp, Meeting, Notification, Reminder

logger = logging.getLogger(__name__)


def build_ics(m: Meeting, organizer_email: str = "noreply@aiclienthunt.app") -> str:
    def fmt(dt):
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    end = m.end_at or m.start_at
    desc = (m.notes or "").replace("\n", "\\n")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//AI Client Hunt//Meetings//EN", "METHOD:PUBLISH", "BEGIN:VEVENT",
             f"UID:{m.id}@aiclienthunt", f"DTSTAMP:{fmt(datetime.now(timezone.utc))}", f"DTSTART:{fmt(m.start_at)}",
             f"DTEND:{fmt(end)}", f"SUMMARY:{m.title}", f"DESCRIPTION:{desc} {m.meeting_link or ''}".strip(),
             f"LOCATION:{m.location or m.meeting_link or ''}", f"ORGANIZER:mailto:{organizer_email}"]
    if m.attendee_email:
        lines.append(f"ATTENDEE;CN={m.attendee_name or m.attendee_email}:mailto:{m.attendee_email}")
    lines += ["BEGIN:VALARM", "TRIGGER:-PT30M", "ACTION:DISPLAY", "DESCRIPTION:Reminder", "END:VALARM", "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


async def _deliver(db, r: Reminder) -> None:
    title, body, link, user_id = "Reminder", r.message or "", "/meetings", None
    if r.meeting_id:
        m = await db.get(Meeting, r.meeting_id)
        if m:
            user_id = m.created_by
            title = f"Upcoming: {m.title}"
            body = r.message or f"{m.title} at {m.start_at.strftime('%d %b %H:%M')} UTC" + (f" - {m.meeting_link}" if m.meeting_link else "")
    elif r.follow_up_id:
        f = await db.get(FollowUp, r.follow_up_id)
        if f:
            title, body, link = "Follow-up due", r.message or f.title, "/meetings?tab=followups"

    delivered_via = "in_app"
    if r.channel == "email" and r.recipient:
        from app.services.email.resend_sender import is_configured, send_email
        if is_configured():
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, lambda: send_email(to_email=r.recipient, subject=title, body=body))
            if res.get("success"):
                delivered_via = "email"
            else:
                r.error = res.get("error")
    elif r.channel == "whatsapp" and r.recipient:
        from app.services.channels import whatsapp
        if whatsapp.configured():
            res = await whatsapp.send_text(r.recipient, f"{title}\n{body}")
            if res.get("success"):
                delivered_via = "whatsapp"
            else:
                r.error = res.get("error")
    # Always leave an in-app notification so nothing is missed
    db.add(Notification(workspace_id=r.workspace_id, user_id=user_id, title=title,
                        body=body + ("" if delivered_via == "in_app" else f" (sent by {delivered_via})"), link=link))
    r.sent = True
    r.sent_at = datetime.now(timezone.utc)


async def process_due_reminders(limit: int = 200, session_factory=None) -> int:
    async with (session_factory or AsyncSessionLocal)() as db:
        now = datetime.now(timezone.utc)
        due = (await db.execute(select(Reminder).where(Reminder.sent == False, Reminder.remind_at <= now)  # noqa: E712
                                .order_by(Reminder.remind_at).limit(limit)
                                .with_for_update(skip_locked=True))).scalars().all()  # safe with beat + in-process loop
        for r in due:
            try:
                await _deliver(db, r)
            except Exception as e:  # never let one bad reminder stop the loop
                r.error = str(e)[:300]
                r.sent = True
        await db.commit()
        return len(due)


async def detect_no_reply(session_factory=None) -> int:
    """
    Smart Reminders: when a contacted lead has not responded within NO_REPLY_DAYS (or the workspace's
    settings.no_reply_days), create a follow-up task + an in-app alert - once per outreach.
    """
    from datetime import timedelta
    from app.core.config import settings
    from app.models.channel import ChannelMessage, TrackedEmail
    from app.models.lead_list import LeadProfile
    from app.models.saved_business import SavedBusiness
    from app.models.workspace import Workspace
    created = 0
    async with (session_factory or AsyncSessionLocal)() as db:
        now = datetime.now(timezone.utc)
        profiles = (await db.execute(select(LeadProfile).where(LeadProfile.status == "contacted"))).scalars().all()
        ws_cache = {}
        for p in profiles:
            if p.workspace_id not in ws_cache:
                ws = await db.get(Workspace, p.workspace_id)
                ws_cache[p.workspace_id] = int((ws.settings or {}).get("no_reply_days") or settings.NO_REPLY_DAYS) if ws else settings.NO_REPLY_DAYS
            days = ws_cache[p.workspace_id]
            last_out = (await db.execute(select(ChannelMessage).where(
                ChannelMessage.business_id == p.business_id, ChannelMessage.direction == "outbound",
                ChannelMessage.status.in_(["sent", "delivered", "read", "simulated"])).order_by(ChannelMessage.created_at.desc()))).scalars().first()
            if not last_out or (last_out.meta or {}).get("no_reply_alerted"):
                continue
            sent_at = last_out.created_at if last_out.created_at.tzinfo else last_out.created_at.replace(tzinfo=timezone.utc)
            if sent_at > now - timedelta(days=days):
                continue
            inbound = (await db.execute(select(ChannelMessage).where(
                ChannelMessage.business_id == p.business_id, ChannelMessage.direction == "inbound",
                ChannelMessage.created_at > last_out.created_at))).scalars().first()
            if inbound:
                continue
            pending = (await db.execute(select(FollowUp).where(FollowUp.business_id == p.business_id,
                                                               FollowUp.status == "pending"))).scalars().first()
            biz = await db.get(SavedBusiness, p.business_id)
            name = biz.business_name if biz else "a lead"
            opens = ""
            te = (await db.execute(select(TrackedEmail).where(TrackedEmail.business_id == p.business_id)
                                   .order_by(TrackedEmail.created_at.desc()))).scalars().first()
            if te and te.open_count:
                opens = f" They opened your email {te.open_count}x."
            if not pending:
                db.add(FollowUp(workspace_id=p.workspace_id, business_id=p.business_id, title=f"No reply from {name} - send a follow-up",
                                channel=last_out.channel, due_at=now, notes=f"Auto-created: no response {days} days after your {last_out.channel}.{opens}"))
            db.add(Notification(workspace_id=p.workspace_id, title=f"No reply from {name}",
                                body=f"{days}+ days since your {last_out.channel}.{opens} A follow-up task was added.", link="/meetings?tab=followups"))
            last_out.meta = {**(last_out.meta or {}), "no_reply_alerted": True}
            created += 1
        await db.commit()
    return created


async def reminder_loop(interval: int = 60):
    tick = 0
    while True:
        try:
            n = await process_due_reminders()
            if n:
                logger.info("Delivered %s reminders", n)
            if tick % 15 == 0:
                await detect_no_reply()
        except Exception as e:
            logger.warning("Reminder loop error: %s", e)
        tick += 1
        await asyncio.sleep(interval)

