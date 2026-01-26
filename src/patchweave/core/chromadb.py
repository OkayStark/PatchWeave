"""
ChromaDB integration for PatchWeave playbook storage.

Provides semantic search capabilities for matching findings
to remediation playbooks using vector embeddings.
"""

from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from patchweave.config import settings
from patchweave.logging import get_logger
from patchweave.models.playbook import Playbook

log = get_logger(__name__)


class PlaybookStore:
    """
    Vector database store for remediation playbooks.
    
    Uses ChromaDB to store playbook embeddings and perform
    semantic similarity search for finding-to-playbook matching.
    """

    COLLECTION_NAME = "playbooks"

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        persist_directory: str | None = None,
    ):
        """
        Initialize the playbook store.
        
        Args:
            host: ChromaDB host (defaults to settings)
            port: ChromaDB port (defaults to settings)
            persist_directory: Local persistence directory for embedded mode
        """
        self.host = host or settings.chroma_host
        self.port = port or settings.chroma_port
        self.persist_directory = persist_directory or settings.chroma_persist_directory
        
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None
        
        log.info(
            "playbook_store_initialized",
            host=self.host,
            port=self.port,
        )

    def connect(self, use_persistent: bool = False) -> None:
        """
        Connect to ChromaDB.
        
        Args:
            use_persistent: If True, use local persistent storage instead of server
        """
        try:
            if use_persistent:
                # Local persistent mode (for development/testing)
                self._client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=ChromaSettings(
                        anonymized_telemetry=False,
                    ),
                )
                log.info("chromadb_connected_persistent", path=self.persist_directory)
            else:
                # Server mode (for production)
                self._client = chromadb.HttpClient(
                    host=self.host,
                    port=self.port,
                    settings=ChromaSettings(
                        anonymized_telemetry=False,
                    ),
                )
                log.info("chromadb_connected_http", host=self.host, port=self.port)

            # Get or create the playbooks collection
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "PatchWeave remediation playbooks"},
            )
            
            log.info(
                "chromadb_collection_ready",
                collection=self.COLLECTION_NAME,
                count=self._collection.count(),
            )
            
        except Exception as e:
            log.error("chromadb_connection_failed", error=str(e))
            raise

    @property
    def collection(self) -> chromadb.Collection:
        """Get the playbooks collection, connecting if needed."""
        if self._collection is None:
            self.connect(use_persistent=True)  # Default to persistent for dev
        return self._collection  # type: ignore

    def add_playbook(self, playbook: Playbook) -> str:
        """
        Add a playbook to the vector store.
        
        Args:
            playbook: Playbook to add
            
        Returns:
            The playbook ID
        """
        # Build document text for embedding
        document = self._playbook_to_document(playbook)
        
        # Build metadata for filtering AND storing code
        # Note: ChromaDB metadata values must be strings, ints, floats, or bools
        metadata = {
            "name": playbook.name,
            "description": playbook.description,
            "vulnerability_type": playbook.vulnerability_type.value,
            "cloud_provider": playbook.cloud_provider.value,
            "resource_type": playbook.resource_type,
            "severity": playbook.severity.value,
            "version": playbook.version,
            "search_text": playbook.search_text,
            # Store the code fields - these are essential for validation!
            "remediation_code": playbook.remediation_code,
            "pre_check_code": playbook.pre_check_code,
            "post_check_code": playbook.post_check_code,
        }
        
        # Add to collection
        self.collection.add(
            ids=[playbook.id],
            documents=[document],
            metadatas=[metadata],
        )
        
        log.info(
            "playbook_added",
            playbook_id=playbook.id,
            name=playbook.name,
            vulnerability_type=playbook.vulnerability_type.value,
        )
        
        return playbook.id

    def add_playbooks(self, playbooks: list[Playbook]) -> list[str]:
        """
        Add multiple playbooks to the store.
        
        Args:
            playbooks: List of playbooks to add
            
        Returns:
            List of playbook IDs
        """
        if not playbooks:
            return []
            
        ids = [p.id for p in playbooks]
        documents = [self._playbook_to_document(p) for p in playbooks]
        metadatas = [
            {
                "name": p.name,
                "description": p.description,
                "vulnerability_type": p.vulnerability_type.value,
                "cloud_provider": p.cloud_provider.value,
                "resource_type": p.resource_type,
                "severity": p.severity.value,
                "version": p.version,
                "search_text": p.search_text,
                # Store the code fields - these are essential for validation!
                "remediation_code": p.remediation_code,
                "pre_check_code": p.pre_check_code,
                "post_check_code": p.post_check_code,
            }
            for p in playbooks
        ]
        
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        
        log.info("playbooks_added_batch", count=len(playbooks))
        return ids

    def _playbook_to_document(self, playbook: Playbook) -> str:
        """
        Convert playbook to searchable document text.
        
        Combines relevant fields to create rich embedding text.
        """
        parts = [
            f"Name: {playbook.name}",
            f"Description: {playbook.description}",
            f"Vulnerability Type: {playbook.vulnerability_type.value}",
            f"Resource Type: {playbook.resource_type}",
            f"Search Text: {playbook.search_text}",
        ]
        
        if playbook.tags:
            parts.append(f"Tags: {', '.join(playbook.tags)}")
            
        if playbook.compliance_frameworks:
            parts.append(f"Compliance: {', '.join(playbook.compliance_frameworks)}")
            
        return "\n".join(parts)

    def search(
        self,
        query: str,
        n_results: int = 5,
        vulnerability_type: str | None = None,
        cloud_provider: str | None = None,
    ) -> list[tuple[Playbook, float]]:
        """
        Search for matching playbooks.
        
        Args:
            query: Search query (semantic search)
            n_results: Maximum number of results
            vulnerability_type: Filter by vulnerability type
            cloud_provider: Filter by cloud provider
            
        Returns:
            List of tuples (Playbook, similarity_score)
        """
        # Build where filter
        where_filter = None
        if vulnerability_type or cloud_provider:
            conditions = []
            if vulnerability_type:
                conditions.append({"vulnerability_type": vulnerability_type})
            if cloud_provider:
                conditions.append({"cloud_provider": cloud_provider})
            
            if len(conditions) == 1:
                where_filter = conditions[0]
            else:
                where_filter = {"$and": conditions}

        # Execute search
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
        
        # Convert to list of (Playbook, similarity) tuples
        matches: list[tuple[Playbook, float]] = []
        if results["ids"] and results["ids"][0]:
            for i, id_ in enumerate(results["ids"][0]):
                # ChromaDB returns L2 distance, convert to similarity score
                # Lower distance = higher similarity
                distance = results["distances"][0][i] if results["distances"] else 0
                # Convert distance to 0-1 similarity score
                # Using exponential decay: similarity = e^(-distance/2)
                import math
                similarity = math.exp(-distance / 2)
                
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                playbook = self._metadata_to_playbook(id_, metadata)
                matches.append((playbook, similarity))
        
        log.debug(
            "playbook_search_complete",
            query=query[:50],
            results_count=len(matches),
            top_similarity=matches[0][1] if matches else 0,
        )
        
        return matches

    def _metadata_to_playbook(self, playbook_id: str, metadata: dict[str, Any]) -> Playbook:
        """Convert stored metadata back to a Playbook object."""
        from patchweave.models.enums import CloudProvider, Severity, VulnerabilityType
        
        return Playbook(
            id=playbook_id,
            name=metadata.get("name", ""),
            description=metadata.get("description", ""),
            vulnerability_type=VulnerabilityType(metadata.get("vulnerability_type", "unknown")),
            cloud_provider=CloudProvider(metadata.get("cloud_provider", "AWS")),
            resource_type=metadata.get("resource_type", ""),
            severity=Severity(metadata.get("severity", "Medium")),
            search_text=metadata.get("search_text", ""),
            remediation_code=metadata.get("remediation_code", ""),
            pre_check_code=metadata.get("pre_check_code", ""),
            post_check_code=metadata.get("post_check_code", ""),
            version=metadata.get("version", "1.0.0"),
        )

    def get_playbook(self, playbook_id: str) -> Playbook | None:
        """
        Get a playbook by ID.
        
        Args:
            playbook_id: Playbook ID
            
        Returns:
            Playbook or None if not found
        """
        results = self.collection.get(
            ids=[playbook_id],
            include=["documents", "metadatas"],
        )
        
        if not results["ids"] or len(results["ids"]) == 0:
            return None
        
        # Safely access metadata with bounds check
        metadata = {}
        if results.get("metadatas") and len(results["metadatas"]) > 0:
            metadata = results["metadatas"][0]
            
        return self._metadata_to_playbook(results["ids"][0], metadata)

    def get_statistics(self) -> dict[str, Any]:
        """
        Get store statistics.
        
        Returns:
            Dictionary with store statistics
        """
        return {
            "collection_name": self.COLLECTION_NAME,
            "total_playbooks": self.collection.count(),
        }

    def delete_playbook(self, playbook_id: str) -> bool:
        """
        Delete a playbook from the store.
        
        Args:
            playbook_id: Playbook ID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            self.collection.delete(ids=[playbook_id])
            log.info("playbook_deleted", playbook_id=playbook_id)
            return True
        except Exception as e:
            log.error("playbook_delete_failed", playbook_id=playbook_id, error=str(e))
            return False

    def clear(self) -> None:
        """Delete all playbooks from the store."""
        if self._client and self._collection:
            self._client.delete_collection(self.COLLECTION_NAME)
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "PatchWeave remediation playbooks"},
            )
            log.info("playbook_store_cleared")

    def count(self) -> int:
        """Get the number of playbooks in the store."""
        return self.collection.count()


# Global instance
_playbook_store: PlaybookStore | None = None


def get_playbook_store() -> PlaybookStore:
    """Get or create the global playbook store instance."""
    global _playbook_store
    if _playbook_store is None:
        _playbook_store = PlaybookStore()
    return _playbook_store
