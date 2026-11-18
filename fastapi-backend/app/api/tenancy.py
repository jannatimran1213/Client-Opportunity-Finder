"""
Module 1 - Multi-Tenant Workspace dependencies.

`get_workspace_context` resolves the active workspace from the `X-Workspace-Id` header
(falls back to the user's first workspace, creating a personal one on first use) and
`require_permission("leads:write")` enforces RBAC on any endpoint.
"""
import re
import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.security import security_manager
from app.db.session import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.subscription import Subscription
from app.models.saved_business import SavedBusiness


@dataclass
class WorkspaceContext:
    user: User
    workspace: Workspace
    role: str

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.workspace.id

    def can(self, permission: str) -> bool:
        return security_manager.user_can(self.user, self.role, permission)

    def ensure(self, obj, what: str = "Resource"):
        """Tenant isolation: 404 unless obj belongs to this workspace (SecurityManager)."""
        return security_manager.ensure_tenant(obj, self, what)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:50] or "workspace"


async def create_workspace(db: AsyncSession, owner: User, name: str) -> Workspace:
    base = slugify(name)
    slug = f"{base}-{uuid.uuid4().hex[:6]}"
    ws = Workspace(name=name, slug=slug, owner_id=owner.id, settings={})
    db.add(ws)
    await db.flush()
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=owner.id, role="owner"))
    from datetime import datetime, timedelta, timezone
    db.add(Subscription(workspace_id=ws.id, plan="basic", interval="monthly", status="trialing", billing_mode="test",
                        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14)))
    # Adopt any of the owner's leads saved before workspaces existed
    await db.execute(
        update(SavedBusiness)
        .where(SavedBusiness.user_id == owner.id, SavedBusiness.workspace_id.is_(None))
        .values(workspace_id=ws.id)
    )
    await db.commit()
    await db.refresh(ws)
    return ws


async def get_workspace_context(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    x_workspace_id: Optional[str] = Header(default=None, alias="X-Workspace-Id"),
) -> WorkspaceContext:
    query = (
        select(WorkspaceMember, Workspace)
        .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == current_user.id)
        .order_by(WorkspaceMember.created_at)
    )
    rows = (await db.execute(query)).all()

    if x_workspace_id:
        try:
            wanted = uuid.UUID(x_workspace_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-Workspace-Id header")
        for member, ws in rows:
            if ws.id == wanted:
                return WorkspaceContext(current_user, ws, member.role)
        if current_user.role == "admin":  # platform admin may enter any workspace
            ws = await db.get(Workspace, wanted)
            if ws:
                return WorkspaceContext(current_user, ws, "owner")
        raise HTTPException(status_code=403, detail="You are not a member of this workspace")

    if rows:
        member, ws = rows[0]
        return WorkspaceContext(current_user, ws, member.role)

    ws = await create_workspace(db, current_user, f"{current_user.full_name.split(' ')[0]}'s Workspace")
    return WorkspaceContext(current_user, ws, "owner")


def require_permission(permission: str):
    async def _checker(ctx: WorkspaceContext = Depends(get_workspace_context)) -> WorkspaceContext:
        if not ctx.can(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your role '{ctx.role}' does not allow '{permission}' in this workspace",
            )
        return ctx
    return _checker


def lead_scope(ctx: WorkspaceContext):
    """SQL filter for leads visible in the active workspace (legacy rows without a workspace stay with their owner)."""
    from sqlalchemy import and_, or_
    return or_(
        SavedBusiness.workspace_id == ctx.workspace.id,
        and_(SavedBusiness.workspace_id.is_(None), SavedBusiness.user_id == ctx.user.id),
    )

