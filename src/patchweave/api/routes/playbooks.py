"""
Playbooks endpoints for PatchWeave API.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class PlaybookSummary(BaseModel):
    """Playbook summary response model."""
    id: str
    name: str
    vulnerability_type: str
    severity: str
    version: str
    resource_type: str


class PlaybookListResponse(BaseModel):
    """List of playbooks response model."""
    count: int
    playbooks: List[PlaybookSummary]


class PlaybookDetail(BaseModel):
    """Full playbook detail response model."""
    id: str
    name: str
    description: str
    vulnerability_type: str
    cloud_provider: str
    resource_type: str
    severity: str
    search_text: str
    remediation_code: str
    pre_check_code: str
    post_check_code: str
    version: str
    required_permissions: List[str]
    estimated_execution_time_seconds: int


@router.get("", response_model=PlaybookListResponse)
async def list_playbooks(
    vulnerability_type: Optional[str] = None,
    severity: Optional[str] = None,
) -> PlaybookListResponse:
    """
    List all available playbooks.
    
    Args:
        vulnerability_type: Filter by vulnerability type
        severity: Filter by severity
        
    Returns:
        List of playbook summaries
    """
    # Placeholder - will be connected to ChromaDB in Phase 3
    return PlaybookListResponse(
        count=0,
        playbooks=[],
    )


@router.get("/{playbook_id}", response_model=PlaybookDetail)
async def get_playbook(playbook_id: str) -> PlaybookDetail:
    """
    Get details of a specific playbook.
    
    Args:
        playbook_id: Playbook UUID
        
    Returns:
        Full playbook details
        
    Raises:
        HTTPException: If playbook not found
    """
    # Placeholder - will be connected to ChromaDB in Phase 3
    raise HTTPException(status_code=404, detail=f"Playbook {playbook_id} not found")
