"""
Jira integration client for PatchWeave.

Handles all communication with Jira Cloud including:
- Polling for new security findings
- Updating ticket status
- Adding comments and work logs
"""

from datetime import datetime, timezone
from typing import Any

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

    # Mapping from JiraStatus enum to Jira transition names
    # These need to be configured to match your Jira workflow
    STATUS_TRANSITIONS: dict[JiraStatus, str] = {
        JiraStatus.ANALYZING: "Start Analysis",
        JiraStatus.PLAYBOOK_SEARCH: "Search Playbooks",
        JiraStatus.VERIFYING: "Verify Match",
        JiraStatus.NO_PLAYBOOK: "No Playbook Found",
        JiraStatus.VALIDATING: "Start Validation",
        JiraStatus.VALIDATION_FAILED: "Validation Failed",
        JiraStatus.PENDING_APPROVAL: "Request Approval",
        JiraStatus.APPROVED: "Approve",
        JiraStatus.REJECTED: "Reject",
        JiraStatus.DEPLOYING: "Start Deployment",
        JiraStatus.DEPLOYMENT_FAILED: "Deployment Failed",
        JiraStatus.RESOLVED: "Resolve",
    }

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        project_key: str | None = None,
    ):
        """
        Initialize Jira client.
        
        Args:
            base_url: Jira instance URL (defaults to settings)
            email: Service account email (defaults to settings)
            api_token: API token (defaults to settings)
            project_key: Project to monitor (defaults to settings)
        """
        self.base_url = base_url or settings.jira_base_url
        self.email = email or settings.jira_email
        self.api_token = api_token or settings.jira_api_token
        self.project_key = project_key or settings.jira_project_key
        
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
        if self._connected and self._client:
            return
            
        try:
            self._client = JIRA(
                server=self.base_url,
                basic_auth=(self.email, self.api_token),
            )
            # Verify connection by fetching server info
            self._client.server_info()
            self._connected = True
            log.info("jira_connected", base_url=self.base_url)
        except JIRAError as e:
            log.error("jira_connection_failed", error=str(e))
            raise JiraClientError(f"Failed to connect to Jira: {e}") from e

    def disconnect(self) -> None:
        """Close the Jira connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._connected = False
            log.info("jira_disconnected")

    @property
    def client(self) -> JIRA:
        """Get the underlying Jira client, connecting if needed."""
        if not self._connected or not self._client:
            self.connect()
        return self._client  # type: ignore

    def fetch_open_findings(
        self,
        max_results: int = 50,
        status: str = "OPEN",
    ) -> list[RawFinding]:
        """
        Fetch security findings from Jira that need processing.
        
        Args:
            max_results: Maximum number of issues to fetch
            status: Jira status to filter by (default: OPEN)
            
        Returns:
            List of RawFinding objects
        """
        jql = (
            f'project = "{self.project_key}" '
            f'AND status = "{status}" '
            f'ORDER BY created ASC'
        )
        
        log.debug("jira_query", jql=jql, max_results=max_results)
        
        try:
            issues = self.client.search_issues(
                jql,
                maxResults=max_results,
                fields="summary,description,created,priority,customfield_*",
            )
        except JIRAError as e:
            log.error("jira_query_failed", jql=jql, error=str(e))
            raise JiraClientError(f"Failed to fetch issues: {e}") from e

        findings: list[RawFinding] = []
        for issue in issues:
            try:
                finding = self._issue_to_finding(issue)
                findings.append(finding)
            except Exception as e:
                log.warning(
                    "jira_issue_parse_failed",
                    issue_key=issue.key,
                    error=str(e),
                )
                continue

        log.info(
            "jira_findings_fetched",
            count=len(findings),
            status=status,
        )
        return findings

    def _issue_to_finding(self, issue: Any) -> RawFinding:
        """
        Convert a Jira issue to a RawFinding model.
        
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
        transition_name = self.STATUS_TRANSITIONS.get(new_status)
        if not transition_name:
            log.error(
                "jira_unknown_transition",
                ticket_id=ticket_id,
                status=new_status.value,
            )
            return False

        try:
            # Get available transitions
            transitions = self.client.transitions(ticket_id)
            transition_id = None
            for t in transitions:
                if t["name"].lower() == transition_name.lower():
                    transition_id = t["id"]
                    break

            if not transition_id:
                # Try matching by target status name
                for t in transitions:
                    if t.get("to", {}).get("name", "").upper() == new_status.value:
                        transition_id = t["id"]
                        break

            if not transition_id:
                log.warning(
                    "jira_transition_not_found",
                    ticket_id=ticket_id,
                    transition_name=transition_name,
                    available=[t["name"] for t in transitions],
                )
                return False

            # Execute transition
            self.client.transition_issue(ticket_id, transition_id)
            
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

        except JIRAError as e:
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
            self.client.add_comment(ticket_id, comment)
            log.debug("jira_comment_added", ticket_id=ticket_id)
            return True
        except JIRAError as e:
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
            issue = self.client.issue(ticket_id)
            return self._issue_to_finding(issue)
        except JIRAError as e:
            log.error(
                "jira_issue_fetch_failed",
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
            issue = self.client.issue(ticket_id, fields="status")
            status_name = issue.fields.status.name.upper()
            
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
            
        except JIRAError as e:
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
