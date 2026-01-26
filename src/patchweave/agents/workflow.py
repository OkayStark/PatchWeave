"""
LangGraph workflow for PatchWeave remediation pipeline.

Defines the multi-agent graph that orchestrates the full
remediation workflow: analyze → match → validate → approve → deploy.
"""

from datetime import datetime
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from patchweave.agents.coordinator import get_coordinator
from patchweave.agents.deployer import get_deployer
from patchweave.agents.state import (
    ApprovalStatus,
    MatchTier,
    WorkflowPhase,
    WorkflowState,
)
from patchweave.agents.validator import get_validator
from patchweave.config import settings
from patchweave.core.matcher import get_matcher
from patchweave.logging import get_logger

log = get_logger(__name__)


# Node functions for the workflow
def analyze_finding(state: WorkflowState) -> dict[str, Any]:
    """
    Node: Analyze the security finding.
    
    Uses the Analyzer Agent to classify and structure the finding.
    """
    from patchweave.agents.analyzer import AnalyzerAgent
    
    log.info(
        "analyze_node_executing",
        workflow_id=state.workflow_id,
    )
    
    # Analysis was already done before workflow starts
    # This node marks the transition
    coordinator = get_coordinator()
    
    if state.analyzed_finding:
        return coordinator.mark_analysis_complete(state)
    else:
        return coordinator.handle_failure(
            state, "analysis", "No analyzed finding provided"
        )


def match_playbook(state: WorkflowState) -> dict[str, Any]:
    """
    Node: Match finding to playbook.
    
    Searches ChromaDB for matching remediation playbooks
    and applies three-tier confidence routing.
    """
    log.info(
        "match_node_executing",
        workflow_id=state.workflow_id,
    )
    
    if not state.analyzed_finding:
        coordinator = get_coordinator()
        return coordinator.handle_failure(
            state, "matching", "No analyzed finding available"
        )
    
    # Get matcher and search for playbooks
    matcher = get_matcher()
    match_result = matcher.match(state.analyzed_finding)
    
    # Update state with match results
    coordinator = get_coordinator()
    return coordinator.mark_matching_complete(
        state,
        playbook=match_result.playbook,
        similarity=match_result.similarity,
        tier=MatchTier(match_result.tier.value),  # Convert from matcher's MatchTier
    )


def verify_match(state: WorkflowState) -> dict[str, Any]:
    """
    Node: Verify moderate-confidence playbook match.
    
    For matches in 70-89% range, uses LLM to verify
    the playbook is appropriate for the finding.
    """
    log.info(
        "verify_node_executing",
        workflow_id=state.workflow_id,
        playbook_id=state.matched_playbook.id if state.matched_playbook else None,
    )
    
    # In a full implementation, this would use an LLM to verify
    # For now, we approve if the vulnerability types match
    if state.matched_playbook and state.analyzed_finding:
        types_match = (
            state.matched_playbook.vulnerability_type ==
            state.analyzed_finding.vulnerability_type
        )
        
        # Use moderate confidence threshold from settings for verification approval
        verification_threshold = settings.moderate_confidence_threshold + 0.10  # 0.80 by default
        approved = types_match or state.match_similarity >= verification_threshold
        reason = (
            "Vulnerability types match" if types_match
            else f"High similarity score ({state.match_similarity:.2f} >= {verification_threshold})"
            if approved
            else f"Vulnerability type mismatch and low similarity ({state.match_similarity:.2f})"
        )
        
        state.add_event(
            "verification_complete",
            {"approved": approved, "reason": reason},
        )
        
        return {
            "verification_approved": approved,
            "verification_reason": reason,
            "phase": WorkflowPhase.VALIDATION if approved else WorkflowPhase.FAILED,
            "events": state.events,
        }
    
    return {
        "verification_approved": False,
        "verification_reason": "No playbook or finding available",
        "phase": WorkflowPhase.FAILED,
    }


def validate_playbook(state: WorkflowState) -> dict[str, Any]:
    """
    Node: Validate playbook in test environment.
    
    Executes the full validation workflow:
    1. Set up test environment
    2. Run pre-check
    3. Execute remediation
    4. Run post-check
    5. Cleanup (always)
    """
    log.info(
        "validate_node_executing",
        workflow_id=state.workflow_id,
        playbook_id=state.matched_playbook.id if state.matched_playbook else None,
    )
    
    if not state.matched_playbook:
        coordinator = get_coordinator()
        return coordinator.handle_failure(
            state, "validation", "No playbook to validate"
        )
    
    coordinator = get_coordinator()
    state_updates = coordinator.mark_validation_started(state)
    
    try:
        validator = get_validator()
        updated_state = validator.validate_playbook(
            state,
            state.matched_playbook,
            state.token_mapping,
        )
        
        # Check if validation passed
        if updated_state.is_validation_successful():
            return {
                **state_updates,
                "stage_results": updated_state.stage_results,
                "environment": updated_state.environment,
            }
        else:
            return coordinator.handle_failure(
                state,
                "validation",
                "Validation stages did not all pass",
            )
            
    except Exception as e:
        return coordinator.handle_failure(
            state, "validation", str(e)
        )


