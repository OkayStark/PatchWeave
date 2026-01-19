"""
Statistics endpoints for PatchWeave API.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from patchweave.api.routes.findings import list_all_workflows
from patchweave.logging import get_logger

router = APIRouter()
log = get_logger(__name__)

# Track system start time for uptime calculation
_system_start_time = datetime.utcnow()


class SystemStats(BaseModel):
    """System statistics response model."""
    resolved_today: int = Field(..., description="Findings resolved today")
    resolved_total: int = Field(..., description="Total findings resolved")
    failed_total: int = Field(..., description="Total failed remediations")
    pending_approval: int = Field(..., description="Findings awaiting approval")
    in_progress: int = Field(..., description="Findings currently processing")
    no_playbook_total: int = Field(..., description="Findings with no matching playbook")
    avg_resolution_minutes: float = Field(..., description="Average time to resolve")
    playbook_hit_rate: float = Field(..., description="Playbook match success rate")
    validation_success_rate: float = Field(..., description="Validation pass rate")
    uptime_hours: float = Field(..., description="System uptime in hours")
    playbook_count: int = Field(..., description="Total number of playbooks")


class PhaseBreakdown(BaseModel):
    """Breakdown of findings by workflow phase."""
    phase: str
    count: int
    percentage: float


class SeverityBreakdown(BaseModel):
    """Breakdown of findings by severity."""
    severity: str
    count: int
    resolved: int
    pending: int


class PlaybookStats(BaseModel):
    """Statistics for a single playbook."""
    playbook_id: str
    playbook_name: str
    vulnerability_type: str
    usage_count: int
    success_count: int
    failure_count: int
    success_rate: float
    last_used: Optional[datetime] = None


class DetailedStats(BaseModel):
    """Detailed statistics response."""
    overview: SystemStats
    phase_breakdown: List[PhaseBreakdown]
    severity_breakdown: List[SeverityBreakdown]
    top_playbooks: List[PlaybookStats]
    recent_activity: List[dict]


@router.get("", response_model=SystemStats)
async def get_statistics() -> SystemStats:
    """
    Get system-wide statistics.
    
    Returns:
        Aggregate statistics about system performance
    """
    workflows = list_all_workflows()
    total = len(workflows)
    
    # Calculate metrics
    resolved_total = sum(1 for w in workflows if w.get("phase") == "COMPLETE")
    failed_total = sum(1 for w in workflows if w.get("phase") == "FAILED")
    pending_approval = sum(1 for w in workflows if w.get("phase") == "APPROVAL")
    in_progress = sum(1 for w in workflows if w.get("phase") not in ["COMPLETE", "FAILED", "APPROVAL"])
    
    # Count findings where no playbook was matched
    no_playbook = sum(1 for w in workflows if w.get("matched_playbook_id") is None)
    
    # Today's resolved
    today = datetime.utcnow().date()
    resolved_today = sum(
        1 for w in workflows
        if w.get("phase") == "COMPLETE" and
        w.get("updated_at", "").startswith(today.isoformat())
    )
    
    # Calculate playbook hit rate
    matched = sum(1 for w in workflows if w.get("matched_playbook_id") is not None)
    playbook_hit_rate = (matched / total * 100) if total > 0 else 0.0
    
    # Calculate validation success rate
    validated = [w for w in workflows if w.get("validation_success") is not None]
    validation_passed = sum(1 for w in validated if w.get("validation_success"))
    validation_success_rate = (validation_passed / len(validated) * 100) if validated else 0.0
    
    # Calculate average resolution time
    resolution_times = []
    for w in workflows:
        if w.get("phase") == "COMPLETE" and w.get("created_at") and w.get("updated_at"):
            try:
                start = datetime.fromisoformat(w["created_at"])
                end = datetime.fromisoformat(w["updated_at"])
                resolution_times.append((end - start).total_seconds() / 60)
            except (ValueError, TypeError):
                pass
    avg_resolution = sum(resolution_times) / len(resolution_times) if resolution_times else 0.0
    
    # Uptime
    uptime = (datetime.utcnow() - _system_start_time).total_seconds() / 3600
    
    # Get playbook count
    try:
        from patchweave.core.loader import get_playbook_loader
        loader = get_playbook_loader()
        playbook_count = len(loader.get_all_playbooks())
    except Exception:
        playbook_count = 0
    
    return SystemStats(
        resolved_today=resolved_today,
        resolved_total=resolved_total,
        failed_total=failed_total,
        pending_approval=pending_approval,
        in_progress=in_progress,
        no_playbook_total=no_playbook,
        avg_resolution_minutes=round(avg_resolution, 2),
        playbook_hit_rate=round(playbook_hit_rate, 2),
        validation_success_rate=round(validation_success_rate, 2),
        uptime_hours=round(uptime, 2),
        playbook_count=playbook_count,
    )


@router.get("/detailed", response_model=DetailedStats)
async def get_detailed_statistics() -> DetailedStats:
    """
    Get detailed statistics with breakdowns.
    
    Returns:
        Comprehensive statistics including phase and severity breakdowns
    """
    workflows = list_all_workflows()
    total = len(workflows) or 1  # Avoid division by zero
    
    # Get overview
    overview = await get_statistics()
    
    # Phase breakdown
    phase_counts: dict[str, int] = {}
    for w in workflows:
        phase = w.get("phase", "UNKNOWN")
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
    
    phase_breakdown = [
        PhaseBreakdown(
            phase=phase,
            count=count,
            percentage=round(count / total * 100, 2)
        )
        for phase, count in sorted(phase_counts.items())
    ]
    
    # Severity breakdown
    severity_counts: dict[str, dict] = {}
    for w in workflows:
        severity = w.get("severity", "UNKNOWN")
        if severity not in severity_counts:
            severity_counts[severity] = {"total": 0, "resolved": 0, "pending": 0}
        severity_counts[severity]["total"] += 1
        if w.get("phase") == "COMPLETE":
            severity_counts[severity]["resolved"] += 1
        elif w.get("phase") not in ["FAILED"]:
            severity_counts[severity]["pending"] += 1
    
    severity_breakdown = [
        SeverityBreakdown(
            severity=severity,
            count=data["total"],
            resolved=data["resolved"],
            pending=data["pending"]
        )
        for severity, data in sorted(severity_counts.items())
    ]
    
    # Top playbooks
    playbook_usage: dict[str, dict] = {}
    for w in workflows:
        pb_id = w.get("matched_playbook_id")
        if pb_id:
            if pb_id not in playbook_usage:
                playbook_usage[pb_id] = {
                    "name": w.get("matched_playbook_name", "Unknown"),
                    "vuln_type": w.get("vulnerability_type", ""),
                    "usage": 0,
                    "success": 0,
                    "failure": 0,
                    "last_used": None,
                }
            playbook_usage[pb_id]["usage"] += 1
            if w.get("deployment_success"):
                playbook_usage[pb_id]["success"] += 1
            elif w.get("phase") == "FAILED":
                playbook_usage[pb_id]["failure"] += 1
            if w.get("updated_at"):
                playbook_usage[pb_id]["last_used"] = w["updated_at"]
    
    top_playbooks = []
    for pb_id, data in sorted(playbook_usage.items(), key=lambda x: x[1]["usage"], reverse=True)[:10]:
        success_rate = (data["success"] / data["usage"] * 100) if data["usage"] > 0 else 0.0
        top_playbooks.append(PlaybookStats(
            playbook_id=pb_id,
            playbook_name=data["name"],
            vulnerability_type=data["vuln_type"],
            usage_count=data["usage"],
            success_count=data["success"],
            failure_count=data["failure"],
            success_rate=round(success_rate, 2),
            last_used=datetime.fromisoformat(data["last_used"]) if data["last_used"] else None,
        ))
    
    # Recent activity (last 10 events)
    recent_activity = []
    for w in sorted(workflows, key=lambda x: x.get("updated_at", ""), reverse=True)[:10]:
        recent_activity.append({
            "finding_id": w.get("jira_ticket_id"),
            "workflow_id": w.get("workflow_id"),
            "phase": w.get("phase"),
            "updated_at": w.get("updated_at"),
            "vulnerability_type": w.get("vulnerability_type"),
        })
    
    return DetailedStats(
        overview=overview,
        phase_breakdown=phase_breakdown,
        severity_breakdown=severity_breakdown,
        top_playbooks=top_playbooks,
        recent_activity=recent_activity,
    )


@router.get("/learning", response_model=dict)
async def get_learning_stats() -> dict:
    """
    Get learning loop statistics.
    
    Returns:
        Statistics about the learning loop and recorded remediations
    """
    try:
        from patchweave.learning import get_learning_loop
        
        learning = get_learning_loop()
        summary = learning.get_learning_summary()
        
        return {
            "status": "active",
            "remediation_history_count": summary.get("remediation_history_count", 0),
            "playbook_stats_count": summary.get("playbook_stats_count", 0),
            "finding_patterns_count": summary.get("finding_patterns_count", 0),
            "most_used_playbooks": summary.get("most_used_playbooks", [])[:5],
        }
    except Exception as e:
        log.warning("learning_stats_error", error=str(e))
        return {
            "status": "unavailable",
            "error": str(e),
        }
