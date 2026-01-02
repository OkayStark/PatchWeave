"""
Unit tests for Finding Queue service.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from patchweave.core.queue import (
    FindingQueue,
    QueueItem,
    QueueItemState,
    get_finding_queue,
)
from patchweave.models.enums import JiraStatus, VulnerabilityType, Severity, CloudProvider
from patchweave.models.finding import RawFinding, AnalyzedFinding


@pytest.fixture
def mock_jira_client():
    """Create a mock Jira client."""
    client = MagicMock()
    client.fetch_open_findings.return_value = []
    client.update_status.return_value = True
    return client


@pytest.fixture
def sample_raw_finding():
    """Create a sample raw finding."""
    return RawFinding(
        jira_ticket_id="SEC-100",
        jira_ticket_url="https://example.atlassian.net/browse/SEC-100",
        title="Test Finding",
        description="Test description",
        severity="High",
        created_at=datetime.now(timezone.utc),
        custom_fields={},
    )


@pytest.fixture
def sample_analyzed_finding():
    """Create a sample analyzed finding."""
    return AnalyzedFinding(
        finding_id="SEC-100",
        vulnerability_type=VulnerabilityType.S3_PUBLIC_ACCESS,
        cloud_provider=CloudProvider.AWS,
        resource_type="AWS::S3::Bucket",
        severity=Severity.HIGH,
        search_query="S3 public access",
        sanitized_title="Test {{BUCKET_NAME}}",
        sanitized_description="Test description",
        token_keys=["BUCKET_NAME"],
        source_ticket_url="https://example.atlassian.net/browse/SEC-100",
        detected_at=datetime.now(timezone.utc),
        analysis_confidence=0.9,
    )


class TestQueueItem:
    """Tests for QueueItem class."""

    def test_initial_state(self, sample_raw_finding):
        """Test initial state of queue item."""
        item = QueueItem(
            finding_id="SEC-100",
            raw_finding=sample_raw_finding,
        )
        
        assert item.state == QueueItemState.PENDING
        assert item.jira_status == JiraStatus.OPEN
        assert item.retry_count == 0
        assert item.can_retry()

    def test_mark_processing(self, sample_raw_finding):
        """Test marking item as processing."""
        item = QueueItem(finding_id="SEC-100", raw_finding=sample_raw_finding)
        item.mark_processing()
        
        assert item.state == QueueItemState.PROCESSING

    def test_mark_completed(self, sample_raw_finding, sample_analyzed_finding):
        """Test marking item as completed."""
        item = QueueItem(finding_id="SEC-100", raw_finding=sample_raw_finding)
        item.mark_completed(sample_analyzed_finding)
        
        assert item.state == QueueItemState.COMPLETED
        assert item.analyzed_finding == sample_analyzed_finding

    def test_mark_failed_with_retries(self, sample_raw_finding):
        """Test marking item as failed with retries remaining."""
        item = QueueItem(finding_id="SEC-100", raw_finding=sample_raw_finding)
        
        item.mark_failed("Test error")
        assert item.retry_count == 1
        assert item.can_retry()
        
        item.mark_failed("Test error 2")
        assert item.retry_count == 2
        assert item.can_retry()
        
        item.mark_failed("Test error 3")
        assert item.retry_count == 3
        assert not item.can_retry()


class TestFindingQueue:
    """Tests for FindingQueue class."""

    def test_init(self, mock_jira_client):
        """Test queue initialization."""
        queue = FindingQueue(jira_client=mock_jira_client, poll_interval=30)
        
        assert queue.pending_count == 0
        assert queue.processing_count == 0
        assert queue.completed_count == 0
        assert queue.failed_count == 0

    @pytest.mark.asyncio
    async def test_poll_once_finds_new(self, mock_jira_client, sample_raw_finding):
        """Test polling discovers new findings."""
        mock_jira_client.fetch_open_findings.return_value = [sample_raw_finding]
        queue = FindingQueue(jira_client=mock_jira_client)
        
        new_findings = await queue.poll_once()
        
        assert len(new_findings) == 1
        assert new_findings[0].jira_ticket_id == "SEC-100"
        assert queue.pending_count == 1

    @pytest.mark.asyncio
    async def test_poll_once_ignores_duplicates(self, mock_jira_client, sample_raw_finding):
        """Test that polling ignores already-known findings."""
        mock_jira_client.fetch_open_findings.return_value = [sample_raw_finding]
        queue = FindingQueue(jira_client=mock_jira_client)
        
        # First poll
        await queue.poll_once()
        assert queue.pending_count == 1
        
        # Second poll with same finding
        new_findings = await queue.poll_once()
        assert len(new_findings) == 0
        assert queue.pending_count == 1  # Still 1

    def test_get_next(self, mock_jira_client, sample_raw_finding):
        """Test getting next item from queue."""
        queue = FindingQueue(jira_client=mock_jira_client)
        
        # Add item manually
        item = QueueItem(finding_id="SEC-100", raw_finding=sample_raw_finding)
        queue._pending.append(item)
        queue._known_ids.add("SEC-100")
        
        next_item = queue.get_next()
        
        assert next_item is not None
        assert next_item.finding_id == "SEC-100"
        assert next_item.state == QueueItemState.PROCESSING
        assert queue.pending_count == 0
        assert queue.processing_count == 1

    def test_get_next_empty(self, mock_jira_client):
        """Test getting next from empty queue."""
        queue = FindingQueue(jira_client=mock_jira_client)
        
        result = queue.get_next()
        assert result is None

    def test_complete_item(self, mock_jira_client, sample_raw_finding, sample_analyzed_finding):
        """Test completing an item."""
        queue = FindingQueue(jira_client=mock_jira_client)
        
        # Setup processing item
        item = QueueItem(finding_id="SEC-100", raw_finding=sample_raw_finding)
        item.mark_processing()
        queue._processing["SEC-100"] = item
        
        result = queue.complete_item("SEC-100", sample_analyzed_finding)
        
        assert result is True
        assert queue.processing_count == 0
        assert queue.completed_count == 1

    def test_fail_item_with_retry(self, mock_jira_client, sample_raw_finding):
        """Test failing an item with retries remaining."""
        queue = FindingQueue(jira_client=mock_jira_client)
        
        # Setup processing item
        item = QueueItem(finding_id="SEC-100", raw_finding=sample_raw_finding)
        item.mark_processing()
        queue._processing["SEC-100"] = item
        
        result = queue.fail_item("SEC-100", "Test error")
        
        assert result is True
        assert queue.processing_count == 0
        assert queue.pending_count == 1  # Re-queued
        assert queue.failed_count == 0

    def test_fail_item_max_retries(self, mock_jira_client, sample_raw_finding):
        """Test failing an item with max retries exceeded."""
        queue = FindingQueue(jira_client=mock_jira_client)
        
        # Setup processing item with max retries
        item = QueueItem(finding_id="SEC-100", raw_finding=sample_raw_finding)
        item.retry_count = 3  # Already at max
        item.mark_processing()
        queue._processing["SEC-100"] = item
        
        result = queue.fail_item("SEC-100", "Final error")
        
        assert result is True
        assert queue.processing_count == 0
        assert queue.pending_count == 0
        assert queue.failed_count == 1

    def test_update_jira_status(self, mock_jira_client, sample_raw_finding):
        """Test updating Jira status."""
        queue = FindingQueue(jira_client=mock_jira_client)
        
        # Setup item
        item = QueueItem(finding_id="SEC-100", raw_finding=sample_raw_finding)
        queue._processing["SEC-100"] = item
        
        result = queue.update_jira_status(
            "SEC-100",
            JiraStatus.ANALYZING,
            comment="Starting analysis",
        )
        
        assert result is True
        mock_jira_client.update_status.assert_called_once_with(
            "SEC-100",
            JiraStatus.ANALYZING,
            "Starting analysis",
        )

    def test_get_status(self, mock_jira_client):
        """Test getting queue status."""
        queue = FindingQueue(jira_client=mock_jira_client)
        
        status = queue.get_status()
        
        assert "pending_count" in status
        assert "processing_count" in status
        assert "completed_count" in status
        assert "failed_count" in status
        assert "is_polling" in status

    def test_get_item_from_any_state(self, mock_jira_client, sample_raw_finding):
        """Test getting item from any state."""
        queue = FindingQueue(jira_client=mock_jira_client)
        
        # Add to pending
        item = QueueItem(finding_id="SEC-100", raw_finding=sample_raw_finding)
        queue._pending.append(item)
        
        found = queue.get_item("SEC-100")
        assert found is not None
        assert found.finding_id == "SEC-100"
