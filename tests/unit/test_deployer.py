"""Tests for Deployer Agent."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from patchweave.agents.deployer import (
    DeployerAgent,
    DeploymentError,
    create_deployer,
    get_deployer,
)
from patchweave.agents.state import (
    ApprovalStatus,
    ValidationStage,
    ValidationStatus,
    WorkflowState,
)
from patchweave.models.enums import CloudProvider, Severity, VulnerabilityType
from patchweave.models.playbook import Playbook


@pytest.fixture
def deployer() -> DeployerAgent:
    """Create a deployer agent in dry-run mode."""
    return DeployerAgent(dry_run=True)


@pytest.fixture
def sample_playbook() -> Playbook:
    """Create a sample playbook for testing."""
    return Playbook(
        id="playbook-test-123",
        name="Test S3 Encryption",
        description="Enable S3 bucket encryption",
        vulnerability_type=VulnerabilityType.S3_ENCRYPTION_DISABLED,
        cloud_provider=CloudProvider.AWS,
        resource_type="AWS::S3::Bucket",
        severity=Severity.HIGH,
        search_text="S3 encryption test",
        remediation_code="""
def remediate(bucket_name, **kwargs):
    return {"success": True, "message": "Encrypted " + bucket_name}
""",
        pre_check_code="""
def pre_check(bucket_name, **kwargs):
    return {"needs_remediation": True}
""",
        post_check_code="""
def post_check(bucket_name, **kwargs):
    return {"verified": True}
""",
    )


@pytest.fixture
def approved_state() -> WorkflowState:
    """Create an approved workflow state."""
    state = WorkflowState(
        workflow_id="wf-test-123",
        jira_ticket_id="SEC-456",
        approval_status=ApprovalStatus.APPROVED,
        approved_by="test-user",
    )
    # Mark validation stages as successful
    for stage in [
        ValidationStage.ENVIRONMENT_SETUP,
        ValidationStage.PRE_CHECK,
        ValidationStage.REMEDIATION,
        ValidationStage.POST_CHECK,
    ]:
        state.set_stage_result(stage, ValidationStatus.SUCCESS)
    return state


@pytest.fixture
def token_mapping() -> dict[str, str]:
    """Create sample token mapping."""
    return {
        "BUCKET_NAME": "prod-bucket",
        "AWS_REGION": "us-east-1",
    }


class TestDeployerAgent:
    """Tests for DeployerAgent class."""

    def test_initialization(self, deployer: DeployerAgent) -> None:
        """Test deployer initialization."""
        assert deployer.dry_run is True
        assert deployer.aws_region == "us-east-1"

    def test_initialization_non_dry_run(self) -> None:
        """Test deployer initialization without dry run."""
        deployer = DeployerAgent(dry_run=False)
        assert deployer.dry_run is False

    def test_deploy_requires_approval(
        self, deployer: DeployerAgent, sample_playbook: Playbook, token_mapping: dict
    ) -> None:
        """Test that deployment requires approval."""
        unapproved_state = WorkflowState(
            workflow_id="wf-test-123",
            jira_ticket_id="SEC-456",
            approval_status=ApprovalStatus.PENDING,
        )
        
        with pytest.raises(DeploymentError) as exc:
            deployer.deploy(unapproved_state, sample_playbook, token_mapping)
        
        assert "approval" in str(exc.value).lower()

    def test_deploy_requires_validation(
        self, deployer: DeployerAgent, sample_playbook: Playbook, token_mapping: dict
    ) -> None:
        """Test that deployment requires validation to pass."""
        approved_but_not_validated = WorkflowState(
            workflow_id="wf-test-123",
            jira_ticket_id="SEC-456",
            approval_status=ApprovalStatus.APPROVED,
        )
        
        with pytest.raises(DeploymentError) as exc:
            deployer.deploy(approved_but_not_validated, sample_playbook, token_mapping)
        
        assert "validation" in str(exc.value).lower()

    def test_dry_run_deployment(
        self,
        deployer: DeployerAgent,
        sample_playbook: Playbook,
        approved_state: WorkflowState,
        token_mapping: dict,
    ) -> None:
        """Test dry run deployment."""
        result_state = deployer.deploy(approved_state, sample_playbook, token_mapping)
        
        assert result_state.deployment_success is True
        assert result_state.deployed_at is not None

    def test_prepare_code_token_substitution(
        self, deployer: DeployerAgent, token_mapping: dict
    ) -> None:
        """Test code preparation with token substitution."""
        code = """
