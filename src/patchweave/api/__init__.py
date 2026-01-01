"""
FastAPI application for PatchWeave REST API.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from patchweave.api.routes import health, queue, findings, playbooks, stats
from patchweave.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events."""
    from patchweave.logging import get_logger
    log = get_logger(__name__)
    
    # Startup
    log.info("api_starting", version="1.0.0")
    yield
    
    # Shutdown
    log.info("api_shutting_down")


# Create FastAPI application
app = FastAPI(
    title="PatchWeave API",
    description="Intelligent Cloud Security Remediation System API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(queue.router, prefix="/queue", tags=["Queue"])
app.include_router(findings.router, prefix="/findings", tags=["Findings"])
app.include_router(playbooks.router, prefix="/playbooks", tags=["Playbooks"])
app.include_router(stats.router, prefix="/stats", tags=["Statistics"])
