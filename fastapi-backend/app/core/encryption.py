"""
Encryption at rest now lives in SecurityManager (app/core/security.py).
This module only re-exports it so older imports keep working.
"""
from app.core.security import security_manager

encrypt = security_manager.encrypt
decrypt = security_manager.decrypt

