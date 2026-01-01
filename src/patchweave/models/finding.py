"""
Finding data models for PatchWeave.

Contains models for raw findings from Jira, tokenized findings,
and fully analyzed findings ready for playbook matching.
"""

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from patchweave.models.enums import (
    VulnerabilityType,
    Severity,
    CloudProvider,
    JiraStatus,
)


class RawFinding(BaseModel):
    """
    Raw finding data from Jira ticket before processing.

    This represents the unprocessed data directly from a Jira ticket
    that has been created by a CSPM tool.
    """

    jira_ticket_id: str = Field(
        ...,
        description="Jira ticket ID (e.g., SEC-1234)",
        examples=["SEC-1234"],
    )
    jira_ticket_url: str = Field(
        ...,
        description="Full URL to Jira ticket",
        examples=["https://org.atlassian.net/browse/SEC-1234"],
    )
    title: str = Field(
        ...,
        description="Ticket title",
        examples=["S3 Bucket 'prod-logs' has public access enabled"],
    )
    description: str = Field(
        ...,
        description="Ticket description (may contain sensitive data)",
    )
    severity: Optional[str] = Field(
        default=None,
        description="Severity from ticket (raw string)",
    )
    created_at: datetime = Field(
        ...,
        description="Ticket creation timestamp",
    )
    custom_fields: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional custom fields from the ticket",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "jira_ticket_id": "SEC-1234",
                "jira_ticket_url": "https://org.atlassian.net/browse/SEC-1234",
                "title": "S3 Bucket 'prod-logs-bucket' has public access enabled",
                "description": "The S3 bucket prod-logs-bucket in account 123456789012 (us-east-1) has Block Public Access disabled.",
                "severity": "Critical",
                "created_at": "2026-01-16T10:00:00Z",
                "custom_fields": {"cspm_source": "Wiz"},
            }
        }
    )


class TokenMapping(BaseModel):
    """
    Mapping of tokens to actual sensitive values.

    This stores the relationship between placeholder tokens (e.g., {{BUCKET_NAME}})
    and their actual values (e.g., 'prod-logs-bucket'). The mapping is used
    during deployment to substitute tokens back to real values.
    """

    finding_id: str = Field(
        ...,
        description="Associated finding ID",
    )
    tokens: Dict[str, str] = Field(
        default_factory=dict,
        description="Token name to actual value mapping",
    )

    def substitute(self, text: str) -> str:
        """
        Replace tokens in text with actual values.

        Args:
            text: Text containing {{TOKEN}} placeholders

        Returns:
            Text with tokens replaced by actual values
        """
        result = text
        for token, value in self.tokens.items():
            result = result.replace(f"{{{{{token}}}}}", value)
        return result

    def get_token(self, name: str, default: str = "") -> str:
        """
        Get a specific token value.

        Args:
            name: Token name (without braces)
            default: Default value if token not found

        Returns:
            Token value or default
        """
        return self.tokens.get(name, default)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "finding_id": "SEC-1234",
                "tokens": {
                    "ACCOUNT_ID": "123456789012",
                    "AWS_REGION": "us-east-1",
                    "BUCKET_NAME": "prod-logs-bucket",
                    "RESOURCE_ARN": "arn:aws:s3:::prod-logs-bucket",
                },
            }
        }
    )


class AnalyzedFinding(BaseModel):
    """
    Structured finding after Analyzer Agent processing.

    This represents a fully analyzed and classified finding that is
    ready for playbook matching and remediation.
    """

    # Identification
    finding_id: str = Field(
        ...,
        description="Jira ticket ID",
    )

    # Classification
    vulnerability_type: VulnerabilityType = Field(
        ...,
        description="Classified vulnerability type from fixed taxonomy",
    )
    cloud_provider: CloudProvider = Field(
        default=CloudProvider.AWS,
        description="Cloud provider",
    )
    resource_type: str = Field(
        ...,
        description="AWS resource type (e.g., AWS::S3::Bucket)",
        examples=["AWS::S3::Bucket", "AWS::EC2::SecurityGroup"],
    )
    severity: Severity = Field(
        ...,
        description="Normalized severity level",
    )

    # Semantic search
    search_query: str = Field(
        ...,
        description="Generated query for ChromaDB semantic search",
    )

    # Sanitized content
    sanitized_title: str = Field(
        ...,
        description="Title with sensitive data replaced by tokens",
    )
    sanitized_description: str = Field(
        ...,
        description="Description with sensitive data replaced by tokens",
    )

    # Token reference (actual values stored separately in TokenMapping)
    token_keys: list[str] = Field(
        default_factory=list,
        description="List of token names used in sanitization",
    )

    # Metadata
    source_ticket_url: str = Field(
        ...,
        description="URL to the original Jira ticket",
    )
    detected_at: datetime = Field(
        ...,
        description="When the finding was originally detected",
    )
    analyzed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When analysis was completed",
    )
    analysis_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Analyzer confidence score (0.0 to 1.0)",
    )

    # Current status
    status: JiraStatus = Field(
        default=JiraStatus.ANALYZING,
        description="Current processing status",
    )

    # Optional: matched playbook info (populated after matching)
    matched_playbook_id: Optional[str] = Field(
        default=None,
        description="ID of matched playbook (if any)",
    )
    match_score: Optional[float] = Field(
        default=None,
        description="Playbook match similarity score",
    )

    def update_status(self, new_status: JiraStatus) -> None:
        """Update the finding status."""
        self.status = new_status

    def set_playbook_match(self, playbook_id: str, score: float) -> None:
        """Record playbook match information."""
        self.matched_playbook_id = playbook_id
        self.match_score = score

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "finding_id": "SEC-1234",
                "vulnerability_type": "s3_public_access",
                "cloud_provider": "AWS",
                "resource_type": "AWS::S3::Bucket",
                "severity": "Critical",
                "search_query": "S3 bucket public access Block Public Access disabled",
                "sanitized_title": "S3 Bucket '{{BUCKET_NAME}}' has public access enabled",
                "sanitized_description": "The S3 bucket {{BUCKET_NAME}} in account {{ACCOUNT_ID}}...",
                "token_keys": ["BUCKET_NAME", "ACCOUNT_ID", "AWS_REGION"],
                "source_ticket_url": "https://org.atlassian.net/browse/SEC-1234",
                "detected_at": "2026-01-16T10:00:00Z",
                "analyzed_at": "2026-01-16T10:00:48Z",
                "analysis_confidence": 0.98,
                "status": "PLAYBOOK SEARCH",
            }
        }
    )
