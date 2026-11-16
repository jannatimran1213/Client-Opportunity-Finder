"""
API v1 Router - Combines all endpoint routers
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    osm_sources,
    audits,
    businesses,
    outreach,
    campaigns,
    mail_chat,
    health,
    auth,
    pricing,
    admin,
    email_accounts,
    # â”€â”€ 32-feature release â”€â”€
    workspaces,
    billing,
    finder,
    leads,
    advanced_audits,
    copywriter,
    channels,
    meetings,
    builder,
    jobs,
)

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(pricing.router, prefix="/pricing", tags=["Pricing"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(osm_sources.router, prefix="/osm", tags=["OSM Business Search"])
api_router.include_router(audits.router, prefix="/audits", tags=["Website Audits"])
api_router.include_router(businesses.router, prefix="/businesses", tags=["Businesses"])
api_router.include_router(outreach.router, prefix="/outreach", tags=["Email Outreach"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"])
api_router.include_router(mail_chat.router, prefix="/mail", tags=["Mail & Chat"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])

# Module 1 - Sign Up & SaaS Access
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["1. Workspaces & RBAC"])
api_router.include_router(billing.router, prefix="/billing", tags=["1. Subscription Engine"])
# Module 2 - Custom Business Finder
api_router.include_router(finder.router, prefix="/finder", tags=["2. Business Finder"])
# Module 3 - Lead Management
api_router.include_router(leads.router, prefix="/leads", tags=["3. Lead Management"])
# Module 4 - Advanced Audit
api_router.include_router(advanced_audits.router, prefix="/advanced-audits", tags=["4. Advanced Audit"])
# Module 5 - AI Copywriter
api_router.include_router(copywriter.router, prefix="/copywriter", tags=["5. AI Copywriter"])
# Module 6 - Multi-Channel Send (+ Gmail / SMTP connections)
api_router.include_router(email_accounts.router, prefix="/email-accounts", tags=["6. Email Accounts"])
api_router.include_router(channels.router, prefix="/channels", tags=["6. Multi-Channel Send"])
api_router.include_router(channels.public_router, prefix="/track", tags=["6. Tracking Pixel (public)"])
# Module 7 - Schedule Meeting
api_router.include_router(meetings.router, prefix="/meetings", tags=["7. Meetings"])
api_router.include_router(meetings.followups_router, prefix="/follow-ups", tags=["7. Follow-up Tracker"])
api_router.include_router(meetings.next_steps_router, prefix="/next-steps", tags=["7. Next Steps"])
api_router.include_router(meetings.notifications_router, prefix="/notifications", tags=["7. Notifications"])
# Background jobs (Celery + Redis, in-process fallback)
api_router.include_router(jobs.router, prefix="/jobs", tags=["Background jobs (Celery)"])
# Module 8 - Drag-and-Drop Builder
api_router.include_router(builder.router, prefix="/builder", tags=["8. Builder"])
api_router.include_router(builder.public_router, prefix="/sites", tags=["8. Hosted sites (public)"])

