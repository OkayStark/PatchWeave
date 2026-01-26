"""
Finding Queue service for PatchWeave.

Manages the queue of security findings being processed:
- Polls Jira for new findings
- Tracks processing state
- Coordinates status updates
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Awaitable

from patchweave.integrations.jira import JiraClient, get_jira_client
from patchweave.logging import get_logger
from patchweave.models.enums import JiraStatus
from patchweave.models.finding import AnalyzedFinding, RawFinding

log = get_logger(__name__)


class QueueItemState(str, Enum):
    """Internal state of a queue item."""
    
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class QueueItem:
    """Item in the finding queue."""
    
    finding_id: str
    raw_finding: RawFinding
    analyzed_finding: AnalyzedFinding | None = None
    state: QueueItemState = QueueItemState.PENDING
    jira_status: JiraStatus = JiraStatus.OPEN
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retry_count: int = 0
    max_retries: int = 3

    def can_retry(self) -> bool:
        """Check if this item can be retried."""
        return self.retry_count < self.max_retries

    def mark_processing(self) -> None:
        """Mark item as being processed."""
        self.state = QueueItemState.PROCESSING
        self.updated_at = datetime.now(timezone.utc)

    def mark_completed(self, analyzed: AnalyzedFinding) -> None:
        """Mark item as successfully completed."""
        self.state = QueueItemState.COMPLETED
        self.analyzed_finding = analyzed
        self.updated_at = datetime.now(timezone.utc)

    def mark_failed(self, error: str) -> None:
        """Mark item as failed."""
        self.state = QueueItemState.FAILED
        self.error = error
        self.retry_count += 1
        self.updated_at = datetime.now(timezone.utc)


class FindingQueue:
    """
    Queue for managing security findings through the analysis pipeline.
    
    Responsibilities:
    - Poll Jira for new OPEN findings
    - Queue findings for processing
    - Track processing state
    - Update Jira status as findings progress
    """

    def __init__(
        self,
        jira_client: JiraClient | None = None,
        poll_interval: int | None = None,
    ):
        """
        Initialize the finding queue.
        
        Args:
            jira_client: Jira client instance (defaults to global)
            poll_interval: Seconds between Jira polls (defaults to settings)
        """
        from patchweave.config import settings
        
        self._jira = jira_client or get_jira_client()
        self._poll_interval = poll_interval or settings.jira_poll_interval_seconds
        
        # Queue storage
        self._pending: deque[QueueItem] = deque()
        self._processing: dict[str, QueueItem] = {}
        self._completed: dict[str, QueueItem] = {}
        self._failed: dict[str, QueueItem] = {}
        
        # Tracking
        self._known_ids: set[str] = set()
        self._is_polling = False
        self._poll_task: asyncio.Task | None = None
        
        # Callbacks
        self._on_new_finding: Callable[[RawFinding], Awaitable[None]] | None = None
        
        log.info(
            "finding_queue_initialized",
            poll_interval=self._poll_interval,
        )

    @property
    def pending_count(self) -> int:
        """Number of pending items."""
        return len(self._pending)

    @property
    def processing_count(self) -> int:
        """Number of items being processed."""
        return len(self._processing)

    @property
    def completed_count(self) -> int:
        """Number of completed items."""
        return len(self._completed)

    @property
    def failed_count(self) -> int:
        """Number of failed items."""
        return len(self._failed)

    def on_new_finding(
        self,
        callback: Callable[[RawFinding], Awaitable[None]],
    ) -> None:
        """Register callback for new findings."""
        self._on_new_finding = callback

    async def poll_once(self) -> list[RawFinding]:
        """
        Poll Jira once for new findings.
        
        Returns:
            List of new findings discovered
        """
        log.debug("polling_jira")
        
        try:
            findings = self._jira.fetch_open_findings()
            new_findings: list[RawFinding] = []
            
            for finding in findings:
                if finding.jira_ticket_id not in self._known_ids:
                    self._known_ids.add(finding.jira_ticket_id)
                    new_findings.append(finding)
                    
                    # Add to queue
                    item = QueueItem(
                        finding_id=finding.jira_ticket_id,
                        raw_finding=finding,
                    )
                    self._pending.append(item)
                    
                    log.info(
                        "new_finding_queued",
                        finding_id=finding.jira_ticket_id,
                        title=finding.title[:50],
                    )
                    
                    # Trigger callback
                    if self._on_new_finding:
                        try:
                            await self._on_new_finding(finding)
                        except Exception as e:
                            log.error(
                                "new_finding_callback_failed",
                                finding_id=finding.jira_ticket_id,
                                error=str(e),
                            )

            if new_findings:
                log.info(
                    "poll_complete",
                    new_count=len(new_findings),
                    total_pending=self.pending_count,
                )
            
            return new_findings
            
        except Exception as e:
            log.error("poll_failed", error=str(e))
            return []

    async def start_polling(self) -> None:
        """Start background polling for new findings."""
        if self._is_polling:
            log.warning("polling_already_started")
            return
            
        self._is_polling = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        log.info("polling_started", interval=self._poll_interval)

    async def stop_polling(self) -> None:
        """Stop background polling."""
        self._is_polling = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        log.info("polling_stopped")

    async def _poll_loop(self) -> None:
        """Background polling loop."""
        while self._is_polling:
            try:
                await self.poll_once()
            except Exception as e:
                log.error("poll_loop_error", error=str(e))
            
            await asyncio.sleep(self._poll_interval)

    def get_next(self) -> QueueItem | None:
        """
        Get the next pending item for processing.
        
        Returns:
            QueueItem or None if queue is empty
        """
        if not self._pending:
            return None
            
        item = self._pending.popleft()
        item.mark_processing()
        self._processing[item.finding_id] = item
        
        log.debug(
            "item_dequeued",
            finding_id=item.finding_id,
            pending_remaining=self.pending_count,
        )
        
        return item

    def complete_item(
        self,
        finding_id: str,
        analyzed_finding: AnalyzedFinding,
    ) -> bool:
        """
        Mark an item as successfully completed.
        
        Args:
            finding_id: Finding ID
            analyzed_finding: The analysis result
            
        Returns:
            True if item was found and updated
        """
        item = self._processing.pop(finding_id, None)
        if not item:
            log.warning("complete_item_not_found", finding_id=finding_id)
            return False
            
        item.mark_completed(analyzed_finding)
        self._completed[finding_id] = item
        
        log.info(
            "item_completed",
            finding_id=finding_id,
            vulnerability_type=analyzed_finding.vulnerability_type.value,
        )
        
        return True

    def fail_item(self, finding_id: str, error: str) -> bool:
        """
        Mark an item as failed.
        
        If retries remain, re-queue the item.
        
        Args:
            finding_id: Finding ID
            error: Error message
            
        Returns:
            True if item was found and updated
        """
        item = self._processing.pop(finding_id, None)
        if not item:
            log.warning("fail_item_not_found", finding_id=finding_id)
            return False
            
        item.mark_failed(error)
        
        if item.can_retry():
            # Re-queue for retry
            item.state = QueueItemState.PENDING
            self._pending.append(item)
            log.warning(
                "item_requeued",
                finding_id=finding_id,
                retry_count=item.retry_count,
                error=error,
            )
        else:
            # Max retries exceeded
            self._failed[finding_id] = item
            log.error(
                "item_failed_permanently",
                finding_id=finding_id,
                retry_count=item.retry_count,
                error=error,
            )
        
        return True

    def update_jira_status(
        self,
        finding_id: str,
        new_status: JiraStatus,
        comment: str | None = None,
    ) -> bool:
        """
        Update the Jira status for a finding.
        
        Args:
            finding_id: Finding ID
            new_status: New Jira status
            comment: Optional comment to add
            
        Returns:
            True if update succeeded
        """
        # Find the item
        item = (
            self._processing.get(finding_id)
            or self._completed.get(finding_id)
            or self._failed.get(finding_id)
        )
        
        if not item:
            # Check pending queue
            for pending_item in self._pending:
                if pending_item.finding_id == finding_id:
                    item = pending_item
                    break
        
        success = self._jira.update_status(finding_id, new_status, comment)
        
        if success and item:
            item.jira_status = new_status
            item.updated_at = datetime.now(timezone.utc)
            
        return success

    def get_item(self, finding_id: str) -> QueueItem | None:
        """Get an item by finding ID from any state."""
        return (
            self._processing.get(finding_id)
            or self._completed.get(finding_id)
            or self._failed.get(finding_id)
            or next(
                (i for i in self._pending if i.finding_id == finding_id),
                None,
            )
        )

    def get_status(self) -> dict:
        """Get queue status summary."""
        return {
            "pending_count": self.pending_count,
            "processing_count": self.processing_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "is_polling": self._is_polling,
            "known_ids_count": len(self._known_ids),
        }

    def get_currently_processing(self) -> list[str]:
        """Get IDs of items currently being processed."""
        return list(self._processing.keys())


# Global instance
_finding_queue: FindingQueue | None = None


def get_finding_queue() -> FindingQueue:
    """Get or create the global finding queue instance."""
    global _finding_queue
    if _finding_queue is None:
        _finding_queue = FindingQueue()
    return _finding_queue
