"""
Enumeration definitions for PatchWeave.

Contains all enum types used throughout the application for type safety
and consistent value handling.
"""

from enum import Enum


class JiraStatus(str, Enum):
    """
    All possible Jira workflow statuses for findings.

    These 10 statuses represent the complete lifecycle of a security finding
    from initial discovery through remediation.
    
    Active States (processing ongoing):
    - OPEN: New finding awaiting processing
    - ANALYZING: Being analyzed by LLM/matcher
    - VALIDATING: Playbook being validated in LocalStack TEST
    - PENDING_APPROVAL: Awaiting human approval
    - DEPLOYING: Approved remediation being deployed
    
    Terminal States (end of processing):
    - RESOLVED: Successfully remediated
    - REJECTED: Human rejected the remediation
    - NO_PLAYBOOK: No suitable playbook found (confidence < 70%)
    - VALIDATION_FAILED: Playbook failed validation in TEST
    - DEPLOYMENT_FAILED: Deployment to PROD failed
    """

    # Active states
    OPEN = "OPEN"
    ANALYZING = "ANALYZING"
    VALIDATING = "VALIDATING"
    PENDING_APPROVAL = "PENDING APPROVAL"
    DEPLOYING = "DEPLOYING"
    
    # Terminal states (success)
    RESOLVED = "RESOLVED"
    
    # Terminal states (failure/rejection)
    REJECTED = "REJECTED"
    NO_PLAYBOOK = "NO PLAYBOOK"
    VALIDATION_FAILED = "VALIDATION FAILED"
    DEPLOYMENT_FAILED = "DEPLOYMENT FAILED"

    @classmethod
    def terminal_states(cls) -> set["JiraStatus"]:
        """Return the 4 terminal states that represent end of processing."""
        return {
            cls.RESOLVED,
            cls.REJECTED,
            cls.NO_PLAYBOOK,
            cls.VALIDATION_FAILED,
            cls.DEPLOYMENT_FAILED,
        }

    @classmethod
    def active_states(cls) -> set["JiraStatus"]:
        """Return the 5 active states where processing is ongoing."""
        return {
            cls.OPEN,
            cls.ANALYZING,
            cls.VALIDATING,
            cls.PENDING_APPROVAL,
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
    LAMBDA_PUBLIC = "lambda_public"
    EC2_IMDSV1 = "ec2_imdsv1"
    ELB_LOGGING_DISABLED = "elb_logging"
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
0+
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
