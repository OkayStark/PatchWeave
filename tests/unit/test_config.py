"""
Unit tests for configuration management.
"""

import os
import pytest
from unittest.mock import patch


class TestSettings:
    """Tests for Settings configuration."""

    def test_default_values(self, test_settings):
        """Test default configuration values."""
        assert test_settings.patchweave_env == "testing"
        assert test_settings.use_localstack is True
        assert test_settings.high_confidence_threshold == 0.90
        assert test_settings.moderate_confidence_threshold == 0.70

    def test_is_development(self):
        """Test is_development property."""
        from patchweave.config import Settings
        settings = Settings(patchweave_env="development")
        assert settings.is_development
        assert not settings.is_production

    def test_is_production(self):
        """Test is_production property."""
        from patchweave.config import Settings
        settings = Settings(patchweave_env="production")
        assert settings.is_production
        assert not settings.is_development

    def test_get_aws_config_test(self, test_settings):
        """Test AWS config for test environment."""
        config = test_settings.get_aws_config("test")
        assert config["aws_access_key_id"] == "test"
        assert config["region_name"] == "us-east-1"
        assert "endpoint_url" in config  # LocalStack endpoint

    def test_get_aws_config_invalid_env(self, test_settings):
        """Test AWS config with invalid environment."""
        with pytest.raises(ValueError, match="Unknown environment"):
            test_settings.get_aws_config("invalid")

    def test_get_chroma_url(self, test_settings):
        """Test ChromaDB URL generation."""
        url = test_settings.get_chroma_url()
        assert url == "http://localhost:8000"

    def test_log_level_validation(self):
        """Test log level validation."""
        from patchweave.config import Settings
        
        # Valid level
        settings = Settings(log_level="DEBUG")
        assert settings.log_level == "DEBUG"
        
        # Invalid level
        with pytest.raises(Exception):
            Settings(log_level="INVALID")

    def test_environment_validation(self):
        """Test environment validation."""
        from patchweave.config import Settings
        
        # Valid environments
        for env in ["development", "production", "testing"]:
            settings = Settings(patchweave_env=env)
            assert settings.patchweave_env == env
        
        # Invalid environment
        with pytest.raises(Exception):
            Settings(patchweave_env="invalid")
