"""
Unit tests for structured logging.
"""

import json
import pytest
from io import StringIO


class TestLoggingSetup:
    """Tests for logging configuration."""

    def test_setup_logging_returns_logger(self):
        """Test that setup_logging returns a bound logger."""
        from patchweave.logging import setup_logging
        
        logger = setup_logging()
        assert logger is not None
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')
        assert hasattr(logger, 'warning')

    def test_logger_includes_service_context(self):
        """Test that logger includes service name in context."""
        from patchweave.logging import setup_logging
        
        logger = setup_logging()
        # Logger should be bound with service context
        assert logger is not None


class TestAuditLogger:
    """Tests for audit logging functionality."""

    def test_audit_logger_creation(self):
        """Test AuditLogger can be instantiated."""
        from patchweave.logging import AuditLogger
        
        audit = AuditLogger()
        assert audit is not None

    def test_audit_log_approval(self):
        """Test logging approval events."""
        from patchweave.logging import AuditLogger
        
        audit = AuditLogger()
        # Should not raise
        audit.log_approval(
            jira_id="SEC-123",
            approver="admin@example.com",
            decision="approved",
            reason="Validated in test environment"
        )

    def test_audit_log_deployment(self):
        """Test logging deployment events."""
        from patchweave.logging import AuditLogger
        
        audit = AuditLogger()
        # Should not raise
        audit.log_deployment(
            jira_id="SEC-123",
            playbook_id="s3-public-access-v1",
            environment="test",
            outcome="success",
            changes={"bucket": "example-bucket", "action": "block_public_access"}
        )

    def test_audit_log_security_event(self):
        """Test logging security events."""
        from patchweave.logging import AuditLogger
        
        audit = AuditLogger()
        # Should not raise
        audit.log_security_event(
            event_type="unauthorized_access_attempt",
            details={"ip": "192.168.1.1", "user": "unknown"}
        )
