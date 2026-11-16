"""
Main  , FastAPI Application - AI Powered Client Hunt & Outreach (v1.0.2)
"""
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router


# Create required directories
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
(STATIC_DIR / "css").mkdir(exist_ok=True)
(STATIC_DIR / "js").mkdir(exist_ok=True)
(STATIC_DIR / "img").mkdir(exist_ok=True)


from app.db.init_db import init_db
from app.core.security import SecurityError
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.subdomain import SubdomainSiteMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    try:
        await init_db()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize database: {e}")
    # Module 7: in-process reminder dispatcher (set REMINDER_LOOP_ENABLED=false if you use a cron job instead)
    reminder_task = None
    if settings.REMINDER_LOOP_ENABLED:
        import asyncio
        from app.services.meetings.reminders import reminder_loop
        reminder_task = asyncio.create_task(reminder_loop(settings.REMINDER_LOOP_SECONDS))
    yield
    if reminder_task:
        reminder_task.cancel()
    # Shutdown
    print(f"Shutting down {settings.APP_NAME}")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered system for hunting potential clients and automated outreach",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security (SecurityManager): rate limiting + subdomain hosting for published builder pages
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SubdomainSiteMiddleware)


@app.exception_handler(SecurityError)
async def security_error_handler(request: Request, exc: SecurityError):
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)


# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Module 8: path-based hosting fallback (https://backend/sites/<subdomain>) when no wildcard domain is set
from app.api.v1.endpoints.builder import public_router as sites_public_router  # noqa: E402
app.include_router(sites_public_router, prefix="/sites", tags=["8. Hosted sites (public)"])

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

