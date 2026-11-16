from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api import deps
from app.core.security import security_manager as security  # the one SecurityManager
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, User as UserSchema
from app.schemas.auth import Token, AuthResponse, Login
from app.services.email.verification import send_verification_email

router = APIRouter()

@router.post("/signup", response_model=dict)
async def signup(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Module 1 - Create an Account.
    Creates the user, their own workspace (tenant) with a Free subscription, and joins an
    invited workspace when an invite token is supplied. Email verification is enforced when
    REQUIRE_EMAIL_VERIFICATION=true and Resend is configured; otherwise the account is active at once.
    """
    if not settings.ALLOW_PUBLIC_SIGNUP:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Public sign up is disabled")

    existing = (await db.execute(select(User).where(User.email == user_in.email))).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    from app.services.email.resend_sender import is_configured as resend_ready
    needs_verification = bool(settings.REQUIRE_EMAIL_VERIFICATION and resend_ready())

    user = User(
        full_name=user_in.full_name.strip(),
        email=user_in.email.lower(),
        hashed_password=security.hash_password(user_in.password),
        is_verified=not needs_verification,
        is_active=True,
        role="user",
        plan="free",
        plan_started_at=datetime.now(timezone.utc),
    )
    if needs_verification:
        user.verification_token = security.generate_verification_token()
        user.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    from app.api.tenancy import create_workspace
    from app.models.workspace import WorkspaceInvite, WorkspaceMember
    ws = await create_workspace(db, user, (user_in.workspace_name or f"{user.full_name.split(' ')[0]}'s Workspace").strip())

    joined_workspace_id = None
    if user_in.invite_token:
        invite = (await db.execute(select(WorkspaceInvite).where(
            WorkspaceInvite.token == user_in.invite_token, WorkspaceInvite.accepted == False  # noqa: E712
        ))).scalars().first()
        if invite and invite.email.lower() == user.email:
            db.add(WorkspaceMember(workspace_id=invite.workspace_id, user_id=user.id, role=invite.role))
            invite.accepted = True
            await db.commit()
            joined_workspace_id = str(invite.workspace_id)

    if needs_verification:
        send_verification_email(user.email, user.verification_token, settings.FRONTEND_URL)
        return {"message": "Account created. Check your email to verify it.", "requires_verification": True,
                "workspace_id": str(ws.id)}

    token = security.create_access_token(user.id, expires_delta=timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES))
    return {
        "message": "Account created",
        "requires_verification": False,
        "token": token,
        "user": UserSchema.model_validate(user).model_dump(mode="json"),
        "workspace_id": joined_workspace_id or str(ws.id),
    }

@router.post("/login", response_model=AuthResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
) -> Any:
    # Find user
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalars().first()
    
    # Verify
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    elif not user.is_verified:
        raise HTTPException(status_code=400, detail="Email not verified")
        
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        user.id, expires_delta=access_token_expires
    )
    
    return {
        "token": access_token,
        "user": UserSchema.model_validate(user)
    }

@router.post("/login/json", response_model=AuthResponse)
async def login_json(
    login_data: Login,
    db: AsyncSession = Depends(get_db)
) -> Any:
    # Find user
    result = await db.execute(select(User).where(User.email == login_data.email))
    user = result.scalars().first()
    
    # Verify
    if not user or not security.verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    elif not user.is_verified:
        raise HTTPException(status_code=400, detail="Email not verified")
        
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        user.id, expires_delta=access_token_expires
    )
    
    return {
        "token": access_token,
        "user": UserSchema.model_validate(user)
    }

@router.get("/verify-email", response_model=dict)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
) -> Any:
    result = await db.execute(select(User).where(User.verification_token == token))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")
        
    if user.token_expires_at and user.token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")
        
    user.is_verified = True
    user.verification_token = None
    user.token_expires_at = None
    await db.commit()
    
    return {"message": "Email verified successfully"}

@router.get("/me", response_model=UserSchema)
async def get_current_user(
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    return UserSchema.model_validate(current_user)

@router.post("/select-plan", response_model=UserSchema)
async def select_plan(
    plan: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    if plan not in ["individual", "team"]:
        raise HTTPException(status_code=400, detail="Invalid plan")
        
    current_user.plan = plan
    current_user.plan_started_at = datetime.now(timezone.utc)
    
    if plan == "individual":
        current_user.plan_expires_at = datetime.now(timezone.utc) + timedelta(days=90)
    elif plan == "team":
        current_user.plan_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
    await db.commit()
    await db.refresh(current_user)
    
    return UserSchema.model_validate(current_user)

@router.delete("/me", response_model=dict)
async def delete_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """Delete the current user account and all associated data."""
    await db.delete(current_user)
    await db.commit()
    return {"message": "Account deleted successfully"}

