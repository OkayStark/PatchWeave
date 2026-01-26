"""
Deployer Agent for PatchWeave.

Handles production deployment of validated remediation playbooks
after human approval has been granted.
"""

import re
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from patchweave.agents.state import (
    ApprovalStatus,
    WorkflowState,
)
from patchweave.config import settings
from patchweave.logging import get_logger
from patchweave.models.playbook import Playbook

log = get_logger(__name__)


class DeployerAgent:
    """
    Agent responsible for deploying remediations to production.
    
    ONLY executes after:
    1. Validation passes in test environment
    2. Human approval is granted in Jira
    
    This is the only agent that touches production resources.
    """
    
    def __init__(
        self,
        aws_region: str | None = None,
        dry_run: bool | None = None,
    ):
        """
        Initialize the deployer.
        
        Args:
            aws_region: AWS region for deployment
            dry_run: If True, simulate but don't execute (for testing).
                     If None, uses settings.deployment_dry_run
        """
        self.aws_region = aws_region or settings.aws_region
        self.dry_run = dry_run if dry_run is not None else settings.deployment_dry_run
        
        log.info(
            "deployer_initialized",
            region=self.aws_region,
            dry_run=self.dry_run,
        )
    
    def deploy(
        self,
        state: WorkflowState,
        playbook: Playbook,
        token_mapping: dict[str, str],
    ) -> WorkflowState:
        """
        Deploy remediation to production.
        
        Preconditions:
        - Validation must have passed
        - Approval status must be APPROVED
        
        Args:
            state: Current workflow state
            playbook: Validated playbook to deploy
            token_mapping: Token to value mapping
            
        Returns:
            Updated workflow state with deployment results
        """
        # Safety checks
        if state.approval_status != ApprovalStatus.APPROVED:
            raise DeploymentError(
                f"Cannot deploy without approval. Status: {state.approval_status}"
            )
        
        if not state.is_validation_successful():
            raise DeploymentError("Cannot deploy: validation did not pass")
        
        log.info(
            "deployment_starting",
            workflow_id=state.workflow_id,
            jira_ticket_id=state.jira_ticket_id,
            playbook_id=playbook.id,
            dry_run=self.dry_run,
            _audit=True,
        )
        
        try:
            if self.dry_run:
                result = self._dry_run_deployment(state, playbook, token_mapping)
            else:
                result = self._execute_deployment(state, playbook, token_mapping)
            
            state.deployment_success = result.get("success", False)
            state.deployed_at = datetime.utcnow()
            state.add_event(
                "deployment_complete",
                {
                    "success": state.deployment_success,
                    "dry_run": self.dry_run,
                    "result": result,
                },
            )
            
            log.info(
                "deployment_complete",
                workflow_id=state.workflow_id,
                success=state.deployment_success,
                dry_run=self.dry_run,
                _audit=True,
            )
            
        except Exception as e:
            state.deployment_success = False
            state.deployment_error = str(e)
            state.add_event(
                "deployment_failed",
                {"error": str(e)},
            )
            
            log.error(
                "deployment_failed",
                workflow_id=state.workflow_id,
                error=str(e),
                _audit=True,
            )
            raise
        
        return state
    
    def _dry_run_deployment(
        self,
        state: WorkflowState,
        playbook: Playbook,
        token_mapping: dict[str, str],
    ) -> dict[str, Any]:
        """
        Simulate deployment without making changes.
        
        Used for testing and validation.
        """
        log.info(
            "dry_run_deployment",
            workflow_id=state.workflow_id,
            playbook_id=playbook.id,
        )
        
        # Validate the code can at least be parsed
        code = self._prepare_code(playbook.remediation_code, token_mapping, use_localstack=False)
        
        try:
            compile(code, "<playbook>", "exec")
        except SyntaxError as e:
            return {
                "success": False,
                "error": f"Code syntax error: {e}",
                "dry_run": True,
            }
        
        return {
            "success": True,
            "dry_run": True,
            "message": "Dry run completed - no changes made",
            "code_valid": True,
        }
    
    def _execute_deployment(
        self,
        state: WorkflowState,
        playbook: Playbook,
        token_mapping: dict[str, str],
    ) -> dict[str, Any]:
        """
        Execute actual production deployment.
        
        This is the ONLY method that modifies production resources.
        In development mode with USE_LOCALSTACK=true, uses LocalStack PROD endpoint.
        """
        log.info(
            "executing_production_deployment",
            workflow_id=state.workflow_id,
            playbook_id=playbook.id,
            resource_type=playbook.resource_type,
            use_localstack=settings.use_localstack,
            _audit=True,
        )
        
        # Get AWS config for production (uses LocalStack PROD in dev mode)
        aws_config = settings.get_aws_config("production")
        
        # Get endpoint URL if using LocalStack
        endpoint_url = aws_config.get("endpoint_url")
        
        # Prepare code with token substitution
        # Add AWS_ENDPOINT_URL to token mapping for LocalStack PROD
        token_mapping_with_endpoint = token_mapping.copy()
        if endpoint_url:
            token_mapping_with_endpoint["AWS_ENDPOINT_URL"] = endpoint_url
        
        code = self._prepare_code(playbook.remediation_code, token_mapping_with_endpoint, use_localstack=bool(endpoint_url))
        
        # Create execution environment with production credentials
        session = boto3.Session(
            aws_access_key_id=aws_config.get("aws_access_key_id"),
            aws_secret_access_key=aws_config.get("aws_secret_access_key"),
            region_name=aws_config.get("region_name", self.aws_region),
        )
        
        namespace = {
            "boto3": boto3,
            "session": session,
            "endpoint_url": endpoint_url,  # Pass to remediation code
            "__builtins__": self._get_restricted_builtins(),
        }
        
        # Log if using LocalStack
        if endpoint_url:
            log.info(
                "using_localstack_prod",
                endpoint=endpoint_url,
                workflow_id=state.workflow_id,
            )
        
        try:
            # Execute remediation
            exec(code, namespace)
            
            # Look for result
            if "result" in namespace:
                result = namespace["result"]
            elif "remediate" in namespace:
                # Call remediate function
                result = namespace["remediate"](
                    **self._get_function_args(token_mapping, playbook)
                )
            else:
                result = {"executed": True}
            
            return {
                "success": True,
                "result": result,
            }
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            
            log.error(
                "aws_api_error",
                error_code=error_code,
                error_message=error_msg,
                _audit=True,
            )
            
            return {
                "success": False,
                "error": f"AWS API error: {error_code} - {error_msg}",
                "error_code": error_code,
            }
            
        except Exception as e:
            log.error(
                "deployment_execution_error",
                error=str(e),
                _audit=True,
            )
            
            return {
                "success": False,
                "error": str(e),
            }
    
    def _prepare_code(
        self,
        code: str,
        token_mapping: dict[str, str],
        use_localstack: bool = False,
    ) -> str:
        """Substitute tokens in code with actual values."""
        result = code
        
        # Substitute user tokens (including AWS_ENDPOINT_URL if provided)
        for token, value in token_mapping.items():
            result = result.replace(f"{{{{{token}}}}}", str(value))
        
        # If NOT using LocalStack (real AWS), remove endpoint_url parameters entirely
        if not use_localstack and "endpoint_url=" in result:
            log.info(
                "removing_endpoint_for_real_aws",
                message="Removing endpoint_url for real AWS deployment",
            )
            # Remove endpoint_url parameter from boto3 client calls
            # Match endpoint_url='...' or endpoint_url="..." with optional leading comma/space
            result = re.sub(r",?\s*endpoint_url=['\"][^'\"]*['\"]", "", result)
        
        return result
    
    def _get_restricted_builtins(self) -> dict[str, Any]:
        """Get restricted set of Python builtins for code execution."""
        return {
            "__import__": __import__,  # Needed for import statements in playbook code
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
            "isinstance": isinstance,
            "type": type,
        }
    
    def _get_function_args(
        self,
        token_mapping: dict[str, str],
        playbook: Playbook,
    ) -> dict[str, str]:
        """Build function arguments from token mapping."""
        # Map common tokens to function parameter names
        args = {}
        
        # Common parameter mappings
        param_mappings = {
            "BUCKET_NAME": "bucket_name",
            "SECURITY_GROUP_ID": "security_group_id",
            "INSTANCE_ID": "instance_id",
            "RDS_INSTANCE_ID": "rds_instance_id",
            "VOLUME_ID": "volume_id",
            "KEY_ID": "key_id",
            "ROLE_NAME": "role_name",
            "USER_NAME": "user_name",
            "TRAIL_NAME": "trail_name",
            "AWS_REGION": "region",
        }
        
        for token, param in param_mappings.items():
            if token in token_mapping:
                args[param] = token_mapping[token]
        
        return args
    
    def verify_deployment(
        self,
        state: WorkflowState,
        playbook: Playbook,
        token_mapping: dict[str, str],
    ) -> dict[str, Any]:
        """
        Verify that production deployment was successful.
        
        Runs the playbook's post_check_code against production
        to confirm the fix was applied.
        """
        log.info(
            "verifying_deployment",
            workflow_id=state.workflow_id,
            playbook_id=playbook.id,
        )
        
        code = self._prepare_code(playbook.post_check_code, token_mapping)
        
        namespace = {
            "boto3": boto3,
            "__builtins__": self._get_restricted_builtins(),
        }
        
        try:
            exec(code, namespace)
            
            if "result" in namespace:
                result = namespace["result"]
            elif "post_check" in namespace:
                result = namespace["post_check"](
                    **self._get_function_args(token_mapping, playbook)
                )
            else:
                result = {"verified": True}
            
            verified = result.get("verified", False)
            
            log.info(
                "deployment_verification_complete",
                workflow_id=state.workflow_id,
                verified=verified,
            )
            
            return {
                "verified": verified,
                "details": result,
            }
            
        except Exception as e:
            log.error(
                "deployment_verification_failed",
                workflow_id=state.workflow_id,
                error=str(e),
            )
            
            return {
                "verified": False,
                "error": str(e),
            }


class DeploymentError(Exception):
    """Deployment workflow error."""
    pass


def create_deployer(dry_run: bool = False) -> DeployerAgent:
    """Factory function to create a deployer agent."""
    return DeployerAgent(dry_run=dry_run)


# Singleton instance
_deployer: DeployerAgent | None = None


def get_deployer() -> DeployerAgent:
    """Get or create the global deployer agent."""
    global _deployer
    if _deployer is None:
        _deployer = create_deployer()
    return _deployer
