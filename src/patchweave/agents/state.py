"""
LangGraph state definitions for PatchWeave validation workflow.

Defines the state model that flows through the multi-agent
validation pipeline: analyze → match → validate → approve → deploy.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Annotated

from pydantic import BaseModel, Field

from patchweave.models.enums import Severity, VulnerabilityType
from patchweave.models.finding import AnalyzedFinding
from patchweave.models.playbook import Playbook


class WorkflowPhase(str, Enum):
    """Current phase in the remediation workflow."""
    
    INGESTION = "ingestion"
    ANALYSIS = "analysis"
    MATCHING = "matching"
    VERIFICATION = "verification"
    VALIDATION = "validation"
    APPROVAL = "approval"
    DEPLOYMENT = "deployment"
    COMPLETE = "complete"
    FAILED = "failed"


class ValidationStage(str, Enum):
    """Stages within the validation phase."""
    
    ENVIRONMENT_SETUP = "environment_setup"
    PRE_CHECK = "pre_check"
    REMEDIATION = "remediation"
    POST_CHECK = "post_check"
    CLEANUP = "cleanup"


class ValidationStatus(str, Enum):
    """Status of validation execution."""
    
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ApprovalStatus(str, Enum):
    """Human approval status."""
    
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MatchTier(str, Enum):
    """Confidence tier from playbook matching."""
    HIGH = "high"          # ≥90% - proceed to validation
    MODERATE = "moderate"  # 70-89% - needs verification
    LOW = "low"            # <70% - no suitable playbook


@dataclass
class StageResult:
    """Result from a validation stage."""
    
    stage: ValidationStage
    status: ValidationStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    logs: list[str] = field(default_factory=list)


@dataclass
class EnvironmentState:
    """State of the test environment."""
    
    environment_id: str | None = None
    terraform_state: dict[str, Any] | None = None
    resources_created: list[str] = field(default_factory=list)
    endpoint_url: str | None = None  # LocalStack or AWS endpoint
    is_active: bool = False
    created_at: datetime | None = None


class WorkflowState(BaseModel):
    """
    Main state object that flows through the LangGraph workflow.
    
    This contains all data needed to track a finding through
    the entire remediation pipeline.
    """
    
    # Workflow identification
    workflow_id: str = Field(
        description="Unique identifier for this workflow execution"
    )
    jira_ticket_id: str = Field(
        description="Source Jira ticket ID"
    )
    
    # Current status
    phase: WorkflowPhase = Field(
        default=WorkflowPhase.INGESTION,
        description="Current workflow phase"
    )
    
    # Finding data (populated during analysis)
    analyzed_finding: AnalyzedFinding | None = Field(
        default=None,
        description="Analyzed and classified finding"
    )
    token_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="Token to value mapping for sensitive data"
    )
    
    # Matching results (populated during matching)
    matched_playbook: Playbook | None = Field(
        default=None,
        description="Best matching playbook"
    )
    match_similarity: float = Field(
        default=0.0,
        description="Similarity score of the match"
    )
    match_tier: MatchTier | None = Field(
        default=None,
        description="Confidence tier of the match"
    )
    
    # Verification (for moderate confidence matches)
    verification_approved: bool | None = Field(
        default=None,
        description="Whether verification agent approved the match"
    )
    verification_reason: str = Field(
        default="",
        description="Reason for verification decision"
    )
    
    # Validation results (populated during validation)
    validation_stage: ValidationStage | None = Field(
        default=None,
        description="Current validation stage"
    )
    stage_results: dict[str, dict] = Field(
        default_factory=dict,
        description="Results from each validation stage"
    )
    environment: dict[str, Any] = Field(
        default_factory=dict,
        description="Test environment state"
    )
    
    # Approval status
    approval_status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING,
        description="Human approval status"
    )
    approval_requested_at: datetime | None = Field(
        default=None,
        description="When approval was requested"
    )
    approved_by: str | None = Field(
        default=None,
        description="Who approved (if approved)"
    )
    rejection_reason: str = Field(
        default="",
        description="Reason for rejection (if rejected)"
    )
    
    # Deployment results
    deployment_success: bool | None = Field(
        default=None,
        description="Whether production deployment succeeded"
    )
    deployment_error: str | None = Field(
        default=None,
        description="Deployment error message if failed"
    )
    deployed_at: datetime | None = Field(
        default=None,
        description="When production deployment completed"
    )
    
    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When workflow started"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if workflow failed"
    )
    
    # Audit trail
    events: list[dict] = Field(
        default_factory=list,
        description="Audit log of workflow events"
    )
    
    model_config = {"extra": "allow"}
    
    def add_event(self, event_type: str, details: dict[str, Any] | None = None) -> None:
        """Add an audit event to the workflow."""
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "phase": self.phase.value,
            "details": details or {},
        }
        self.events.append(event)
        self.updated_at = datetime.utcnow()
    
    def set_stage_result(
        self,
        stage: ValidationStage,
        status: ValidationStatus,
        output: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Record the result of a validation stage."""
        self.stage_results[stage.value] = {
            "status": status.value,
            "completed_at": datetime.utcnow().isoformat(),
            "output": output or {},
            "error": error,
        }
        self.validation_stage = stage
        self.add_event(
            f"validation_stage_{status.value}",
            {"stage": stage.value, "error": error},
        )
    
    def is_validation_successful(self) -> bool:
        """Check if all validation stages passed."""
        required_stages = [
            ValidationStage.ENVIRONMENT_SETUP,
            ValidationStage.PRE_CHECK,
            ValidationStage.REMEDIATION,
            ValidationStage.POST_CHECK,
        ]
        for stage in required_stages:
            result = self.stage_results.get(stage.value, {})
            if result.get("status") != ValidationStatus.SUCCESS.value:
                return False
        return True
    
    def get_remediation_code(self) -> str | None:
        """Get the remediation code with tokens substituted."""
        if not self.matched_playbook:
            return None
            
        code = self.matched_playbook.remediation_code
        for token, value in self.token_mapping.items():
            code = code.replace(f"{{{{{token}}}}}", value)
        return code


# Type alias for the state with reducer annotations
# LangGraph uses these for state updates
def merge_events(left: list[dict], right: list[dict]) -> list[dict]:
    """Merge event lists, preserving order."""
    return left + right


def latest_value(left: Any, right: Any) -> Any:
    """Take the latest non-None value."""
    return right if right is not None else left


# State update type for LangGraph
WorkflowStateUpdate = dict[str, Any]
