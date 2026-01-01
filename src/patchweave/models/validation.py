"""
Validation workflow data models for PatchWeave.

Contains models for test environments, validation stages, and results.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from patchweave.models.enums import ValidationStage


class TestEnvironment(BaseModel):
    """
    Represents a temporary test environment for validation.

    Test environments are created via Terraform to replicate production
    vulnerabilities in an isolated setting.
    """

    environment_id: str = Field(
        ...,
        description="Unique environment ID",
    )
    finding_id: str = Field(
        ...,
        description="Associated finding being validated",
    )
    terraform_state_path: str = Field(
        ...,
        description="Path to Terraform state file",
    )
    terraform_dir: str = Field(
        ...,
        description="Directory containing Terraform configuration",
    )
    resources_created: list[str] = Field(
        default_factory=list,
        description="List of created resource identifiers",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the environment was created",
    )
    is_cleaned_up: bool = Field(
        default=False,
        description="Whether cleanup has been completed",
    )
    cleanup_attempted: bool = Field(
        default=False,
        description="Whether cleanup was attempted (may have failed)",
    )

    # Test environment specific tokens (different from production)
    test_tokens: dict[str, str] = Field(
        default_factory=dict,
        description="Token values for the test environment",
    )

    def mark_cleaned_up(self) -> None:
        """Mark the environment as successfully cleaned up."""
        self.is_cleaned_up = True
        self.cleanup_attempted = True

    def mark_cleanup_attempted(self) -> None:
        """Mark that cleanup was attempted (even if it failed)."""
        self.cleanup_attempted = True

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "environment_id": "env-sec-1234-a1b2c3d4",
                "finding_id": "SEC-1234",
                "terraform_state_path": "/tmp/patchweave/SEC-1234/terraform.tfstate",
                "terraform_dir": "/tmp/patchweave/SEC-1234",
                "resources_created": ["aws_s3_bucket.test_bucket"],
                "created_at": "2026-01-16T10:01:00Z",
                "is_cleaned_up": False,
                "test_tokens": {"BUCKET_NAME": "patchweave-test-sec-1234-a1b2c3d4"},
            }
        }
    )


class StageResult(BaseModel):
    """
    Result of a single validation stage.

    Each stage in the validation workflow produces a StageResult
    indicating success/failure and timing information.
    """

    stage: ValidationStage = Field(
        ...,
        description="Which validation stage this result is for",
    )
    success: bool = Field(
        ...,
        description="Whether the stage completed successfully",
    )
    message: str = Field(
        ...,
        description="Human-readable result message",
    )
    duration_seconds: float = Field(
        ...,
        ge=0.0,
        description="Time taken to complete the stage",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if the stage failed",
    )
    logs: list[str] = Field(
        default_factory=list,
        description="Captured log output from the stage",
    )
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the stage started",
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When the stage completed",
    )

    @classmethod
    def success_result(
        cls,
        stage: ValidationStage,
        message: str,
        duration: float,
        logs: list[str] | None = None,
    ) -> "StageResult":
        """Create a successful stage result."""
        return cls(
            stage=stage,
            success=True,
            message=message,
            duration_seconds=duration,
            logs=logs or [],
            completed_at=datetime.utcnow(),
        )

    @classmethod
    def failure_result(
        cls,
        stage: ValidationStage,
        error: str,
        duration: float,
        logs: list[str] | None = None,
    ) -> "StageResult":
        """Create a failed stage result."""
        return cls(
            stage=stage,
            success=False,
            message=f"Stage failed: {error}",
            duration_seconds=duration,
            error=error,
            logs=logs or [],
            completed_at=datetime.utcnow(),
        )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stage": "pre_check",
                "success": True,
                "message": "Vulnerability confirmed in test environment",
                "duration_seconds": 1.5,
                "logs": ["Checking public access block configuration..."],
            }
        }
    )


class ValidationResult(BaseModel):
    """
    Complete result of the validation workflow.

    Contains results from all validation stages and overall success status.
    """

    finding_id: str = Field(
        ...,
        description="Finding being validated",
    )
    playbook_id: str = Field(
        ...,
        description="Playbook being validated",
    )

    # Stage results
    environment_creation: Optional[StageResult] = Field(
        default=None,
        description="Result of environment creation stage",
    )
    pre_check: Optional[StageResult] = Field(
        default=None,
        description="Result of pre-check verification stage",
    )
    remediation: Optional[StageResult] = Field(
        default=None,
        description="Result of remediation execution stage",
    )
    post_check: Optional[StageResult] = Field(
        default=None,
        description="Result of post-check verification stage",
    )
    cleanup: Optional[StageResult] = Field(
        default=None,
        description="Result of cleanup stage",
    )

    # Overall result
    success: bool = Field(
        default=False,
        description="Whether validation succeeded overall",
    )
    failure_stage: Optional[ValidationStage] = Field(
        default=None,
        description="Which stage failed (if any)",
    )
    failure_reason: Optional[str] = Field(
        default=None,
        description="Reason for failure (if any)",
    )

    # Timing
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When validation started",
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When validation completed",
    )
    total_duration_seconds: Optional[float] = Field(
        default=None,
        description="Total validation duration",
    )

    # Environment reference
    environment_id: Optional[str] = Field(
        default=None,
        description="ID of the test environment used",
    )

    def set_stage_result(self, result: StageResult) -> None:
        """Set the result for a specific stage."""
        stage_map = {
            ValidationStage.ENVIRONMENT_CREATION: "environment_creation",
            ValidationStage.PRE_CHECK: "pre_check",
            ValidationStage.REMEDIATION: "remediation",
            ValidationStage.POST_CHECK: "post_check",
            ValidationStage.CLEANUP: "cleanup",
        }
        attr_name = stage_map.get(result.stage)
        if attr_name:
            setattr(self, attr_name, result)

    def mark_failed(self, stage: ValidationStage, reason: str) -> None:
        """Mark validation as failed at a specific stage."""
        self.success = False
        self.failure_stage = stage
        self.failure_reason = reason

    def mark_complete(self, success: bool) -> None:
        """Mark validation as complete."""
        self.success = success
        self.completed_at = datetime.utcnow()
        self.total_duration_seconds = (self.completed_at - self.started_at).total_seconds()

    def all_stages_passed(self) -> bool:
        """Check if all validation stages passed (excluding cleanup)."""
        stages = [
            self.environment_creation,
            self.pre_check,
            self.remediation,
            self.post_check,
        ]
        return all(s is not None and s.success for s in stages)

    def get_summary(self) -> dict:
        """Get a summary of all stage results."""
        stages = {
            "environment_creation": self.environment_creation,
            "pre_check": self.pre_check,
            "remediation": self.remediation,
            "post_check": self.post_check,
            "cleanup": self.cleanup,
        }
        return {
            name: {
                "success": stage.success if stage else None,
                "duration": stage.duration_seconds if stage else None,
            }
            for name, stage in stages.items()
        }

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "finding_id": "SEC-1234",
                "playbook_id": "550e8400-...",
                "success": True,
                "total_duration_seconds": 18.5,
                "environment_creation": {"stage": "environment_creation", "success": True},
                "pre_check": {"stage": "pre_check", "success": True},
                "remediation": {"stage": "remediation", "success": True},
                "post_check": {"stage": "post_check", "success": True},
                "cleanup": {"stage": "cleanup", "success": True},
            }
        }
    )
