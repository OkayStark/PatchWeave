"""
Coordinator Agent for PatchWeave.

Orchestrates the multi-agent validation workflow, managing state
transitions and coordinating between validation agents.
"""

from datetime import datetime
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from patchweave.agents.state import (
    ApprovalStatus,
    MatchTier,
    ValidationStage,
    ValidationStatus,
    WorkflowPhase,
    WorkflowState,
)
from patchweave.config import settings
from patchweave.logging import get_logger

log = get_logger(__name__)


class CoordinatorAgent:
    """
    Orchestrates the remediation workflow.
    
    Responsibilities:
    - Manage workflow state transitions
    - Route findings based on match confidence
    - Coordinate validation stages
    - Handle failures with cleanup guarantee
    """
    
    def __init__(self):
        """Initialize the coordinator."""
        self.high_threshold = settings.high_confidence_threshold
        self.moderate_threshold = settings.moderate_confidence_threshold
        
        log.info(
            "coordinator_initialized",
            high_threshold=self.high_threshold,
            moderate_threshold=self.moderate_threshold,
        )
    
    def route_by_match_tier(self, state: WorkflowState) -> str:
        """
        Route workflow based on playbook match confidence.
        
        Returns:
            Next node name: 'validation', 'verification', or 'no_playbook'
        """
        if state.match_tier == MatchTier.HIGH:
            log.info(
                "routing_to_validation",
                workflow_id=state.workflow_id,
                similarity=state.match_similarity,
            )
            return "validation"
        elif state.match_tier == MatchTier.MODERATE:
            log.info(
                "routing_to_verification",
                workflow_id=state.workflow_id,
                similarity=state.match_similarity,
            )
            return "verification"
        else:
            log.info(
                "routing_to_no_playbook",
                workflow_id=state.workflow_id,
                similarity=state.match_similarity,
            )
            return "no_playbook"
    
    def route_after_verification(self, state: WorkflowState) -> str:
        """
        Route after verification agent decision.
        
        Returns:
            'validation' if approved, 'no_playbook' if rejected
        """
        if state.verification_approved:
            log.info(
                "verification_approved_routing_to_validation",
                workflow_id=state.workflow_id,
            )
            return "validation"
        else:
            log.info(
                "verification_rejected_routing_to_no_playbook",
                workflow_id=state.workflow_id,
                reason=state.verification_reason,
            )
            return "no_playbook"
    
    def route_after_validation(self, state: WorkflowState) -> str:
        """
        Route after validation completes.
        
        Returns:
            'approval' if successful, 'failed' if validation failed
        """
        if state.is_validation_successful():
            log.info(
                "validation_successful_routing_to_approval",
                workflow_id=state.workflow_id,
            )
            return "approval"
        else:
            log.info(
                "validation_failed",
                workflow_id=state.workflow_id,
                stage_results=state.stage_results,
            )
            return "failed"
    
    def route_after_approval(self, state: WorkflowState) -> str:
        """
        Route after human approval decision.
        
        Returns:
            'deployment' if approved, 'rejected' if rejected
        """
        if state.approval_status == ApprovalStatus.APPROVED:
            log.info(
                "approval_granted_routing_to_deployment",
                workflow_id=state.workflow_id,
                approved_by=state.approved_by,
            )
            return "deployment"
        else:
            log.info(
                "approval_rejected",
                workflow_id=state.workflow_id,
                reason=state.rejection_reason,
            )
            return "rejected"
    
    def start_workflow(self, state: WorkflowState) -> dict[str, Any]:
        """
        Initialize workflow state.
        
        Returns:
            State updates for workflow start
        """
        log.info(
            "workflow_started",
            workflow_id=state.workflow_id,
            jira_ticket_id=state.jira_ticket_id,
        )
        
        state.add_event("workflow_started")
        
        return {
            "phase": WorkflowPhase.INGESTION,
            "created_at": datetime.utcnow(),
            "events": state.events,
        }
    
    def mark_analysis_complete(self, state: WorkflowState) -> dict[str, Any]:
        """Mark analysis phase complete and transition to matching."""
        log.info(
            "analysis_complete",
            workflow_id=state.workflow_id,
            vulnerability_type=state.analyzed_finding.vulnerability_type.value if state.analyzed_finding else None,
        )
        
        state.add_event(
            "analysis_complete",
            {
                "vulnerability_type": state.analyzed_finding.vulnerability_type.value if state.analyzed_finding else None,
            },
        )
        
        return {
            "phase": WorkflowPhase.MATCHING,
            "events": state.events,
        }
    
    def mark_matching_complete(
        self,
        state: WorkflowState,
        playbook: Any,
        similarity: float,
        tier: MatchTier,
    ) -> dict[str, Any]:
        """Record matching results and determine next phase."""
        log.info(
            "matching_complete",
            workflow_id=state.workflow_id,
            playbook_id=playbook.id if playbook else None,
            similarity=similarity,
            tier=tier.value,
        )
        
        state.add_event(
            "matching_complete",
            {
                "playbook_id": playbook.id if playbook else None,
                "similarity": similarity,
                "tier": tier.value,
            },
        )
        
        next_phase = WorkflowPhase.VERIFICATION if tier == MatchTier.MODERATE else WorkflowPhase.VALIDATION
        if tier == MatchTier.LOW:
            next_phase = WorkflowPhase.FAILED
        
        return {
            "matched_playbook": playbook,
            "match_similarity": similarity,
            "match_tier": tier,
            "phase": next_phase,
            "events": state.events,
        }
    
    def mark_validation_started(self, state: WorkflowState) -> dict[str, Any]:
        """Mark start of validation phase."""
        log.info(
            "validation_started",
            workflow_id=state.workflow_id,
            playbook_id=state.matched_playbook.id if state.matched_playbook else None,
        )
        
        state.add_event("validation_started")
        
        return {
            "phase": WorkflowPhase.VALIDATION,
            "validation_stage": ValidationStage.ENVIRONMENT_SETUP,
            "events": state.events,
        }
    
    def mark_approval_requested(self, state: WorkflowState) -> dict[str, Any]:
        """Mark that approval has been requested."""
        log.info(
            "approval_requested",
            workflow_id=state.workflow_id,
            jira_ticket_id=state.jira_ticket_id,
        )
        
        state.add_event("approval_requested")
        
        return {
            "phase": WorkflowPhase.APPROVAL,
            "approval_status": ApprovalStatus.PENDING,
            "approval_requested_at": datetime.utcnow(),
            "events": state.events,
        }
    
    def mark_workflow_complete(
        self,
        state: WorkflowState,
        success: bool,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Mark workflow as complete."""
        phase = WorkflowPhase.COMPLETE if success else WorkflowPhase.FAILED
        
        log.info(
            "workflow_complete",
            workflow_id=state.workflow_id,
            success=success,
            error=error,
        )
        
        state.add_event(
            "workflow_complete",
            {"success": success, "error": error},
        )
        
        return {
            "phase": phase,
            "error_message": error,
            "updated_at": datetime.utcnow(),
            "events": state.events,
        }
    
    def handle_failure(
        self,
        state: WorkflowState,
        stage: str,
        error: str,
    ) -> dict[str, Any]:
        """Handle workflow failure with logging."""
        log.error(
            "workflow_failed",
            workflow_id=state.workflow_id,
            stage=stage,
            error=error,
            _audit=True,
        )
        
        state.add_event(
            "workflow_failed",
            {"stage": stage, "error": error},
        )
        
        return {
            "phase": WorkflowPhase.FAILED,
            "error_message": f"{stage}: {error}",
            "events": state.events,
        }


def create_coordinator() -> CoordinatorAgent:
    """Factory function to create a coordinator agent."""
    return CoordinatorAgent()


# Singleton instance
_coordinator: CoordinatorAgent | None = None


def get_coordinator() -> CoordinatorAgent:
    """Get or create the global coordinator agent."""
    global _coordinator
    if _coordinator is None:
        _coordinator = create_coordinator()
    return _coordinator
