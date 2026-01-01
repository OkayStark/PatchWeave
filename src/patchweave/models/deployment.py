"""
Deployment data models for PatchWeave.

Contains models for deployment execution and results.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DeploymentResult(BaseModel):
    """
    Result of production deployment.

    Records the outcome of applying a validated remediation to production.
    """

    finding_id: str = Field(
        ...,
        description="Finding that was remediated",
    )
    playbook_id: str = Field(
        ...,
        description="Playbook that was executed",
    )

    # Execution details
    success: bool = Field(
        ...,
        description="Whether deployment succeeded",
    )
    executed_code: str = Field(
        ...,
        description="Actual code executed (with real values substituted)",
    )

    # Results
    resources_modified: list[str] = Field(
        default_factory=list,
        description="List of resources that were modified",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if deployment failed",
    )
    output: Optional[str] = Field(
        default=None,
        description="Output from code execution",
    )

    # Timing
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When deployment started",
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When deployment completed",
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Time taken to deploy",
    )

    # Approval info
    approved_by: Optional[str] = Field(
        default=None,
        description="Who approved the deployment",
    )
    approved_at: Optional[datetime] = Field(
        default=None,
        description="When deployment was approved",
    )

    def mark_complete(self, success: bool, error: str | None = None) -> None:
        """Mark deployment as complete."""
        self.success = success
        self.error = error
        self.completed_at = datetime.utcnow()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

    def add_modified_resource(self, resource_arn: str) -> None:
        """Add a resource to the modified resources list."""
        if resource_arn not in self.resources_modified:
            self.resources_modified.append(resource_arn)

    @classmethod
    def success_deployment(
        cls,
        finding_id: str,
        playbook_id: str,
        executed_code: str,
        resources_modified: list[str],
        approved_by: str,
        approved_at: datetime,
        output: str | None = None,
    ) -> "DeploymentResult":
        """Create a successful deployment result."""
        result = cls(
            finding_id=finding_id,
            playbook_id=playbook_id,
            success=True,
            executed_code=executed_code,
            resources_modified=resources_modified,
            output=output,
            approved_by=approved_by,
            approved_at=approved_at,
        )
        result.mark_complete(success=True)
        return result

    @classmethod
    def failed_deployment(
        cls,
        finding_id: str,
        playbook_id: str,
        executed_code: str,
        error: str,
        approved_by: str,
        approved_at: datetime,
    ) -> "DeploymentResult":
        """Create a failed deployment result."""
        result = cls(
            finding_id=finding_id,
            playbook_id=playbook_id,
            success=False,
            executed_code=executed_code,
            error=error,
            approved_by=approved_by,
            approved_at=approved_at,
        )
        result.mark_complete(success=False, error=error)
        return result

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "finding_id": "SEC-1234",
                "playbook_id": "550e8400-...",
                "success": True,
                "executed_code": "s3.put_public_access_block(Bucket='prod-logs'...)",
                "resources_modified": ["arn:aws:s3:::prod-logs-bucket"],
                "started_at": "2026-01-16T10:16:31Z",
                "completed_at": "2026-01-16T10:16:33Z",
                "duration_seconds": 2.0,
                "approved_by": "john.security@company.com",
                "approved_at": "2026-01-16T10:15:00Z",
            }
        }
    )
