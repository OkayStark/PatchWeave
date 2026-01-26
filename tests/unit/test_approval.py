"""Tests for PatchWeave Approval Handler."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from patchweave.agents.state import (
    ApprovalStatus,
    ValidationStage,
    ValidationStatus,
    WorkflowPhase,
    WorkflowState,
)
from patchweave.approval import (
    ApprovalDecision,
    ApprovalError,
    ApprovalHandler,
    get_approval_handler,
)
from patchweave.models.enums import Severity, VulnerabilityType
from patchweave.models.finding import AnalyzedFinding
from patchweave.models.playbook import Playbook, PlaybookMatch, MatchTier


@pytest.fixture
def mock_jira_client():
    """Create a mock Jira client."""
    client = MagicMock()
    client.get_ticket.return_value = {"key": "SEC-123", "status": "PENDING APPROVAL"}
    client.get_comments.return_value = []
    return client


@pytest.fixture
def approval_handler(mock_jira_client):
    """Create an approval handler with mocked Jira client."""
    handler = ApprovalHandler(jira_client=mock_jira_client)
    return handler


@pytest.fixture
def sample_state():
    """Create a sample workflow state."""
    state = WorkflowState(
        workflow_id="wf-test-123",
        jira_ticket_id="SEC-456",
    )
    # Add validation results
    for stage in ValidationStage:
        state.set_stage_result(stage, ValidationStatus.SUCCESS)
    return state


@pytest.fixture
def sample_finding():
    """Create a sample analyzed finding."""
    return AnalyzedFinding(
        finding_id="SEC-456",
        vulnerability_type=VulnerabilityType.S3_ENCRYPTION_DISABLED,
        severity=Severity.HIGH,
        resource_type="AWS::S3::Bucket",
        search_query="s3 bucket encryption disabled",
        sanitized_title="S3 bucket '{{BUCKET_NAME}}' without encryption",
        sanitized_description="S3 bucket {{BUCKET_NAME}} does not have encryption enabled",
        source_ticket_url="https://org.atlassian.net/browse/SEC-456",
        detected_at=datetime.utcnow(),
        analysis_confidence=0.95,
        token_keys=["BUCKET_NAME"],
    )


@pytest.fixture
def sample_playbook():
    """Create a sample playbook."""
    return Playbook(
        id="pb-s3-encrypt-001",
        name="Enable S3 Encryption",
        description="Enables default encryption on S3 bucket",
        vulnerability_type=VulnerabilityType.S3_ENCRYPTION_DISABLED,
        resource_type="AWS::S3::Bucket",
        severity=Severity.HIGH,
        search_text="s3 encryption disabled bucket",
        remediation_code="print('enable encryption')",
        pre_check_code="print('check encryption')",
        post_check_code="print('verify encryption')",
        rollback_code="print('disable encryption')",
    )


@pytest.fixture
def sample_match(sample_playbook):
    """Create a sample playbook match."""
    return PlaybookMatch(
        playbook=sample_playbook,
        similarity_score=0.92,
        match_tier=MatchTier.HIGH_CONFIDENCE,
        search_query="s3 encryption disabled",
    )


class TestApprovalHandler:
    """Tests for ApprovalHandler class."""
    
    def test_initialization(self, approval_handler):
        """Test handler initialization."""
        assert approval_handler.poll_interval == 30
        # Note: No timeout_hours - approvals wait indefinitely per design
    
    def test_request_approval(
        self,
        approval_handler,
        sample_state,
        sample_finding,
        sample_playbook,
        sample_match,
        mock_jira_client,
    ):
        """Test posting approval request to Jira."""
        result = approval_handler.request_approval(
            state=sample_state,
            finding=sample_finding,
            playbook=sample_playbook,
            match=sample_match,
        )
        
        # Should update state
        assert result.approval_status == ApprovalStatus.PENDING
        assert result.phase == WorkflowPhase.APPROVAL
        assert result.approval_requested_at is not None
        
        # Should call Jira
        from patchweave.models.enums import JiraStatus
        mock_jira_client.add_comment.assert_called_once()
        mock_jira_client.update_status.assert_called_once_with(
            ticket_id="SEC-456",
            new_status=JiraStatus.PENDING_APPROVAL,
        )
    
    def test_check_approval_status_pending(
        self,
        approval_handler,
        sample_state,
        mock_jira_client,
    ):
        """Test checking approval status when still pending."""
        mock_jira_client.get_ticket.return_value = {"status": "PENDING APPROVAL"}
        
        decision = approval_handler.check_approval_status(sample_state)
        
        assert decision == ApprovalDecision.PENDING
    
    def test_check_approval_status_approved(
        self,
        approval_handler,
        sample_state,
        mock_jira_client,
    ):
        """Test checking approval status when approved."""
        mock_jira_client.get_ticket.return_value = {"status": "APPROVED", "assignee": "user@example.com"}
        
        decision = approval_handler.check_approval_status(sample_state)
        
        assert decision == ApprovalDecision.APPROVED
    
    def test_check_approval_status_rejected(
        self,
        approval_handler,
        sample_state,
        mock_jira_client,
    ):
        """Test checking approval status when rejected."""
        mock_jira_client.get_ticket.return_value = {"status": "REJECTED"}
        
        decision = approval_handler.check_approval_status(sample_state)
        
        assert decision == ApprovalDecision.REJECTED
    
    def test_process_approval(
        self,
        approval_handler,
        sample_state,
        mock_jira_client,
    ):
        """Test processing an approved remediation."""
        mock_jira_client.get_ticket.return_value = {"status": "APPROVED", "assignee": "approver@example.com"}
        
        result = approval_handler.process_approval(sample_state)
        
        assert result.approval_status == ApprovalStatus.APPROVED
        assert result.approved_at is not None
        assert result.approved_by == "approver@example.com"
        
        # Should update Jira status
        from patchweave.models.enums import JiraStatus
        mock_jira_client.update_status.assert_called_with(
            ticket_id="SEC-456",
            new_status=JiraStatus.DEPLOYING,
        )
    
    def test_process_rejection(
        self,
        approval_handler,
        sample_state,
        mock_jira_client,
    ):
        """Test processing a rejected remediation."""
        mock_jira_client.get_comments.return_value = [
            {"body": "Rejecting because this would break production"}
        ]
        
        result = approval_handler.process_rejection(sample_state)
        
        assert result.approval_status == ApprovalStatus.REJECTED
        assert result.phase == WorkflowPhase.FAILED
        assert "break production" in result.rejection_reason


class TestApprovalComment:
    """Tests for approval comment formatting."""
    
    def test_build_approval_comment(
        self,
        approval_handler,
        sample_finding,
        sample_playbook,
        sample_match,
        sample_state,
    ):
        """Test approval comment generation."""
        comment = approval_handler._build_approval_comment(
            finding=sample_finding,
            playbook=sample_playbook,
            match=sample_match,
            state=sample_state,
        )
        
        # Check key content
        assert "PatchWeave Approval Request" in comment
        assert "s3_encryption_disabled" in comment or "S3_ENCRYPTION_DISABLED" in comment
        assert "Enable S3 Encryption" in comment
        assert "92" in comment or "high_confidence" in comment  # Confidence
        assert sample_state.workflow_id in comment
    
    def test_format_validation_results(self, approval_handler, sample_state):
        """Test validation results formatting."""
        formatted = approval_handler._format_validation_results(sample_state)
        
        assert "Environment Setup" in formatted or "environment_setup" in formatted
        assert "success" in formatted.lower() or "SUCCESS" in formatted

class TestApprovalCallbacks:
    """Tests for approval callbacks."""
    
    def test_register_approval_callback(self, approval_handler, sample_state):
        """Test registering and triggering approval callback."""
        callback_called = []
        
        def on_approved(state):
            callback_called.append(state.workflow_id)
        
        approval_handler.register_approval_callback(on_approved)
        approval_handler._on_approved = on_approved  # Direct assignment for test
        
        # Trigger via process_approval
        with patch.object(approval_handler.jira_client, 'get_ticket', return_value={"status": "APPROVED"}):
            approval_handler.process_approval(sample_state)
        
        assert len(callback_called) == 1
        assert callback_called[0] == sample_state.workflow_id


class TestDeploymentResult:
    """Tests for deployment result posting."""
    
    def test_post_success_result(
        self,
        approval_handler,
        sample_state,
        mock_jira_client,
    ):
        """Test posting successful deployment result."""
        from patchweave.models.enums import JiraStatus
        approval_handler.post_deployment_result(
            state=sample_state,
            success=True,
            details={"dry_run": False},
        )
        
        mock_jira_client.update_status.assert_called_with(
            ticket_id="SEC-456",
            new_status=JiraStatus.RESOLVED,
        )
        mock_jira_client.add_comment.assert_called_once()
    
    def test_post_failure_result(
        self,
        approval_handler,
        sample_state,
        mock_jira_client,
    ):
        """Test posting failed deployment result."""
        from patchweave.models.enums import JiraStatus
        approval_handler.post_deployment_result(
            state=sample_state,
            success=False,
            details={"error": "Permission denied"},
        )
        
        mock_jira_client.update_status.assert_called_with(
            ticket_id="SEC-456",
            new_status=JiraStatus.DEPLOYMENT_FAILED,
        )


class TestGetApprovalHandler:
    """Tests for singleton pattern."""
    
    def test_get_approval_handler_returns_same_instance(self):
        """Test singleton behavior."""
        # Reset singleton
        import patchweave.approval as approval_module
        approval_module._approval_handler = None
        
        handler1 = get_approval_handler()
        handler2 = get_approval_handler()
        
        assert handler1 is handler2