bucket = '{{BUCKET_NAME}}'
region = '{{AWS_REGION}}'
"""
        result = deployer._prepare_code(code, token_mapping)
        
        assert "prod-bucket" in result
        assert "us-east-1" in result
        assert "{{BUCKET_NAME}}" not in result

    def test_get_function_args(
        self, deployer: DeployerAgent, sample_playbook: Playbook, token_mapping: dict
    ) -> None:
        """Test function argument mapping."""
        args = deployer._get_function_args(token_mapping, sample_playbook)
        
        assert args["bucket_name"] == "prod-bucket"
        assert args["region"] == "us-east-1"

    def test_restricted_builtins(self, deployer: DeployerAgent) -> None:
        """Test restricted builtins are provided."""
        builtins = deployer._get_restricted_builtins()
        
        # Safe builtins should be present
        assert "print" in builtins
        assert "dict" in builtins
        assert "list" in builtins
        assert "True" in builtins
        assert "False" in builtins
        
        # Dangerous builtins should NOT be present
        assert "open" not in builtins
        assert "exec" not in builtins
        assert "eval" not in builtins
        assert "__import__" not in builtins

    def test_dry_run_validates_syntax(
        self, deployer: DeployerAgent, approved_state: WorkflowState, token_mapping: dict
    ) -> None:
        """Test dry run validates code syntax."""
        bad_playbook = Playbook(
            id="bad-playbook",
            name="Bad Syntax",
            description="Has syntax errors",
            vulnerability_type=VulnerabilityType.S3_ENCRYPTION_DISABLED,
            cloud_provider=CloudProvider.AWS,
            resource_type="AWS::S3::Bucket",
            severity=Severity.HIGH,
            search_text="test",
            remediation_code="def broken( missing paren",
            pre_check_code="pass",
            post_check_code="pass",
        )
        
        result = deployer._dry_run_deployment(approved_state, bad_playbook, token_mapping)
        
        assert result["success"] is False
        assert "syntax" in result["error"].lower()


class TestDeployerFactory:
    """Tests for deployer factory functions."""

    def test_create_deployer_default(self) -> None:
        """Test creating a deployer with defaults."""
        deployer = create_deployer()
        assert isinstance(deployer, DeployerAgent)

    def test_create_deployer_dry_run(self) -> None:
        """Test creating a deployer in dry run mode."""
        deployer = create_deployer(dry_run=True)
        assert deployer.dry_run is True

    def test_get_deployer_singleton(self) -> None:
        """Test that get_deployer returns the same instance."""
        import patchweave.agents.deployer as dep_module
        dep_module._deployer = None
        
        dep1 = get_deployer()
        dep2 = get_deployer()
        
        assert dep1 is dep2


class TestDeploymentAuditTrail:
    """Tests for deployment audit trail."""

    def test_deployment_adds_events(
        self,
        deployer: DeployerAgent,
        sample_playbook: Playbook,
        approved_state: WorkflowState,
        token_mapping: dict,
    ) -> None:
        """Test that deployment adds audit events."""
        initial_events = len(approved_state.events)
        
        result_state = deployer.deploy(approved_state, sample_playbook, token_mapping)
        
        # Should have new deployment events
        assert len(result_state.events) > initial_events
        
        # Check for deployment event
        event_types = [e["type"] for e in result_state.events]
        assert "deployment_complete" in event_types
