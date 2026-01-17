"""
Approval Flow for PatchWeave.

Handles the human approval workflow including:
- Posting approval requests to Jira
- Polling for approval status changes  
- Processing approved/rejected decisions
- Triggering deployment on approval
"""

from datetime import datetime
from enum import Enum
from typing import Any, Callable

from patchweave.agents.state import (
    ApprovalStatus,
    WorkflowPhase,
    WorkflowState,
)
from patchweave.config import settings
from patchweave.integrations.jira import JiraClient
from patchweave.logging import get_logger
from patchweave.models.enums import JiraStatus
from patchweave.models.finding import AnalyzedFinding
from patchweave.models.playbook import Playbook, PlaybookMatch

log = get_logger(__name__)


class ApprovalDecision(str, Enum):
    """Possible approval decisions from Jira."""
    
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"
    TIMEOUT = "timeout"


class ApprovalError(Exception):
    """Error during approval workflow."""
    pass


class ApprovalHandler:
    """
    Handles the human approval workflow for remediation playbooks.
    
    Flow:
    1. After validation passes, post approval request to Jira
    2. Update Jira status to "PENDING APPROVAL"
    3. Poll Jira for status change (APPROVED/REJECTED)
    4. On APPROVED, trigger Deployment Agent
    5. On REJECTED, parse comment for rejection reason and close workflow
    """
    
    def __init__(
        self,
        jira_client: JiraClient | None = None,
        poll_interval_seconds: int = 30,
        approval_timeout_hours: int = 24,
    ):
        """
        Initialize the approval handler.
        
        Args:
            jira_client: Jira client for API calls
            poll_interval_seconds: How often to poll for status changes
            approval_timeout_hours: Max time to wait for approval
        """
        self.jira_client = jira_client or JiraClient()
        self.poll_interval = poll_interval_seconds
        self.timeout_hours = approval_timeout_hours
        
        # Callbacks for approval events
        self._on_approved: Callable[[WorkflowState], None] | None = None
        self._on_rejected: Callable[[WorkflowState, str], None] | None = None
        
        log.info(
            "approval_handler_initialized",
            poll_interval=self.poll_interval,
            timeout_hours=self.timeout_hours,
        )
    
    def request_approval(
        self,
        state: WorkflowState,
        finding: AnalyzedFinding,
        playbook: Playbook,
        match: PlaybookMatch,
    ) -> WorkflowState:
        """
        Post an approval request to Jira for a matched playbook.
        
        Creates a detailed comment showing:
        - Finding summary
        - Matched playbook details
        - Validation results
        - Approval instructions
        
        Args:
            state: Current workflow state
            finding: The analyzed security finding
            playbook: Matched remediation playbook
            match: Playbook match details
            
        Returns:
            Updated workflow state
        """
        log.info(
            "requesting_approval",
            workflow_id=state.workflow_id,
            jira_ticket_id=state.jira_ticket_id,
            playbook_id=playbook.id,
            confidence=getattr(match, 'similarity', getattr(match, 'similarity_score', 0.0)),
        )
        
        # Build approval request comment
        comment = self._build_approval_comment(
            finding=finding,
            playbook=playbook,
            match=match,
            state=state,
        )
        
        # Post comment to Jira
        self.jira_client.add_comment(
            ticket_id=state.jira_ticket_id,
            comment=comment,
        )
        
        # Update Jira status to PENDING APPROVAL
        self.jira_client.update_status(
            ticket_id=state.jira_ticket_id,
            new_status=JiraStatus.PENDING_APPROVAL,
        )
        
        # Update workflow state
        state.approval_status = ApprovalStatus.PENDING
        state.phase = WorkflowPhase.APPROVAL
        state.approval_requested_at = datetime.utcnow()
        state.add_event(
            "approval_requested",
            {
                "jira_ticket_id": state.jira_ticket_id,
                "playbook_id": playbook.id,
                "confidence": getattr(match, 'similarity', getattr(match, 'similarity_score', 0.0)),
            },
        )
        
        log.info(
            "approval_request_posted",
            workflow_id=state.workflow_id,
            jira_ticket_id=state.jira_ticket_id,
            _audit=True,
        )
        
        return state
    
    def _build_approval_comment(
        self,
        finding: AnalyzedFinding,
        playbook: Playbook,
        match: PlaybookMatch,
        state: WorkflowState,
    ) -> str:
        """Build a detailed approval request comment for Jira."""
        
        # Validation summary
        validation_summary = self._format_validation_results(state)
        
        # Confidence indicator
        similarity = getattr(match, 'similarity', getattr(match, 'similarity_score', 0.0))
        confidence_pct = similarity * 100
        if confidence_pct >= 90:
            confidence_indicator = "🟢 HIGH"
        elif confidence_pct >= 70:
            confidence_indicator = "🟡 MODERATE"
        else:
            confidence_indicator = "🔴 LOW"
        
        comment = f"""
h2. 🔐 PatchWeave Approval Request

A remediation playbook has been identified and validated for this security finding.

h3. 📋 Finding Summary
||Property||Value||
|Type|{finding.vulnerability_type.value}|
|Resource Type|{finding.resource_type}|
|Severity|{finding.severity.value}|
|Detected|{finding.detected_at.strftime('%Y-%m-%d %H:%M UTC')}|

h3. 🎯 Matched Playbook
||Property||Value||
|Name|{playbook.name}|
|ID|{playbook.id}|
|Description|{playbook.description}|
|Confidence|{confidence_indicator} ({confidence_pct:.1f}%)|
|Match Tier|{getattr(match, 'tier', getattr(match, 'match_tier', 'unknown'))}|

h3. ✅ Validation Results
{validation_summary}

h3. 🔧 Remediation Action
{{code:python}}
{playbook.remediation_code[:500]}{'...' if len(playbook.remediation_code) > 500 else ''}
{{code}}

h3. ⚡ Action Required
*To approve this remediation:*
# Review the playbook and remediation action above
# Transition this ticket to status *APPROVED*

*To reject this remediation:*
# Transition this ticket to status *REJECTED*
# Add a comment explaining the rejection reason

----
_PatchWeave Workflow ID: {state.workflow_id}_
_Validation completed at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_
"""
        return comment
    
    def _format_validation_results(self, state: WorkflowState) -> str:
        """Format validation stage results for display."""
        
        if not state.stage_results:
            return "_No validation results available_"
        
        lines = ["||Stage||Status||Details||"]
        
        stage_names = {
            "environment_setup": "Environment Setup",
            "pre_check": "Pre-Check (Vulnerability Exists)",
            "remediation": "Remediation Execution",
            "post_check": "Post-Check (Fix Verified)",
            "cleanup": "Environment Cleanup",
        }
        
        status_icons = {
            "success": "(/)",
            "failed": "(x)",
            "skipped": "(-)",
            "pending": "(?)",
            "running": "(i)",
        }
        
        for stage_key, stage_name in stage_names.items():
            if stage_key in state.stage_results:
                result = state.stage_results[stage_key]
                status = result.get("status", "unknown")
                icon = status_icons.get(status, "(?)")
                details = result.get("message", "-")
                lines.append(f"|{stage_name}|{icon} {status.upper()}|{details[:50]}|")
            else:
                lines.append(f"|{stage_name}|(-) NOT RUN|-|")
        
        return "\n".join(lines)
    
    def check_approval_status(
        self,
        state: WorkflowState,
    ) -> ApprovalDecision:
        """
        Check Jira for approval decision.
        
        Checks both ticket status and comments for approval/rejection.
        Accepts 'DONE' as approved since simple Jira workflows may not have
        custom APPROVED status.
        
        Args:
            state: Current workflow state
            
        Returns:
            Current approval decision
        """
        ticket = self.jira_client.get_ticket(state.jira_ticket_id)
        
        if ticket is None:
            log.warning(
                "ticket_not_found",
                jira_ticket_id=state.jira_ticket_id,
            )
            return ApprovalDecision.PENDING
        
        jira_status = ticket.get("status", "").upper()
        
        log.debug(
            "checking_approval_status",
            jira_ticket_id=state.jira_ticket_id,
            current_status=jira_status,
        )
        
        # Check status - accept DONE or APPROVED as approved
        if jira_status in ("APPROVED", "DONE"):
            log.info(
                "approval_detected",
                jira_ticket_id=state.jira_ticket_id,
                status=jira_status,
            )
            return ApprovalDecision.APPROVED
        elif jira_status in ("REJECTED", "CANCELLED", "CLOSED"):
            return ApprovalDecision.REJECTED
        else:
            # Check for timeout
            if state.approval_requested_at:
                elapsed = datetime.utcnow() - state.approval_requested_at
                if elapsed.total_seconds() > self.timeout_hours * 3600:
                    return ApprovalDecision.TIMEOUT
            
            return ApprovalDecision.PENDING
    
    def process_approval(
        self,
        state: WorkflowState,
    ) -> WorkflowState:
        """
        Process an approved remediation.
        
        Updates state and extracts approver information.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state
        """
        log.info(
            "approval_granted",
            workflow_id=state.workflow_id,
            jira_ticket_id=state.jira_ticket_id,
            _audit=True,
        )
        
        # Get approver info from Jira
        ticket = self.jira_client.get_ticket(state.jira_ticket_id)
        if ticket:
            # Extract who changed the status
            state.approved_by = ticket.get("assignee", "Unknown")
        
        state.approval_status = ApprovalStatus.APPROVED
        state.approved_at = datetime.utcnow()
        state.add_event(
            "approval_granted",
            {
                "approved_by": state.approved_by,
                "approved_at": state.approved_at.isoformat(),
            },
        )
        
        # Update Jira status to DEPLOYING
        self.jira_client.update_status(
            ticket_id=state.jira_ticket_id,
            new_status=JiraStatus.DEPLOYING,
        )
        
        # Trigger callback if registered
        if self._on_approved:
            self._on_approved(state)
        
        return state
    
    def process_rejection(
        self,
        state: WorkflowState,
    ) -> WorkflowState:
        """
        Process a rejected remediation.
        
        Extracts rejection reason from comments.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state
        """
        log.info(
            "approval_rejected",
            workflow_id=state.workflow_id,
            jira_ticket_id=state.jira_ticket_id,
            _audit=True,
        )
        
        # Try to get rejection reason from comments
        rejection_reason = self._get_rejection_reason(state.jira_ticket_id)
        
        state.approval_status = ApprovalStatus.REJECTED
        state.rejection_reason = rejection_reason
        state.phase = WorkflowPhase.FAILED
        state.add_event(
            "approval_rejected",
            {
                "reason": rejection_reason,
            },
        )
        
        # Trigger callback if registered
        if self._on_rejected:
            self._on_rejected(state, rejection_reason)
        
        return state
    
    def _get_rejection_reason(self, ticket_id: str) -> str:
        """Extract rejection reason from recent Jira comments."""
        
        comments = self.jira_client.get_comments(ticket_id)
        
        if not comments:
            return "No reason provided"
        
        # Look for most recent comment after status change
        # Assume it contains the rejection reason
        latest_comment = comments[-1] if comments else None
        
        if latest_comment:
            body = latest_comment.get("body", "")
            # Truncate if too long
            return body[:500] if body else "No reason provided"
        
        return "No reason provided"
    
    def process_timeout(
        self,
        state: WorkflowState,
    ) -> WorkflowState:
        """
        Process an approval timeout.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state
        """
        log.warning(
            "approval_timeout",
            workflow_id=state.workflow_id,
            jira_ticket_id=state.jira_ticket_id,
            timeout_hours=self.timeout_hours,
            _audit=True,
        )
        
        state.phase = WorkflowPhase.FAILED
        state.add_event(
            "approval_timeout",
            {
                "timeout_hours": self.timeout_hours,
            },
        )
        
        # Post timeout notification to Jira
        comment = f"""
h2. ⏰ Approval Timeout

This remediation request has not received approval within {self.timeout_hours} hours.

The workflow has been closed. If approval is still needed, please:
1. Manually trigger a new analysis
2. Or re-open this ticket for processing

_PatchWeave Workflow ID: {state.workflow_id}_
"""
        self.jira_client.add_comment(
            ticket_id=state.jira_ticket_id,
            comment=comment,
        )
        
        return state
    
    def register_approval_callback(
        self,
        callback: Callable[[WorkflowState], None],
    ) -> None:
        """Register a callback for approval events."""
        self._on_approved = callback
    
    def register_rejection_callback(
        self,
        callback: Callable[[WorkflowState, str], None],
    ) -> None:
        """Register a callback for rejection events."""
        self._on_rejected = callback
    
    def post_deployment_result(
        self,
        state: WorkflowState,
        success: bool,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Post deployment result to Jira.
        
        Args:
            state: Current workflow state
            success: Whether deployment succeeded
            details: Additional deployment details
        """
        details = details or {}
        
        if success:
            new_status = JiraStatus.RESOLVED
            comment = self._build_success_comment(state, details)
        else:
            new_status = JiraStatus.DEPLOYMENT_FAILED
            comment = self._build_failure_comment(state, details)
        
        # Update Jira status
        self.jira_client.update_status(
            ticket_id=state.jira_ticket_id,
            new_status=new_status,
        )
        
        # Post result comment
        self.jira_client.add_comment(
            ticket_id=state.jira_ticket_id,
            comment=comment,
        )
        
        log.info(
            "deployment_result_posted",
            workflow_id=state.workflow_id,
            jira_ticket_id=state.jira_ticket_id,
            success=success,
            _audit=True,
        )
    
    def _build_success_comment(
        self,
        state: WorkflowState,
        details: dict[str, Any],
    ) -> str:
        """Build a success notification comment."""
        
        return f"""
h2. ✅ Remediation Successfully Deployed

The security vulnerability has been remediated in production.

h3. 📊 Deployment Summary
||Property||Value||
|Workflow ID|{state.workflow_id}|
|Deployed At|{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}|
|Approved By|{state.approved_by or 'Unknown'}|
|Dry Run|{details.get('dry_run', False)}|

h3. 🔍 Verification
{details.get('verification_message', 'Remediation applied successfully.')}

h3. 🎓 Learning Update
This successful remediation has been recorded to improve future matching.

----
_This issue can now be closed._
_PatchWeave v1.0_
"""
    
    def _build_failure_comment(
        self,
        state: WorkflowState,
        details: dict[str, Any],
    ) -> str:
        """Build a failure notification comment."""
        
        error = details.get('error', 'Unknown error')
        
        return f"""
h2. ❌ Deployment Failed

The remediation deployment encountered an error.

h3. ⚠️ Error Details
{{code}}
{error}
{{code}}

h3. 📋 Next Steps
1. Review the error above
2. Check AWS CloudWatch logs for additional details
3. Consider manual remediation if automated fix is not possible
4. Contact the PatchWeave team if this appears to be a system issue

----
_PatchWeave Workflow ID: {state.workflow_id}_
_Failed at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_
"""


# Singleton instance
_approval_handler: ApprovalHandler | None = None


def get_approval_handler() -> ApprovalHandler:
    """Get or create the singleton approval handler."""
    global _approval_handler
    if _approval_handler is None:
        _approval_handler = ApprovalHandler()
    return _approval_handler
