"""
Validator Agent for PatchWeave.

Handles the validation workflow including:
- Test environment setup (LocalStack/Terraform)
- Pre-remediation checks
- Remediation execution  
- Post-remediation verification
- Environment cleanup
"""

import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from patchweave.agents.state import (
    ValidationStage,
    ValidationStatus,
    WorkflowState,
)
from patchweave.config import settings
from patchweave.logging import get_logger
from patchweave.models.playbook import Playbook

log = get_logger(__name__)


class ValidatorAgent:
    """
    Agent responsible for validating remediation playbooks.
    
    Executes the full validation workflow:
    1. Set up test environment (LocalStack + Terraform)
    2. Run pre-check to confirm vulnerability exists
    3. Execute remediation code
    4. Run post-check to verify fix worked
    5. Clean up test environment (ALWAYS runs)
    """
    
    def __init__(
        self,
        localstack_endpoint: str | None = None,
        terraform_templates_dir: str | None = None,
    ):
        """
        Initialize the validator.
        
        Args:
            localstack_endpoint: LocalStack endpoint URL (defaults to TEST endpoint)
            terraform_templates_dir: Directory containing Terraform templates
        """
        # Use TEST endpoint for validation (creates/deletes test resources)
        self.localstack_endpoint = localstack_endpoint or settings.localstack_test_endpoint
        self.terraform_templates_dir = Path(
            terraform_templates_dir or settings.terraform_templates_directory
        )
        
        log.info(
            "validator_initialized",
            localstack_endpoint=self.localstack_endpoint,
            terraform_dir=str(self.terraform_templates_dir),
        )
    
    def validate_playbook(
        self,
        state: WorkflowState,
        playbook: Playbook,
        token_mapping: dict[str, str],
    ) -> WorkflowState:
        """
        Execute full validation workflow for a playbook.
        
        This method guarantees cleanup runs even if validation fails.
        
        Args:
            state: Current workflow state
            playbook: Playbook to validate
            token_mapping: Token to actual value mapping
            
        Returns:
            Updated workflow state with validation results
        """
        log.info(
            "validation_starting",
            workflow_id=state.workflow_id,
            playbook_id=playbook.id,
        )
        
        environment_state: dict[str, Any] = {}
        
        try:
            # Stage 1: Environment Setup
            environment_state = self._setup_environment(
                state, playbook, token_mapping
            )
            state.set_stage_result(
                ValidationStage.ENVIRONMENT_SETUP,
                ValidationStatus.SUCCESS,
                output=environment_state,
            )
            
            # Stage 2: Pre-Check
            pre_check_result = self._run_pre_check(
                state, playbook, token_mapping, environment_state
            )
            if not pre_check_result.get("vulnerability_exists", False):
                state.set_stage_result(
                    ValidationStage.PRE_CHECK,
                    ValidationStatus.FAILED,
                    error="Pre-check failed: vulnerability not found in test environment",
                )
                raise ValidationError("Pre-check failed: vulnerability not found")
                
            state.set_stage_result(
                ValidationStage.PRE_CHECK,
                ValidationStatus.SUCCESS,
                output=pre_check_result,
            )
            
            # Stage 3: Remediation
            remediation_result = self._run_remediation(
                state, playbook, token_mapping, environment_state
            )
            if not remediation_result.get("success", False):
                state.set_stage_result(
                    ValidationStage.REMEDIATION,
                    ValidationStatus.FAILED,
                    error=remediation_result.get("error", "Remediation failed"),
                )
                raise ValidationError(f"Remediation failed: {remediation_result.get('error')}")
                
            state.set_stage_result(
                ValidationStage.REMEDIATION,
                ValidationStatus.SUCCESS,
                output=remediation_result,
            )
            
            # Stage 4: Post-Check
            post_check_result = self._run_post_check(
                state, playbook, token_mapping, environment_state
            )
            if not post_check_result.get("fix_verified", False):
                state.set_stage_result(
                    ValidationStage.POST_CHECK,
                    ValidationStatus.FAILED,
                    error="Post-check failed: fix did not resolve vulnerability",
                )
                raise ValidationError("Post-check failed: fix not effective")
                
            state.set_stage_result(
                ValidationStage.POST_CHECK,
                ValidationStatus.SUCCESS,
                output=post_check_result,
            )
            
            log.info(
                "validation_successful",
                workflow_id=state.workflow_id,
                playbook_id=playbook.id,
            )
            
        except Exception as e:
            log.error(
                "validation_failed",
                workflow_id=state.workflow_id,
                playbook_id=playbook.id,
                error=str(e),
            )
            raise
            
        finally:
            # CRITICAL: Cleanup ALWAYS runs
            try:
                cleanup_result = self._cleanup_environment(
                    state, environment_state
                )
                state.set_stage_result(
                    ValidationStage.CLEANUP,
                    ValidationStatus.SUCCESS,
                    output=cleanup_result,
                )
            except Exception as cleanup_error:
                log.critical(
                    "cleanup_failed",
                    workflow_id=state.workflow_id,
                    error=str(cleanup_error),
                    _audit=True,
                )
                state.set_stage_result(
                    ValidationStage.CLEANUP,
                    ValidationStatus.FAILED,
                    error=str(cleanup_error),
                )
        
        state.environment = environment_state
        return state
    
    def _setup_environment(
        self,
        state: WorkflowState,
        playbook: Playbook,
        token_mapping: dict[str, str],
    ) -> dict[str, Any]:
        """
        Set up test environment using Terraform.
        
        Creates a simulated vulnerable resource in LocalStack
        that matches the finding's characteristics.
        
        Returns:
            Environment state dictionary
        """
        log.info(
            "setting_up_environment",
            workflow_id=state.workflow_id,
            resource_type=playbook.resource_type,
        )
        
        # Generate Terraform configuration
        tf_config = self._generate_terraform(playbook, token_mapping)
        
        # Create temporary directory for Terraform
        with tempfile.TemporaryDirectory() as tf_dir:
            tf_path = Path(tf_dir) / "main.tf"
            tf_path.write_text(tf_config)
            
            # Initialize Terraform
            self._run_terraform_command(["init"], tf_dir)
            
            # Apply Terraform
            apply_output = self._run_terraform_command(
                ["apply", "-auto-approve", "-json"],
                tf_dir,
            )
            
            # Parse outputs
            return {
                "terraform_dir": tf_dir,
                "endpoint_url": self.localstack_endpoint,
                "created_at": datetime.utcnow().isoformat(),
                "resources": self._parse_terraform_state(tf_dir),
                "apply_output": apply_output,
            }
    
    def _generate_terraform(
        self,
        playbook: Playbook,
        token_mapping: dict[str, str],
    ) -> str:
        """
        Generate Terraform configuration for test environment.
        
        Creates a vulnerable resource configuration based on 
        the playbook's target resource type.
        """
        resource_type = playbook.resource_type
        
        # AWS provider configuration for LocalStack
        provider_config = f'''
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  access_key                  = "test"
  secret_key                  = "test"
  region                      = "{token_mapping.get('AWS_REGION', 'us-east-1')}"
  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {{
    s3  = "{self.localstack_endpoint}"
    ec2 = "{self.localstack_endpoint}"
    rds = "{self.localstack_endpoint}"
    iam = "{self.localstack_endpoint}"
    sts = "{self.localstack_endpoint}"
    kms = "{self.localstack_endpoint}"
  }}
}}
'''
        
        # Resource-specific Terraform
        resource_config = self._get_resource_terraform(playbook, token_mapping)
        
        return provider_config + "\n" + resource_config
    
    def _get_resource_terraform(
        self,
        playbook: Playbook,
        token_mapping: dict[str, str],
    ) -> str:
        """Generate resource-specific Terraform based on playbook type."""
        vuln_type = playbook.vulnerability_type.value
        
        # S3 Bucket without encryption (for s3_encryption_disabled)
        if vuln_type == "s3_encryption_disabled":
            bucket_name = token_mapping.get("BUCKET_NAME", "test-vulnerable-bucket")
            return f'''
resource "aws_s3_bucket" "vulnerable" {{
  bucket = "{bucket_name}"
}}

output "bucket_name" {{
  value = aws_s3_bucket.vulnerable.bucket
}}
'''
        
        # S3 Bucket with public access (for s3_public_access)
        elif vuln_type == "s3_public_access":
            bucket_name = token_mapping.get("BUCKET_NAME", "test-public-bucket")
            return f'''
resource "aws_s3_bucket" "vulnerable" {{
  bucket = "{bucket_name}"
}}

resource "aws_s3_bucket_public_access_block" "vulnerable" {{
  bucket = aws_s3_bucket.vulnerable.id
  
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}}

output "bucket_name" {{
  value = aws_s3_bucket.vulnerable.bucket
}}
'''
        
        # Security Group with open SSH
        elif vuln_type == "security_group_open_ssh":
            return '''
resource "aws_vpc" "test" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_security_group" "vulnerable" {
  name        = "vulnerable-sg"
  description = "Security group with open SSH"
  vpc_id      = aws_vpc.test.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

output "security_group_id" {
  value = aws_security_group.vulnerable.id
}
'''
        
        # Default: empty resource (for testing)
        else:
            return '''
# Placeholder for unsupported resource type
output "status" {
  value = "placeholder"
}
'''
    
    def _run_terraform_command(
        self,
        args: list[str],
        working_dir: str,
    ) -> str:
        """Run a Terraform command and return output."""
        cmd = ["terraform"] + args
        
        log.debug(
            "running_terraform_command",
            command=" ".join(cmd),
            working_dir=working_dir,
        )
        
        try:
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
            
            if result.returncode != 0:
                log.error(
                    "terraform_command_failed",
                    command=" ".join(cmd),
                    stderr=result.stderr,
                )
                raise TerraformError(f"Terraform failed: {result.stderr}")
                
            return result.stdout
            
        except subprocess.TimeoutExpired:
            raise TerraformError("Terraform command timed out")
    
    def _parse_terraform_state(self, tf_dir: str) -> list[str]:
        """Parse Terraform state to get created resource IDs."""
        # This is a simplified implementation
        # In production, parse the actual state file
        return ["resource-1"]
    
    def _run_pre_check(
        self,
        state: WorkflowState,
        playbook: Playbook,
        token_mapping: dict[str, str],
        environment: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Run pre-check to verify vulnerability exists.
        
        Executes the playbook's pre_check_code against the test
        environment to confirm the vulnerable state.
        """
        log.info(
            "running_pre_check",
            workflow_id=state.workflow_id,
            playbook_id=playbook.id,
        )
        
        code = self._substitute_tokens(
            playbook.pre_check_code,
            token_mapping,
            environment,
        )
        
        result = self._execute_code_safely(code, environment)
        
        return {
            "vulnerability_exists": result.get("needs_remediation", True),
            "current_state": result.get("current_state"),
            "details": result,
        }
    
    def _run_remediation(
        self,
        state: WorkflowState,
        playbook: Playbook,
        token_mapping: dict[str, str],
        environment: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute remediation code against test environment.
        """
        log.info(
            "running_remediation",
            workflow_id=state.workflow_id,
            playbook_id=playbook.id,
        )
        
        code = self._substitute_tokens(
            playbook.remediation_code,
            token_mapping,
            environment,
        )
        
        try:
            result = self._execute_code_safely(code, environment)
            return {
                "success": True,
                "result": result,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    def _run_post_check(
        self,
        state: WorkflowState,
        playbook: Playbook,
        token_mapping: dict[str, str],
        environment: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Run post-check to verify remediation worked.
        """
        log.info(
            "running_post_check",
            workflow_id=state.workflow_id,
            playbook_id=playbook.id,
        )
        
        code = self._substitute_tokens(
            playbook.post_check_code,
            token_mapping,
            environment,
        )
        
        result = self._execute_code_safely(code, environment)
        
        return {
            "fix_verified": result.get("verified", False),
            "final_state": result.get("settings"),
            "details": result,
        }
    
    def _cleanup_environment(
        self,
        state: WorkflowState,
        environment: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Destroy test environment.
        
        This MUST be called in a finally block to guarantee
        cleanup runs even if validation fails.
        """
        log.info(
            "cleaning_up_environment",
            workflow_id=state.workflow_id,
        )
        
        tf_dir = environment.get("terraform_dir")
        
        if tf_dir and Path(tf_dir).exists():
            try:
                self._run_terraform_command(
                    ["destroy", "-auto-approve"],
                    tf_dir,
                )
            except Exception as e:
                log.error(
                    "terraform_destroy_failed",
                    workflow_id=state.workflow_id,
                    error=str(e),
                )
                # Re-raise to mark cleanup as failed
                raise
        
        return {
            "destroyed": True,
            "destroyed_at": datetime.utcnow().isoformat(),
        }
    
    def _substitute_tokens(
        self,
        code: str,
        token_mapping: dict[str, str],
        environment: dict[str, Any],
    ) -> str:
        """
        Substitute tokens in code with actual values.
        
        Handles both user tokens (BUCKET_NAME, etc.) and
        system tokens (AWS_ENDPOINT_URL, etc.).
        """
        # Add environment-specific tokens
        full_mapping = {
            **token_mapping,
            "AWS_ENDPOINT_URL": environment.get("endpoint_url", self.localstack_endpoint),
            "AWS_REGION": token_mapping.get("AWS_REGION", "us-east-1"),
        }
        
        result = code
        for token, value in full_mapping.items():
            result = result.replace(f"{{{{{token}}}}}", str(value))
        
        return result
    
    def _execute_code_safely(
        self,
        code: str,
        environment: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute playbook code in a restricted environment.
        
        NOTE: In production, this would use a proper sandbox
        (e.g., RestrictedPython, subprocess isolation).
        """
        log.debug("executing_code", code_length=len(code))
        
        # Create execution namespace with AWS clients
        import boto3
        
        namespace = {
            "boto3": boto3,
            "__builtins__": {
                # Restricted builtins
                "print": print,
                "dict": dict,
                "list": list,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "True": True,
                "False": False,
                "None": None,
                "all": all,
                "any": any,
                "len": len,
                "range": range,
                "Exception": Exception,
            },
        }
        
        try:
            # Execute the code
            exec(code, namespace)
            
            # Look for result in namespace
            if "result" in namespace:
                return namespace["result"]
            elif "pre_check" in namespace:
                # Call pre_check function
                return namespace["pre_check"](
                    bucket_name=environment.get("bucket_name", "test-bucket"),
                )
            elif "remediate" in namespace:
                # Call remediate function
                return namespace["remediate"](
                    bucket_name=environment.get("bucket_name", "test-bucket"),
                )
            elif "post_check" in namespace:
                # Call post_check function
                return namespace["post_check"](
                    bucket_name=environment.get("bucket_name", "test-bucket"),
                )
            else:
                return {"executed": True}
                
        except Exception as e:
            log.error("code_execution_failed", error=str(e))
            raise CodeExecutionError(f"Code execution failed: {e}")


class ValidationError(Exception):
    """Validation workflow error."""
    pass


class TerraformError(Exception):
    """Terraform execution error."""
    pass


class CodeExecutionError(Exception):
    """Code execution error."""
    pass


def create_validator() -> ValidatorAgent:
    """Factory function to create a validator agent."""
    return ValidatorAgent()


# Singleton instance
_validator: ValidatorAgent | None = None


def get_validator() -> ValidatorAgent:
    """Get or create the global validator agent."""
    global _validator
    if _validator is None:
        _validator = create_validator()
    return _validator
