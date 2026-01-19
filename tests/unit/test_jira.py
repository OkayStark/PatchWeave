"""
Unit tests for Jira client.

Tests the Jira integration using mocked HTTP requests since
the client uses direct REST API calls.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, Mock

import pytest
import requests

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

    @patch('patchweave.integrations.jira.requests.get')
    def test_connect_success(self, mock_get):
        """Test successful connection to Jira."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
        )
        client.connect()
        
        assert client._connected
        mock_get.assert_called_once()

    @patch('patchweave.integrations.jira.requests.get')
    def test_connect_failure(self, mock_get):
        """Test connection failure to Jira."""
        mock_get.side_effect = requests.RequestException("Connection failed")
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            api_token="test-token",
        )
        
        with pytest.raises(JiraClientError):
            client.connect()

    def test_disconnect(self):
        """Test disconnecting from Jira."""
        client = JiraClient()
        client._connected = True
        
        client.disconnect()
        
        assert not client._connected

    @patch('patchweave.integrations.jira.requests.get')
    def test_fetch_open_findings(self, mock_get):
        """Test fetching open findings from Jira."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "issues": [
                {
                    "key": "SEC-123",
                    "fields": {
                        "summary": "Test finding",
                        "description": "Test description",
                        "created": "2026-01-16T10:00:00.000+0000",
                        "priority": {"name": "High"},
                        "status": {"name": "Open"},
                    }
                }
            ]
        }
        mock_get.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            api_token="test-token",
        )
        findings = client.fetch_open_findings()
        
        assert len(findings) == 1
        assert findings[0].jira_ticket_id == "SEC-123"
        assert findings[0].title == "Test finding"

    @patch('patchweave.integrations.jira.requests.post')
    @patch('patchweave.integrations.jira.requests.get')
    def test_update_status(self, mock_get, mock_post):
        """Test updating ticket status."""
        # Mock transitions response
        mock_transitions_response = Mock()
        mock_transitions_response.status_code = 200
        mock_transitions_response.raise_for_status = Mock()
        mock_transitions_response.json.return_value = {
            "transitions": [
                {"id": "1", "name": "Analyzing", "to": {"name": "ANALYZING"}},
            ]
        }
        mock_get.return_value = mock_transitions_response
        
        # Mock transition execution
        mock_post_response = Mock()
        mock_post_response.status_code = 204
        mock_post_response.raise_for_status = Mock()
        mock_post.return_value = mock_post_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            api_token="test-token",
        )
        result = client.update_status("SEC-123", JiraStatus.ANALYZING)
        
        assert result is True
        mock_post.assert_called_once()

    @patch('patchweave.integrations.jira.requests.get')
    def test_update_status_transition_not_found(self, mock_get):
        """Test updating status when transition not available."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"transitions": []}  # No transitions
        mock_get.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            api_token="test-token",
        )
        # Now returns True to not block workflow
        result = client.update_status("SEC-123", JiraStatus.ANALYZING)
        
        assert result is True  # Changed: returns True even if transition not found

    @patch('patchweave.integrations.jira.requests.post')
    def test_add_comment(self, mock_post):
        """Test adding comment to ticket."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            api_token="test-token",
        )
        result = client.add_comment("SEC-123", "Test comment")
        
        assert result is True
        mock_post.assert_called_once()

    @patch('patchweave.integrations.jira.requests.get')
    def test_get_issue(self, mock_get):
        """Test getting a single issue."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "key": "SEC-123",
            "fields": {
                "summary": "Test finding",
                "description": "Test description",
                "created": "2026-01-16T10:00:00.000+0000",
                "priority": {"name": "High"},
                "status": {"name": "Open"},
            }
        }
        mock_get.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            api_token="test-token",
        )
        finding = client.get_issue("SEC-123")
        
        assert finding is not None
        assert finding.jira_ticket_id == "SEC-123"

    @patch('patchweave.integrations.jira.requests.get')
    def test_get_current_status(self, mock_get):
        """Test getting current status of a ticket."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "key": "SEC-123",
            "fields": {
                "status": {"name": "Analyzing"}
            }
        }
        mock_get.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            api_token="test-token",
        )
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


class TestJiraADFParsing:
    """Tests for Atlassian Document Format parsing."""
    
    def test_adf_to_text_simple(self):
        """Test parsing simple ADF document."""
        client = JiraClient()
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Hello "},
                        {"type": "text", "text": "World"}
                    ]
                }
            ]
        }
        result = client._adf_to_text(adf)
        assert "Hello" in result
        assert "World" in result
    
    def test_adf_to_text_nested(self):
        """Test parsing nested ADF document."""
        client = JiraClient()
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "bulletList",
                    "content": [
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {"type": "text", "text": "Item 1"}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        result = client._adf_to_text(adf)
        assert "Item 1" in result


class TestGetJiraClient:
    """Tests for singleton pattern."""

    def test_get_jira_client_returns_same_instance(self):
        """Test singleton behavior."""
        # Reset singleton
        import patchweave.integrations.jira as jira_module
        jira_module._jira_client = None
        
        client1 = get_jira_client()
        client2 = get_jira_client()
        
        assert client1 is client2
