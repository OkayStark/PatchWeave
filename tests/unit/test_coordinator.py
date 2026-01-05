"""Tests for Coordinator Agent."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from patchweave.agents.coordinator import (
    CoordinatorAgent,
    create_coordinator,
    get_coordinator,
)
from patchweave.agents.state import (
    ApprovalStatus,
    MatchTier,
    ValidationStage,
    ValidationStatus,
    WorkflowPhase,
    WorkflowState,
)


@pytest.fixture
def coordinator() -> CoordinatorAgent:
    """Create a coordinator agent for testing."""
    return CoordinatorAgent()


@pytest.fixture
def sample_state() -> WorkflowState:
    """Create a sample workflow state."""
    return WorkflowState(
        workflow_id="wf-test-123",
        jira_ticket_id="SEC-456",
    )


class TestCoordinatorAgent:
    """Tests for CoordinatorAgent class."""

    def test_initialization(self, coordinator: CoordinatorAgent) -> None:
        """Test coordinator initialization."""
        assert coordinator.high_threshold == 0.90
        assert coordinator.moderate_threshold == 0.70

    def test_route_by_match_tier_high(
        self, coordinator: CoordinatorAgent, sample_state: WorkflowState
    ) -> None:
        """Test routing for high confidence match."""
        sample_state.match_tier = MatchTier.HIGH
        sample_state.match_similarity = 0.95
        
        result = coordinator.route_by_match_tier(sample_state)
        assert result == "validation"

    def test_route_by_match_tier_moderate(
        self, coordinator: CoordinatorAgent, sample_state: WorkflowState
    ) -> None:
        """Test routing for moderate confidence match."""
        sample_state.match_tier = MatchTier.MODERATE
        sample_state.match_similarity = 0.80
        
        result = coordinator.route_by_match_tier(sample_state)
        assert result == "verification"

    def test_route_by_match_tier_low(
        self, coordinator: CoordinatorAgent, sample_state: WorkflowState
    ) -> None:
        """Test routing for low confidence match."""
        sample_state.match_tier = MatchTier.LOW
        sample_state.match_similarity = 0.50
        
        result = coordinator.route_by_match_tier(sample_state)
        assert result == "no_playbook"

    def test_route_after_verification_approved(
        self, coordinator: CoordinatorAgent, sample_state: WorkflowState
    ) -> None:
        """Test routing after verification approval."""
        sample_state.verification_approved = True
        
        result = coordinator.route_after_verification(sample_state)
        assert result == "validation"

    def test_route_after_verification_rejected(
        self, coordinator: CoordinatorAgent, sample_state: WorkflowState
    ) -> None:
        """Test routing after verification rejection."""
        sample_state.verification_approved = False
        sample_state.verification_reason = "Type mismatch"
        
        result = coordinator.route_after_verification(sample_state)
        assert result == "no_playbook"

    def test_route_after_approval_approved(
        self, coordinator: CoordinatorAgent, sample_state: WorkflowState
    ) -> None:
        """Test routing after human approval."""
        sample_state.approval_status = ApprovalStatus.APPROVED
        
        result = coordinator.route_after_approval(sample_state)
        assert result == "deployment"

    def test_route_after_approval_rejected(
        self, coordinator: CoordinatorAgent, sample_state: WorkflowState
    ) -> None:
        """Test routing after human rejection."""
        sample_state.approval_status = ApprovalStatus.REJECTED
        sample_state.rejection_reason = "Risk too high"
        
        result = coordinator.route_after_approval(sample_state)
        assert result == "rejected"

    def test_start_workflow(
        self, coordinator: CoordinatorAgent, sample_state: WorkflowState
    ) -> None:
        """Test starting a workflow."""
        result = coordinator.start_workflow(sample_state)
        
        assert result["phase"] == WorkflowPhase.INGESTION
        assert "created_at" in result
        assert len(result["events"]) == 1
        assert result["events"][0]["type"] == "workflow_started"

    def test_mark_analysis_complete(
        self, coordinator: CoordinatorAgent, sample_state: WorkflowState
    ) -> None:
        """Test marking analysis complete."""
        # Add a mock finding
        sample_state.analyzed_finding = MagicMock()
        sample_state.analyzed_finding.vulnerability_type.value = "s3_public_access"
        
        result = coordinator.mark_analysis_complete(sample_state)
        
        assert result["phase"] == WorkflowPhase.MATCHING
        assert len(result["events"]) >= 1

    def test_mark_matching_complete(
        self, coordinator: CoordinatorAgent, sample_state: WorkflowState
    ) -> None:
        """Test marking matching complete."""
        mock_playbook = MagicMock()
        mock_playbook.id = "playbook-123"
        
        result = coordinator.mark_matching_complete(
            sample_state,
            playbook=mock_playbook,
            similarity=0.95,
            tier=MatchTier.HIGH,
        )
        
        assert result["matched_playbook"] == mock_playbook
        assert result["match_similarity"] == 0.95
        assert result["match_tier"] == MatchTier.HIGH

    def test_mark_workflow_complete_success(
        self, coordinator: CoordinatorAgent, sample_state: WorkflowState
    ) -> None:
        """Test marking workflow complete with success."""
        result = coordinator.mark_workflow_complete(sample_state, success=True)
        
        assert result["phase"] == WorkflowPhase.COMPLETE
        assert result["error_message"] is None

    def test_mark_workflow_complete_failure(
        self, coordinator: CoordinatorAgent, sample_state: WorkflowState
    ) -> None:
        """Test marking workflow complete with failure."""
        result = coordinator.mark_workflow_complete(
            sample_state,
            success=False,
            error="Validation failed",
        )
        
        assert result["phase"] == WorkflowPhase.FAILED
        assert result["error_message"] == "Validation failed"

    def test_handle_failure(
        self, coordinator: CoordinatorAgent, sample_state: WorkflowState
    ) -> None:
        """Test handling a failure."""
        result = coordinator.handle_failure(
            sample_state,
            stage="validation",
            error="AWS connection failed",
        )
        
        assert result["phase"] == WorkflowPhase.FAILED
        assert "validation" in result["error_message"]
        assert "AWS connection failed" in result["error_message"]


class TestCoordinatorFactory:
    """Tests for coordinator factory functions."""

    def test_create_coordinator(self) -> None:
        """Test creating a new coordinator."""
        coordinator = create_coordinator()
        assert isinstance(coordinator, CoordinatorAgent)

    def test_get_coordinator_singleton(self) -> None:
        """Test that get_coordinator returns the same instance."""
        # Reset singleton
        import patchweave.agents.coordinator as coord_module
        coord_module._coordinator = None
        
        coord1 = get_coordinator()
        coord2 = get_coordinator()
        
        assert coord1 is coord2
