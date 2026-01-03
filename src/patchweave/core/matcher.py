"""
Three-tier playbook matcher for PatchWeave.

Matches security findings to remediation playbooks using
semantic similarity with three confidence tiers:
- High (≥90%): Direct remediation with post-validation
- Moderate (70-89%): Remediation with verification step
- Low (<70%): No automatic remediation
"""

from dataclasses import dataclass
from enum import Enum

from patchweave.config import settings
from patchweave.core.chromadb import PlaybookStore, get_playbook_store
from patchweave.logging import get_logger
from patchweave.models.finding import AnalyzedFinding as Finding
from patchweave.models.playbook import Playbook

log = get_logger(__name__)


class MatchTier(str, Enum):
    """Confidence tiers for playbook matching."""
    HIGH = "high"          # ≥90% confidence
    MODERATE = "moderate"  # 70-89% confidence
    LOW = "low"            # <70% confidence


@dataclass
class MatchResult:
    """Result of matching a finding to a playbook."""
    finding: Finding
    playbook: Playbook | None
    similarity: float
    tier: MatchTier
    requires_verification: bool
    auto_remediate: bool
    
    def __post_init__(self) -> None:
        """Calculate derived fields based on tier."""
        if self.tier == MatchTier.HIGH:
            self.requires_verification = False
            self.auto_remediate = True
        elif self.tier == MatchTier.MODERATE:
            self.requires_verification = True
            self.auto_remediate = True
        else:  # LOW
            self.requires_verification = False
            self.auto_remediate = False


