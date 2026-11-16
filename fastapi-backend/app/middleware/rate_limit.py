"""Rate limiting middleware - the limiter itself lives in SecurityManager."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.security import security_manager

RULES = [
    ("/api/v1/auth/login", 10, 60),
    ("/api/v1/auth/signup", 10, 60),
    ("/api/v1/", 300, 60),
]


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if path.startswith("/api/v1/track/") or request.method == "OPTIONS":
            return await call_next(request)
        ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "anon")).split(",")[0].strip()
        for prefix, limit, window in RULES:
            if path.startswith(prefix):
                ok, retry = security_manager.check_rate_limit(f"{prefix}:{ip}", limit, window)
                if not ok:
                    return JSONResponse({"detail": "Too many requests, slow down"}, status_code=429,
                                        headers={"Retry-After": str(retry)})
                break
        return await call_next(request)

