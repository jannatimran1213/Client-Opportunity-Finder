"""
Module 1 - Multi-Tenant Workspace + Role-Based Access Control endpoints.
"""
import secrets
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.api.tenancy import WorkspaceContext, create_workspace, get_workspace_context, require_permission
from app.core.config import settings
from app.core.security import security_manager

ROLES = security_manager.ROLES
ROLE_DESCRIPTIONS = security_manager.ROLE_DESCRIPTIONS
ALL_PERMISSIONS = security_manager.all_permissions
can_assign = security_manager.can_assign_role
permission_matrix = security_manager.permission_matrix
from app.db.session import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceInvite, WorkspaceMember
from app.services.billing.plans import enforce_limit

router = APIRouter()


class WorkspaceCreate(BaseModel):
    name: str


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    company_name: Optional[str] = None
    company_website: Optional[str] = None
    services: Optional[str] = None
    settings: Optional[dict] = None


class InviteIn(BaseModel):
    email: EmailStr
    role: str = "member"


class RoleIn(BaseModel):
    role: str


class AcceptIn(BaseModel):
    token: str


def _ws(ws: Workspace, role: Optional[str] = None) -> dict:
    return {
        "id": str(ws.id), "name": ws.name, "slug": ws.slug, "owner_id": str(ws.owner_id),
        "company_name": ws.company_name, "company_website": ws.company_website, "services": ws.services,
        "settings": ws.settings or {}, "role": role,
        "created_at": ws.created_at.isoformat() if ws.created_at else None,
    }


@router.get("")
async def list_my_workspaces(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    rows = (await db.execute(
        select(WorkspaceMember, Workspace).join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == user.id).order_by(WorkspaceMember.created_at)
    )).all()
    if not rows:  # first visit after upgrade: give the user a personal workspace
        ws = await create_workspace(db, user, f"{user.full_name.split(' ')[0]}'s Workspace")
        return {"workspaces": [_ws(ws, "owner")]}
    return {"workspaces": [_ws(ws, m.role) for m, ws in rows]}


@router.post("")
async def create_new_workspace(body: WorkspaceCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    ws = await create_workspace(db, user, body.name.strip() or "New Workspace")
    return _ws(ws, "owner")


@router.get("/current")
async def current_workspace(ctx: WorkspaceContext = Depends(get_workspace_context)):
    data = _ws(ctx.workspace, ctx.role)
    data["permissions"] = [p for p in ALL_PERMISSIONS if ctx.can(p)]
    return data


@router.put("/current")
async def update_workspace(body: WorkspaceUpdate, db: AsyncSession = Depends(get_db),
                           ctx: WorkspaceContext = Depends(require_permission("workspace:manage"))):
    ws = ctx.workspace
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(ws, k, v)
    db.add(ws)
    await db.commit()
    await db.refresh(ws)
    return _ws(ws, ctx.role)


@router.delete("/current")
async def delete_workspace(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)):
    if ctx.role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can delete a workspace")
    count = (await db.execute(select(func.count()).select_from(WorkspaceMember).where(WorkspaceMember.user_id == ctx.user.id))).scalar()
    if count <= 1:
        raise HTTPException(status_code=400, detail="You cannot delete your only workspace")
    ws = await db.get(Workspace, ctx.workspace.id)
    await db.delete(ws)
    await db.commit()
    return {"message": "Workspace deleted"}


@router.get("/roles")
async def roles():
    """RBAC catalogue: roles, what they mean, and the full permission matrix."""
    return {"roles": [{"role": r, "description": ROLE_DESCRIPTIONS[r]} for r in ROLES],
            "permissions": ALL_PERMISSIONS, "matrix": permission_matrix()}


@router.get("/members")
async def list_members(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)):
    rows = (await db.execute(
        select(WorkspaceMember, User).join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == ctx.workspace.id).order_by(WorkspaceMember.created_at)
    )).all()
    invites = (await db.execute(select(WorkspaceInvite).where(
        WorkspaceInvite.workspace_id == ctx.workspace.id, WorkspaceInvite.accepted == False  # noqa: E712
    ))).scalars().all()
    # Workspace management: monitor each team member's activity in this workspace
    from app.models.saved_business import SavedBusiness
    from app.models.meeting import Meeting
    lead_stats = dict((uid, (n, last)) for uid, n, last in (await db.execute(
        select(SavedBusiness.user_id, func.count(), func.max(SavedBusiness.created_at))
        .where(SavedBusiness.workspace_id == ctx.workspace.id).group_by(SavedBusiness.user_id))).all())
    meet_stats = dict((uid, (n, last)) for uid, n, last in (await db.execute(
        select(Meeting.created_by, func.count(), func.max(Meeting.created_at))
        .where(Meeting.workspace_id == ctx.workspace.id).group_by(Meeting.created_by))).all())

    def activity(uid):
        l, mt = lead_stats.get(uid, (0, None)), meet_stats.get(uid, (0, None))
        last = max([d for d in (l[1], mt[1]) if d] or [None]) if (l[1] or mt[1]) else None
        return {"leads_added": l[0], "meetings_booked": mt[0], "last_activity": last.isoformat() if last else None}

    return {
        "members": [{"id": str(m.id), "user_id": str(u.id), "full_name": u.full_name, "email": u.email,
                     "role": m.role, "joined_at": m.created_at.isoformat() if m.created_at else None,
                     "is_active": u.is_active, **activity(u.id)} for m, u in rows],
        "pending_invites": [{"id": str(i.id), "email": i.email, "role": i.role,
                             "invite_link": f"{settings.FRONTEND_URL}/signup?invite={i.token}&email={i.email}"} for i in invites],
        "my_role": ctx.role,
    }


