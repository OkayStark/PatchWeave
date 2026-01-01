"""
Unit tests for API endpoints.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client():
    """Create test client for API."""
    from patchweave.api import app
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_liveness(self, api_client):
        """Test liveness probe."""
        response = api_client.get("/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    def test_readiness(self, api_client):
        """Test readiness probe."""
        response = api_client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


class TestQueueEndpoint:
    """Tests for queue status endpoint."""

    def test_get_queue_status(self, api_client):
        """Test queue status retrieval."""
        response = api_client.get("/queue")
        assert response.status_code == 200
        data = response.json()
        assert "pending_count" in data
        assert "currently_processing" in data


class TestFindingsEndpoint:
    """Tests for findings endpoints."""

    def test_list_findings(self, api_client):
        """Test listing findings."""
        response = api_client.get("/findings")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "findings" in data

    def test_get_finding_not_found(self, api_client):
        """Test getting non-existent finding."""
        response = api_client.get("/findings/NONEXISTENT-123")
        assert response.status_code == 404


class TestPlaybooksEndpoint:
    """Tests for playbooks endpoints."""

    def test_list_playbooks(self, api_client):
        """Test listing playbooks."""
        response = api_client.get("/playbooks")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "playbooks" in data

    def test_get_playbook_not_found(self, api_client):
        """Test getting non-existent playbook."""
        response = api_client.get("/playbooks/nonexistent-id")
        assert response.status_code == 404


class TestStatsEndpoint:
    """Tests for statistics endpoint."""

    def test_get_stats(self, api_client):
        """Test getting system statistics."""
        response = api_client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert "resolved_total" in data
        assert "playbook_hit_rate" in data
