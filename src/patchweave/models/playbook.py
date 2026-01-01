"""
Playbook data models for PatchWeave.

Contains models for remediation playbooks and playbook matching results.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from patchweave.models.enums import (
    VulnerabilityType,
    Severity,
    CloudProvider,
    MatchTier,
)


class Playbook(BaseModel):
    """
    Remediation playbook definition.

    A playbook contains all the information needed to detect, fix, and verify
    a specific type of cloud security vulnerability.
    """

    # Identification
    id: str = Field(
        ...,
        description="Unique playbook ID (UUID)",
    )
    name: str = Field(
        ...,
        description="Human-readable playbook name",
        examples=["S3 Block Public Access"],
    )
    description: str = Field(
        ...,
        description="Detailed description of what this playbook does",
    )

    # Classification
    vulnerability_type: VulnerabilityType = Field(
        ...,
        description="Type of vulnerability this playbook fixes",
    )
    cloud_provider: CloudProvider = Field(
        default=CloudProvider.AWS,
        description="Cloud provider this playbook targets",
    )
    resource_type: str = Field(
        ...,
        description="AWS resource type this playbook operates on",
        examples=["AWS::S3::Bucket", "AWS::EC2::SecurityGroup"],
    )
    severity: Severity = Field(
        ...,
        description="Typical severity of findings this playbook addresses",
    )

    # Semantic search content
    search_text: str = Field(
        ...,
        description="Text used for embedding generation and semantic search",
    )

    # Executable code (Python/Boto3)
    remediation_code: str = Field(
        ...,
        description="Python/Boto3 code to fix the vulnerability",
    )
    pre_check_code: str = Field(
        ...,
        description="Python code to verify vulnerability exists before remediation",
    )
    post_check_code: str = Field(
        ...,
        description="Python code to verify fix was successful",
    )

    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the playbook was created",
    )
    created_by: str = Field(
        default="PatchWeave Team",
        description="Author of the playbook",
    )
    version: str = Field(
        default="1.0.0",
        description="Playbook version",
    )

    # Requirements
    required_permissions: list[str] = Field(
        default_factory=list,
        description="IAM permissions required to execute this playbook",
    )
    estimated_execution_time_seconds: int = Field(
        default=30,
        description="Estimated time to execute remediation in seconds",
    )

    # Optional metadata
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for categorization",
    )
    compliance_frameworks: list[str] = Field(
        default_factory=list,
        description="Compliance frameworks this playbook helps satisfy",
        examples=[["CIS AWS 2.1.1", "SOC2"]],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "name": "S3 Block Public Access",
                "description": "Enables S3 Block Public Access settings on a bucket",
                "vulnerability_type": "s3_public_access",
                "cloud_provider": "AWS",
                "resource_type": "AWS::S3::Bucket",
                "severity": "Critical",
                "search_text": "S3 bucket public access Block Public Access disabled",
                "remediation_code": "import boto3\ns3 = boto3.client('s3')...",
                "pre_check_code": "# Check if public access is enabled",
                "post_check_code": "# Verify Block Public Access is enabled",
                "required_permissions": ["s3:GetPublicAccessBlock", "s3:PutPublicAccessBlock"],
                "estimated_execution_time_seconds": 5,
            }
        }
    )


class PlaybookMatch(BaseModel):
    """
    Result of playbook matching from ChromaDB.

    Contains the matched playbook, similarity score, and tier classification.
    """

    playbook: Optional[Playbook] = Field(
        default=None,
        description="Matched playbook (None if no match)",
    )
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity score between 0 and 1",
    )
    match_tier: MatchTier = Field(
        ...,
        description="Three-tier classification of the match",
    )

    # Additional context
    search_query: Optional[str] = Field(
        default=None,
        description="Query that was used for matching",
    )
    alternative_matches: list["PlaybookMatch"] = Field(
        default_factory=list,
        description="Other playbooks that also matched (lower scores)",
    )

    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high confidence match (≥90%)."""
        return self.match_tier == MatchTier.HIGH_CONFIDENCE

    @property
    def is_moderate_confidence(self) -> bool:
        """Check if this is a moderate confidence match (70-89%)."""
        return self.match_tier == MatchTier.MODERATE_CONFIDENCE

    @property
    def is_no_match(self) -> bool:
        """Check if this is a no-match result (<70%)."""
        return self.match_tier == MatchTier.NO_MATCH

    @property
    def has_playbook(self) -> bool:
        """Check if a playbook was found."""
        return self.playbook is not None and not self.is_no_match

    @classmethod
    def no_match(cls, query: str | None = None) -> "PlaybookMatch":
        """Create a no-match result."""
        return cls(
            playbook=None,
            similarity_score=0.0,
            match_tier=MatchTier.NO_MATCH,
            search_query=query,
        )

    @classmethod
    def from_score(
        cls,
        playbook: Playbook,
        score: float,
        high_threshold: float = 0.90,
        moderate_threshold: float = 0.70,
        query: str | None = None,
    ) -> "PlaybookMatch":
        """
        Create a PlaybookMatch with automatic tier classification.

        Args:
            playbook: The matched playbook
            score: Similarity score (0.0 to 1.0)
            high_threshold: Threshold for high confidence (default: 0.90)
            moderate_threshold: Threshold for moderate confidence (default: 0.70)
            query: The search query used

        Returns:
            PlaybookMatch with appropriate tier classification
        """
        if score >= high_threshold:
            tier = MatchTier.HIGH_CONFIDENCE
        elif score >= moderate_threshold:
            tier = MatchTier.MODERATE_CONFIDENCE
        else:
            tier = MatchTier.NO_MATCH

        return cls(
            playbook=playbook if tier != MatchTier.NO_MATCH else None,
            similarity_score=score,
            match_tier=tier,
            search_query=query,
        )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "playbook": {"id": "550e8400-...", "name": "S3 Block Public Access"},
                "similarity_score": 0.94,
                "match_tier": "high_confidence",
                "search_query": "S3 bucket public access enabled",
            }
        }
    )
