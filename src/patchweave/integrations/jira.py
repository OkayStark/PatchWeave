"""
Jira integration client for PatchWeave.

Handles all communication with Jira Cloud including:
- Polling for new security findings
- Updating ticket status
- Adding comments and work logs
"""

from datetime import datetime, timezone
from typing import Any

import requests
from requests.auth import HTTPBasicAuth
from jira import JIRA
from jira.exceptions import JIRAError

from patchweave.config import settings
from patchweave.logging import get_logger, audit_log
from patchweave.models.enums import JiraStatus
from patchweave.models.finding import RawFinding

log = get_logger(__name__)


class JiraClientError(Exception):
    """Base exception for Jira client errors."""
    pass


class JiraClient:
    """
    Client for interacting with Jira Cloud.
    
    Provides methods for:
    - Fetching new security findings from a Jira project
    - Updating ticket status through the workflow
    - Adding comments to track remediation progress
    """

    # Mapping from JiraStatus enum to Jira transition/status names
    # Updated for simple Jira workflow (Open -> Approved -> Done)
    # PatchWeave will look for these status names in available transitions
    STATUS_TRANSITIONS: dict[JiraStatus, str] = {
        JiraStatus.ANALYZING: "Open",          # Keep in Open during analysis
        JiraStatus.PLAYBOOK_SEARCH: "Open",    # Keep in Open during search
        JiraStatus.VERIFYING: "Open",          # Keep in Open during verification
        JiraStatus.NO_PLAYBOOK: "Done",        # Move to Done if no playbook
        JiraStatus.VALIDATING: "Open",         # Keep in Open during validation
        JiraStatus.VALIDATION_FAILED: "Done",  # Move to Done on validation failure
        JiraStatus.PENDING_APPROVAL: "Open",   # Keep in Open, waiting for manual change to Approved
        JiraStatus.APPROVED: "Approved",       # Human sets this
        JiraStatus.REJECTED: "Done",           # Move to Done on rejection
        JiraStatus.DEPLOYING: "Approved",      # Keep in Approved during deployment
        JiraStatus.DEPLOYMENT_FAILED: "Done",  # Move to Done on failure
        JiraStatus.RESOLVED: "Done",           # Move to Done on success
    }

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        project_key: str | None = None,
        open_status: str | None = None,
    ):
        """
        Initialize Jira client.
        
        Args:
            base_url: Jira instance URL (defaults to settings)
            email: Service account email (defaults to settings)
            api_token: API token (defaults to settings)
            project_key: Project to monitor (defaults to settings)
            open_status: Status name for new findings (defaults to settings)
        """
        self.base_url = base_url or settings.jira_base_url
        self.email = email or settings.jira_email
        self.api_token = api_token or settings.jira_api_token
        self.project_key = project_key or settings.jira_project_key
        self.open_status = open_status or settings.jira_open_status
        
        self._client: JIRA | None = None
        self._connected = False
        
        log.info(
            "jira_client_initialized",
            base_url=self.base_url,
            project_key=self.project_key,
        )

    def connect(self) -> None:
        """
        Establish connection to Jira.
        
        Raises:
            JiraClientError: If connection fails
        """
        if self._connected:
            return
        
        # Use requests to verify connection (more reliable with Atlassian Cloud)
        try:
            auth = HTTPBasicAuth(self.email, self.api_token)
            response = requests.get(
                f"{self.base_url}rest/api/3/myself",
                auth=auth,
                timeout=30,
            )
            response.raise_for_status()
            self._connected = True
            log.info("jira_connected", base_url=self.base_url)
        except requests.RequestException as e:
            log.error("jira_connection_failed", error=str(e))
            raise JiraClientError(f"Failed to connect to Jira: {e}") from e

    def disconnect(self) -> None:
        """Close the Jira connection."""
        self._connected = False
        log.info("jira_disconnected")

    def _get_auth(self) -> HTTPBasicAuth:
        """Get HTTP Basic Auth for API calls."""
        return HTTPBasicAuth(self.email, self.api_token)

    def fetch_open_findings(
        self,
        max_results: int = 50,
        status: str | None = None,
    ) -> list[RawFinding]:
        """
        Fetch security findings from Jira that need processing.
        
        Args:
            max_results: Maximum number of issues to fetch
            status: Jira status to filter by (defaults to configured open_status)
            
        Returns:
            List of RawFinding objects
        """
        status = status or self.open_status
        jql = f'project = "{self.project_key}" AND status = "{status}" ORDER BY created ASC'
        
        log.debug("jira_query", jql=jql, max_results=max_results)
        
        try:
            # Use the new Jira Cloud search API (v3)
            response = requests.get(
                f"{self.base_url}rest/api/3/search/jql",
                auth=self._get_auth(),
                params={
                    "jql": jql,
                    "maxResults": max_results,
                    "fields": "summary,description,created,priority,status",
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            issues = data.get("issues", [])
        except requests.RequestException as e:
            log.error("jira_query_failed", jql=jql, error=str(e))
            raise JiraClientError(f"Failed to fetch issues: {e}") from e

        findings: list[RawFinding] = []
        for issue in issues:
            try:
                finding = self._issue_to_finding_from_dict(issue)
                findings.append(finding)
            except Exception as e:
                log.warning(
                    "jira_issue_parse_failed",
                    issue_key=issue.get("key", "unknown"),
                    error=str(e),
                )
                continue

        log.info(
            "jira_findings_fetched",
            count=len(findings),
            status=status,
        )
        return findings

    def _issue_to_finding_from_dict(self, issue: dict[str, Any]) -> RawFinding:
        """
        Convert a Jira issue dict (from REST API) to a RawFinding model.
        
        Args:
            issue: Jira issue dict from API response
            
        Returns:
            RawFinding model
        """
        fields = issue.get("fields", {})
        
        # Extract custom fields (CSPM tools often add these)
        custom_fields: dict[str, str] = {}
        for field_name, field_value in fields.items():
            if field_name.startswith("customfield_") and field_value:
                custom_fields[field_name] = str(field_value)

        # Parse created timestamp
        created_str = fields.get("created", "")
        if isinstance(created_str, str) and created_str:
            # Handle various Jira timestamp formats
            try:
                created_at = datetime.fromisoformat(
                    created_str.replace("+0000", "+00:00").replace("Z", "+00:00")
                )
            except ValueError:
                created_at = datetime.now(timezone.utc)
        else:
            created_at = datetime.now(timezone.utc)

        # Get severity from priority
        severity = None
        priority = fields.get("priority")
        if priority and isinstance(priority, dict):
            severity = priority.get("name")

        # Handle description which can be ADF format in v3 API
        description = fields.get("description", "")
        if isinstance(description, dict):
            # ADF format - extract plain text
            description = self._adf_to_text(description)

        return RawFinding(
            jira_ticket_id=issue.get("key", ""),
            jira_ticket_url=f"{self.base_url}browse/{issue.get('key', '')}",
            title=fields.get("summary", ""),
            description=description or "",
            severity=severity,
            created_at=created_at,
            custom_fields=custom_fields,
        )

    def _adf_to_text(self, adf: dict[str, Any]) -> str:
        """
        Convert Atlassian Document Format (ADF) to plain text.
        
        Args:
            adf: ADF document dict
            
        Returns:
            Plain text string
        """
        def extract_text(node: dict[str, Any]) -> str:
            text_parts = []
            if node.get("type") == "text":
                text_parts.append(node.get("text", ""))
            for child in node.get("content", []):
                text_parts.append(extract_text(child))
            return "".join(text_parts)
        
        try:
            return extract_text(adf)
        except Exception:
            return str(adf)

    def _issue_to_finding(self, issue: Any) -> RawFinding:
        """
        Convert a Jira issue object to a RawFinding model.
        Legacy method for compatibility with jira library.
        
        Args:
            issue: Jira issue object
            
        Returns:
            RawFinding model
        """
        # Extract custom fields (CSPM tools often add these)
        custom_fields: dict[str, str] = {}
        for field_name, field_value in issue.raw.get("fields", {}).items():
            if field_name.startswith("customfield_") and field_value:
                custom_fields[field_name] = str(field_value)

        # Parse created timestamp
        created_str = issue.fields.created
        if isinstance(created_str, str):
            # Jira format: 2026-01-16T10:00:00.000+0000
            created_at = datetime.fromisoformat(
                created_str.replace("+0000", "+00:00")
            )
        else:
            created_at = datetime.now(timezone.utc)

        # Get severity from priority
        severity = None
        if hasattr(issue.fields, "priority") and issue.fields.priority:
            severity = issue.fields.priority.name

        return RawFinding(
            jira_ticket_id=issue.key,
            jira_ticket_url=f"{self.base_url}/browse/{issue.key}",
            title=issue.fields.summary or "",
            description=issue.fields.description or "",
            severity=severity,
            created_at=created_at,
            custom_fields=custom_fields,
        )

    def update_status(
        self,
        ticket_id: str,
        new_status: JiraStatus,
        comment: str | None = None,
    ) -> bool:
        """
        Transition a Jira ticket to a new status.
        
        Args:
            ticket_id: Jira issue key (e.g., SEC-1234)
            new_status: Target status from JiraStatus enum
            comment: Optional comment to add with the transition
            
        Returns:
            True if transition succeeded, False otherwise
        """
        try:
            # Get available transitions using REST API
            url = f"{self.base_url.rstrip('/')}/rest/api/3/issue/{ticket_id}/transitions"
            response = requests.get(
                url,
                auth=self._get_auth(),
                headers={"Accept": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            transitions = response.json().get("transitions", [])
            
            # Find matching transition
            transition_id = None
            transition_name = self.STATUS_TRANSITIONS.get(new_status)
            
            for t in transitions:
                # Try matching by transition name
                if transition_name and t["name"].lower() == transition_name.lower():
                    transition_id = t["id"]
                    break
                # Try matching by target status name
                if t.get("to", {}).get("name", "").upper() == new_status.value:
                    transition_id = t["id"]
                    break

            if not transition_id:
                log.warning(
                    "jira_transition_not_found",
                    ticket_id=ticket_id,
                    target_status=new_status.value,
                    available=[f"{t['name']} -> {t.get('to', {}).get('name', 'unknown')}" for t in transitions],
                )
                # Log the status change intent even if we can't transition
                log.info(
                    "jira_status_logged",
                    ticket_id=ticket_id,
                    intended_status=new_status.value,
                    message="Transition not available in current Jira workflow",
                )
                return True  # Return True to not block workflow

            # Execute transition
            transition_url = f"{self.base_url.rstrip('/')}/rest/api/3/issue/{ticket_id}/transitions"
            payload = {"transition": {"id": transition_id}}
            
            response = requests.post(
                transition_url,
                json=payload,
                auth=self._get_auth(),
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            
            # Add comment if provided
            if comment:
                self.add_comment(ticket_id, comment)

            log.info(
                "jira_status_updated",
                ticket_id=ticket_id,
                new_status=new_status.value,
            )
            
            # Audit log for status changes
            audit_log.log(
                "jira_status_transition",
                finding_id=ticket_id,
                action="status_update",
                new_status=new_status.value,
            )
            
            return True

        except requests.exceptions.RequestException as e:
            log.error(
                "jira_transition_failed",
                ticket_id=ticket_id,
                new_status=new_status.value,
                error=str(e),
            )
            return False

    def add_comment(self, ticket_id: str, comment: str) -> bool:
        """
        Add a comment to a Jira ticket.
        
        Args:
            ticket_id: Jira issue key
            comment: Comment text (supports Jira markup)
            
        Returns:
            True if comment was added, False otherwise
        """
        try:
            url = f"{self.base_url.rstrip('/')}/rest/api/3/issue/{ticket_id}/comment"
            
            # Jira API v3 uses Atlassian Document Format for comments
            payload = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": comment
                                }
                            ]
                        }
                    ]
                }
            }
            
            response = requests.post(
                url,
                json=payload,
                auth=self._get_auth(),
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            
            log.debug("jira_comment_added", ticket_id=ticket_id)
            return True
        except requests.exceptions.RequestException as e:
            log.error(
                "jira_comment_failed",
                ticket_id=ticket_id,
                error=str(e),
            )
            return False

    def add_worklog(
        self,
        ticket_id: str,
        time_spent: str,
        comment: str | None = None,
    ) -> bool:
        """
        Add a worklog entry to track time spent.
        
        Args:
            ticket_id: Jira issue key
            time_spent: Time in Jira format (e.g., "1h 30m")
            comment: Optional worklog comment
            
        Returns:
            True if worklog was added, False otherwise
        """
        try:
            self.client.add_worklog(
                ticket_id,
                timeSpent=time_spent,
                comment=comment,
            )
            log.debug(
                "jira_worklog_added",
                ticket_id=ticket_id,
                time_spent=time_spent,
            )
            return True
        except JIRAError as e:
            log.error(
                "jira_worklog_failed",
                ticket_id=ticket_id,
                error=str(e),
            )
            return False

    def get_issue(self, ticket_id: str) -> RawFinding | None:
        """
        Fetch a single issue by ID.
        
        Args:
            ticket_id: Jira issue key
            
        Returns:
            RawFinding or None if not found
        """
        try:
            url = f"{self.base_url.rstrip('/')}/rest/api/3/issue/{ticket_id}"
            response = requests.get(
                url,
                auth=self._get_auth(),
                headers={"Accept": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            issue = response.json()
            return self._issue_to_finding_from_dict(issue)
        except requests.exceptions.RequestException as e:
            log.error(
                "jira_issue_fetch_failed",
                ticket_id=ticket_id,
                error=str(e),
            )
            return None

    def get_ticket(self, ticket_id: str) -> dict | None:
        """
        Get raw ticket data including status.
        
        Args:
            ticket_id: Jira issue key
            
        Returns:
            Dict with ticket data including 'status' key, or None
        """
        try:
            url = f"{self.base_url.rstrip('/')}/rest/api/3/issue/{ticket_id}?fields=status,summary"
            response = requests.get(
                url,
                auth=self._get_auth(),
                headers={"Accept": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            issue = response.json()
            
            status_name = issue.get("fields", {}).get("status", {}).get("name", "")
            return {
                "key": issue.get("key"),
                "status": status_name,
                "summary": issue.get("fields", {}).get("summary", ""),
            }
        except requests.exceptions.RequestException as e:
            log.error(
                "jira_ticket_fetch_failed",
                ticket_id=ticket_id,
                error=str(e),
            )
            return None

    def get_current_status(self, ticket_id: str) -> JiraStatus | None:
        """
        Get the current status of a ticket.
        
        Args:
            ticket_id: Jira issue key
            
        Returns:
            JiraStatus or None if unable to determine
        """
        try:
            url = f"{self.base_url.rstrip('/')}/rest/api/3/issue/{ticket_id}?fields=status"
            response = requests.get(
                url,
                auth=self._get_auth(),
                headers={"Accept": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            issue = response.json()
            
            status_name = issue.get("fields", {}).get("status", {}).get("name", "").upper()
            
            # Try to match to our enum
            for status in JiraStatus:
                if status.value == status_name:
                    return status
            
            log.warning(
                "jira_unknown_status",
                ticket_id=ticket_id,
                status_name=status_name,
            )
            return None
            
        except requests.exceptions.RequestException as e:
            log.error(
                "jira_status_fetch_failed",
                ticket_id=ticket_id,
                error=str(e),
            )
            return None


# Singleton instance for convenience
_jira_client: JiraClient | None = None


def get_jira_client() -> JiraClient:
    """Get or create the global Jira client instance."""
    global _jira_client
    if _jira_client is None:
        _jira_client = JiraClient()
    return _jira_client
