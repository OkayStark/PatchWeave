"""
Unit tests for Pydantic data models.
"""

import pytest
from datetime import datetime

from patchweave.models import (
    JiraStatus,
    VulnerabilityType,
    Severity,
    MatchTier,
    RawFinding,
    TokenMapping,
    AnalyzedFinding,
    Playbook,
    PlaybookMatch,
    ValidationResult,
    StageResult,
    ValidationStage,
    DeploymentResult,
    CloudProvider,
)


class TestJiraStatus:
    """Tests for JiraStatus enum."""

    def test_terminal_states(self):
        """Test that terminal states are correctly identified."""
        terminal = JiraStatus.terminal_states()
        assert JiraStatus.RESOLVED in terminal
        assert JiraStatus.REJECTED in terminal
        assert JiraStatus.NO_PLAYBOOK in terminal
        assert JiraStatus.VALIDATION_FAILED in terminal
        assert JiraStatus.DEPLOYMENT_FAILED in terminal
        assert JiraStatus.OPEN not in terminal

    def test_active_states(self):
        """Test that active states are correctly identified."""
        active = JiraStatus.active_states()
        assert JiraStatus.OPEN in active
        assert JiraStatus.ANALYZING in active
        assert JiraStatus.VALIDATING in active
        assert JiraStatus.RESOLVED not in active

    def test_is_terminal(self):
        """Test is_terminal method."""
        assert JiraStatus.RESOLVED.is_terminal()
        assert not JiraStatus.OPEN.is_terminal()


class TestVulnerabilityType:
    """Tests for VulnerabilityType enum."""

    def test_from_string_valid(self):
        """Test conversion from valid string."""
        assert VulnerabilityType.from_string("s3_public_access") == VulnerabilityType.S3_PUBLIC_ACCESS
        assert VulnerabilityType.from_string("S3_PUBLIC_ACCESS") == VulnerabilityType.S3_PUBLIC_ACCESS

    def test_from_string_invalid(self):
        """Test conversion from invalid string returns UNKNOWN."""
        assert VulnerabilityType.from_string("invalid_type") == VulnerabilityType.UNKNOWN
        assert VulnerabilityType.from_string("") == VulnerabilityType.UNKNOWN


class TestSeverity:
    """Tests for Severity enum."""

    def test_from_string_valid(self):
        """Test conversion from valid string."""
        assert Severity.from_string("Critical") == Severity.CRITICAL
        assert Severity.from_string("critical") == Severity.CRITICAL
        assert Severity.from_string("HIGH") == Severity.HIGH

    def test_from_string_invalid(self):
        """Test conversion from invalid string returns MEDIUM."""
        assert Severity.from_string("invalid") == Severity.MEDIUM

    def test_comparison(self):
        """Test severity comparison."""
        assert Severity.LOW < Severity.MEDIUM
        assert Severity.MEDIUM < Severity.HIGH
        assert Severity.HIGH < Severity.CRITICAL


class TestTokenMapping:
    """Tests for TokenMapping model."""

    def test_substitute(self, sample_token_mapping):
        """Test token substitution."""
        text = "Bucket {{BUCKET_NAME}} in region {{AWS_REGION}}"
        result = sample_token_mapping.substitute(text)
        assert result == "Bucket prod-logs-bucket in region us-east-1"

    def test_substitute_no_tokens(self, sample_token_mapping):
        """Test substitution when no tokens present."""
        text = "Plain text without tokens"
        result = sample_token_mapping.substitute(text)
        assert result == text

    def test_get_token(self, sample_token_mapping):
        """Test getting specific token."""
        assert sample_token_mapping.get_token("BUCKET_NAME") == "prod-logs-bucket"
        assert sample_token_mapping.get_token("MISSING", "default") == "default"


class TestRawFinding:
    """Tests for RawFinding model."""

    def test_creation(self, sample_raw_finding):
        """Test RawFinding creation."""
        assert sample_raw_finding.jira_ticket_id == "SEC-1234"
        assert sample_raw_finding.severity == "Critical"
        assert "prod-logs-bucket" in sample_raw_finding.title

    def test_validation(self):
        """Test that validation works."""
        with pytest.raises(Exception):
            RawFinding(
                jira_ticket_id="SEC-1234",
                # Missing required fields
            )


