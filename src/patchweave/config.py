"""
Configuration management for PatchWeave.

Loads configuration from environment variables with sensible defaults.
Uses pydantic-settings for validation and type conversion.
"""

from typing import Optional
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application Settings
    # -------------------------------------------------------------------------
    patchweave_env: str = Field(
        default="development",
        description="Environment: development or production",
    )
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="logs/patchweave.log", description="Log file path")

    # -------------------------------------------------------------------------
    # Jira Configuration
    # -------------------------------------------------------------------------
    jira_base_url: str = Field(
        default="https://example.atlassian.net",
        description="Jira instance URL",
    )
    jira_email: str = Field(
        default="patchweave@example.com",
        description="Jira service account email",
    )
    jira_api_token: str = Field(
        default="",
        description="Jira API token",
    )
    jira_project_key: str = Field(
        default="SEC",
        description="Jira project to monitor",
    )
    jira_open_status: str = Field(
        default="To Do",
        description="Jira status name for open/new findings (e.g., 'To Do', 'Open', 'OPEN')",
    )
    jira_poll_interval_seconds: int = Field(
        default=60,
        description="Polling interval for Jira in seconds",
    )
    approval_poll_interval_seconds: int = Field(
        default=30,
        description="Polling interval for approval status in seconds",
    )

    # -------------------------------------------------------------------------
    # AWS Test Environment
    # -------------------------------------------------------------------------
    aws_test_access_key_id: str = Field(
        default="test",
        description="AWS test account access key",
    )
    aws_test_secret_access_key: str = Field(
        default="test",
        description="AWS test account secret key",
    )
    aws_test_region: str = Field(default="us-east-1", description="AWS test region")

    # -------------------------------------------------------------------------
    # AWS Production Environment
    # -------------------------------------------------------------------------
    aws_prod_access_key_id: str = Field(
        default="",
        description="AWS prod account access key",
    )
    aws_prod_secret_access_key: str = Field(
        default="",
        description="AWS prod account secret key",
    )
    aws_prod_region: str = Field(default="us-east-1", description="AWS prod region")

    # -------------------------------------------------------------------------
    # LocalStack Configuration
    # -------------------------------------------------------------------------
    localstack_endpoint: str = Field(
        default="http://localhost:4566",
        description="LocalStack endpoint URL",
    )
    use_localstack: bool = Field(
        default=True,
        description="Use LocalStack instead of real AWS",
    )

    # -------------------------------------------------------------------------
    # ChromaDB Configuration
    # -------------------------------------------------------------------------
    chroma_host: str = Field(default="localhost", description="ChromaDB host")
    chroma_port: int = Field(default=8000, description="ChromaDB port")
    chroma_persist_directory: str = Field(
        default="./chroma_data",
        description="ChromaDB persistence directory",
    )

    # -------------------------------------------------------------------------
    # LLM Configuration
    # -------------------------------------------------------------------------
    llm_provider: str = Field(
        default="gemini",
        description="LLM provider to use: 'gemini' or 'openai'",
    )
    google_api_key: Optional[str] = Field(
        default=None,
        description="Google API key for Gemini",
    )
    google_api_key_2: Optional[str] = Field(
        default=None,
        description="Second Google API key for rate limit rotation",
    )
    google_api_key_3: Optional[str] = Field(
        default=None,
        description="Third Google API key for rate limit rotation",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key (optional, for OpenAI provider)",
    )
    llm_model: str = Field(
        default="gemini-1.5-flash",
        description="LLM model to use (gemini-1.5-flash for free tier, or gpt-4-turbo-preview for OpenAI)",
    )
    llm_temperature: float = Field(
        default=0.0,
        description="LLM temperature for generation",
    )

    # -------------------------------------------------------------------------
    # Playbooks Configuration
    # -------------------------------------------------------------------------
    playbooks_directory: str = Field(
        default="./playbooks",
        description="Directory containing playbook YAML files",
    )

    # -------------------------------------------------------------------------
    # Matching Thresholds
    # -------------------------------------------------------------------------
    high_confidence_threshold: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description="Threshold for high confidence matches (direct to validation)",
    )
    moderate_confidence_threshold: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Threshold for moderate confidence matches (needs verification)",
    )

    # -------------------------------------------------------------------------
    # API Configuration
    # -------------------------------------------------------------------------
    api_host: str = Field(default="0.0.0.0", description="API host to bind to")
    api_port: int = Field(default=8080, description="API port to bind to")

    # -------------------------------------------------------------------------
    # Deployment Configuration
    # -------------------------------------------------------------------------
    aws_region: str = Field(
        default="us-east-1",
        description="Default AWS region for deployment",
    )
    deployment_dry_run: bool = Field(
        default=True,
        description="If True, simulate deployments without making changes",
    )
    terraform_templates_directory: str = Field(
        default="./terraform",
        description="Directory containing Terraform templates",
    )

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return upper_v

    @field_validator("patchweave_env")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Ensure environment is valid."""
        valid_envs = {"development", "production", "testing"}
        lower_v = v.lower()
        if lower_v not in valid_envs:
            raise ValueError(f"patchweave_env must be one of {valid_envs}")
        return lower_v

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.patchweave_env == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.patchweave_env == "production"

    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode."""
        return self.patchweave_env == "testing"

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    def get_aws_config(self, environment: str = "test") -> dict:
        """
        Get AWS configuration for the specified environment.

        Args:
            environment: Either 'test' or 'production'

        Returns:
            Dictionary with AWS configuration suitable for boto3 client/resource

        Raises:
            ValueError: If environment is not 'test' or 'production'
        """
        if environment == "test":
            config = {
                "aws_access_key_id": self.aws_test_access_key_id,
                "aws_secret_access_key": self.aws_test_secret_access_key,
                "region_name": self.aws_test_region,
            }
            if self.use_localstack:
                config["endpoint_url"] = self.localstack_endpoint
            return config
        elif environment == "production":
            if not self.aws_prod_access_key_id or not self.aws_prod_secret_access_key:
                raise ValueError("Production AWS credentials not configured")
            return {
                "aws_access_key_id": self.aws_prod_access_key_id,
                "aws_secret_access_key": self.aws_prod_secret_access_key,
                "region_name": self.aws_prod_region,
            }
        else:
            raise ValueError(f"Unknown environment: {environment}. Use 'test' or 'production'")

    def get_chroma_url(self) -> str:
        """Get the ChromaDB URL."""
        return f"http://{self.chroma_host}:{self.chroma_port}"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Returns:
        Settings instance (cached for performance)
    """
    return Settings()


# Module-level convenience access
settings = get_settings()
