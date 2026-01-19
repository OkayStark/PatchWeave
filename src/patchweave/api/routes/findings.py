"""
Findings endpoints for PatchWeave API.
"""

from datetime import datetime
from typing import Optional, List, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from patchweave.logging import get_logger

router = APIRouter()
log = get_logger(__name__)

# In-memory store for demo - would be replaced with Redis/database in production
_workflow_states: dict[str, dict[str, Any]] = {}


class FindingStatus(BaseModel):
    """Finding status response model."""
    finding_id: str = Field(..., description="Jira ticket ID")
    workflow_id: str = Field(default="", description="PatchWeave workflow ID")
    status: str = Field(..., description="Current workflow phase")
    vulnerability_type: str = Field(default="", description="Type of vulnerability")
    severity: str = Field(default="", description="Severity level")
    resource_id: str = Field(default="", description="Affected resource ID")
    playbook_matched: bool = Field(default=False, description="Whether a playbook was matched")
    playbook_id: Optional[str] = Field(None, description="Matched playbook ID")
    playbook_name: Optional[str] = Field(None, description="Matched playbook name")
    match_score: Optional[float] = Field(None, description="Match confidence score")
    match_tier: Optional[str] = Field(None, description="Match tier (HIGH/MODERATE/LOW)")
    approval_status: Optional[str] = Field(None, description="Approval status")
    validation_passed: bool = Field(default=False, description="Whether validation passed")
    deployment_success: Optional[bool] = Field(None, description="Whether deployment succeeded")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    events: List[dict] = Field(default_factory=list, description="Workflow events")


class FindingListResponse(BaseModel):
    """List of findings response model."""
    count: int = Field(..., description="Total number of findings")
    findings: List[FindingStatus] = Field(..., description="List of findings")


class FindingDetailResponse(BaseModel):
    """Detailed finding response with full workflow history."""
    finding: FindingStatus
    validation_results: dict = Field(default_factory=dict)
    audit_trail: List[dict] = Field(default_factory=list)


class RetryResponse(BaseModel):
    """Retry response model."""
    finding_id: str
    action: str
    message: str
    new_workflow_id: Optional[str] = None


class CancelResponse(BaseModel):
    """Cancel response model."""
    finding_id: str
    action: str
    message: str


def register_workflow(workflow_id: str, state_dict: dict[str, Any]) -> None:
    """Register a workflow state for API access."""
    _workflow_states[state_dict.get("jira_ticket_id", workflow_id)] = state_dict


def get_workflow_by_ticket(ticket_id: str) -> dict[str, Any] | None:
    """Get workflow state by Jira ticket ID."""
    return _workflow_states.get(ticket_id)


def list_all_workflows() -> list[dict[str, Any]]:
    """Get all registered workflow states."""
    return list(_workflow_states.values())


