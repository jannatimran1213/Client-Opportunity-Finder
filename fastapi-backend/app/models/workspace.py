"""
Module 1 - Multi-Tenant Workspace + Role-Based Access Control.

Every feature table added for the 32-feature release carries a workspace_id, so a
workspace (tenant) only ever sees its own data. Members join a workspace with a role
(owner / admin / member / viewer) that the RBAC layer (app/core/rbac.py) checks.
"""
from app.models._common import *  # noqa: F401,F403


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Branding / sender defaults used by the copywriter and builder
    company_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    company_website: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    services: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)

    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")


class WorkspaceMember(Base, TimestampMixin):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="member")  # owner | admin | member | viewer

    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User")


class WorkspaceInvite(Base, TimestampMixin):
    __tablename__ = "workspace_invites"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="member")
    token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    invited_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