class TestAnalyzedFinding:
    """Tests for AnalyzedFinding model."""

    def test_creation(self, sample_analyzed_finding):
        """Test AnalyzedFinding creation."""
        assert sample_analyzed_finding.finding_id == "SEC-1234"
        assert sample_analyzed_finding.vulnerability_type == VulnerabilityType.S3_PUBLIC_ACCESS
        assert sample_analyzed_finding.analysis_confidence == 0.98

    def test_update_status(self, sample_analyzed_finding):
        """Test status update."""
        sample_analyzed_finding.update_status(JiraStatus.VALIDATING)
        assert sample_analyzed_finding.status == JiraStatus.VALIDATING

    def test_set_playbook_match(self, sample_analyzed_finding):
        """Test playbook match recording."""
        sample_analyzed_finding.set_playbook_match("playbook-123", 0.92)
        assert sample_analyzed_finding.matched_playbook_id == "playbook-123"
        assert sample_analyzed_finding.match_score == 0.92


class TestPlaybookMatch:
    """Tests for PlaybookMatch model."""

    def test_high_confidence(self, sample_playbook):
        """Test high confidence match."""
        match = PlaybookMatch.from_score(sample_playbook, 0.95)
        assert match.is_high_confidence
        assert not match.is_moderate_confidence
        assert match.has_playbook

    def test_moderate_confidence(self, sample_playbook):
        """Test moderate confidence match."""
        match = PlaybookMatch.from_score(sample_playbook, 0.80)
        assert not match.is_high_confidence
        assert match.is_moderate_confidence
        assert match.has_playbook

    def test_no_match(self, sample_playbook):
        """Test no match result."""
        match = PlaybookMatch.from_score(sample_playbook, 0.50)
        assert match.is_no_match
        assert not match.has_playbook

    def test_no_match_factory(self):
        """Test no_match factory method."""
        match = PlaybookMatch.no_match(query="test query")
        assert match.is_no_match
        assert match.playbook is None
        assert match.similarity_score == 0.0


class TestValidationResult:
    """Tests for ValidationResult model."""

    def test_creation(self, sample_playbook):
        """Test ValidationResult creation."""
        result = ValidationResult(
            finding_id="SEC-1234",
            playbook_id=sample_playbook.id,
        )
        assert not result.success
        assert result.total_duration_seconds is None

    def test_mark_complete(self, sample_playbook):
        """Test marking validation as complete."""
        result = ValidationResult(
            finding_id="SEC-1234",
            playbook_id=sample_playbook.id,
        )
        result.mark_complete(success=True)
        assert result.success
        assert result.completed_at is not None
        assert result.total_duration_seconds is not None

    def test_set_stage_result(self, sample_playbook):
        """Test setting stage results."""
        result = ValidationResult(
            finding_id="SEC-1234",
            playbook_id=sample_playbook.id,
        )
        stage_result = StageResult.success_result(
            stage=ValidationStage.PRE_CHECK,
            message="Success",
            duration=1.5,
        )
        result.set_stage_result(stage_result)
        assert result.pre_check is not None
        assert result.pre_check.success


class TestDeploymentResult:
    """Tests for DeploymentResult model."""

    def test_success_deployment(self):
        """Test successful deployment creation."""
        result = DeploymentResult.success_deployment(
            finding_id="SEC-1234",
            playbook_id="playbook-123",
            executed_code="boto3.client('s3')...",
            resources_modified=["arn:aws:s3:::bucket"],
            approved_by="user@example.com",
            approved_at=datetime.utcnow(),
        )
        assert result.success
        assert len(result.resources_modified) == 1

    def test_failed_deployment(self):
        """Test failed deployment creation."""
        result = DeploymentResult.failed_deployment(
            finding_id="SEC-1234",
            playbook_id="playbook-123",
            executed_code="boto3.client('s3')...",
            error="AccessDenied",
            approved_by="user@example.com",
            approved_at=datetime.utcnow(),
        )
        assert not result.success
        assert result.error == "AccessDenied"