@router.post("/members/invite")
async def invite_member(body: InviteIn, db: AsyncSession = Depends(get_db),
                        ctx: WorkspaceContext = Depends(require_permission("members:manage"))):
    if body.role not in ROLES or body.role == "owner":
        raise HTTPException(status_code=400, detail="Role must be admin, member or viewer")
    if not can_assign(ctx.role if ctx.user.role != "admin" else "owner", body.role):
        raise HTTPException(status_code=403, detail="You cannot assign this role")
    member_count = (await db.execute(select(func.count()).select_from(WorkspaceMember).where(
        WorkspaceMember.workspace_id == ctx.workspace.id))).scalar()
    await enforce_limit(db, ctx.workspace.id, "members", current=member_count)

    email = body.email.lower()
    existing_user = (await db.execute(select(User).where(User.email == email))).scalars().first()
    if existing_user:
        already = (await db.execute(select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ctx.workspace.id, WorkspaceMember.user_id == existing_user.id))).scalars().first()
        if already:
            raise HTTPException(status_code=400, detail="This person is already a member")
        db.add(WorkspaceMember(workspace_id=ctx.workspace.id, user_id=existing_user.id, role=body.role))
        await db.commit()
        return {"status": "added", "message": f"{email} added as {body.role}"}

    token = secrets.token_urlsafe(24)
    db.add(WorkspaceInvite(workspace_id=ctx.workspace.id, email=email, role=body.role, token=token, invited_by=ctx.user.id))
    await db.commit()
    link = f"{settings.FRONTEND_URL}/signup?invite={token}&email={email}"
    sent = False
    try:
        from app.services.email.resend_sender import is_configured, send_email
        if is_configured():
            res = send_email(to_email=email, subject=f"You're invited to {ctx.workspace.name}",
                             body=f"{ctx.user.full_name} invited you to join {ctx.workspace.name}. Accept: {link}",
                             html_body=f"<p>{ctx.user.full_name} invited you to join <b>{ctx.workspace.name}</b>.</p><p><a href='{link}'>Accept invite</a></p>")
            sent = bool(res.get("success"))
    except Exception:
        sent = False
    return {"status": "invited", "invite_link": link, "email_sent": sent}


@router.post("/invites/accept")
async def accept_invite(body: AcceptIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    invite = (await db.execute(select(WorkspaceInvite).where(WorkspaceInvite.token == body.token))).scalars().first()
    if not invite or invite.accepted:
        raise HTTPException(status_code=404, detail="Invite not found or already used")
    if invite.email.lower() != user.email.lower():
        raise HTTPException(status_code=403, detail="This invite was sent to a different email")
    db.add(WorkspaceMember(workspace_id=invite.workspace_id, user_id=user.id, role=invite.role))
    invite.accepted = True
    await db.commit()
    return {"workspace_id": str(invite.workspace_id), "role": invite.role}


@router.delete("/invites/{invite_id}")
async def revoke_invite(invite_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        ctx: WorkspaceContext = Depends(require_permission("members:manage"))):
    inv = await db.get(WorkspaceInvite, invite_id)
    if not inv or inv.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Invite not found")
    await db.delete(inv)
    await db.commit()
    return {"message": "Invite revoked"}


@router.put("/members/{member_id}/role")
async def change_role(member_id: uuid.UUID, body: RoleIn, db: AsyncSession = Depends(get_db),
                      ctx: WorkspaceContext = Depends(require_permission("members:manage"))):
    member = await db.get(WorkspaceMember, member_id)
    if not member or member.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Member not found")
    actor = "owner" if ctx.user.role == "admin" else ctx.role
    if member.role == "owner" or not can_assign(actor, body.role):
        raise HTTPException(status_code=403, detail="You cannot change this member to that role")
    member.role = body.role
    await db.commit()
    return {"id": str(member.id), "role": member.role}


@router.delete("/members/{member_id}")
async def remove_member(member_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        ctx: WorkspaceContext = Depends(get_workspace_context)):
    member = await db.get(WorkspaceMember, member_id)
    if not member or member.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="Member not found")
    leaving_self = member.user_id == ctx.user.id
    if not leaving_self and not ctx.can("members:manage"):
        raise HTTPException(status_code=403, detail="Not allowed")
    if member.role == "owner":
        raise HTTPException(status_code=400, detail="The owner cannot be removed")
    await db.delete(member)
    await db.commit()
    return {"message": "Member removed"}

