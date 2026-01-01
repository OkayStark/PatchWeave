"""
Structured logging setup for PatchWeave.

Uses structlog for JSON-formatted, context-rich logging with support
for audit events and file rotation.
"""

import logging
import sys
from pathlib import Path
from typing import Any
from logging.handlers import RotatingFileHandler

import structlog
from structlog.types import Processor

from patchweave.config import settings


def add_log_level(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add log level to the event dict."""
    if method_name == "warn":
        method_name = "warning"
    event_dict["level"] = method_name.upper()
    return event_dict


def add_app_context(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add application context to all log events."""
    event_dict["app"] = "patchweave"
    event_dict["env"] = settings.patchweave_env
    return event_dict


def setup_logging() -> structlog.stdlib.BoundLogger:
    """
    Configure structured logging for the application.

    Sets up:
    - JSON-formatted console output
    - Rotating file handler for persistence
    - Context processors for enrichment
    - Audit event marking

    Returns:
        Configured structlog BoundLogger instance
    """
    # Determine log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Create logs directory if needed
    log_file = Path(settings.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Configure standard library logging
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler (for development visibility)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # File handler with rotation (for persistence)
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)

    # Shared processors for structlog
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        add_log_level,
        add_app_context,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Configure structlog
    if settings.is_development:
        # Development: colored console output
        structlog.configure(
            processors=shared_processors
            + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        # Console formatter for development (colored)
        console_formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
        )

        # File formatter (JSON for parsing)
        file_formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
    else:
        # Production: JSON everywhere
        structlog.configure(
            processors=shared_processors
            + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        json_formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
        console_formatter = json_formatter
        file_formatter = json_formatter

    # Apply formatters to handlers
    console_handler.setFormatter(console_formatter)
    file_handler.setFormatter(file_formatter)

    # Add handlers to root logger
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Configure third-party loggers to be less verbose
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)

    # Return a logger instance
    return get_logger("patchweave")


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        Configured structlog BoundLogger instance
    """
    return structlog.get_logger(name)


class AuditLogger:
    """
    Specialized logger for audit events.

    Audit events are security-sensitive and marked with _audit=True
    for compliance and security monitoring.
    """

    def __init__(self, name: str = "patchweave.audit"):
        self._logger = get_logger(name)

    def log(
        self,
        event: str,
        *,
        finding_id: str | None = None,
        action: str | None = None,
        actor: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Log an audit event.

        Args:
            event: Event name/type
            finding_id: Associated finding ID
            action: Action being audited
            actor: User/system performing the action
            **kwargs: Additional context
        """
        self._logger.info(
            event,
            finding_id=finding_id,
            action=action,
            actor=actor,
            _audit=True,
            **kwargs,
        )

    def log_approval(
        self,
        jira_id: str,
        approver: str,
        decision: str,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Log an approval event.

        Args:
            jira_id: Jira issue ID
            approver: Email/ID of approver
            decision: approved/rejected
            reason: Reason for decision
        """
        self.log(
            "approval_decision",
            finding_id=jira_id,
            action=f"approval_{decision}",
            actor=approver,
            decision=decision,
            reason=reason,
            **kwargs,
        )

    def log_deployment(
        self,
        jira_id: str,
        playbook_id: str,
        environment: str,
        outcome: str,
        changes: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Log a deployment event.

        Args:
            jira_id: Jira issue ID
            playbook_id: Playbook that was deployed
            environment: test/production
            outcome: success/failure
            changes: Dictionary of changes made
        """
        self.log(
            "deployment_executed",
            finding_id=jira_id,
            action=f"deploy_{outcome}",
            playbook_id=playbook_id,
            environment=environment,
            outcome=outcome,
            changes=changes or {},
            **kwargs,
        )

    def log_security_event(
        self,
        event_type: str,
        details: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """
        Log a security event.

        Args:
            event_type: Type of security event
            details: Event details
        """
        self._logger.warning(
            "security_event",
            event_type=event_type,
            details=details,
            _audit=True,
            **kwargs,
        )

    def approval_requested(self, finding_id: str, **kwargs: Any) -> None:
        """Log approval request event."""
        self.log(
            "approval_requested",
            finding_id=finding_id,
            action="approval_request",
            **kwargs,
        )

    def approval_granted(
        self, finding_id: str, approver: str, **kwargs: Any
    ) -> None:
        """Log approval granted event."""
        self.log(
            "approval_granted",
            finding_id=finding_id,
            action="approve",
            actor=approver,
            **kwargs,
        )

    def approval_rejected(
        self, finding_id: str, rejector: str, reason: str, **kwargs: Any
    ) -> None:
        """Log approval rejected event."""
        self.log(
            "approval_rejected",
            finding_id=finding_id,
            action="reject",
            actor=rejector,
            reason=reason,
            **kwargs,
        )

    def deployment_started(self, finding_id: str, playbook_id: str, **kwargs: Any) -> None:
        """Log deployment start event."""
        self.log(
            "deployment_started",
            finding_id=finding_id,
            action="deploy_start",
            playbook_id=playbook_id,
            **kwargs,
        )

    def deployment_complete(
        self,
        finding_id: str,
        playbook_id: str,
        success: bool,
        resources_modified: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Log deployment completion event."""
        self.log(
            "deployment_complete",
            finding_id=finding_id,
            action="deploy_complete",
            playbook_id=playbook_id,
            success=success,
            resources_modified=resources_modified or [],
            **kwargs,
        )

    def cleanup_failed(
        self,
        finding_id: str,
        environment_id: str,
        error: str,
        **kwargs: Any,
    ) -> None:
        """Log cleanup failure event (CRITICAL)."""
        self._logger.critical(
            "cleanup_failed",
            finding_id=finding_id,
            environment_id=environment_id,
            error=error,
            action="cleanup_failed",
            _audit=True,
            **kwargs,
        )


# Global audit logger instance
audit_log = AuditLogger()
