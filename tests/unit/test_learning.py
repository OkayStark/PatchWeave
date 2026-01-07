"""Tests for PatchWeave Learning Loop."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from patchweave.agents.state import (
    ApprovalStatus,
    ValidationStage,
    ValidationStatus,
    WorkflowPhase,
    WorkflowState,
)
from patchweave.learning import LearningLoop, get_learning_loop
from patchweave.models.enums import Severity, VulnerabilityType, MatchTier
from patchweave.models.finding import AnalyzedFinding
from patchweave.models.playbook import Playbook, PlaybookMatch


@pytest.fixture
def learning_loop():
    """Create a fresh learning loop for testing."""
    return LearningLoop()


@pytest.fixture
def sample_state():
    """Create a sample workflow state."""
    state = WorkflowState(
        workflow_id="wf-test-123",
        jira_ticket_id="SEC-456",
        approval_status=ApprovalStatus.APPROVED,
        approved_by="approver@example.com",
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


class TestLearningLoopInit:
    """Tests for LearningLoop initialization."""
    
    def test_initialization(self, learning_loop):
        """Test learning loop initialization."""
        assert learning_loop._remediation_history == []
        assert learning_loop._playbook_stats == {}
        assert learning_loop._finding_patterns == []


class TestRecordSuccessfulRemediation:
    """Tests for recording successful remediations."""
    
    def test_record_successful_remediation(
        self,
        learning_loop,
        sample_state,
        sample_finding,
        sample_playbook,
        sample_match,
    ):
        """Test recording a successful remediation."""
        record_id = learning_loop.record_successful_remediation(
            state=sample_state,
            finding=sample_finding,
            playbook=sample_playbook,
            match=sample_match,
        )
        
        # Should return a record ID
        assert record_id.startswith("rem-")
        assert sample_state.workflow_id in record_id
        
        # Should add to history
        assert len(learning_loop._remediation_history) == 1
        record = learning_loop._remediation_history[0]
        assert record["workflow_id"] == sample_state.workflow_id
        assert record["playbook_id"] == sample_playbook.id
        assert record["vulnerability_type"] == "s3_encryption_disabled"
    
    def test_record_updates_playbook_stats(
        self,
        learning_loop,
        sample_state,
        sample_finding,
        sample_playbook,
        sample_match,
    ):
        """Test that recording updates playbook statistics."""
        learning_loop.record_successful_remediation(
            state=sample_state,
            finding=sample_finding,
            playbook=sample_playbook,
            match=sample_match,
        )
        
        stats = learning_loop.get_playbook_stats(sample_playbook.id)
        
        assert stats is not None
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 0
        assert stats["playbook_name"] == sample_playbook.name
    
    def test_record_learns_finding_pattern(
        self,
        learning_loop,
        sample_state,
        sample_finding,
        sample_playbook,
        sample_match,
    ):
        """Test that recording learns finding patterns."""
        learning_loop.record_successful_remediation(
            state=sample_state,
            finding=sample_finding,
            playbook=sample_playbook,
            match=sample_match,
        )
        
        assert len(learning_loop._finding_patterns) == 1
        pattern = learning_loop._finding_patterns[0]
        assert pattern["vulnerability_type"] == "s3_encryption_disabled"
        assert pattern["successful_playbook_id"] == sample_playbook.id
    
    def test_multiple_remediations_increment_stats(
        self,
        learning_loop,
        sample_state,
        sample_finding,
        sample_playbook,
        sample_match,
    ):
        """Test that multiple remediations increment stats correctly."""
        # Record twice
        learning_loop.record_successful_remediation(
            state=sample_state,
            finding=sample_finding,
            playbook=sample_playbook,
            match=sample_match,
        )
        
        # Create new state for second remediation
        state2 = WorkflowState(
            workflow_id="wf-test-456",
            jira_ticket_id="SEC-789",
            approval_status=ApprovalStatus.APPROVED,
        )
        
        learning_loop.record_successful_remediation(
            state=state2,
            finding=sample_finding,
            playbook=sample_playbook,
            match=sample_match,
        )
        
        stats = learning_loop.get_playbook_stats(sample_playbook.id)
        assert stats["success_count"] == 2


class TestRecordFailedRemediation:
    """Tests for recording failed remediations."""
    
    def test_record_failed_remediation(
        self,
        learning_loop,
        sample_state,
        sample_finding,
        sample_playbook,
    ):
        """Test recording a failed remediation."""
        learning_loop.record_failed_remediation(
            state=sample_state,
            finding=sample_finding,
            playbook=sample_playbook,
            error="Permission denied",
        )
        
        stats = learning_loop.get_playbook_stats(sample_playbook.id)
        
        assert stats is not None
        assert stats["failure_count"] == 1
        assert stats["success_count"] == 0
        assert stats["last_failure_error"] == "Permission denied"
    
    def test_mixed_success_and_failure(
        self,
        learning_loop,
        sample_state,
        sample_finding,
        sample_playbook,
        sample_match,
    ):
        """Test recording both successful and failed remediations."""
        # Record success
        learning_loop.record_successful_remediation(
            state=sample_state,
            finding=sample_finding,
            playbook=sample_playbook,
            match=sample_match,
        )
        
        # Record failure
        learning_loop.record_failed_remediation(
            state=sample_state,
            finding=sample_finding,
            playbook=sample_playbook,
            error="Network error",
        )
        
        stats = learning_loop.get_playbook_stats(sample_playbook.id)
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 1


class TestGetStatistics:
    """Tests for retrieving statistics."""
    
    def test_get_playbook_stats_not_found(self, learning_loop):
        """Test getting stats for unknown playbook."""
        stats = learning_loop.get_playbook_stats("unknown-playbook")
        assert stats is None
    
    def test_get_all_playbook_stats(
        self,
        learning_loop,
        sample_state,
        sample_finding,
        sample_playbook,
        sample_match,
    ):
        """Test getting all playbook statistics."""
        learning_loop.record_successful_remediation(
            state=sample_state,
            finding=sample_finding,
            playbook=sample_playbook,
            match=sample_match,
        )
        
        all_stats = learning_loop.get_all_playbook_stats()
        
        assert len(all_stats) == 1
        assert all_stats[0]["playbook_id"] == sample_playbook.id
    
    def test_get_remediation_history(
        self,
        learning_loop,
        sample_state,
        sample_finding,
        sample_playbook,
        sample_match,
    ):
        """Test getting remediation history."""
        learning_loop.record_successful_remediation(
            state=sample_state,
            finding=sample_finding,
            playbook=sample_playbook,
            match=sample_match,
        )
        
        history = learning_loop.get_remediation_history()
        
        assert len(history) == 1
        assert history[0]["workflow_id"] == sample_state.workflow_id
    
    def test_get_remediation_history_limit(
        self,
        learning_loop,
        sample_state,
        sample_finding,
        sample_playbook,
        sample_match,
    ):
        """Test history limit parameter."""
        # Add multiple records
        for i in range(10):
            state = WorkflowState(
                workflow_id=f"wf-test-{i}",
                jira_ticket_id=f"SEC-{i}",
            )
            learning_loop.record_successful_remediation(
                state=state,
                finding=sample_finding,
                playbook=sample_playbook,
                match=sample_match,
            )
        
        # Get limited history
        history = learning_loop.get_remediation_history(limit=5)
        
        assert len(history) == 5


class TestLearningSummary:
    """Tests for learning summary."""
    
    def test_get_learning_summary_empty(self, learning_loop):
        """Test summary with no data."""
        summary = learning_loop.get_learning_summary()
        
        assert summary["remediation_history_count"] == 0
        assert summary["playbook_stats_count"] == 0
        assert summary["finding_patterns_count"] == 0
    
    def test_get_learning_summary_with_data(
        self,
        learning_loop,
        sample_state,
        sample_finding,
        sample_playbook,
        sample_match,
    ):
        """Test summary with recorded data."""
        learning_loop.record_successful_remediation(
            state=sample_state,
            finding=sample_finding,
            playbook=sample_playbook,
            match=sample_match,
        )
        
        summary = learning_loop.get_learning_summary()
        
        assert summary["remediation_history_count"] == 1
        assert summary["playbook_stats_count"] == 1
        assert summary["finding_patterns_count"] == 1
        assert len(summary["most_used_playbooks"]) == 1


class TestGetLearningLoop:
    """Tests for singleton pattern."""
    
    def test_get_learning_loop_returns_same_instance(self):
        """Test singleton behavior."""
        # Reset singleton
        import patchweave.learning as learning_module
        learning_module._learning_loop = None
        
        loop1 = get_learning_loop()
        loop2 = get_learning_loop()
        
        assert loop1 is loop2
