"""
Unit tests for Jira client.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from patchweave.integrations.jira import (
    JiraClient,
    JiraClientError,
    get_jira_client,
)
from patchweave.models.enums import JiraStatus


class TestJiraClient:
    """Tests for the JiraClient class."""

    def test_init_defaults(self):
        """Test initialization with default settings."""
        from patchweave.config import settings
        client = JiraClient()
        
        # Uses values from settings (may be from .env or defaults)
        assert client.base_url == settings.jira_base_url
        assert client.project_key == settings.jira_project_key
        assert not client._connected

    def test_init_custom(self):
        """Test initialization with custom settings."""
        client = JiraClient(
            base_url="https://custom.atlassian.net",
            email="user@example.com",
            api_token="token123",
            project_key="CSEC",
        )
        
        assert client.base_url == "https://custom.atlassian.net"
        assert client.project_key == "CSEC"
        assert client.email == "user@example.com"

    @patch('patchweave.integrations.jira.JIRA')
    def test_connect_success(self, mock_jira_class):
        """Test successful connection to Jira."""
        mock_jira = MagicMock()
        mock_jira_class.return_value = mock_jira
        
        client = JiraClient(api_token="test-token")
        client.connect()
        
        assert client._connected
        mock_jira_class.assert_called_once()

    @patch('patchweave.integrations.jira.JIRA')
    def test_connect_failure(self, mock_jira_class):
        """Test connection failure to Jira."""
        from jira.exceptions import JIRAError
        mock_jira_class.side_effect = JIRAError("Connection failed")
        
        client = JiraClient(api_token="test-token")
        
        with pytest.raises(JiraClientError):
            client.connect()

    def test_disconnect(self):
        """Test disconnecting from Jira."""
        client = JiraClient()
        client._client = MagicMock()
        client._connected = True
        
        client.disconnect()
        
        assert not client._connected
        assert client._client is None

    @patch('patchweave.integrations.jira.JIRA')
    def test_fetch_open_findings(self, mock_jira_class):
        """Test fetching open findings from Jira."""
        # Setup mock issue
        mock_issue = MagicMock()
        mock_issue.key = "SEC-123"
        mock_issue.fields.summary = "Test finding"
        mock_issue.fields.description = "Test description"
        mock_issue.fields.created = "2026-01-16T10:00:00.000+0000"
        mock_issue.fields.priority.name = "High"  # Set .name directly as string
        mock_issue.raw = {"fields": {}}
        
        mock_jira = MagicMock()
        mock_jira.search_issues.return_value = [mock_issue]
        mock_jira_class.return_value = mock_jira
        
        client = JiraClient(api_token="test-token")
        findings = client.fetch_open_findings()
        
        assert len(findings) == 1
        assert findings[0].jira_ticket_id == "SEC-123"
        assert findings[0].title == "Test finding"

    @patch('patchweave.integrations.jira.JIRA')
    def test_update_status(self, mock_jira_class):
        """Test updating ticket status."""
        mock_jira = MagicMock()
        mock_jira.transitions.return_value = [
            {"id": "1", "name": "Start Analysis", "to": {"name": "ANALYZING"}},
        ]
        mock_jira_class.return_value = mock_jira
        
        client = JiraClient(api_token="test-token")
        result = client.update_status("SEC-123", JiraStatus.ANALYZING)
        
        assert result is True
        mock_jira.transition_issue.assert_called_once()

    @patch('patchweave.integrations.jira.JIRA')
    def test_update_status_transition_not_found(self, mock_jira_class):
        """Test updating status when transition not available."""
        mock_jira = MagicMock()
        mock_jira.transitions.return_value = []  # No transitions available
        mock_jira_class.return_value = mock_jira
        
        client = JiraClient(api_token="test-token")
        result = client.update_status("SEC-123", JiraStatus.ANALYZING)
        
        assert result is False

    @patch('patchweave.integrations.jira.JIRA')
    def test_add_comment(self, mock_jira_class):
        """Test adding comment to ticket."""
        mock_jira = MagicMock()
        mock_jira_class.return_value = mock_jira
        
        client = JiraClient(api_token="test-token")
        result = client.add_comment("SEC-123", "Test comment")
        
        assert result is True
        mock_jira.add_comment.assert_called_once_with("SEC-123", "Test comment")

    @patch('patchweave.integrations.jira.JIRA')
    def test_get_issue(self, mock_jira_class):
        """Test getting a single issue."""
        mock_issue = MagicMock()
        mock_issue.key = "SEC-123"
        mock_issue.fields.summary = "Test finding"
        mock_issue.fields.description = "Test description"
        mock_issue.fields.created = "2026-01-16T10:00:00.000+0000"
        mock_issue.fields.priority.name = "High"  # Set .name directly as string
        mock_issue.raw = {"fields": {}}
        
        mock_jira = MagicMock()
        mock_jira.issue.return_value = mock_issue
        mock_jira_class.return_value = mock_jira
        
        client = JiraClient(api_token="test-token")
        finding = client.get_issue("SEC-123")
        
        assert finding is not None
        assert finding.jira_ticket_id == "SEC-123"

    @patch('patchweave.integrations.jira.JIRA')
    def test_get_current_status(self, mock_jira_class):
        """Test getting current status of a ticket."""
        mock_issue = MagicMock()
        mock_issue.fields.status.name = "ANALYZING"
        
        mock_jira = MagicMock()
        mock_jira.issue.return_value = mock_issue
        mock_jira_class.return_value = mock_jira
        
        client = JiraClient(api_token="test-token")
        status = client.get_current_status("SEC-123")
        
        assert status == JiraStatus.ANALYZING


class TestJiraStatusTransitions:
    """Tests for Jira status transition mapping."""

    def test_all_statuses_have_transitions(self):
        """Test that all non-OPEN statuses have transition names."""
        # OPEN is the starting state, so it shouldn't have a transition
        for status in JiraStatus:
            if status != JiraStatus.OPEN:
                assert status in JiraClient.STATUS_TRANSITIONS
