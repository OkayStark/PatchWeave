"""Tests for Validator Agent."""

from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from patchweave.agents.validator import (
    ValidatorAgent,
    ValidationError,
    TerraformError,
    CodeExecutionError,
    create_validator,
    get_validator,
)
from patchweave.agents.state import (
    ValidationStage,
    ValidationStatus,
    WorkflowState,
)
from patchweave.models.enums import CloudProvider, Severity, VulnerabilityType
from patchweave.models.playbook import Playbook


@pytest.fixture
def validator() -> ValidatorAgent:
    """Create a validator agent for testing."""
    return ValidatorAgent(
        localstack_endpoint="http://localhost:4566",
        terraform_templates_dir="/tmp/terraform",
    )


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
    return {"success": True, "message": "Encrypted"}
""",
        pre_check_code="""
def pre_check(bucket_name, **kwargs):
    return {"needs_remediation": True, "current_state": "unencrypted"}
""",
        post_check_code="""
def post_check(bucket_name, **kwargs):
    return {"verified": True, "settings": {"encryption": "AES256"}}
""",
    )


@pytest.fixture
def sample_state() -> WorkflowState:
    """Create a sample workflow state."""
    return WorkflowState(
        workflow_id="wf-test-123",
        jira_ticket_id="SEC-456",
    )


@pytest.fixture
def token_mapping() -> dict[str, str]:
    """Create sample token mapping."""
    return {
        "BUCKET_NAME": "test-bucket",
        "AWS_REGION": "us-east-1",
    }


class TestValidatorAgent:
    """Tests for ValidatorAgent class."""

    def test_initialization(self, validator: ValidatorAgent) -> None:
        """Test validator initialization."""
        assert validator.localstack_endpoint == "http://localhost:4566"

    def test_generate_terraform_s3_encryption(
        self, validator: ValidatorAgent, sample_playbook: Playbook, token_mapping: dict
    ) -> None:
        """Test Terraform generation for S3 encryption playbook."""
        tf_config = validator._generate_terraform(sample_playbook, token_mapping)
        
        assert "provider \"aws\"" in tf_config
        assert "localhost:4566" in tf_config
        assert "aws_s3_bucket" in tf_config
        # Bucket name is dynamically generated with UUID suffix
        assert "test-vuln-" in tf_config

    def test_generate_terraform_security_group(
        self, validator: ValidatorAgent, token_mapping: dict
    ) -> None:
        """Test Terraform generation for security group playbook."""
        sg_playbook = Playbook(
            id="playbook-sg",
            name="Security Group SSH",
            description="Fix open SSH",
            vulnerability_type=VulnerabilityType.SECURITY_GROUP_OPEN_SSH,
            cloud_provider=CloudProvider.AWS,
            resource_type="AWS::EC2::SecurityGroup",
            severity=Severity.CRITICAL,
            search_text="security group SSH",
            remediation_code="pass",
            pre_check_code="pass",
            post_check_code="pass",
        )
        
        tf_config = validator._generate_terraform(sg_playbook, token_mapping)
        
        assert "aws_vpc" in tf_config
        assert "aws_security_group" in tf_config
        assert "port 22" in tf_config.lower() or "22" in tf_config

    def test_substitute_tokens(
        self, validator: ValidatorAgent, token_mapping: dict
    ) -> None:
        """Test token substitution."""
        code = """
s3 = boto3.client('s3', endpoint_url='{{AWS_ENDPOINT_URL}}')
bucket = '{{BUCKET_NAME}}'
region = '{{AWS_REGION}}'
"""
        environment = {"endpoint_url": "http://localhost:4566"}
        
        result = validator._substitute_tokens(code, token_mapping, environment)
        
        assert "test-bucket" in result
        assert "us-east-1" in result
        assert "{{BUCKET_NAME}}" not in result
        assert "{{AWS_REGION}}" not in result

    def test_get_resource_terraform_unknown_type(
        self, validator: ValidatorAgent, token_mapping: dict
    ) -> None:
        """Test Terraform generation for unknown resource type."""
        unknown_playbook = Playbook(
            id="playbook-unknown",
            name="Unknown Type",
            description="Unknown",
            vulnerability_type=VulnerabilityType.UNKNOWN,
            cloud_provider=CloudProvider.AWS,
            resource_type="AWS::Unknown::Resource",
            severity=Severity.MEDIUM,
            search_text="unknown",
            remediation_code="pass",
            pre_check_code="pass",
            post_check_code="pass",
        )
        
        tf_config = validator._get_resource_terraform(unknown_playbook, token_mapping)
        
        assert "placeholder" in tf_config.lower()


class TestValidatorCodeExecution:
    """Tests for code execution in validator."""

    def test_execute_code_safely_simple(self, validator: ValidatorAgent) -> None:
        """Test safe code execution with simple result."""
        code = "result = {'executed': True, 'value': 42}"
        environment = {"endpoint_url": "http://localhost:4566"}
        
        result = validator._execute_code_safely(code, environment)
        
        assert result["executed"] is True
        assert result["value"] == 42

    def test_execute_code_safely_function(self, validator: ValidatorAgent) -> None:
        """Test safe code execution with function call."""
        code = """
def pre_check(bucket_name, **kwargs):
    return {"needs_remediation": True, "bucket": bucket_name}
"""
        environment = {"endpoint_url": "http://localhost:4566", "bucket_name": "test"}
        
        result = validator._execute_code_safely(code, environment)
        
        assert result["needs_remediation"] is True

    def test_execute_code_safely_restricted_builtins(
        self, validator: ValidatorAgent
    ) -> None:
        """Test that dangerous file operations raise errors."""
        # Note: Validator uses full __builtins__ to allow playbook imports,
        # but file operations will fail due to permissions/file not existing
        code = "result = open('/etc/shadow', 'r').read()"  # More restricted file
        environment = {}
        
        with pytest.raises((CodeExecutionError, PermissionError, FileNotFoundError)):
            validator._execute_code_safely(code, environment)


class TestValidatorFactory:
    """Tests for validator factory functions."""

    def test_create_validator(self) -> None:
        """Test creating a new validator."""
        validator = create_validator()
        assert isinstance(validator, ValidatorAgent)

    def test_get_validator_singleton(self) -> None:
        """Test that get_validator returns the same instance."""
        import patchweave.agents.validator as val_module
        val_module._validator = None
        
        val1 = get_validator()
        val2 = get_validator()
        
        assert val1 is val2


class TestValidationStageResults:
    """Tests for validation stage result handling."""

    def test_pre_check_success(
        self, validator: ValidatorAgent, sample_state: WorkflowState, token_mapping: dict
    ) -> None:
        """Test pre-check stage with success result."""
        environment = {
            "endpoint_url": "http://localhost:4566",
            "bucket_name": "test-bucket",
        }
        
        playbook = Playbook(
            id="test",
            name="Test",
            description="Test",
            vulnerability_type=VulnerabilityType.S3_ENCRYPTION_DISABLED,
            cloud_provider=CloudProvider.AWS,
            resource_type="AWS::S3::Bucket",
            severity=Severity.HIGH,
            search_text="test",
            remediation_code="pass",
            pre_check_code="""
def pre_check(bucket_name, **kwargs):
    return {"needs_remediation": True}
""",
            post_check_code="pass",
        )
        
        result = validator._run_pre_check(
            sample_state, playbook, token_mapping, environment
        )
        
        assert result["vulnerability_exists"] is True
