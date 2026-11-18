"""
Module 8 - Live Subdomain Hosting.

When SITES_BASE_DOMAIN=sites.yourplatform.com and a wildcard DNS record (*.sites.yourplatform.com)
points at this backend, a request for https://acme.sites.yourplatform.com/ is answered with the
published page whose subdomain is "acme". Every other host goes to the normal API.
"""
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class SubdomainSiteMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        base = (settings.SITES_BASE_DOMAIN or "").lower().strip(".")
        host = (request.headers.get("host") or "").split(":")[0].lower()
        if base and host.endswith("." + base) and request.method == "GET" and not request.url.path.startswith("/api/"):
            sub = host[: -(len(base) + 1)]
            if sub and "." not in sub:
                from app.db.session import AsyncSessionLocal
                from app.api.v1.endpoints.builder import serve_site
                async with AsyncSessionLocal() as db:
                    return await serve_site(db, sub)
        return await call_next(request)