class PlaybookMatcher:
    """
    Matches security findings to remediation playbooks.
    
    Uses semantic similarity search against ChromaDB to find
    the best matching playbook, then applies confidence thresholds
    to determine the action tier.
    
    Thresholds (configurable):
    - High confidence: ≥ 0.90 (90%)
    - Moderate confidence: ≥ 0.70 (70%)
    - Low confidence: < 0.70
    """

    def __init__(
        self,
        store: PlaybookStore | None = None,
        high_threshold: float | None = None,
        moderate_threshold: float | None = None,
    ):
        """
        Initialize the matcher.
        
        Args:
            store: PlaybookStore instance (uses global if not provided)
            high_threshold: Minimum similarity for HIGH tier (default: 0.90)
            moderate_threshold: Minimum similarity for MODERATE tier (default: 0.70)
        """
        self.store = store or get_playbook_store()
        self.high_threshold = high_threshold or settings.high_confidence_threshold
        self.moderate_threshold = moderate_threshold or settings.moderate_confidence_threshold
        
        log.info(
            "matcher_initialized",
            high_threshold=self.high_threshold,
            moderate_threshold=self.moderate_threshold,
        )

    def _build_search_text(self, finding: Finding) -> str:
        """
        Build search text from a finding for semantic matching.
        
        Combines relevant fields to create a rich search query
        that captures the essence of the finding.
        
        Args:
            finding: Security finding to match
            
        Returns:
            Search text for semantic matching
        """
        # Use sanitized fields from AnalyzedFinding
        parts = [
            finding.sanitized_title,
            finding.sanitized_description,
            f"vulnerability type: {finding.vulnerability_type.value}",
            f"resource type: {finding.resource_type}",
            f"severity: {finding.severity.value}",
            f"cloud provider: {finding.cloud_provider.value}",
        ]
        
        # Use pre-generated search query if available
        if finding.search_query:
            parts.append(finding.search_query)
            
        return " ".join(parts)

    def _determine_tier(self, similarity: float) -> MatchTier:
        """
        Determine the confidence tier based on similarity score.
        
        Args:
            similarity: Similarity score (0.0 to 1.0)
            
        Returns:
            MatchTier based on thresholds
        """
        if similarity >= self.high_threshold:
            return MatchTier.HIGH
        elif similarity >= self.moderate_threshold:
            return MatchTier.MODERATE
        else:
            return MatchTier.LOW

    def match(self, finding: Finding) -> MatchResult:
        """
        Match a finding to the best playbook.
        
        Performs semantic search to find the most similar playbook,
        then determines the confidence tier and action path.
        
        Args:
            finding: Security finding to match
            
        Returns:
            MatchResult with playbook (if found) and tier info
        """
        search_text = self._build_search_text(finding)
        
        log.debug(
            "matching_finding",
            finding_id=finding.finding_id,
            vulnerability_type=finding.vulnerability_type.value,
            search_text_length=len(search_text),
        )
        
        # Search for matching playbooks
        results = self.store.search(
            query=search_text,
            n_results=1,  # Only need the best match
            cloud_provider=finding.cloud_provider.value,
        )
        
        if not results:
            log.info(
                "no_playbook_found",
                finding_id=finding.finding_id,
                vulnerability_type=finding.vulnerability_type.value,
            )
            return MatchResult(
                finding=finding,
                playbook=None,
                similarity=0.0,
                tier=MatchTier.LOW,
                requires_verification=False,
                auto_remediate=False,
            )
        
        # Best match
        playbook, similarity = results[0]
        tier = self._determine_tier(similarity)
        
        log.info(
            "playbook_matched",
            finding_id=finding.finding_id,
            playbook_id=playbook.id,
            playbook_name=playbook.name,
            similarity=round(similarity, 4),
            tier=tier.value,
        )
        
        return MatchResult(
            finding=finding,
            playbook=playbook,
            similarity=similarity,
            tier=tier,
            requires_verification=(tier == MatchTier.MODERATE),
            auto_remediate=(tier in [MatchTier.HIGH, MatchTier.MODERATE]),
        )

    def match_by_type(self, finding: Finding) -> MatchResult:
        """
        Match a finding using vulnerability type as primary filter.
        
        First searches within the same vulnerability type, then
        falls back to general search if no match found.
        
        Args:
            finding: Security finding to match
            
        Returns:
            MatchResult with playbook (if found) and tier info
        """
        search_text = self._build_search_text(finding)
        
        # First try matching with vulnerability type filter
        results = self.store.search(
            query=search_text,
            n_results=3,
            cloud_provider=finding.cloud_provider.value,
            vulnerability_type=finding.vulnerability_type.value,
        )
        
        if results:
            playbook, similarity = results[0]
            tier = self._determine_tier(similarity)
            
            log.info(
                "playbook_matched_by_type",
                finding_id=finding.finding_id,
                playbook_id=playbook.id,
                vulnerability_type=finding.vulnerability_type.value,
                similarity=round(similarity, 4),
                tier=tier.value,
            )
            
            return MatchResult(
                finding=finding,
                playbook=playbook,
                similarity=similarity,
                tier=tier,
                requires_verification=(tier == MatchTier.MODERATE),
                auto_remediate=(tier in [MatchTier.HIGH, MatchTier.MODERATE]),
            )
        
        # Fall back to general matching
        log.debug(
            "type_match_fallback",
            finding_id=finding.finding_id,
            vulnerability_type=finding.vulnerability_type.value,
        )
        return self.match(finding)

    def match_batch(self, findings: list[Finding]) -> list[MatchResult]:
        """
        Match multiple findings to playbooks.
        
        Args:
            findings: List of security findings
            
        Returns:
            List of MatchResults in same order as input
        """
        results = []
        
        for finding in findings:
            result = self.match_by_type(finding)
            results.append(result)
            
        # Log summary
        tier_counts = {"high": 0, "moderate": 0, "low": 0}
        for result in results:
            tier_counts[result.tier.value] += 1
            
        log.info(
            "batch_matching_complete",
            total=len(findings),
            high_confidence=tier_counts["high"],
            moderate_confidence=tier_counts["moderate"],
            low_confidence=tier_counts["low"],
        )
        
        return results

    def get_statistics(self) -> dict:
        """
        Get matching statistics for monitoring.
        
        Returns:
            Dictionary with playbook store statistics
        """
        return self.store.get_statistics()


# Global instance
_matcher: PlaybookMatcher | None = None


def get_matcher() -> PlaybookMatcher:
    """Get or create the global matcher instance."""
    global _matcher
    if _matcher is None:
        _matcher = PlaybookMatcher()
    return _matcher


def match_finding(finding: Finding) -> MatchResult:
    """
    Convenience function to match a single finding.
    
    Args:
        finding: Security finding to match
        
    Returns:
        MatchResult with playbook and tier info
    """
    return get_matcher().match_by_type(finding)
