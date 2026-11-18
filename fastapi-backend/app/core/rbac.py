"""
RBAC now lives in SecurityManager (app/core/security.py). Re-exported here for convenience.
"""
from app.core.security import security_manager

ROLES = security_manager.ROLES
ROLE_DESCRIPTIONS = security_manager.ROLE_DESCRIPTIONS
PERMISSIONS = security_manager.PERMISSIONS
ALL_PERMISSIONS = security_manager.all_permissions
has_permission = security_manager.has_permission
can_assign = security_manager.can_assign_role
permission_matrix = security_manager.permission_matrix

