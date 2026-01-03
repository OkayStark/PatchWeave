"""Tests for playbook matcher."""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from patchweave.core.matcher import (
    MatchResult,
    MatchTier,
    PlaybookMatcher,
    get_matcher,
    match_finding,
)
from patchweave.models.enums import CloudProvider, Severity, VulnerabilityType
from patchweave.models.finding import AnalyzedFinding as Finding
from patchweave.models.playbook import Playbook


def create_finding(**overrides) -> Finding:
    """Create a Finding with defaults for testing."""
    defaults = {
        "finding_id": str(uuid.uuid4()),
        "vulnerability_type": VulnerabilityType.S3_ENCRYPTION_DISABLED,
        "cloud_provider": CloudProvider.AWS,
        "resource_type": "AWS::S3::Bucket",
        "severity": Severity.HIGH,
        "search_query": "S3 bucket encryption server-side AES256",
        "sanitized_title": "S3 bucket lacks encryption",
        "sanitized_description": "The S3 bucket {{BUCKET_NAME}} does not have encryption enabled",
        "source_ticket_url": "https://jira.example.com/browse/SEC-123",
        "detected_at": datetime.utcnow(),
        "analysis_confidence": 0.95,
    }
    defaults.update(overrides)
    return Finding(**defaults)


@pytest.fixture
def sample_finding() -> Finding:
    """Create a sample finding for testing."""
    return create_finding()


@pytest.fixture
def sample_playbook() -> Playbook:
    """Create a sample playbook for testing."""
    return Playbook(
        id="playbook-s3-encryption",
        name="S3 Encryption Playbook",
        description="Enable AES-256 encryption for S3 buckets",
        vulnerability_type=VulnerabilityType.S3_ENCRYPTION_DISABLED,
        cloud_provider=CloudProvider.AWS,
        resource_type="AWS::S3::Bucket",
        severity=Severity.HIGH,
        search_text="S3 bucket encryption AES-256 server-side encryption data at rest",
        remediation_code="def remediate(): pass",
        pre_check_code="def pre_check(): pass",
        post_check_code="def post_check(): pass",
    )


@pytest.fixture
def mock_store() -> MagicMock:
    """Create a mock PlaybookStore."""
    return MagicMock()


class TestMatchTier:
    """Tests for MatchTier enum."""

    def test_tier_values(self) -> None:
        """Test tier enum values."""
        assert MatchTier.HIGH.value == "high"
        assert MatchTier.MODERATE.value == "moderate"
        assert MatchTier.LOW.value == "low"


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_high_tier_result(
        self, sample_finding: Finding, sample_playbook: Playbook
    ) -> None:
        """Test HIGH tier result properties."""
        result = MatchResult(
            finding=sample_finding,
            playbook=sample_playbook,
            similarity=0.95,
            tier=MatchTier.HIGH,
            requires_verification=False,
            auto_remediate=True,
        )

        # __post_init__ should set these based on tier
        assert result.requires_verification is False
        assert result.auto_remediate is True

    def test_moderate_tier_result(
        self, sample_finding: Finding, sample_playbook: Playbook
    ) -> None:
        """Test MODERATE tier result properties."""
        result = MatchResult(
            finding=sample_finding,
            playbook=sample_playbook,
            similarity=0.80,
            tier=MatchTier.MODERATE,
            requires_verification=True,
            auto_remediate=True,
        )

        assert result.requires_verification is True
        assert result.auto_remediate is True

    def test_low_tier_result(self, sample_finding: Finding) -> None:
        """Test LOW tier result properties."""
        result = MatchResult(
            finding=sample_finding,
            playbook=None,
            similarity=0.50,
            tier=MatchTier.LOW,
            requires_verification=False,
            auto_remediate=False,
        )

        assert result.requires_verification is False
        assert result.auto_remediate is False
        assert result.playbook is None


