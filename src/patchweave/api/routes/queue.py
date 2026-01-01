"""
Queue status endpoint for PatchWeave API.
"""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class QueueStatus(BaseModel):
    """Queue status response model."""
    pending_count: int
    currently_processing: Optional[str]
    current_status: Optional[str]
    total_processed_today: int
    total_processed_all_time: int


@router.get("", response_model=QueueStatus)
async def get_queue_status() -> QueueStatus:
    """
    Get current queue status.
    
    Returns:
        Current state of the finding queue
    """
    # Placeholder - will be connected to actual queue in Phase 2
    return QueueStatus(
        pending_count=0,
        currently_processing=None,
        current_status=None,
        total_processed_today=0,
        total_processed_all_time=0,
    )
