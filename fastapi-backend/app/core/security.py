"""
SecurityManager - the ONE class that owns every security concern in the platform.

    from app.core.security import security_manager

Responsibilities (all in this class, nowhere else):
  1. Passwords ............ hash_password / verify_password (bcrypt, 12 rounds) + password_strength
  2. Tokens ............... create_access_token / decode_access_token (JWT HS256), random tokens
  3. RBAC ................. ROLES / PERMISSIONS, has_permission, can_assign_role, permission_matrix
  4. Tenant isolation ..... assert_same_tenant / ensure_tenant (every workspace-scoped row is checked)
  5. Encryption at rest ... encrypt / decrypt (Fernet) for SMTP passwords, OAuth tokens, API keys
  6. Rate limiting ........ check_rate_limit (sliding window; used by RateLimitMiddleware)
  7. Input sanitisation ... sanitize_text, sanitize_html, sanitize_subdomain, is_safe_redirect_url
  8. Signatures ........... sign / verify_signature (tracking links), verify_stripe_signature,
                            verify_meta_signature (WhatsApp webhook)
  9. Website security audit inspect_ssl, audit_security_headers, security_score (Module 4 uses these)

Module-level names (verify_password, get_password_hash, create_access_token, encrypt, decrypt, ...)
are kept as aliases of the singleton's methods so older imports keep working.
"""
import base64
import hashlib
import hmac
import html as html_lib
import re
import secrets
import socket
import ssl
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from app.core.config import settings


class SecurityError(Exception):
    """Raised for tenant violations, bad signatures and other security failures."""

    def __init__(self, message: str, status_code: int = 403):
        super().__init__(message)
        self.status_code = status_code