class TestPlaybookMatcher:
    """Tests for PlaybookMatcher class."""

    def test_initialization_defaults(self, mock_store: MagicMock) -> None:
        """Test matcher initialization with default thresholds."""
        matcher = PlaybookMatcher(store=mock_store)

        assert matcher.store == mock_store
        assert matcher.high_threshold == 0.90
        assert matcher.moderate_threshold == 0.70

    def test_initialization_custom_thresholds(self, mock_store: MagicMock) -> None:
        """Test matcher with custom thresholds."""
        matcher = PlaybookMatcher(
            store=mock_store,
            high_threshold=0.95,
            moderate_threshold=0.75,
        )

        assert matcher.high_threshold == 0.95
        assert matcher.moderate_threshold == 0.75

    def test_determine_tier_high(self, mock_store: MagicMock) -> None:
        """Test tier determination for high confidence."""
        matcher = PlaybookMatcher(store=mock_store)

        assert matcher._determine_tier(0.95) == MatchTier.HIGH
        assert matcher._determine_tier(0.90) == MatchTier.HIGH
        assert matcher._determine_tier(1.0) == MatchTier.HIGH

    def test_determine_tier_moderate(self, mock_store: MagicMock) -> None:
        """Test tier determination for moderate confidence."""
        matcher = PlaybookMatcher(store=mock_store)

        assert matcher._determine_tier(0.89) == MatchTier.MODERATE
        assert matcher._determine_tier(0.80) == MatchTier.MODERATE
        assert matcher._determine_tier(0.70) == MatchTier.MODERATE

    def test_determine_tier_low(self, mock_store: MagicMock) -> None:
        """Test tier determination for low confidence."""
        matcher = PlaybookMatcher(store=mock_store)

        assert matcher._determine_tier(0.69) == MatchTier.LOW
        assert matcher._determine_tier(0.50) == MatchTier.LOW
        assert matcher._determine_tier(0.0) == MatchTier.LOW

    def test_build_search_text(
        self, mock_store: MagicMock, sample_finding: Finding
    ) -> None:
        """Test search text construction from finding."""
        matcher = PlaybookMatcher(store=mock_store)
        search_text = matcher._build_search_text(sample_finding)

        # AnalyzedFinding uses sanitized_title and sanitized_description
        assert sample_finding.sanitized_title in search_text
        assert sample_finding.sanitized_description in search_text
        assert sample_finding.vulnerability_type.value in search_text
        assert sample_finding.resource_type in search_text
        assert sample_finding.severity.value in search_text

    def test_match_returns_high_confidence(
        self,
        mock_store: MagicMock,
        sample_finding: Finding,
        sample_playbook: Playbook,
    ) -> None:
        """Test matching returns HIGH tier for high similarity."""
        mock_store.search.return_value = [(sample_playbook, 0.95)]

        matcher = PlaybookMatcher(store=mock_store)
        result = matcher.match(sample_finding)

        assert result.tier == MatchTier.HIGH
        assert result.similarity == 0.95
        assert result.playbook == sample_playbook
        assert result.auto_remediate is True

    def test_match_returns_moderate_confidence(
        self,
        mock_store: MagicMock,
        sample_finding: Finding,
        sample_playbook: Playbook,
    ) -> None:
        """Test matching returns MODERATE tier for moderate similarity."""
        mock_store.search.return_value = [(sample_playbook, 0.80)]

        matcher = PlaybookMatcher(store=mock_store)
        result = matcher.match(sample_finding)

        assert result.tier == MatchTier.MODERATE
        assert result.similarity == 0.80
        assert result.requires_verification is True

    def test_match_returns_low_confidence(
        self,
        mock_store: MagicMock,
        sample_finding: Finding,
        sample_playbook: Playbook,
    ) -> None:
        """Test matching returns LOW tier for low similarity."""
        mock_store.search.return_value = [(sample_playbook, 0.50)]

        matcher = PlaybookMatcher(store=mock_store)
        result = matcher.match(sample_finding)

        assert result.tier == MatchTier.LOW
        assert result.similarity == 0.50
        assert result.auto_remediate is False

    def test_match_no_results(
        self, mock_store: MagicMock, sample_finding: Finding
    ) -> None:
        """Test matching when no playbooks found."""
        mock_store.search.return_value = []

        matcher = PlaybookMatcher(store=mock_store)
        result = matcher.match(sample_finding)

        assert result.tier == MatchTier.LOW
        assert result.similarity == 0.0
        assert result.playbook is None
        assert result.auto_remediate is False

    def test_match_by_type_uses_filter(
        self,
        mock_store: MagicMock,
        sample_finding: Finding,
        sample_playbook: Playbook,
    ) -> None:
        """Test match_by_type passes vulnerability type filter."""
        mock_store.search.return_value = [(sample_playbook, 0.92)]

        matcher = PlaybookMatcher(store=mock_store)
        matcher.match_by_type(sample_finding)

        # Should be called with vulnerability_type filter
        mock_store.search.assert_called()
        call_kwargs = mock_store.search.call_args[1]
        assert call_kwargs["vulnerability_type"] == sample_finding.vulnerability_type.value

    def test_match_by_type_fallback(
        self,
        mock_store: MagicMock,
        sample_finding: Finding,
        sample_playbook: Playbook,
    ) -> None:
        """Test match_by_type falls back to general search."""
        # First call (with filter) returns empty, second call returns match
        mock_store.search.side_effect = [[], [(sample_playbook, 0.75)]]

        matcher = PlaybookMatcher(store=mock_store)
        result = matcher.match_by_type(sample_finding)

        assert mock_store.search.call_count == 2
        assert result.playbook == sample_playbook

    def test_match_batch(
        self,
        mock_store: MagicMock,
        sample_playbook: Playbook,
    ) -> None:
        """Test batch matching of multiple findings."""
        findings = [
            create_finding(
                finding_id=f"finding-{i}",
                sanitized_title=f"Finding {i}",
                sanitized_description=f"Description {i}",
            )
            for i in range(3)
        ]

        # Return different similarities
        mock_store.search.side_effect = [
            [(sample_playbook, 0.95)],  # HIGH
            [(sample_playbook, 0.80)],  # MODERATE
            [(sample_playbook, 0.50)],  # LOW
        ]

        matcher = PlaybookMatcher(store=mock_store)
        results = matcher.match_batch(findings)

        assert len(results) == 3
        assert results[0].tier == MatchTier.HIGH
        assert results[1].tier == MatchTier.MODERATE
        assert results[2].tier == MatchTier.LOW

    def test_get_statistics(self, mock_store: MagicMock) -> None:
        """Test getting statistics from store."""
        mock_store.get_statistics.return_value = {"total_playbooks": 10}

        matcher = PlaybookMatcher(store=mock_store)
        stats = matcher.get_statistics()

        assert stats["total_playbooks"] == 10
        mock_store.get_statistics.assert_called_once()


