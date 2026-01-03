"""Tests for ChromaDB playbook store."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from patchweave.core.chromadb import PlaybookStore
from patchweave.models.enums import CloudProvider, Severity, VulnerabilityType
from patchweave.models.playbook import Playbook


@pytest.fixture
def sample_playbook() -> Playbook:
    """Create a sample playbook for testing."""
    return Playbook(
        id=str(uuid.uuid4()),
        name="Test S3 Encryption Playbook",
        description="Enable encryption for S3 buckets",
        vulnerability_type=VulnerabilityType.S3_ENCRYPTION_DISABLED,
        cloud_provider=CloudProvider.AWS,
        resource_type="AWS::S3::Bucket",
        severity=Severity.HIGH,
        search_text="S3 bucket encryption AES-256 server-side encryption data at rest AWS",
        remediation_code="def remediate(bucket): pass",
        pre_check_code="def pre_check(bucket): pass",
        post_check_code="def post_check(bucket): pass",
        required_permissions=["s3:GetBucketEncryption", "s3:PutBucketEncryption"],
        tags=["s3", "encryption"],
    )


@pytest.fixture
def multiple_playbooks() -> list[Playbook]:
    """Create multiple playbooks for testing."""
    return [
        Playbook(
            id=str(uuid.uuid4()),
            name="S3 Encryption Playbook",
            description="Enable encryption for S3 buckets",
            vulnerability_type=VulnerabilityType.S3_ENCRYPTION_DISABLED,
            cloud_provider=CloudProvider.AWS,
            resource_type="AWS::S3::Bucket",
            severity=Severity.HIGH,
            search_text="S3 bucket encryption server-side AES256",
            remediation_code="pass",
            pre_check_code="pass",
            post_check_code="pass",
        ),
        Playbook(
            id=str(uuid.uuid4()),
            name="Security Group SSH Remediation",
            description="Remove open SSH access from security groups",
            vulnerability_type=VulnerabilityType.SECURITY_GROUP_OPEN_SSH,
            cloud_provider=CloudProvider.AWS,
            resource_type="AWS::EC2::SecurityGroup",
            severity=Severity.CRITICAL,
            search_text="Security group SSH port 22 open unrestricted 0.0.0.0/0",
            remediation_code="pass",
            pre_check_code="pass",
            post_check_code="pass",
        ),
        Playbook(
            id=str(uuid.uuid4()),
            name="RDS Public Access",
            description="Disable public accessibility for RDS",
            vulnerability_type=VulnerabilityType.RDS_PUBLICLY_ACCESSIBLE,
            cloud_provider=CloudProvider.AWS,
            resource_type="AWS::RDS::DBInstance",
            severity=Severity.CRITICAL,
            search_text="RDS database public accessible internet exposed",
            remediation_code="pass",
            pre_check_code="pass",
            post_check_code="pass",
        ),
    ]


class TestPlaybookStore:
    """Tests for PlaybookStore class."""

    def test_initialization(self) -> None:
        """Test store initialization."""
        store = PlaybookStore()
        assert store._client is None
        assert store._collection is None
        assert store.host is not None

    def test_initialization_custom_params(self) -> None:
        """Test initialization with custom parameters."""
        store = PlaybookStore(
            host="custom-host",
            port=9000,
            persist_directory="/custom/path",
        )
        assert store.host == "custom-host"
        assert store.port == 9000
        assert store.persist_directory == "/custom/path"

    @patch("patchweave.core.chromadb.chromadb")
    def test_connect_persistent_mode(self, mock_chromadb: MagicMock) -> None:
        """Test connecting in persistent mode."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        store = PlaybookStore()
        store.connect(use_persistent=True)

        mock_chromadb.PersistentClient.assert_called_once()
        mock_client.get_or_create_collection.assert_called_once()
        assert store._client == mock_client
        assert store._collection == mock_collection

    @patch("patchweave.core.chromadb.chromadb")
    def test_connect_http_mode(self, mock_chromadb: MagicMock) -> None:
        """Test connecting in HTTP mode."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chromadb.HttpClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        store = PlaybookStore()
        store.connect(use_persistent=False)

        mock_chromadb.HttpClient.assert_called_once()
        assert store._client == mock_client

    @patch("patchweave.core.chromadb.chromadb")
    def test_add_playbook(
        self, mock_chromadb: MagicMock, sample_playbook: Playbook
    ) -> None:
        """Test adding a single playbook."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        store = PlaybookStore()
        store.connect(use_persistent=True)
        store.add_playbook(sample_playbook)

        mock_collection.add.assert_called_once()
        call_kwargs = mock_collection.add.call_args[1]
        assert call_kwargs["ids"] == [sample_playbook.id]
        assert len(call_kwargs["documents"]) == 1
        assert len(call_kwargs["metadatas"]) == 1

    @patch("patchweave.core.chromadb.chromadb")
    def test_add_playbooks_batch(
        self, mock_chromadb: MagicMock, multiple_playbooks: list[Playbook]
    ) -> None:
        """Test adding multiple playbooks."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        store = PlaybookStore()
        store.connect(use_persistent=True)
        store.add_playbooks(multiple_playbooks)

        mock_collection.add.assert_called_once()
        call_kwargs = mock_collection.add.call_args[1]
        assert len(call_kwargs["ids"]) == 3
        assert len(call_kwargs["documents"]) == 3

    @patch("patchweave.core.chromadb.chromadb")
    def test_search_returns_results(self, mock_chromadb: MagicMock) -> None:
        """Test search returns playbooks with similarity scores."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 2
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        # Mock search results
        mock_collection.query.return_value = {
            "ids": [["playbook-1", "playbook-2"]],
            "documents": [["doc1", "doc2"]],
            "metadatas": [
                [
                    {
                        "name": "Test Playbook 1",
                        "description": "Test description",
                        "vulnerability_type": "s3_encryption_disabled",
                        "cloud_provider": "AWS",
                        "resource_type": "AWS::S3::Bucket",
                        "severity": "High",
                        "version": "1.0.0",
                    },
                    {
                        "name": "Test Playbook 2",
                        "description": "Test description 2",
                        "vulnerability_type": "security_group_open_ssh",
                        "cloud_provider": "AWS",
                        "resource_type": "AWS::EC2::SecurityGroup",
                        "severity": "Critical",
                        "version": "1.0.0",
                    },
                ]
            ],
            "distances": [[0.1, 0.3]],
        }

        store = PlaybookStore()
        store.connect(use_persistent=True)
        results = store.search("S3 bucket encryption", n_results=2)

        assert len(results) == 2
        playbook1, score1 = results[0]
        playbook2, score2 = results[1]
        assert score1 > score2  # Lower distance = higher similarity
        assert playbook1.id == "playbook-1"

    @patch("patchweave.core.chromadb.chromadb")
    def test_search_with_filters(self, mock_chromadb: MagicMock) -> None:
        """Test search with metadata filters."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

        store = PlaybookStore()
        store.connect(use_persistent=True)
        store.search(
            "test query",
            cloud_provider="AWS",
            vulnerability_type="s3_encryption_disabled",
        )

        call_kwargs = mock_collection.query.call_args[1]
        assert "where" in call_kwargs
        # Should have filter for cloud_provider and vulnerability_type
        where_clause = call_kwargs["where"]
        assert "$and" in where_clause

    @patch("patchweave.core.chromadb.chromadb")
    def test_get_playbook_by_id(
        self, mock_chromadb: MagicMock, sample_playbook: Playbook
    ) -> None:
        """Test retrieving a playbook by ID."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 1
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        mock_collection.get.return_value = {
            "ids": [sample_playbook.id],
            "metadatas": [
                {
                    "name": sample_playbook.name,
                    "vulnerability_type": sample_playbook.vulnerability_type.value,
                    "cloud_provider": sample_playbook.cloud_provider.value,
                    "resource_type": sample_playbook.resource_type,
                    "severity": sample_playbook.severity.value,
                    "version": "1.0.0",
                }
            ],
            "documents": ["test document"],
        }

        store = PlaybookStore()
        store.connect(use_persistent=True)
        result = store.get_playbook(sample_playbook.id)

        assert result is not None
        assert result.id == sample_playbook.id
        assert result.name == sample_playbook.name

    @patch("patchweave.core.chromadb.chromadb")
    def test_get_playbook_not_found(self, mock_chromadb: MagicMock) -> None:
        """Test retrieving non-existent playbook returns None."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_collection.get.return_value = {"ids": [], "metadatas": [], "documents": []}

        store = PlaybookStore()
        store.connect(use_persistent=True)
        result = store.get_playbook("nonexistent-id")

        assert result is None

    @patch("patchweave.core.chromadb.chromadb")
    def test_delete_playbook(self, mock_chromadb: MagicMock) -> None:
        """Test deleting a playbook."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 1
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        store = PlaybookStore()
        store.connect(use_persistent=True)
        store.delete_playbook("playbook-id")

        mock_collection.delete.assert_called_once_with(ids=["playbook-id"])

    @patch("patchweave.core.chromadb.chromadb")
    def test_get_statistics(self, mock_chromadb: MagicMock) -> None:
        """Test getting store statistics."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 15
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        store = PlaybookStore()
        store.connect(use_persistent=True)
        stats = store.get_statistics()

        assert stats["collection_name"] == "playbooks"
        assert stats["total_playbooks"] == 15

    def test_playbook_to_document(self, sample_playbook: Playbook) -> None:
        """Test playbook to document conversion."""
        store = PlaybookStore()
        doc = store._playbook_to_document(sample_playbook)

        assert sample_playbook.name in doc
        assert sample_playbook.description in doc
        assert sample_playbook.search_text in doc
        assert sample_playbook.vulnerability_type.value in doc


class TestPlaybookStoreIntegration:
    """Integration-style tests for PlaybookStore (mocked)."""

    @patch("patchweave.core.chromadb.chromadb")
    def test_full_workflow(
        self, mock_chromadb: MagicMock, multiple_playbooks: list[Playbook]
    ) -> None:
        """Test complete add-search-retrieve workflow."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 3
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        store = PlaybookStore()
        store.connect(use_persistent=True)

        # Add playbooks
        store.add_playbooks(multiple_playbooks)
        assert mock_collection.add.called

        # Verify count
        stats = store.get_statistics()
        assert stats["total_playbooks"] == 3