def request_approval(state: WorkflowState) -> dict[str, Any]:
    """
    Node: Request human approval via Jira.
    
    Posts validation results to Jira and updates
    ticket status to PENDING APPROVAL.
    """
    log.info(
        "approval_node_executing",
        workflow_id=state.workflow_id,
        jira_ticket_id=state.jira_ticket_id,
    )
    
    coordinator = get_coordinator()
    state_updates = coordinator.mark_approval_requested(state)
    
    # In full implementation, this would:
    # 1. Format validation results as Jira comment
    # 2. Post comment to Jira ticket
    # 3. Update ticket status to PENDING APPROVAL
    
    # For now, we simulate the approval request
    log.info(
        "approval_request_posted",
        workflow_id=state.workflow_id,
        jira_ticket_id=state.jira_ticket_id,
        _audit=True,
    )
    
    return state_updates


def check_approval(state: WorkflowState) -> dict[str, Any]:
    """
    Node: Check for approval decision.
    
    In real implementation, would poll Jira for status changes.
    Returns approval status.
    """
    log.info(
        "check_approval_executing",
        workflow_id=state.workflow_id,
    )
    
    # This would poll Jira in production
    # For now, return current state
    return {
        "approval_status": state.approval_status,
    }


def deploy_remediation(state: WorkflowState) -> dict[str, Any]:
    """
    Node: Deploy remediation to production.
    
    ONLY executes after human approval.
    """
    log.info(
        "deploy_node_executing",
        workflow_id=state.workflow_id,
        jira_ticket_id=state.jira_ticket_id,
    )
    
    if state.approval_status != ApprovalStatus.APPROVED:
        coordinator = get_coordinator()
        return coordinator.handle_failure(
            state, "deployment", "Not approved for deployment"
        )
    
    if not state.matched_playbook:
        coordinator = get_coordinator()
        return coordinator.handle_failure(
            state, "deployment", "No playbook available"
        )
    
    deployer = get_deployer()
    
    try:
        updated_state = deployer.deploy(
            state,
            state.matched_playbook,
            state.token_mapping,
        )
        
        coordinator = get_coordinator()
        return coordinator.mark_workflow_complete(
            state,
            success=updated_state.deployment_success or False,
            error=updated_state.deployment_error,
        )
        
    except Exception as e:
        coordinator = get_coordinator()
        return coordinator.handle_failure(
            state, "deployment", str(e)
        )


def mark_no_playbook(state: WorkflowState) -> dict[str, Any]:
    """
    Node: Handle case where no suitable playbook exists.
    
    Updates Jira with NO PLAYBOOK status and ends workflow.
    """
    log.info(
        "no_playbook_node_executing",
        workflow_id=state.workflow_id,
    )
    
    state.add_event(
        "no_playbook_found",
        {
            "similarity": state.match_similarity,
            "tier": state.match_tier.value if state.match_tier else "none",
        },
    )
    
    coordinator = get_coordinator()
    return coordinator.mark_workflow_complete(
        state,
        success=False,
        error="No suitable playbook found for this finding",
    )


def mark_rejected(state: WorkflowState) -> dict[str, Any]:
    """
    Node: Handle rejected approval.
    """
    log.info(
        "rejected_node_executing",
        workflow_id=state.workflow_id,
        reason=state.rejection_reason,
    )
    
    state.add_event(
        "approval_rejected",
        {"reason": state.rejection_reason},
    )
    
    coordinator = get_coordinator()
    return coordinator.mark_workflow_complete(
        state,
        success=False,
        error=f"Approval rejected: {state.rejection_reason}",
    )


def mark_failed(state: WorkflowState) -> dict[str, Any]:
    """
    Node: Handle workflow failure.
    """
    log.info(
        "failed_node_executing",
        workflow_id=state.workflow_id,
        error=state.error_message,
    )
    
    return {
        "phase": WorkflowPhase.FAILED,
        "updated_at": datetime.utcnow(),
    }


