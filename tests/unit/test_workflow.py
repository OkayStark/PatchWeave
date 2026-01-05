"""Tests for LangGraph workflow."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from patchweave.agents.state import (
    ApprovalStatus,
    MatchTier,
    ValidationStage,
    ValidationStatus,
    WorkflowPhase,
    WorkflowState,
)
from patchweave.agents.workflow import (
    analyze_finding,
    match_playbook,
    verify_match,
    validate_playbook,
    request_approval,
    deploy_remediation,
    mark_no_playbook,
    mark_rejected,
    mark_failed,
    route_after_match,
    route_after_verify,
    route_after_validate,
    route_after_approval,
    build_workflow_graph,
    get_workflow,
)
from patchweave.models.enums import CloudProvider, Severity, VulnerabilityType


@pytest.fixture
def sample_state() -> WorkflowState:
    """Create a sample workflow state."""
    return WorkflowState(
        workflow_id="wf-test-123",
        jira_ticket_id="SEC-456",
    )


@pytest.fixture
def mock_finding():
    """Create a mock analyzed finding."""
    finding = MagicMock()
    finding.finding_id = "finding-123"
    finding.vulnerability_type = VulnerabilityType.S3_ENCRYPTION_DISABLED
    finding.sanitized_title = "Test Finding"
    finding.sanitized_description = "Test Description"
    finding.search_query = "S3 encryption disabled"
    return finding


@pytest.fixture
def mock_playbook():
    """Create a mock playbook."""
    playbook = MagicMock()
    playbook.id = "playbook-123"
    playbook.vulnerability_type = VulnerabilityType.S3_ENCRYPTION_DISABLED
    playbook.name = "Test Playbook"
    return playbook


class TestAnalyzeNode:
    """Tests for analyze_finding node."""

    def test_analyze_with_finding(
        self, sample_state: WorkflowState, mock_finding
    ) -> None:
        """Test analyze node with an analyzed finding."""
        sample_state.analyzed_finding = mock_finding
        
        result = analyze_finding(sample_state)
        
        assert result["phase"] == WorkflowPhase.MATCHING

    def test_analyze_without_finding(self, sample_state: WorkflowState) -> None:
        """Test analyze node without a finding."""
        sample_state.analyzed_finding = None
        
        result = analyze_finding(sample_state)
        
        assert result["phase"] == WorkflowPhase.FAILED
        assert "error_message" in result


class TestMatchNode:
    """Tests for match_playbook node."""

    @patch("patchweave.agents.workflow.get_matcher")
    def test_match_success(
        self, mock_get_matcher, sample_state: WorkflowState, mock_finding, mock_playbook
    ) -> None:
        """Test successful playbook matching."""
        sample_state.analyzed_finding = mock_finding
        
        # Mock matcher
        mock_matcher = MagicMock()
        mock_result = MagicMock()
        mock_result.playbook = mock_playbook
        mock_result.similarity = 0.95
        mock_result.tier = MagicMock()
        mock_result.tier.value = "high"
        mock_matcher.match.return_value = mock_result
        mock_get_matcher.return_value = mock_matcher
        
        result = match_playbook(sample_state)
        
        assert result["matched_playbook"] == mock_playbook
        assert result["match_similarity"] == 0.95

    def test_match_without_finding(self, sample_state: WorkflowState) -> None:
        """Test match node without a finding."""
        sample_state.analyzed_finding = None
        
        result = match_playbook(sample_state)
        
        assert result["phase"] == WorkflowPhase.FAILED


class TestVerifyNode:
    """Tests for verify_match node."""

    def test_verify_types_match(
        self, sample_state: WorkflowState, mock_finding, mock_playbook
    ) -> None:
        """Test verification when vulnerability types match."""
        sample_state.analyzed_finding = mock_finding
        sample_state.matched_playbook = mock_playbook
        sample_state.match_similarity = 0.80
        
        result = verify_match(sample_state)
        
        assert result["verification_approved"] is True
        assert "match" in result["verification_reason"].lower()

    def test_verify_types_mismatch_low_similarity(
        self, sample_state: WorkflowState, mock_finding, mock_playbook
    ) -> None:
        """Test verification when types mismatch and similarity is low."""
        sample_state.analyzed_finding = mock_finding
        mock_playbook.vulnerability_type = VulnerabilityType.S3_PUBLIC_ACCESS
        sample_state.matched_playbook = mock_playbook
        sample_state.match_similarity = 0.72
        
        result = verify_match(sample_state)
        
        assert result["verification_approved"] is False

    def test_verify_no_playbook(self, sample_state: WorkflowState) -> None:
        """Test verification without a playbook."""
        sample_state.matched_playbook = None
        
        result = verify_match(sample_state)
        
        assert result["verification_approved"] is False


class TestValidateNode:
    """Tests for validate_playbook node."""

    @patch("patchweave.agents.workflow.get_validator")
    def test_validate_success(
        self, mock_get_validator, sample_state: WorkflowState, mock_playbook
    ) -> None:
        """Test successful validation."""
        sample_state.matched_playbook = mock_playbook
        sample_state.token_mapping = {"BUCKET_NAME": "test"}
        
        # Mock validator
        mock_validator = MagicMock()
        validated_state = WorkflowState(
            workflow_id=sample_state.workflow_id,
            jira_ticket_id=sample_state.jira_ticket_id,
        )
        # Mark all stages successful
        for stage in [
            ValidationStage.ENVIRONMENT_SETUP,
            ValidationStage.PRE_CHECK,
            ValidationStage.REMEDIATION,
            ValidationStage.POST_CHECK,
        ]:
            validated_state.set_stage_result(stage, ValidationStatus.SUCCESS)
        mock_validator.validate_playbook.return_value = validated_state
        mock_get_validator.return_value = mock_validator
        
        result = validate_playbook(sample_state)
        
        assert "stage_results" in result

    def test_validate_without_playbook(self, sample_state: WorkflowState) -> None:
        """Test validation without a playbook."""
        sample_state.matched_playbook = None
        
        result = validate_playbook(sample_state)
        
        assert result["phase"] == WorkflowPhase.FAILED


class TestApprovalNode:
    """Tests for request_approval node."""

    def test_request_approval(self, sample_state: WorkflowState) -> None:
        """Test approval request."""
        result = request_approval(sample_state)
        
        assert result["phase"] == WorkflowPhase.APPROVAL
        assert result["approval_status"] == ApprovalStatus.PENDING
        assert result["approval_requested_at"] is not None


class TestDeployNode:
    """Tests for deploy_remediation node."""

    @patch("patchweave.agents.workflow.get_deployer")
    def test_deploy_approved(
        self, mock_get_deployer, sample_state: WorkflowState, mock_playbook
    ) -> None:
        """Test deployment with approval."""
        sample_state.approval_status = ApprovalStatus.APPROVED
        sample_state.matched_playbook = mock_playbook
        sample_state.token_mapping = {"BUCKET_NAME": "test"}
        # Set validation stages as successful
        for stage in [
            ValidationStage.ENVIRONMENT_SETUP,
            ValidationStage.PRE_CHECK,
            ValidationStage.REMEDIATION,
            ValidationStage.POST_CHECK,
        ]:
            sample_state.set_stage_result(stage, ValidationStatus.SUCCESS)
        
        # Mock deployer
        mock_deployer = MagicMock()
        deployed_state = WorkflowState(
            workflow_id=sample_state.workflow_id,
            jira_ticket_id=sample_state.jira_ticket_id,
        )
        deployed_state.deployment_success = True
        mock_deployer.deploy.return_value = deployed_state
        mock_get_deployer.return_value = mock_deployer
        
        result = deploy_remediation(sample_state)
        
        assert result["phase"] == WorkflowPhase.COMPLETE

    def test_deploy_not_approved(self, sample_state: WorkflowState) -> None:
        """Test deployment without approval."""
        sample_state.approval_status = ApprovalStatus.PENDING
        
        result = deploy_remediation(sample_state)
        
        assert result["phase"] == WorkflowPhase.FAILED


class TestRouterFunctions:
    """Tests for router functions."""

    def test_route_after_match_high(self, sample_state: WorkflowState) -> None:
        """Test routing after high confidence match."""
        sample_state.match_tier = MatchTier.HIGH
        sample_state.match_similarity = 0.95
        
        result = route_after_match(sample_state)
        assert result == "validate"

    def test_route_after_match_moderate(self, sample_state: WorkflowState) -> None:
        """Test routing after moderate confidence match."""
        sample_state.match_tier = MatchTier.MODERATE
        sample_state.match_similarity = 0.80
        
        result = route_after_match(sample_state)
        assert result == "verify"

    def test_route_after_match_low(self, sample_state: WorkflowState) -> None:
        """Test routing after low confidence match."""
        sample_state.match_tier = MatchTier.LOW
        sample_state.match_similarity = 0.50
        
        result = route_after_match(sample_state)
        assert result == "no_playbook"

    def test_route_after_verify_approved(self, sample_state: WorkflowState) -> None:
        """Test routing after verification approval."""
        sample_state.verification_approved = True
        
        result = route_after_verify(sample_state)
        assert result == "validate"

    def test_route_after_verify_rejected(self, sample_state: WorkflowState) -> None:
        """Test routing after verification rejection."""
        sample_state.verification_approved = False
        
        result = route_after_verify(sample_state)
        assert result == "no_playbook"

    def test_route_after_validate_success(self, sample_state: WorkflowState) -> None:
        """Test routing after validation success."""
        for stage in [
            ValidationStage.ENVIRONMENT_SETUP,
            ValidationStage.PRE_CHECK,
            ValidationStage.REMEDIATION,
            ValidationStage.POST_CHECK,
        ]:
            sample_state.set_stage_result(stage, ValidationStatus.SUCCESS)
        
        result = route_after_validate(sample_state)
        assert result == "request_approval"

    def test_route_after_validate_failed(self, sample_state: WorkflowState) -> None:
        """Test routing after validation failure."""
        sample_state.set_stage_result(ValidationStage.PRE_CHECK, ValidationStatus.FAILED)
        
        result = route_after_validate(sample_state)
        assert result == "failed"

    def test_route_after_approval_approved(self, sample_state: WorkflowState) -> None:
        """Test routing after approval."""
        sample_state.approval_status = ApprovalStatus.APPROVED
        
        result = route_after_approval(sample_state)
        assert result == "deploy"

    def test_route_after_approval_rejected(self, sample_state: WorkflowState) -> None:
        """Test routing after rejection."""
        sample_state.approval_status = ApprovalStatus.REJECTED
        
        result = route_after_approval(sample_state)
        assert result == "rejected"


class TestWorkflowGraph:
    """Tests for workflow graph building."""

    def test_build_workflow_graph(self) -> None:
        """Test building the workflow graph."""
        graph = build_workflow_graph()
        
        assert graph is not None

    def test_get_workflow_singleton(self) -> None:
        """Test that get_workflow returns the same instance."""
        import patchweave.agents.workflow as wf_module
        wf_module._workflow = None
        
        wf1 = get_workflow()
        wf2 = get_workflow()
        
        assert wf1 is wf2


class TestTerminalNodes:
    """Tests for terminal workflow nodes."""

    def test_mark_no_playbook(self, sample_state: WorkflowState) -> None:
        """Test no playbook node."""
        sample_state.match_similarity = 0.40
        sample_state.match_tier = MatchTier.LOW
        
        result = mark_no_playbook(sample_state)
        
        assert result["phase"] == WorkflowPhase.FAILED
        assert "no suitable playbook" in result["error_message"].lower()

    def test_mark_rejected(self, sample_state: WorkflowState) -> None:
        """Test rejection node."""
        sample_state.rejection_reason = "Risk assessment failed"
        
        result = mark_rejected(sample_state)
        
        assert result["phase"] == WorkflowPhase.FAILED
        assert "rejected" in result["error_message"].lower()

    def test_mark_failed(self, sample_state: WorkflowState) -> None:
        """Test failure node."""
        sample_state.error_message = "Validation failed"
        
        result = mark_failed(sample_state)
        
        assert result["phase"] == WorkflowPhase.FAILED
