"""
Health check endpoint for PatchWeave API.
"""

from datetime import datetime
from typing import Dict

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ComponentHealth(BaseModel):
    """Health status of a single component."""
    status: str
    message: str | None = None


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    version: str
    environment: str
    timestamp: datetime
    components: Dict[str, ComponentHealth]


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Check system health and component status.
    
    Returns:
        Health status of all system components
    """
    from patchweave.config import settings
    
    # Check component health
    components = {}
    overall_status = "healthy"
    
    # Check ChromaDB
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.get_chroma_url()}/api/v1/heartbeat",
                timeout=5.0
            )
            if response.status_code == 200:
                components["chromadb"] = ComponentHealth(status="healthy")
            else:
                components["chromadb"] = ComponentHealth(
                    status="unhealthy",
                    message=f"HTTP {response.status_code}"
                )
                overall_status = "degraded"
    except Exception as e:
        components["chromadb"] = ComponentHealth(
            status="unhealthy",
            message=str(e)
        )
        overall_status = "degraded"
    
    # Check LocalStack (if enabled)
    if settings.use_localstack:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.localstack_endpoint}/_localstack/health",
                    timeout=5.0
                )
                if response.status_code == 200:
                    components["localstack"] = ComponentHealth(status="healthy")
                else:
                    components["localstack"] = ComponentHealth(
                        status="unhealthy",
                        message=f"HTTP {response.status_code}"
                    )
                    overall_status = "degraded"
        except Exception as e:
            components["localstack"] = ComponentHealth(
                status="unhealthy",
                message=str(e)
            )
            overall_status = "degraded"
    
    # Queue status (placeholder - will be implemented in Phase 2)
    components["queue"] = ComponentHealth(status="healthy")
    
    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        environment=settings.patchweave_env,
        timestamp=datetime.utcnow(),
        components=components,
    )


@router.get("/ready")
async def readiness_check() -> Dict[str, str]:
    """
    Kubernetes-style readiness probe.
    
    Returns:
        Simple ready status
    """
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> Dict[str, str]:
    """
    Kubernetes-style liveness probe.
    
    Returns:
        Simple alive status
    """
    return {"status": "alive"}