class TestMatcherModuleFunctions:
    """Tests for module-level convenience functions."""

    @patch("patchweave.core.matcher._matcher", None)
    @patch("patchweave.core.matcher.PlaybookMatcher")
    def test_get_matcher_creates_instance(self, mock_class: MagicMock) -> None:
        """Test get_matcher creates instance on first call."""
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance

        result = get_matcher()

        mock_class.assert_called_once()
        assert result == mock_instance

    @patch("patchweave.core.matcher.get_matcher")
    def test_match_finding_convenience(
        self, mock_get_matcher: MagicMock, sample_finding: Finding
    ) -> None:
        """Test match_finding convenience function."""
        mock_matcher = MagicMock()
        mock_get_matcher.return_value = mock_matcher
        mock_result = MagicMock()
        mock_matcher.match_by_type.return_value = mock_result

        result = match_finding(sample_finding)

        mock_matcher.match_by_type.assert_called_once_with(sample_finding)
        assert result == mock_result


class TestMatcherThresholds:
    """Tests for threshold edge cases."""

    def test_exact_high_threshold(self, mock_store: MagicMock) -> None:
        """Test exact match at high threshold."""
        matcher = PlaybookMatcher(store=mock_store, high_threshold=0.90)

        assert matcher._determine_tier(0.90) == MatchTier.HIGH
        assert matcher._determine_tier(0.8999) == MatchTier.MODERATE

    def test_exact_moderate_threshold(self, mock_store: MagicMock) -> None:
        """Test exact match at moderate threshold."""
        matcher = PlaybookMatcher(
            store=mock_store, high_threshold=0.90, moderate_threshold=0.70
        )

        assert matcher._determine_tier(0.70) == MatchTier.MODERATE
        assert matcher._determine_tier(0.6999) == MatchTier.LOW

    def test_custom_thresholds(self, mock_store: MagicMock) -> None:
        """Test with custom threshold values."""
        matcher = PlaybookMatcher(
            store=mock_store,
            high_threshold=0.85,
            moderate_threshold=0.60,
        )

        assert matcher._determine_tier(0.85) == MatchTier.HIGH
        assert matcher._determine_tier(0.84) == MatchTier.MODERATE
        assert matcher._determine_tier(0.60) == MatchTier.MODERATE
        assert matcher._determine_tier(0.59) == MatchTier.LOW


class TestMatcherSearchText:
    """Tests for search text building."""

    def test_search_text_includes_search_query(self, mock_store: MagicMock) -> None:
        """Test search text includes the search query from finding."""
        finding = create_finding(
            search_query="S3 encryption AES-256 compliance",
            sanitized_title="S3 Bucket without encryption",
            sanitized_description="Bucket lacks server-side encryption",
        )

        matcher = PlaybookMatcher(store=mock_store)
        search_text = matcher._build_search_text(finding)

        assert "S3 Bucket without encryption" in search_text
        assert "S3 encryption AES-256 compliance" in search_text

    def test_search_text_includes_classification(self, mock_store: MagicMock) -> None:
        """Test search text includes classification fields."""
        finding = create_finding(
            vulnerability_type=VulnerabilityType.S3_ENCRYPTION_DISABLED,
            severity=Severity.HIGH,
            cloud_provider=CloudProvider.AWS,
        )

        matcher = PlaybookMatcher(store=mock_store)
        search_text = matcher._build_search_text(finding)

        assert "s3_encryption_disabled" in search_text
        assert "High" in search_text
        assert "AWS" in search_text