# Router functions
def route_after_match(state: WorkflowState) -> Literal["validate", "verify", "no_playbook"]:
    """Route based on match tier."""
    coordinator = get_coordinator()
    result = coordinator.route_by_match_tier(state)
    
    # Map to actual node names
    if result == "validation":
        return "validate"
    elif result == "verification":
        return "verify"
    else:
        return "no_playbook"


def route_after_verify(state: WorkflowState) -> Literal["validate", "no_playbook"]:
    """Route based on verification result."""
    if state.verification_approved:
        return "validate"
    return "no_playbook"


def route_after_validate(state: WorkflowState) -> Literal["request_approval", "failed"]:
    """Route based on validation result."""
    if state.is_validation_successful():
        return "request_approval"
    return "failed"


def route_after_approval(state: WorkflowState) -> Literal["deploy", "rejected"]:
    """Route based on approval status."""
    if state.approval_status == ApprovalStatus.APPROVED:
        return "deploy"
    return "rejected"


def build_workflow_graph() -> CompiledStateGraph:
    """
    Build the LangGraph workflow for remediation.
    
    Graph structure:
    
    START → analyze → match → [route_after_match]
                              ├── HIGH → validate → [route_after_validate]
                              │                     ├── SUCCESS → request_approval → [route_after_approval]
                              │                     │                               ├── APPROVED → deploy → END
                              │                     │                               └── REJECTED → rejected → END
                              │                     └── FAILED → failed → END
                              ├── MODERATE → verify → [route_after_verify]
                              │                       ├── APPROVED → validate → ...
                              │                       └── REJECTED → no_playbook → END
                              └── LOW → no_playbook → END
    """
    # Create the graph with WorkflowState schema
    graph = StateGraph(WorkflowState)
    
    # Add nodes
    graph.add_node("analyze", analyze_finding)
    graph.add_node("match", match_playbook)
    graph.add_node("verify", verify_match)
    graph.add_node("validate", validate_playbook)
    graph.add_node("request_approval", request_approval)
    graph.add_node("deploy", deploy_remediation)
    graph.add_node("no_playbook", mark_no_playbook)
    graph.add_node("rejected", mark_rejected)
    graph.add_node("failed", mark_failed)
    
    # Add edges
    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "match")
    
    # Conditional routing after match
    graph.add_conditional_edges(
        "match",
        route_after_match,
        {
            "validate": "validate",
            "verify": "verify",
            "no_playbook": "no_playbook",
        },
    )
    
    # Conditional routing after verification
    graph.add_conditional_edges(
        "verify",
        route_after_verify,
        {
            "validate": "validate",
            "no_playbook": "no_playbook",
        },
    )
    
    # Conditional routing after validation
    graph.add_conditional_edges(
        "validate",
        route_after_validate,
        {
            "request_approval": "request_approval",
            "failed": "failed",
        },
    )
    
    # Conditional routing after approval
    graph.add_conditional_edges(
        "request_approval",
        route_after_approval,
        {
            "deploy": "deploy",
            "rejected": "rejected",
        },
    )
    
    # Terminal edges
    graph.add_edge("deploy", END)
    graph.add_edge("no_playbook", END)
    graph.add_edge("rejected", END)
    graph.add_edge("failed", END)
    
    # Compile the graph
    compiled = graph.compile()
    
    log.info("workflow_graph_compiled")
    
    return compiled


# Singleton workflow instance
_workflow: CompiledStateGraph | None = None


def get_workflow() -> CompiledStateGraph:
    """Get or create the workflow graph."""
    global _workflow
    if _workflow is None:
        _workflow = build_workflow_graph()
    return _workflow


def run_workflow(
    workflow_id: str,
    jira_ticket_id: str,
    analyzed_finding: Any,
    token_mapping: dict[str, str],
) -> WorkflowState:
    """
    Run the remediation workflow for a finding.
    
    Args:
        workflow_id: Unique workflow identifier
        jira_ticket_id: Source Jira ticket ID
        analyzed_finding: AnalyzedFinding from analyzer
        token_mapping: Token to value mapping
        
    Returns:
        Final workflow state
    """
    log.info(
        "running_workflow",
        workflow_id=workflow_id,
        jira_ticket_id=jira_ticket_id,
    )
    
    # Create initial state
    initial_state = WorkflowState(
        workflow_id=workflow_id,
        jira_ticket_id=jira_ticket_id,
        analyzed_finding=analyzed_finding,
        token_mapping=token_mapping,
    )
    
    # Get workflow graph
    workflow = get_workflow()
    
    # Run the workflow
    final_state = workflow.invoke(initial_state)
    
    log.info(
        "workflow_completed",
        workflow_id=workflow_id,
        final_phase=final_state.get("phase", "unknown"),
    )
    
    return WorkflowState(**final_state)
