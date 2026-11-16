from app.db.base import Base
from app.models.user import User
from app.models.pricing_plan import PricingPlan
from app.models.email_account import EmailAccount
from app.models.saved_business import SavedBusiness
from app.models.usage_log import UsageLog
from app.models.payment_history import PaymentHistory

# â”€â”€ 32-feature release models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceInvite          # Module 1
from app.models.subscription import Subscription, WorkspaceUsage                     # Module 1
from app.models.search_job import SearchJob                                          # Module 2
from app.models.lead_list import LeadList, LeadListItem, LeadProfile                 # Module 3
from app.models.advanced_audit import AdvancedAudit, CompetitorBenchmark             # Module 4
from app.models.copy_draft import CopyDraft                                          # Module 5
from app.models.channel import ChannelMessage, LinkedInTask, TrackedEmail, TrackingEvent  # Module 6
from app.models.meeting import Meeting, Reminder, FollowUp, NextStep, Notification   # Module 7
from app.models.site_page import SitePage                                            # Module 8
from app.models.job import BackgroundJob                                             # Celery jobs

# Expose models for Alembic/SQLAlchemy to discover
__all__ = [
    "Base", "User", "PricingPlan", "EmailAccount", "SavedBusiness", "UsageLog", "PaymentHistory",
    "Workspace", "WorkspaceMember", "WorkspaceInvite", "Subscription", "WorkspaceUsage",
    "SearchJob", "LeadList", "LeadListItem", "LeadProfile", "AdvancedAudit", "CompetitorBenchmark",
    "CopyDraft", "ChannelMessage", "LinkedInTask", "TrackedEmail", "TrackingEvent",
    "Meeting", "Reminder", "FollowUp", "NextStep", "Notification", "SitePage", "BackgroundJob",
]

