"""
Statistics endpoints for PatchWeave API.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SystemStats(BaseModel):
    """System statistics response model."""
    resolved_today: int
    resolved_total: int
    failed_total: int
    pending_approval: int
    no_playbook_total: int
    avg_resolution_minutes: float
    playbook_hit_rate: float
    uptime_hours: float
    playbook_count: int


@router.get("", response_model=SystemStats)
async def get_statistics() -> SystemStats:
    """
    Get system-wide statistics.
    
    Returns:
        Aggregate statistics about system performance
    """
    # Placeholder - will be connected to metrics store in Phase 5
    return SystemStats(
        resolved_today=0,
        resolved_total=0,
        failed_total=0,
        pending_approval=0,
        no_playbook_total=0,
        avg_resolution_minutes=0.0,
        playbook_hit_rate=0.0,
        uptime_hours=0.0,
        playbook_count=0,
    )
