"""Tests for LangGraph workflow state model."""

from datetime import datetime

import pytest

from patchweave.agents.state import (
    ApprovalStatus,
    MatchTier,
    ValidationStage,
    ValidationStatus,
    WorkflowPhase,
    WorkflowState,
)


class TestWorkflowState:
    """Tests for WorkflowState model."""

    def test_initial_state(self) -> None:
        """Test initial state creation."""
        state = WorkflowState(
            workflow_id="wf-123",
            jira_ticket_id="SEC-456",
        )
        
        assert state.workflow_id == "wf-123"
        assert state.jira_ticket_id == "SEC-456"
        assert state.phase == WorkflowPhase.INGESTION
        assert state.analyzed_finding is None
        assert state.matched_playbook is None
        assert state.match_tier is None
        assert state.approval_status == ApprovalStatus.PENDING
        assert len(state.events) == 0
        assert len(state.stage_results) == 0

    def test_add_event(self) -> None:
        """Test adding audit events."""
        state = WorkflowState(
            workflow_id="wf-123",
            jira_ticket_id="SEC-456",
        )
        
        state.add_event("test_event", {"key": "value"})
        
        assert len(state.events) == 1
        event = state.events[0]
        assert event["type"] == "test_event"
        assert event["details"]["key"] == "value"
        assert "timestamp" in event
        assert event["phase"] == "ingestion"

    def test_set_stage_result(self) -> None:
        """Test setting validation stage results."""
        state = WorkflowState(
            workflow_id="wf-123",
            jira_ticket_id="SEC-456",
        )
        
        state.set_stage_result(
            ValidationStage.PRE_CHECK,
            ValidationStatus.SUCCESS,
            output={"vulnerability_exists": True},
        )
        
        assert "pre_check" in state.stage_results
        result = state.stage_results["pre_check"]
        assert result["status"] == "success"
        assert result["output"]["vulnerability_exists"] is True
        assert result["error"] is None

    def test_set_stage_result_with_error(self) -> None:
        """Test setting failed stage result."""
        state = WorkflowState(
            workflow_id="wf-123",
            jira_ticket_id="SEC-456",
        )
        
        state.set_stage_result(
            ValidationStage.REMEDIATION,
            ValidationStatus.FAILED,
            error="AWS API error",
        )
        
        result = state.stage_results["remediation"]
        assert result["status"] == "failed"
        assert result["error"] == "AWS API error"

    def test_is_validation_successful_all_pass(self) -> None:
        """Test validation success check when all stages pass."""
        state = WorkflowState(
            workflow_id="wf-123",
            jira_ticket_id="SEC-456",
        )
        
        # Set all required stages to success
        for stage in [
            ValidationStage.ENVIRONMENT_SETUP,
            ValidationStage.PRE_CHECK,
            ValidationStage.REMEDIATION,
            ValidationStage.POST_CHECK,
        ]:
            state.set_stage_result(stage, ValidationStatus.SUCCESS)
        
        assert state.is_validation_successful()

    def test_is_validation_successful_one_failed(self) -> None:
        """Test validation success check when one stage fails."""
        state = WorkflowState(
            workflow_id="wf-123",
            jira_ticket_id="SEC-456",
        )
        
        state.set_stage_result(ValidationStage.ENVIRONMENT_SETUP, ValidationStatus.SUCCESS)
        state.set_stage_result(ValidationStage.PRE_CHECK, ValidationStatus.SUCCESS)
        state.set_stage_result(
            ValidationStage.REMEDIATION,
            ValidationStatus.FAILED,
            error="Execution failed",
        )
        
        assert not state.is_validation_successful()

    def test_is_validation_successful_missing_stages(self) -> None:
        """Test validation check when stages are missing."""
        state = WorkflowState(
            workflow_id="wf-123",
            jira_ticket_id="SEC-456",
        )
        
        # Only set one stage
        state.set_stage_result(ValidationStage.PRE_CHECK, ValidationStatus.SUCCESS)
        
        assert not state.is_validation_successful()


class TestWorkflowPhase:
    """Tests for WorkflowPhase enum."""

    def test_phase_values(self) -> None:
        """Test phase enum values."""
        assert WorkflowPhase.INGESTION.value == "ingestion"
        assert WorkflowPhase.ANALYSIS.value == "analysis"
        assert WorkflowPhase.MATCHING.value == "matching"
        assert WorkflowPhase.VALIDATION.value == "validation"
        assert WorkflowPhase.APPROVAL.value == "approval"
        assert WorkflowPhase.DEPLOYMENT.value == "deployment"
        assert WorkflowPhase.COMPLETE.value == "complete"
        assert WorkflowPhase.FAILED.value == "failed"


class TestValidationStage:
    """Tests for ValidationStage enum."""

    def test_stage_values(self) -> None:
        """Test stage enum values."""
        assert ValidationStage.ENVIRONMENT_SETUP.value == "environment_setup"
        assert ValidationStage.PRE_CHECK.value == "pre_check"
        assert ValidationStage.REMEDIATION.value == "remediation"
        assert ValidationStage.POST_CHECK.value == "post_check"
        assert ValidationStage.CLEANUP.value == "cleanup"


class TestMatchTier:
    """Tests for MatchTier enum."""

    def test_tier_values(self) -> None:
        """Test tier enum values."""
        assert MatchTier.HIGH.value == "high"
        assert MatchTier.MODERATE.value == "moderate"
        assert MatchTier.LOW.value == "low"


class TestApprovalStatus:
    """Tests for ApprovalStatus enum."""

    def test_status_values(self) -> None:
        """Test approval status values."""
        assert ApprovalStatus.PENDING.value == "pending"
        assert ApprovalStatus.APPROVED.value == "approved"
        assert ApprovalStatus.REJECTED.value == "rejected"
