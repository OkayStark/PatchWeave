"""
Enumeration definitions for PatchWeave.

Contains all enum types used throughout the application for type safety
and consistent value handling.
"""

from enum import Enum


class JiraStatus(str, Enum):
    """
    All possible Jira workflow statuses for findings.

    These statuses represent the complete lifecycle of a security finding
    from initial discovery through remediation.
    """

    OPEN = "OPEN"
    ANALYZING = "ANALYZING"
    PLAYBOOK_SEARCH = "PLAYBOOK SEARCH"
    VERIFYING = "VERIFYING"
    NO_PLAYBOOK = "NO PLAYBOOK"
    VALIDATING = "VALIDATING"
    VALIDATION_FAILED = "VALIDATION FAILED"
    PENDING_APPROVAL = "PENDING APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEPLOYING = "DEPLOYING"
    DEPLOYMENT_FAILED = "DEPLOYMENT FAILED"
    RESOLVED = "RESOLVED"

    @classmethod
    def terminal_states(cls) -> set["JiraStatus"]:
        """Return states that represent end of processing."""
        return {
            cls.RESOLVED,
            cls.REJECTED,
            cls.NO_PLAYBOOK,
            cls.VALIDATION_FAILED,
            cls.DEPLOYMENT_FAILED,
        }

    @classmethod
    def active_states(cls) -> set["JiraStatus"]:
        """Return states where processing is ongoing."""
        return {
            cls.OPEN,
            cls.ANALYZING,
            cls.PLAYBOOK_SEARCH,
            cls.VERIFYING,
            cls.VALIDATING,
            cls.PENDING_APPROVAL,
            cls.APPROVED,
            cls.DEPLOYING,
        }

    def is_terminal(self) -> bool:
        """Check if this status is a terminal state."""
        return self in self.terminal_states()


class VulnerabilityType(str, Enum):
    """
    Fixed taxonomy of supported vulnerability types.

    This taxonomy ensures consistent classification and enables
    reliable playbook matching.
    """

    S3_PUBLIC_ACCESS = "s3_public_access"
    S3_ENCRYPTION_DISABLED = "s3_encryption_disabled"
    S3_VERSIONING_DISABLED = "s3_versioning_disabled"
    SECURITY_GROUP_OPEN_SSH = "security_group_open_ssh"
    SECURITY_GROUP_OPEN_RDP = "security_group_open_rdp"
    SECURITY_GROUP_UNRESTRICTED_EGRESS = "security_group_unrestricted_egress"
    EBS_UNENCRYPTED = "ebs_unencrypted"
    RDS_PUBLICLY_ACCESSIBLE = "rds_publicly_accessible"
    RDS_UNENCRYPTED = "rds_unencrypted"
    RDS_NO_BACKUP = "rds_no_backup"
    CLOUDTRAIL_DISABLED = "cloudtrail_disabled"
    VPC_FLOW_LOGS_DISABLED = "vpc_flow_logs_disabled"
    IAM_ROOT_ACCOUNT_USAGE = "iam_root_account_usage"
    IAM_MFA_DISABLED = "iam_mfa_disabled"
    KMS_KEY_ROTATION_DISABLED = "kms_key_rotation_disabled"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> "VulnerabilityType":
        """
        Convert string to VulnerabilityType, defaulting to UNKNOWN.

        Args:
            value: String value to convert

        Returns:
            Matching VulnerabilityType or UNKNOWN if not found
        """
        try:
            return cls(value.lower().strip())
        except ValueError:
            return cls.UNKNOWN


class Severity(str, Enum):
    """Finding severity levels."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"

    @classmethod
    def from_string(cls, value: str) -> "Severity":
        """
        Convert string to Severity with case-insensitive matching.

        Args:
            value: String value to convert

        Returns:
            Matching Severity or MEDIUM as default
        """
        value_lower = value.lower().strip()
        for severity in cls:
            if severity.value.lower() == value_lower:
                return severity
        # Default to MEDIUM for unknown severities
        return cls.MEDIUM

    def __lt__(self, other: "Severity") -> bool:
        """Enable severity comparison (CRITICAL > HIGH > MEDIUM > LOW > INFO)."""
        order = [self.INFO, self.LOW, self.MEDIUM, self.HIGH, self.CRITICAL]
        return order.index(self) < order.index(other)


class CloudProvider(str, Enum):
    """Supported cloud providers."""

    AWS = "AWS"
    # Future support:
    # AZURE = "Azure"
    # GCP = "GCP"


class MatchTier(str, Enum):
    """
    Three-tier matching result classification.

    Determines how a playbook match should be handled:
    - HIGH_CONFIDENCE: Proceed directly to validation
    - MODERATE_CONFIDENCE: Route to Playbook Verification Agent
    - NO_MATCH: Escalate as no suitable playbook
    """

    HIGH_CONFIDENCE = "high_confidence"  # ≥90%
    MODERATE_CONFIDENCE = "moderate_confidence"  # 70-89%
    NO_MATCH = "no_match"  # <70%


class VerificationDecision(str, Enum):
    """Playbook Verification Agent decision."""

    APPROVED = "approved"
    REJECTED = "rejected"


class ValidationStage(str, Enum):
    """Validation workflow stages."""

    ENVIRONMENT_CREATION = "environment_creation"
    PRE_CHECK = "pre_check"
    REMEDIATION = "remediation"
    POST_CHECK = "post_check"
    CLEANUP = "cleanup"

    def description(self) -> str:
        """Human-readable description of the stage."""
        descriptions = {
            self.ENVIRONMENT_CREATION: "Creating test environment",
            self.PRE_CHECK: "Verifying vulnerability exists",
            self.REMEDIATION: "Applying remediation",
            self.POST_CHECK: "Verifying fix applied",
            self.CLEANUP: "Cleaning up test environment",
        }
        return descriptions.get(self, self.value)