class SecurityManager:
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
    BCRYPT_ROUNDS = 12

    # â”€â”€ RBAC catalogue â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    ROLES = ["owner", "admin", "member", "viewer"]
    ROLE_DESCRIPTIONS = {
        "owner": "Full control, including billing and deleting the workspace",
        "admin": "Manage members, settings, publish pages and send on every channel",
        "member": "Find, edit and contact leads, run audits, build pages, schedule meetings",
        "viewer": "Read-only access to leads, audits, meetings and reports",
    }
    PERMISSIONS: Dict[str, Set[str]] = {
        "owner": {"*"},
        "admin": {
            "workspace:manage", "members:manage", "billing:view",
            "leads:read", "leads:write", "leads:delete",
            "audits:run", "copy:generate", "outreach:send", "channels:manage",
            "meetings:write", "builder:write", "builder:publish",
        },
        "member": {
            "billing:view", "leads:read", "leads:write", "audits:run", "copy:generate",
            "outreach:send", "meetings:write", "builder:write",
        },
        "viewer": {"billing:view", "leads:read"},
    }

    # â”€â”€ Website security audit catalogue â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    SECURITY_HEADERS = {
        "strict-transport-security": ("HSTS", 20, "Add Strict-Transport-Security: max-age=31536000; includeSubDomains"),
        "content-security-policy": ("Content-Security-Policy", 20, "Define a Content-Security-Policy to block XSS / injected scripts"),
        "x-frame-options": ("X-Frame-Options", 15, "Add X-Frame-Options: SAMEORIGIN to prevent clickjacking"),
        "x-content-type-options": ("X-Content-Type-Options", 15, "Add X-Content-Type-Options: nosniff"),
        "referrer-policy": ("Referrer-Policy", 15, "Add Referrer-Policy: strict-origin-when-cross-origin"),
        "permissions-policy": ("Permissions-Policy", 15, "Add a Permissions-Policy to restrict camera/mic/geolocation"),
    }

    def __init__(self):
        self._fernet = self._build_fernet()
        self._rate_buckets: Dict[str, deque] = defaultdict(deque)
        self._rate_lock = threading.Lock()

    # â•â•â•â• 1. Passwords â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=self.BCRYPT_ROUNDS)).decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception:
            return False

    def password_strength(self, password: str) -> Dict[str, Any]:
        checks = {
            "length_8": len(password) >= 8,
            "upper": bool(re.search(r"[A-Z]", password)),
            "lower": bool(re.search(r"[a-z]", password)),
            "digit": bool(re.search(r"\d", password)),
            "symbol": bool(re.search(r"[^A-Za-z0-9]", password)),
        }
        score = sum(checks.values())
        return {"score": score, "strong": score >= 4 and checks["length_8"], "checks": checks}

    # â•â•â•â• 2. Tokens â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    def create_access_token(self, subject: Union[str, Any], expires_delta: Optional[timedelta] = None,
                            extra_claims: Optional[dict] = None) -> str:
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES))
        claims = {"exp": expire, "sub": str(subject)}
        if extra_claims:
            claims.update(extra_claims)
        return jwt.encode(claims, settings.SECRET_KEY, algorithm=self.ALGORITHM)

    def decode_access_token(self, token: str) -> Optional[dict]:
        """Returns the claims, or None when the token is invalid/expired."""
        try:
            return jwt.decode(token, settings.SECRET_KEY, algorithms=[self.ALGORITHM])
        except JWTError:
            return None

    def generate_token(self, nbytes: int = 32) -> str:
        return secrets.token_urlsafe(nbytes)

    def generate_verification_token(self) -> str:
        return self.generate_token(32)

    # â•â•â•â• 3. RBAC â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    @property
    def all_permissions(self) -> List[str]:
        return sorted({p for perms in self.PERMISSIONS.values() for p in perms if p != "*"} | {"billing:manage"})

    def has_permission(self, role: str, permission: str) -> bool:
        perms = self.PERMISSIONS.get(role, set())
        return "*" in perms or permission in perms

    def user_can(self, user: Any, role: str, permission: str) -> bool:
        """Platform admins (users.role == 'admin') pass every check."""
        if getattr(user, "role", None) == "admin":
            return True
        return self.has_permission(role, permission)

    def can_assign_role(self, actor_role: str, target_role: str) -> bool:
        if actor_role == "owner":
            return target_role in self.ROLES
        if actor_role == "admin":
            return target_role in ("member", "viewer")
        return False

    def permission_matrix(self) -> Dict[str, Dict[str, bool]]:
        return {r: {p: self.has_permission(r, p) for p in self.all_permissions} for r in self.ROLES}

    # â•â•â•â• 4. Tenant isolation â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    def assert_same_tenant(self, obj: Any, workspace_id: Any, what: str = "Resource") -> Any:
        """Raise 404 (not 403, to avoid leaking existence) if obj is missing or belongs to another workspace."""
        if obj is None or str(getattr(obj, "workspace_id", None)) != str(workspace_id):
            raise SecurityError(f"{what} not found", status_code=404)
        return obj

    def ensure_tenant(self, obj: Any, ctx: Any, what: str = "Resource") -> Any:
        return self.assert_same_tenant(obj, ctx.workspace.id, what)

    # â•â•â•â• 5. Encryption at rest â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    def _build_fernet(self) -> Fernet:
        raw_key = getattr(settings, "ENCRYPTION_KEY", None)
        if raw_key:
            return Fernet(raw_key.encode())
        digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def try_decrypt(self, ciphertext: str) -> Optional[str]:
        try:
            return self.decrypt(ciphertext)
        except (InvalidToken, Exception):
            return None

    def mask_secret(self, value: Optional[str], keep: int = 4) -> str:
        if not value:
            return ""
        return ("*" * max(len(value) - keep, 4)) + value[-keep:]

    # â•â•â•â• 6. Rate limiting â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        """Sliding-window limiter. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._rate_lock:
            bucket = self._rate_buckets[key]
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                return False, int(window_seconds - (now - bucket[0])) + 1
            bucket.append(now)
            return True, 0

    def reset_rate_limits(self) -> None:
        with self._rate_lock:
            self._rate_buckets.clear()

    # â•â•â•â• 7. Input sanitisation â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    _SCRIPT_RE = re.compile(r"<\s*(script|iframe|object|embed|style)[^>]*>.*?<\s*/\s*\1\s*>", re.I | re.S)
    _VOID_DANGER_RE = re.compile(r"<\s*(script|iframe|object|embed|link|meta)[^>]*?/?>", re.I)
    _EVENT_ATTR_RE = re.compile(r"\s+on[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
    _JS_URL_RE = re.compile(r"(href|src)\s*=\s*([\"'])\s*javascript:[^\"']*\2", re.I)

    def sanitize_text(self, value: Optional[str], max_length: int = 5000) -> str:
        if value is None:
            return ""
        value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value))
        return value.strip()[:max_length]

    def escape(self, value: Any) -> str:
        return html_lib.escape("" if value is None else str(value), quote=True)

    def sanitize_html(self, value: Optional[str]) -> str:
        """Allow formatting HTML from the builder's rich-text blocks but strip scripts/handlers/js: URLs."""
        if not value:
            return ""
        value = self._SCRIPT_RE.sub("", value)
        value = self._VOID_DANGER_RE.sub("", value)
        value = self._EVENT_ATTR_RE.sub("", value)
        value = self._JS_URL_RE.sub(r'\1="#"', value)
        return value

    def sanitize_subdomain(self, value: str) -> str:
        sub = re.sub(r"[^a-z0-9-]", "-", (value or "").lower()).strip("-")
        sub = re.sub(r"-{2,}", "-", sub)[:63].strip("-")
        if sub in {"www", "api", "admin", "app", "mail", "static"}:
            sub = f"{sub}-site"
        return sub

    def is_safe_redirect_url(self, url: str) -> bool:
        try:
            p = urlparse(url)
        except Exception:
            return False
        return p.scheme in ("http", "https", "mailto", "tel") and (bool(p.netloc) or p.scheme in ("mailto", "tel"))

    def normalize_url(self, url: str) -> str:
        url = (url or "").strip()
        if url and not re.match(r"^https?://", url, re.I):
            url = "https://" + url
        return url

    # â•â•â•â• 8. Signatures â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    def _tracking_secret(self) -> bytes:
        return (settings.TRACKING_SECRET or settings.SECRET_KEY).encode()

    def sign(self, message: str, length: int = 16) -> str:
        return hmac.new(self._tracking_secret(), message.encode(), hashlib.sha256).hexdigest()[:length]

    def verify_signature(self, message: str, signature: str, length: int = 16) -> bool:
        return hmac.compare_digest(self.sign(message, length), signature or "")

    def constant_time_equals(self, a: Optional[str], b: Optional[str]) -> bool:
        return hmac.compare_digest((a or "").encode(), (b or "").encode())

    def verify_stripe_signature(self, payload: bytes, sig_header: str, secret: str, tolerance: int = 300) -> bool:
        try:
            parts = dict(item.split("=", 1) for item in sig_header.split(","))
            timestamp, signature = int(parts["t"]), parts["v1"]
        except Exception:
            return False
        if abs(time.time() - timestamp) > tolerance:
            return False
        expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def verify_meta_signature(self, payload: bytes, sig_header: Optional[str], app_secret: Optional[str]) -> bool:
        """WhatsApp Cloud API webhook: X-Hub-Signature-256 = sha256=HMAC(app_secret, body). Skipped if no secret set."""
        if not app_secret:
            return True
        if not sig_header or not sig_header.startswith("sha256="):
            return False
        expected = hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig_header.split("=", 1)[1])

    # â•â•â•â• 9. Website security audit (Module 4) â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    def inspect_ssl(self, hostname: str, port: int = 443, timeout: float = 6.0) -> Dict[str, Any]:
        result: Dict[str, Any] = {"valid": False, "issuer": None, "expires_at": None, "days_left": None,
                                  "protocol": None, "error": None}
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=timeout) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    result["protocol"] = ssock.version()
            expires = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            issuer = dict(x[0] for x in cert.get("issuer", []))
            result.update(valid=True, issuer=issuer.get("organizationName") or issuer.get("commonName"),
                          expires_at=expires.isoformat(), days_left=(expires - datetime.now(timezone.utc)).days)
        except Exception as e:
            result["error"] = str(e)[:200]
        return result

    def audit_security_headers(self, headers: Dict[str, str]) -> Dict[str, Any]:
        lower = {k.lower(): v for k, v in (headers or {}).items()}
        present, missing, recommendations, score = [], [], [], 0
        for key, (label, weight, fix) in self.SECURITY_HEADERS.items():
            if key in lower:
                present.append({"header": label, "value": lower[key][:200]})
                score += weight
            else:
                missing.append(label)
                recommendations.append(fix)
        leaks = [h for h in ("server", "x-powered-by", "x-aspnet-version") if h in lower and re.search(r"\d", lower[h])]
        if leaks:
            recommendations.append("Hide version numbers in " + ", ".join(leaks) + " headers")
        return {"score": score, "present": present, "missing": missing, "version_leaks": leaks,
                "recommendations": recommendations}

    def security_score(self, *, is_https: bool, redirects_to_https: bool, ssl_info: Dict[str, Any],
                       headers_audit: Dict[str, Any], mixed_content: int = 0) -> float:
        score = 0.0
        score += 25 if is_https else 0
        score += 10 if redirects_to_https else 0
        if ssl_info.get("valid"):
            score += 20
            if (ssl_info.get("days_left") or 0) > 14:
                score += 5
        score += headers_audit.get("score", 0) * 0.40  # headers are worth up to 40
        score -= min(mixed_content, 5) * 2
        return round(max(0.0, min(100.0, score)), 1)


# Single shared instance used by every module
security_manager = SecurityManager()

# â”€â”€ Backward-compatible aliases (all route through the one SecurityManager) â”€â”€
ALGORITHM = SecurityManager.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = SecurityManager.ACCESS_TOKEN_EXPIRE_MINUTES
verify_password = security_manager.verify_password
get_password_hash = security_manager.hash_password
create_access_token = security_manager.create_access_token
generate_verification_token = security_manager.generate_verification_token
encrypt = security_manager.encrypt
decrypt = security_manager.decrypt

