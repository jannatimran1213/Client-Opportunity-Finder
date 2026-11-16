"""
Module 7 - Schedule Meeting.

  Add Meeting Date & Time ........ /meetings (CRUD, .ics download, complete with outcome)
  Set Reminders & Notifications .. /meetings/{id}/reminders, /meetings/reminders/run-due, /notifications
  Follow-up Tracker .............. /follow-ups (overdue / today / upcoming, done, snooze)
  Set Next Steps ................. /next-steps (per lead / meeting, owner, due date, pipeline stage)
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tenancy import WorkspaceContext, lead_scope, require_permission
from app.core.security import security_manager
from app.db.session import get_db
from app.models.lead_list import LeadProfile
from app.models.meeting import FollowUp, Meeting, NextStep, Notification, Reminder
from app.models.saved_business import SavedBusiness
from app.services.meetings.reminders import build_ics, detect_no_reply, process_due_reminders

router = APIRouter()
followups_router = APIRouter()
next_steps_router = APIRouter()
notifications_router = APIRouter()


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ReminderIn(BaseModel):
    minutes_before: int = 30
    channel: str = "in_app"   # in_app | email | whatsapp
    recipient: Optional[str] = None
    message: Optional[str] = None


class MeetingIn(BaseModel):
    title: str
    start_at: datetime
    end_at: Optional[datetime] = None
    duration_minutes: int = 30
    timezone: str = "UTC"
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    attendee_name: Optional[str] = None
    attendee_email: Optional[str] = None
    attendee_phone: Optional[str] = None
    business_id: Optional[str] = None
    notes: Optional[str] = None
    reminders: List[ReminderIn] = [ReminderIn(minutes_before=60), ReminderIn(minutes_before=15)]


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    attendee_name: Optional[str] = None
    attendee_email: Optional[str] = None
    attendee_phone: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class CompleteIn(BaseModel):
    status: str = "completed"  # completed | no_show | cancelled
    outcome: Optional[str] = None
    next_steps: List[str] = []
    follow_up_in_days: Optional[int] = 3
    follow_up_title: Optional[str] = None


class FollowUpIn(BaseModel):
    title: str
    due_at: datetime
    business_id: Optional[str] = None
    meeting_id: Optional[str] = None
    channel: str = "email"
    notes: Optional[str] = None
    remind: bool = True


class FollowUpUpdate(BaseModel):
    title: Optional[str] = None
    due_at: Optional[datetime] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    snooze_days: Optional[int] = None


class NextStepIn(BaseModel):
    title: str
    business_id: Optional[str] = None
    meeting_id: Optional[str] = None
    owner: Optional[str] = None
    due_date: Optional[date] = None
    stage: Optional[str] = None


class NextStepUpdate(BaseModel):
    title: Optional[str] = None
    owner: Optional[str] = None
    due_date: Optional[date] = None
    stage: Optional[str] = None
    done: Optional[bool] = None


async def _business(db, ctx, business_id) -> Optional[SavedBusiness]:
    if not business_id:
        return None
    b = (await db.execute(select(SavedBusiness).where(SavedBusiness.id == uuid.UUID(business_id), lead_scope(ctx)))).scalars().first()
    if not b:
        raise HTTPException(status_code=404, detail="Lead not found")
    return b


def _m(m: Meeting, names=None, reminders=None) -> dict:
    return {"id": str(m.id), "title": m.title, "start_at": m.start_at.isoformat(), "end_at": m.end_at.isoformat() if m.end_at else None,
            "timezone": m.timezone, "location": m.location, "meeting_link": m.meeting_link, "attendee_name": m.attendee_name,
            "attendee_email": m.attendee_email, "attendee_phone": m.attendee_phone, "notes": m.notes, "status": m.status,
            "outcome": m.outcome, "business_id": str(m.business_id) if m.business_id else None,
            "business_name": (names or {}).get(m.business_id),
            "reminders": [{"id": str(r.id), "remind_at": r.remind_at.isoformat(), "channel": r.channel, "sent": r.sent}
                          for r in (reminders or [])]}


def _f(f: FollowUp, names=None) -> dict:
    now = datetime.now(timezone.utc)
    due = _aware(f.due_at)
    bucket = "done" if f.status != "pending" else ("overdue" if due < now else "today" if due.date() == now.date() else "upcoming")
    return {"id": str(f.id), "title": f.title, "due_at": f.due_at.isoformat(), "status": f.status, "channel": f.channel,
            "notes": f.notes, "bucket": bucket, "business_id": str(f.business_id) if f.business_id else None,
            "business_name": (names or {}).get(f.business_id), "meeting_id": str(f.meeting_id) if f.meeting_id else None}


def _n(s: NextStep, names=None) -> dict:
    return {"id": str(s.id), "title": s.title, "owner": s.owner, "due_date": s.due_date.isoformat() if s.due_date else None,
            "stage": s.stage, "done": s.done, "business_id": str(s.business_id) if s.business_id else None,
            "business_name": (names or {}).get(s.business_id), "meeting_id": str(s.meeting_id) if s.meeting_id else None}


async def _names(db, ids) -> dict:
    ids = [i for i in set(ids) if i]
    if not ids:
        return {}
    return dict((await db.execute(select(SavedBusiness.id, SavedBusiness.business_name).where(SavedBusiness.id.in_(ids)))).all())


async def _add_reminders(db, ctx, m: Meeting, reminders: List[ReminderIn]):
    for r in reminders:
        when = _aware(m.start_at) - timedelta(minutes=max(0, r.minutes_before))
        recipient = r.recipient or (ctx.user.email if r.channel == "email" else m.attendee_phone if r.channel == "whatsapp" else None)
        db.add(Reminder(workspace_id=ctx.workspace.id, meeting_id=m.id, remind_at=when, channel=r.channel,
                        recipient=recipient, message=r.message))


# â”€â”€ Meetings â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("")
async def list_meetings(start: Optional[datetime] = None, end: Optional[datetime] = None, status: Optional[str] = None,
                        business_id: Optional[str] = None, db: AsyncSession = Depends(get_db),
                        ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    q = select(Meeting).where(Meeting.workspace_id == ctx.workspace.id)
    if start:
        q = q.where(Meeting.start_at >= _aware(start))
    if end:
        q = q.where(Meeting.start_at <= _aware(end))
    if status:
        q = q.where(Meeting.status == status)
    if business_id:
        q = q.where(Meeting.business_id == uuid.UUID(business_id))
    rows = (await db.execute(q.order_by(Meeting.start_at))).scalars().all()
    rem = (await db.execute(select(Reminder).where(Reminder.meeting_id.in_([m.id for m in rows])))).scalars().all() if rows else []
    by_m = {}
    for r in rem:
        by_m.setdefault(r.meeting_id, []).append(r)
    names = await _names(db, [m.business_id for m in rows])
    return {"meetings": [_m(m, names, by_m.get(m.id)) for m in rows]}


@router.get("/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    now = datetime.now(timezone.utc)
    start_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    upcoming = (await db.execute(select(Meeting).where(Meeting.workspace_id == ctx.workspace.id, Meeting.status == "scheduled",
                                                       Meeting.start_at >= start_day).order_by(Meeting.start_at).limit(10))).scalars().all()
    fus = (await db.execute(select(FollowUp).where(FollowUp.workspace_id == ctx.workspace.id, FollowUp.status == "pending")
                            .order_by(FollowUp.due_at))).scalars().all()
    steps = (await db.execute(select(NextStep).where(NextStep.workspace_id == ctx.workspace.id, NextStep.done == False)  # noqa: E712
                              .order_by(NextStep.due_date.nulls_last()).limit(20))).scalars().all()
    names = await _names(db, [m.business_id for m in upcoming] + [f.business_id for f in fus] + [s.business_id for s in steps])
    fl = [_f(f, names) for f in fus]
    by_m = {}
    if upcoming:
        for r in (await db.execute(select(Reminder).where(Reminder.meeting_id.in_([m.id for m in upcoming])))).scalars().all():
            by_m.setdefault(r.meeting_id, []).append(r)
    return {"upcoming_meetings": [_m(m, names, by_m.get(m.id)) for m in upcoming],
            "follow_ups": {"overdue": [f for f in fl if f["bucket"] == "overdue"], "today": [f for f in fl if f["bucket"] == "today"],
                           "upcoming": [f for f in fl if f["bucket"] == "upcoming"][:20]},
            "next_steps": [_n(s, names) for s in steps]}


@router.post("/reminders/run-due")
async def run_due(ctx: WorkspaceContext = Depends(require_permission("meetings:write"))):
    """Cron hook: deliver all due reminders now (the in-process loop also does this every minute)."""
    return {"delivered": await process_due_reminders(), "no_reply_alerts": await detect_no_reply()}


@router.get("/slots")
async def free_slots(day: date, duration_minutes: int = 30, start_hour: int = 9, end_hour: int = 18, tz_offset_minutes: int = 0,
                     db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    """Calendar integration: bookable slots for a day (local working hours), excluding existing meetings."""
    local_start = datetime(day.year, day.month, day.day, start_hour, tzinfo=timezone.utc) - timedelta(minutes=tz_offset_minutes)
    local_end = datetime(day.year, day.month, day.day, end_hour, tzinfo=timezone.utc) - timedelta(minutes=tz_offset_minutes)
    busy = (await db.execute(select(Meeting).where(Meeting.workspace_id == ctx.workspace.id, Meeting.status == "scheduled",
                                                   Meeting.start_at < local_end, Meeting.end_at > local_start))).scalars().all()
    slots, t = [], local_start
    step = timedelta(minutes=max(15, duration_minutes))
    while t + step <= local_end:
        clash = any(_aware(m.start_at) < t + step and _aware(m.end_at or m.start_at) > t for m in busy)
        if t > datetime.now(timezone.utc) and not clash:
            slots.append({"start": t.isoformat(), "end": (t + step).isoformat()})
        t += step
    return {"day": day.isoformat(), "duration_minutes": duration_minutes, "slots": slots, "busy": len(busy)}


@router.get("/timeline/{business_id}")
async def timeline(business_id: str, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    """Historical discussion timeline for a lead: messages, meetings, follow-ups and next steps in one feed."""
    from app.models.channel import ChannelMessage, TrackedEmail
    b = await _business(db, ctx, business_id)
    ev = []
    for m in (await db.execute(select(ChannelMessage).where(ChannelMessage.business_id == b.id))).scalars().all():
        ev.append({"at": m.created_at.isoformat(), "type": f"{m.channel}_{m.direction}", "title": m.subject or f"{m.channel} {m.direction}",
                   "detail": (m.body or "")[:300], "status": m.status})
    for t in (await db.execute(select(TrackedEmail).where(TrackedEmail.business_id == b.id))).scalars().all():
        if t.first_opened_at:
            ev.append({"at": t.first_opened_at.isoformat(), "type": "email_opened", "title": f"Opened: {t.subject}",
                       "detail": f"{t.open_count} opens, {t.click_count} clicks", "status": t.status})
    for m in (await db.execute(select(Meeting).where(Meeting.business_id == b.id))).scalars().all():
        ev.append({"at": m.start_at.isoformat(), "type": "meeting", "title": m.title, "detail": m.outcome or m.notes or "", "status": m.status})
    for f in (await db.execute(select(FollowUp).where(FollowUp.business_id == b.id))).scalars().all():
        ev.append({"at": f.due_at.isoformat(), "type": "follow_up", "title": f.title, "detail": f.notes or "", "status": f.status})
    for s_ in (await db.execute(select(NextStep).where(NextStep.business_id == b.id))).scalars().all():
        ev.append({"at": (s_.created_at or datetime.now(timezone.utc)).isoformat(), "type": "next_step", "title": s_.title,
                   "detail": s_.stage or "", "status": "done" if s_.done else "open"})
    if b.notes:
        ev.append({"at": b.created_at.isoformat(), "type": "note", "title": "Lead saved", "detail": b.notes[:300], "status": ""})
    return {"business_id": str(b.id), "business_name": b.business_name, "events": sorted(ev, key=lambda e: e["at"], reverse=True)}


@router.post("")
async def create_meeting(body: MeetingIn, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("meetings:write"))):
    b = await _business(db, ctx, body.business_id)
    start = _aware(body.start_at)
    m = Meeting(workspace_id=ctx.workspace.id, business_id=b.id if b else None, created_by=ctx.user.id,
                title=security_manager.sanitize_text(body.title, 200), start_at=start,
                end_at=_aware(body.end_at) or start + timedelta(minutes=body.duration_minutes), timezone=body.timezone,
                location=body.location, meeting_link=body.meeting_link, attendee_name=body.attendee_name,
                attendee_email=body.attendee_email or (b.email if b else None), attendee_phone=body.attendee_phone or (b.phone if b else None),
                notes=body.notes, status="scheduled")
    db.add(m)
    await db.flush()
    await _add_reminders(db, ctx, m, body.reminders)
    if b:
        p = await db.get(LeadProfile, b.id)
        if p:
            p.status = "meeting"
        else:
            db.add(LeadProfile(business_id=b.id, workspace_id=ctx.workspace.id, status="meeting", tags=[]))
    db.add(Notification(workspace_id=ctx.workspace.id, user_id=ctx.user.id, title="Meeting scheduled",
                        body=f"{m.title} on {start.strftime('%d %b %Y %H:%M')} UTC", link="/meetings"))
    await db.commit()
    rem = (await db.execute(select(Reminder).where(Reminder.meeting_id == m.id))).scalars().all()
    return _m(m, {m.business_id: b.business_name} if b else {}, rem)


@router.get("/{meeting_id}")
async def get_meeting(meeting_id: str, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    m = ctx.ensure(await db.get(Meeting, uuid.UUID(meeting_id)), "Meeting")
    rem = (await db.execute(select(Reminder).where(Reminder.meeting_id == m.id))).scalars().all()
    steps = (await db.execute(select(NextStep).where(NextStep.meeting_id == m.id))).scalars().all()
    data = _m(m, await _names(db, [m.business_id]), rem)
    data["next_steps"] = [_n(s) for s in steps]
    return data


@router.put("/{meeting_id}")
async def update_meeting(meeting_id: str, body: MeetingUpdate, db: AsyncSession = Depends(get_db),
                         ctx: WorkspaceContext = Depends(require_permission("meetings:write"))):
    m = ctx.ensure(await db.get(Meeting, uuid.UUID(meeting_id)), "Meeting")
    data = body.model_dump(exclude_unset=True)
    old_start = _aware(m.start_at)
    for k, v in data.items():
        setattr(m, k, _aware(v) if isinstance(v, datetime) else v)
    if "start_at" in data and _aware(m.start_at) != old_start:  # re-time pending reminders
        delta = _aware(m.start_at) - old_start
        for r in (await db.execute(select(Reminder).where(Reminder.meeting_id == m.id, Reminder.sent == False))).scalars().all():  # noqa: E712
            r.remind_at = _aware(r.remind_at) + delta
    await db.commit()
    return _m(m)


@router.delete("/{meeting_id}")
async def delete_meeting(meeting_id: str, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("meetings:write"))):
    m = ctx.ensure(await db.get(Meeting, uuid.UUID(meeting_id)), "Meeting")
    await db.delete(m)
    await db.commit()
    return {"message": "deleted"}


@router.get("/{meeting_id}/ics")
async def meeting_ics(meeting_id: str, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    m = ctx.ensure(await db.get(Meeting, uuid.UUID(meeting_id)), "Meeting")
    return Response(build_ics(m, ctx.user.email), media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="meeting-{m.id}.ics"'})


@router.post("/{meeting_id}/reminders")
async def add_reminder(meeting_id: str, body: ReminderIn, db: AsyncSession = Depends(get_db),
                       ctx: WorkspaceContext = Depends(require_permission("meetings:write"))):
    m = ctx.ensure(await db.get(Meeting, uuid.UUID(meeting_id)), "Meeting")
    await _add_reminders(db, ctx, m, [body])
    await db.commit()
    return {"message": "Reminder added"}


@router.delete("/reminders/{reminder_id}")
async def delete_reminder(reminder_id: str, db: AsyncSession = Depends(get_db),
                          ctx: WorkspaceContext = Depends(require_permission("meetings:write"))):
    r = ctx.ensure(await db.get(Reminder, uuid.UUID(reminder_id)), "Reminder")
    await db.delete(r)
    await db.commit()
    return {"message": "deleted"}


@router.post("/{meeting_id}/complete")
async def complete_meeting(meeting_id: str, body: CompleteIn, db: AsyncSession = Depends(get_db),
                           ctx: WorkspaceContext = Depends(require_permission("meetings:write"))):
    m = ctx.ensure(await db.get(Meeting, uuid.UUID(meeting_id)), "Meeting")
    m.status, m.outcome = body.status, body.outcome
    for title in [t for t in body.next_steps if t.strip()]:
        db.add(NextStep(workspace_id=ctx.workspace.id, business_id=m.business_id, meeting_id=m.id, title=title.strip(),
                        owner=ctx.user.full_name))
    fu = None
    if body.follow_up_in_days:
        due = datetime.now(timezone.utc) + timedelta(days=body.follow_up_in_days)
        fu = FollowUp(workspace_id=ctx.workspace.id, business_id=m.business_id, meeting_id=m.id,
                      title=body.follow_up_title or f"Follow up after: {m.title}", due_at=due)
        db.add(fu)
        await db.flush()
        db.add(Reminder(workspace_id=ctx.workspace.id, follow_up_id=fu.id, remind_at=due, channel="in_app"))
    await db.commit()
    return {"meeting": _m(m), "follow_up_id": str(fu.id) if fu else None}


# â”€â”€ Follow-up tracker â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@followups_router.get("")
async def list_followups(status: Optional[str] = None, bucket: Optional[str] = None, business_id: Optional[str] = None,
                         db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    q = select(FollowUp).where(FollowUp.workspace_id == ctx.workspace.id)
    if status:
        q = q.where(FollowUp.status == status)
    if business_id:
        q = q.where(FollowUp.business_id == uuid.UUID(business_id))
    rows = (await db.execute(q.order_by(FollowUp.due_at))).scalars().all()
    names = await _names(db, [f.business_id for f in rows])
    items = [_f(f, names) for f in rows]
    if bucket:
        items = [i for i in items if i["bucket"] == bucket]
    counts = {b: sum(1 for i in items if i["bucket"] == b) for b in ("overdue", "today", "upcoming", "done")}
    return {"follow_ups": items, "counts": counts}


@followups_router.post("")
async def create_followup(body: FollowUpIn, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("meetings:write"))):
    b = await _business(db, ctx, body.business_id)
    f = FollowUp(workspace_id=ctx.workspace.id, business_id=b.id if b else None,
                 meeting_id=uuid.UUID(body.meeting_id) if body.meeting_id else None, title=security_manager.sanitize_text(body.title, 200),
                 due_at=_aware(body.due_at), channel=body.channel, notes=body.notes)
    db.add(f)
    await db.flush()
    if body.remind:
        db.add(Reminder(workspace_id=ctx.workspace.id, follow_up_id=f.id, remind_at=_aware(body.due_at), channel="in_app"))
    await db.commit()
    return _f(f, {f.business_id: b.business_name} if b else {})


@followups_router.put("/{fid}")
async def update_followup(fid: str, body: FollowUpUpdate, db: AsyncSession = Depends(get_db),
                          ctx: WorkspaceContext = Depends(require_permission("meetings:write"))):
    f = ctx.ensure(await db.get(FollowUp, uuid.UUID(fid)), "Follow-up")
    data = body.model_dump(exclude_unset=True)
    if data.get("snooze_days"):
        f.due_at = max(_aware(f.due_at), datetime.now(timezone.utc)) + timedelta(days=data["snooze_days"])
        await db.execute(update(Reminder).where(Reminder.follow_up_id == f.id, Reminder.sent == False).values(remind_at=f.due_at))  # noqa: E712
    for k in ("title", "notes"):
        if k in data:
            setattr(f, k, data[k])
    if "due_at" in data and data["due_at"]:
        f.due_at = _aware(data["due_at"])
    if data.get("status"):
        f.status = data["status"]
        f.completed_at = datetime.now(timezone.utc) if f.status == "done" else None
    await db.commit()
    return _f(f)


@followups_router.delete("/{fid}")
async def delete_followup(fid: str, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("meetings:write"))):
    f = ctx.ensure(await db.get(FollowUp, uuid.UUID(fid)), "Follow-up")
    await db.delete(f)
    await db.commit()
    return {"message": "deleted"}


# â”€â”€ Next steps â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@next_steps_router.get("")
async def list_steps(business_id: Optional[str] = None, include_done: bool = False, db: AsyncSession = Depends(get_db),
                     ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    q = select(NextStep).where(NextStep.workspace_id == ctx.workspace.id)
    if business_id:
        q = q.where(NextStep.business_id == uuid.UUID(business_id))
    if not include_done:
        q = q.where(NextStep.done == False)  # noqa: E712
    rows = (await db.execute(q.order_by(NextStep.created_at.desc()))).scalars().all()
    names = await _names(db, [s.business_id for s in rows])
    return {"next_steps": [_n(s, names) for s in rows]}


@next_steps_router.post("")
async def create_step(body: NextStepIn, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("meetings:write"))):
    b = await _business(db, ctx, body.business_id)
    s = NextStep(workspace_id=ctx.workspace.id, business_id=b.id if b else None,
                 meeting_id=uuid.UUID(body.meeting_id) if body.meeting_id else None,
                 title=security_manager.sanitize_text(body.title, 200), owner=body.owner or ctx.user.full_name,
                 due_date=body.due_date, stage=body.stage)
    db.add(s)
    await db.commit()
    return _n(s, {s.business_id: b.business_name} if b else {})


@next_steps_router.put("/{sid}")
async def update_step(sid: str, body: NextStepUpdate, db: AsyncSession = Depends(get_db),
                      ctx: WorkspaceContext = Depends(require_permission("meetings:write"))):
    s = ctx.ensure(await db.get(NextStep, uuid.UUID(sid)), "Next step")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    await db.commit()
    return _n(s)


@next_steps_router.delete("/{sid}")
async def delete_step(sid: str, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("meetings:write"))):
    s = ctx.ensure(await db.get(NextStep, uuid.UUID(sid)), "Next step")
    await db.delete(s)
    await db.commit()
    return {"message": "deleted"}


# â”€â”€ Notifications â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@notifications_router.get("")
async def list_notifications(unread_only: bool = False, db: AsyncSession = Depends(get_db),
                             ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    q = select(Notification).where(Notification.workspace_id == ctx.workspace.id,
                                   (Notification.user_id == ctx.user.id) | (Notification.user_id.is_(None)))
    if unread_only:
        q = q.where(Notification.read == False)  # noqa: E712
    rows = (await db.execute(q.order_by(Notification.created_at.desc()).limit(50))).scalars().all()
    return {"unread": sum(1 for n in rows if not n.read),
            "notifications": [{"id": str(n.id), "title": n.title, "body": n.body, "link": n.link, "read": n.read,
                               "created_at": n.created_at.isoformat() if n.created_at else None} for n in rows]}


@notifications_router.post("/read-all")
async def read_all(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    await db.execute(update(Notification).where(Notification.workspace_id == ctx.workspace.id,
                                                (Notification.user_id == ctx.user.id) | (Notification.user_id.is_(None))).values(read=True))
    await db.commit()
    return {"message": "ok"}


@notifications_router.put("/{nid}/read")
async def read_one(nid: str, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    n = ctx.ensure(await db.get(Notification, uuid.UUID(nid)), "Notification")
    n.read = True
    await db.commit()
    return {"message": "ok"}