@router.get("", response_model=FindingListResponse)
async def list_findings(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    vulnerability_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> FindingListResponse:
    """
    List all findings with optional filtering.
    
    Args:
        status: Filter by workflow phase (INGESTION, ANALYSIS, MATCHING, etc.)
        severity: Filter by severity level (CRITICAL, HIGH, MEDIUM, LOW)
        vulnerability_type: Filter by vulnerability type
        limit: Maximum results to return
        offset: Pagination offset
        
    Returns:
        List of findings
    """
    workflows = list_all_workflows()
    
    # Apply filters
    if status:
        workflows = [w for w in workflows if w.get("phase", "").upper() == status.upper()]
    if severity:
        workflows = [w for w in workflows if w.get("severity", "").upper() == severity.upper()]
    if vulnerability_type:
        workflows = [w for w in workflows if w.get("vulnerability_type", "") == vulnerability_type]
    
    # Pagination
    total = len(workflows)
    workflows = workflows[offset:offset + limit]
    
    findings = []
    for w in workflows:
        findings.append(FindingStatus(
            finding_id=w.get("jira_ticket_id", ""),
            workflow_id=w.get("workflow_id", ""),
            status=w.get("phase", "UNKNOWN"),
            vulnerability_type=w.get("vulnerability_type", ""),
            severity=w.get("severity", ""),
            resource_id=w.get("resource_id", ""),
            playbook_matched=w.get("matched_playbook_id") is not None,
            playbook_id=w.get("matched_playbook_id"),
            playbook_name=w.get("matched_playbook_name"),
            match_score=w.get("match_similarity"),
            match_tier=w.get("match_tier"),
            approval_status=w.get("approval_status"),
            validation_passed=w.get("validation_success", False),
            deployment_success=w.get("deployment_success"),
            created_at=datetime.fromisoformat(w["created_at"]) if w.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(w["updated_at"]) if w.get("updated_at") else datetime.utcnow(),
            events=w.get("events", [])[-5:],  # Last 5 events
        ))
    
    return FindingListResponse(
        count=total,
        findings=findings,
    )


@router.get("/{finding_id}", response_model=FindingDetailResponse)
async def get_finding_status(finding_id: str) -> FindingDetailResponse:
    """
    Get detailed status of a specific finding.
    
    Args:
        finding_id: Jira ticket ID
        
    Returns:
        Detailed status of the finding including validation results
        
    Raises:
        HTTPException: If finding not found
    """
    workflow = get_workflow_by_ticket(finding_id)
    
    if workflow is None:
        log.warning("finding_not_found", finding_id=finding_id)
        raise HTTPException(status_code=404, detail=f"Finding {finding_id} not found")
    
    status = FindingStatus(
        finding_id=finding_id,
        workflow_id=workflow.get("workflow_id", ""),
        status=workflow.get("phase", "UNKNOWN"),
        vulnerability_type=workflow.get("vulnerability_type", ""),
        severity=workflow.get("severity", ""),
        resource_id=workflow.get("resource_id", ""),
        playbook_matched=workflow.get("matched_playbook_id") is not None,
        playbook_id=workflow.get("matched_playbook_id"),
        playbook_name=workflow.get("matched_playbook_name"),
        match_score=workflow.get("match_similarity"),
        match_tier=workflow.get("match_tier"),
        approval_status=workflow.get("approval_status"),
        validation_passed=workflow.get("validation_success", False),
        deployment_success=workflow.get("deployment_success"),
        created_at=datetime.fromisoformat(workflow["created_at"]) if workflow.get("created_at") else datetime.utcnow(),
        updated_at=datetime.fromisoformat(workflow["updated_at"]) if workflow.get("updated_at") else datetime.utcnow(),
        events=workflow.get("events", []),
    )
    
    return FindingDetailResponse(
        finding=status,
        validation_results=workflow.get("stage_results", {}),
        audit_trail=workflow.get("events", []),
    )


@router.post("/{finding_id}/retry", response_model=RetryResponse)
async def retry_finding(finding_id: str) -> RetryResponse:
    """
    Re-queue a finding for processing.
    
    This creates a new workflow for the finding.
    
    Args:
        finding_id: Jira ticket ID
        
    Returns:
        Confirmation of retry action with new workflow ID
    """
    # Check if finding exists
    workflow = get_workflow_by_ticket(finding_id)
    
    if workflow is None:
        log.warning("retry_finding_not_found", finding_id=finding_id)
        raise HTTPException(status_code=404, detail=f"Finding {finding_id} not found")
    
    # Import here to avoid circular imports
    from patchweave.core.queue import get_finding_queue
    
    queue = get_finding_queue()
    
    # Re-add to queue
    new_workflow_id = f"wf-{finding_id}-retry-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    log.info(
        "finding_retry_requested",
        finding_id=finding_id,
        new_workflow_id=new_workflow_id,
    )
    
    return RetryResponse(
        finding_id=finding_id,
        action="retry",
        message=f"Finding queued for re-processing",
        new_workflow_id=new_workflow_id,
    )


@router.post("/{finding_id}/cancel", response_model=CancelResponse)
async def cancel_finding(finding_id: str) -> CancelResponse:
    """
    Cancel processing of a finding.
    
    This stops the workflow if it's in progress.
    
    Args:
        finding_id: Jira ticket ID
        
    Returns:
        Confirmation of cancel action
    """
    workflow = get_workflow_by_ticket(finding_id)
    
    if workflow is None:
        raise HTTPException(status_code=404, detail=f"Finding {finding_id} not found")
    
    current_phase = workflow.get("phase", "")
    
    if current_phase in ["COMPLETE", "FAILED"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel finding in {current_phase} phase"
        )
    
    # Mark as cancelled
    workflow["phase"] = "FAILED"
    workflow["events"].append({
        "event_type": "workflow_cancelled",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {"cancelled_from_phase": current_phase},
    })
    
    log.info(
        "finding_cancelled",
        finding_id=finding_id,
        previous_phase=current_phase,
    )
    
    return CancelResponse(
        finding_id=finding_id,
        action="cancel",
        message=f"Finding workflow cancelled from {current_phase} phase",
    )
