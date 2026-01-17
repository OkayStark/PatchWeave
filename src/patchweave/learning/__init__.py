"""
Learning Loop for PatchWeave.

Stores successful remediations to improve future matching.
Tracks playbook usage statistics and effectiveness metrics.
"""

from datetime import datetime
from typing import Any

from patchweave.agents.state import WorkflowState
from patchweave.logging import get_logger
from patchweave.models.finding import AnalyzedFinding
from patchweave.models.playbook import Playbook, PlaybookMatch

log = get_logger(__name__)


class LearningLoop:
    """
    Records successful remediations to improve future matching.
    
    When a remediation is successfully deployed:
    1. Extracts the finding signature
    2. Associates it with the successful playbook
    3. Stores for future retrieval
    4. Updates playbook usage statistics
    """
    
    def __init__(self):
        """Initialize the learning loop."""
        # In-memory storage for demo/testing
        # In production, would use ChromaDB or another persistence layer
        self._remediation_history: list[dict[str, Any]] = []
        self._playbook_stats: dict[str, dict[str, Any]] = {}
        self._finding_patterns: list[dict[str, Any]] = []
        
        log.info("learning_loop_initialized")
    
    def record_successful_remediation(
        self,
        state: WorkflowState,
        finding: AnalyzedFinding,
        playbook: Playbook,
        match: PlaybookMatch,
        deployment_details: dict[str, Any] | None = None,
    ) -> str:
        """
        Record a successful remediation for future learning.
        
        Args:
            state: Final workflow state
            finding: The remediated finding
            playbook: Playbook that was used
            match: How the playbook was matched
            deployment_details: Additional deployment info
            
        Returns:
            ID of the recorded remediation
        """
        log.info(
            "recording_successful_remediation",
            workflow_id=state.workflow_id,
            finding_id=finding.finding_id,
            playbook_id=playbook.id,
        )
        
        deployment_details = deployment_details or {}
        
        # Generate unique ID
        record_id = f"rem-{state.workflow_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        # Store remediation record
        record = {
            "record_id": record_id,
            "workflow_id": state.workflow_id,
            "jira_ticket_id": state.jira_ticket_id,
            "finding_id": finding.finding_id,
            "playbook_id": playbook.id,
            "playbook_name": playbook.name,
            "vulnerability_type": finding.vulnerability_type.value,
            "severity": finding.severity.value,
            "resource_type": finding.resource_type,
            "source_ticket_url": finding.source_ticket_url,
            "match_similarity": getattr(match, 'similarity', getattr(match, 'similarity_score', 0.0)),
            "match_tier": str(getattr(match, 'tier', getattr(match, 'match_tier', 'unknown'))),
            "approved_by": state.approved_by or "Unknown",
            "deployed_at": datetime.utcnow().isoformat(),
            "dry_run": deployment_details.get("dry_run", False),
        }
        self._remediation_history.append(record)
        
        # Update playbook stats
        self._update_playbook_stats(playbook, success=True)
        
        # Learn finding pattern
        self._learn_finding_pattern(finding, playbook)
        
        log.info(
            "remediation_recorded",
            record_id=record_id,
            workflow_id=state.workflow_id,
            _audit=True,
        )
        
        return record_id
    
    def record_failed_remediation(
        self,
        state: WorkflowState,
        finding: AnalyzedFinding,
        playbook: Playbook,
        error: str,
    ) -> None:
        """
        Record a failed remediation for analysis.
        
        Args:
            state: Final workflow state
            finding: The finding that failed remediation
            playbook: Playbook that was attempted
            error: Error message
        """
        log.warning(
            "recording_failed_remediation",
            workflow_id=state.workflow_id,
            finding_id=finding.finding_id,
            playbook_id=playbook.id,
            error=error,
        )
        
        # Update playbook failure stats
        self._update_playbook_stats(playbook, success=False, error=error)
    
    def _update_playbook_stats(
        self,
        playbook: Playbook,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Update usage statistics for a playbook."""
        
        if playbook.id not in self._playbook_stats:
            self._playbook_stats[playbook.id] = {
                "playbook_id": playbook.id,
                "playbook_name": playbook.name,
                "vulnerability_type": playbook.vulnerability_type.value,
                "success_count": 0,
                "failure_count": 0,
                "first_used_at": datetime.utcnow().isoformat(),
                "last_used_at": None,
                "last_failure_error": None,
            }
        
        stats = self._playbook_stats[playbook.id]
        stats["last_used_at"] = datetime.utcnow().isoformat()
        
        if success:
            stats["success_count"] += 1
        else:
            stats["failure_count"] += 1
            stats["last_failure_error"] = error[:200] if error else None
        
        log.debug(
            "playbook_stats_updated",
            playbook_id=playbook.id,
            success_count=stats["success_count"],
            failure_count=stats["failure_count"],
        )
    
    def _learn_finding_pattern(
        self,
        finding: AnalyzedFinding,
        playbook: Playbook,
    ) -> None:
        """Extract and store finding patterns."""
        
        pattern = {
            "vulnerability_type": finding.vulnerability_type.value,
            "resource_type": finding.resource_type,
            "successful_playbook_id": playbook.id,
            "successful_playbook_name": playbook.name,
            "finding_token_keys": finding.token_keys[:20] if finding.token_keys else [],
            "last_seen_at": datetime.utcnow().isoformat(),
        }
        self._finding_patterns.append(pattern)
        
        log.debug(
            "finding_pattern_learned",
            vulnerability_type=finding.vulnerability_type.value,
            playbook_id=playbook.id,
        )
    
    def get_playbook_stats(self, playbook_id: str) -> dict[str, Any] | None:
        """Get usage statistics for a playbook."""
        return self._playbook_stats.get(playbook_id)
    
    def get_all_playbook_stats(self) -> list[dict[str, Any]]:
        """Get all playbook statistics."""
        return list(self._playbook_stats.values())
    
    def get_remediation_history(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get recent remediation history."""
        return self._remediation_history[-limit:]
    
    def get_learning_summary(self) -> dict[str, Any]:
        """Get a summary of learning data."""
        
        # Sort by success count
        sorted_stats = sorted(
            self._playbook_stats.values(),
            key=lambda x: x.get("success_count", 0),
            reverse=True,
        )
        
        return {
            "remediation_history_count": len(self._remediation_history),
            "playbook_stats_count": len(self._playbook_stats),
            "finding_patterns_count": len(self._finding_patterns),
            "most_used_playbooks": sorted_stats[:5],
            "recent_remediations": self._remediation_history[-5:],
        }


# Singleton instance
_learning_loop: LearningLoop | None = None


def get_learning_loop() -> LearningLoop:
    """Get or create the singleton learning loop."""
    global _learning_loop
    if _learning_loop is None:
        _learning_loop = LearningLoop()
    return _learning_loop
    
    def record_successful_remediation(
        self,
        state: WorkflowState,
        finding: AnalyzedFinding,
        playbook: Playbook,
        match: PlaybookMatch,
        deployment_details: dict[str, Any] | None = None,
    ) -> str:
        """
        Record a successful remediation for future learning.
        
        This is the main entry point called after a successful deployment.
        
        Args:
            state: Final workflow state
            finding: The remediated finding
            playbook: Playbook that was used
            match: How the playbook was matched
            deployment_details: Additional deployment info
            
        Returns:
            ID of the recorded remediation
        """
        log.info(
            "recording_successful_remediation",
            workflow_id=state.workflow_id,
            finding_id=finding.finding_id,
            playbook_id=playbook.id,
        )
        
        # 1. Store remediation history record
        record_id = self._store_remediation_record(
            state=state,
            finding=finding,
            playbook=playbook,
            match=match,
            deployment_details=deployment_details,
        )
        
        # 2. Update playbook statistics
        self._update_playbook_stats(playbook)
        
        # 3. Extract and store finding pattern
        self._learn_finding_pattern(finding, playbook)
        
        log.info(
            "remediation_recorded",
            record_id=record_id,
            workflow_id=state.workflow_id,
            _audit=True,
        )
        
        return record_id
    
    def _store_remediation_record(
        self,
        state: WorkflowState,
        finding: AnalyzedFinding,
        playbook: Playbook,
        match: PlaybookMatch,
        deployment_details: dict[str, Any] | None = None,
    ) -> str:
        """Store a complete remediation record in ChromaDB."""
        
        deployment_details = deployment_details or {}
        
        # Generate a unique ID
        record_id = f"rem-{state.workflow_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        # Build searchable text from finding
        search_text = self._build_remediation_search_text(finding, playbook)
        
        # Metadata for the record
        metadata = {
            "record_id": record_id,
            "workflow_id": state.workflow_id,
            "jira_ticket_id": state.jira_ticket_id,
            "finding_id": finding.finding_id,
            "playbook_id": playbook.id,
            "playbook_name": playbook.name,
            "vulnerability_type": finding.vulnerability_type.value,
            "severity": finding.severity.value,
            "resource_id": finding.resource_id,
            "resource_type": finding.resource_type,
            "region": finding.region,
            "account_id": finding.account_id,
            "match_similarity": getattr(match, 'similarity', getattr(match, 'similarity_score', 0.0)),
            "match_tier": str(getattr(match, 'tier', getattr(match, 'match_tier', 'unknown'))),
            "approved_by": state.approved_by or "Unknown",
            "deployed_at": datetime.utcnow().isoformat(),
            "dry_run": deployment_details.get("dry_run", False),
        }
        
        # Store in ChromaDB
        self.chromadb.add_documents(
            collection_name=self.REMEDIATION_HISTORY_COLLECTION,
            documents=[search_text],
            metadatas=[metadata],
            ids=[record_id],
        )
        
        return record_id
    
    def _build_remediation_search_text(
        self,
        finding: AnalyzedFinding,
        playbook: Playbook,
    ) -> str:
        """Build searchable text for a remediation record."""
        
        parts = [
            f"vulnerability type: {finding.vulnerability_type.value}",
            f"severity: {finding.severity.value}",
            f"resource type: {finding.resource_type}",
            f"title: {finding.sanitized_title}",
            f"description: {finding.sanitized_description}",
            f"playbook: {playbook.name}",
            f"playbook description: {playbook.description}",
        ]
        
        # Add extracted entities
        if finding.extracted_entities:
            if finding.extracted_entities.get("service"):
                parts.append(f"service: {finding.extracted_entities['service']}")
            if finding.extracted_entities.get("resource_patterns"):
                parts.append(f"patterns: {', '.join(finding.extracted_entities['resource_patterns'])}")
        
        return " | ".join(parts)
    
    def _update_playbook_stats(self, playbook: Playbook) -> None:
        """Update usage statistics for a playbook."""
        
        stats_id = f"stats-{playbook.id}"
        
        # Try to get existing stats
        existing = self.chromadb.query(
            collection_name=self.PLAYBOOK_STATS_COLLECTION,
            query_texts=[""],
            n_results=1,
            where={"playbook_id": playbook.id},
        )
        
        if existing and existing.get("ids") and existing["ids"][0]:
            # Update existing stats
            current_metadata = existing["metadatas"][0][0] if existing.get("metadatas") else {}
            success_count = current_metadata.get("success_count", 0) + 1
            
            metadata = {
                **current_metadata,
                "success_count": success_count,
                "last_used_at": datetime.utcnow().isoformat(),
            }
            
            # Update by re-adding with same ID
            self.chromadb.add_documents(
                collection_name=self.PLAYBOOK_STATS_COLLECTION,
                documents=[f"playbook stats for {playbook.name}"],
                metadatas=[metadata],
                ids=[stats_id],
            )
        else:
            # Create new stats record
            metadata = {
                "playbook_id": playbook.id,
                "playbook_name": playbook.name,
                "vulnerability_type": playbook.vulnerability_type.value,
                "success_count": 1,
                "failure_count": 0,
                "first_used_at": datetime.utcnow().isoformat(),
                "last_used_at": datetime.utcnow().isoformat(),
            }
            
            self.chromadb.add_documents(
                collection_name=self.PLAYBOOK_STATS_COLLECTION,
                documents=[f"playbook stats for {playbook.name}"],
                metadatas=[metadata],
                ids=[stats_id],
            )
        
        log.debug(
            "playbook_stats_updated",
            playbook_id=playbook.id,
        )
    
    def _learn_finding_pattern(
        self,
        finding: AnalyzedFinding,
        playbook: Playbook,
    ) -> None:
        """
        Extract and store finding patterns to improve future matching.
        
        Learns the association between finding characteristics and
        successful playbooks.
        """
        
        pattern_id = f"pattern-{finding.vulnerability_type.value}-{finding.resource_type}"
        
        # Build pattern search text
        pattern_text = " ".join([
            finding.vulnerability_type.value,
            finding.resource_type,
            finding.sanitized_title,
            *finding.keywords[:10],  # Top keywords
        ])
        
        metadata = {
            "vulnerability_type": finding.vulnerability_type.value,
            "resource_type": finding.resource_type,
            "successful_playbook_id": playbook.id,
            "successful_playbook_name": playbook.name,
            "finding_keywords": ",".join(finding.keywords[:20]),
            "occurrence_count": 1,  # Would increment on repeat patterns
            "last_seen_at": datetime.utcnow().isoformat(),
        }
        
        # Store pattern
        self.chromadb.add_documents(
            collection_name=self.FINDING_PATTERNS_COLLECTION,
            documents=[pattern_text],
            metadatas=[metadata],
            ids=[pattern_id],
        )
        
        log.debug(
            "finding_pattern_learned",
            vulnerability_type=finding.vulnerability_type.value,
            resource_type=finding.resource_type,
            playbook_id=playbook.id,
        )
    
    def record_failed_remediation(
        self,
        state: WorkflowState,
        finding: AnalyzedFinding,
        playbook: Playbook,
        error: str,
    ) -> None:
        """
        Record a failed remediation for analysis.
        
        Args:
            state: Final workflow state
            finding: The finding that failed remediation
            playbook: Playbook that was attempted
            error: Error message
        """
        log.warning(
            "recording_failed_remediation",
            workflow_id=state.workflow_id,
            finding_id=finding.finding_id,
            playbook_id=playbook.id,
            error=error,
        )
        
        # Update playbook failure stats
        stats_id = f"stats-{playbook.id}"
        
        existing = self.chromadb.query(
            collection_name=self.PLAYBOOK_STATS_COLLECTION,
            query_texts=[""],
            n_results=1,
            where={"playbook_id": playbook.id},
        )
        
        if existing and existing.get("ids") and existing["ids"][0]:
            current_metadata = existing["metadatas"][0][0] if existing.get("metadatas") else {}
            failure_count = current_metadata.get("failure_count", 0) + 1
            
            metadata = {
                **current_metadata,
                "failure_count": failure_count,
                "last_failure_at": datetime.utcnow().isoformat(),
                "last_failure_error": error[:200],  # Truncate error
            }
            
            self.chromadb.add_documents(
                collection_name=self.PLAYBOOK_STATS_COLLECTION,
                documents=[f"playbook stats for {playbook.name}"],
                metadatas=[metadata],
                ids=[stats_id],
            )
    
    def get_playbook_stats(self, playbook_id: str) -> dict[str, Any] | None:
        """
        Get usage statistics for a playbook.
        
        Args:
            playbook_id: Playbook to get stats for
            
        Returns:
            Statistics dictionary or None if not found
        """
        results = self.chromadb.query(
            collection_name=self.PLAYBOOK_STATS_COLLECTION,
            query_texts=[""],
            n_results=1,
            where={"playbook_id": playbook_id},
        )
        
        if results and results.get("metadatas") and results["metadatas"][0]:
            return results["metadatas"][0][0]
        
        return None
    
    def get_similar_past_remediations(
        self,
        finding: AnalyzedFinding,
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Find similar past remediations for a finding.
        
        Used to boost confidence when matching - if we've successfully
        remediated similar findings before with a certain playbook.
        
        Args:
            finding: Finding to search for similar past remediations
            n_results: Number of results to return
            
        Returns:
            List of similar past remediation records
        """
        search_text = " ".join([
            finding.vulnerability_type.value,
            finding.resource_type,
            finding.sanitized_title,
        ])
        
        results = self.chromadb.query(
            collection_name=self.REMEDIATION_HISTORY_COLLECTION,
            query_texts=[search_text],
            n_results=n_results,
        )
        
        if not results or not results.get("metadatas"):
            return []
        
        remediations = []
        for i, metadata in enumerate(results["metadatas"][0]):
            if results.get("distances") and results["distances"][0]:
                similarity = 1 - results["distances"][0][i]  # Convert distance to similarity
            else:
                similarity = 0.0
            
            remediations.append({
                **metadata,
                "similarity": similarity,
            })
        
        return remediations
    
    def get_learning_summary(self) -> dict[str, Any]:
        """Get a summary of learning data for monitoring."""
        
        # Count records in each collection
        summary = {
            "remediation_history_count": 0,
            "playbook_stats_count": 0,
            "finding_patterns_count": 0,
            "most_used_playbooks": [],
            "recent_remediations": [],
        }
        
        try:
            # Get remediation count
            history = self.chromadb.query(
                collection_name=self.REMEDIATION_HISTORY_COLLECTION,
                query_texts=[""],
                n_results=100,
            )
            if history and history.get("ids"):
                summary["remediation_history_count"] = len(history["ids"][0])
            
            # Get playbook stats
            stats = self.chromadb.query(
                collection_name=self.PLAYBOOK_STATS_COLLECTION,
                query_texts=[""],
                n_results=100,
            )
            if stats and stats.get("metadatas") and stats["metadatas"][0]:
                summary["playbook_stats_count"] = len(stats["metadatas"][0])
                
                # Sort by success count
                sorted_stats = sorted(
                    stats["metadatas"][0],
                    key=lambda x: x.get("success_count", 0),
                    reverse=True,
                )
                summary["most_used_playbooks"] = sorted_stats[:5]
            
        except Exception as e:
            log.warning(
                "learning_summary_error",
                error=str(e),
            )
        
        return summary


# Singleton instance
_learning_loop: LearningLoop | None = None


def get_learning_loop() -> LearningLoop:
    """Get or create the singleton learning loop."""
    global _learning_loop
    if _learning_loop is None:
        _learning_loop = LearningLoop()
    return _learning_loop
