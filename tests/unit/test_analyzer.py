"""
Unit tests for Analyzer Agent.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from patchweave.agents.analyzer import (
    AnalyzerAgent,
    AnalysisOutput,
    ANALYZER_SYSTEM_PROMPT,
)
from patchweave.models.enums import Severity, VulnerabilityType
from patchweave.models.finding import RawFinding


@pytest.fixture
def sample_finding():
    """Create a sample raw finding for testing."""
    return RawFinding(
        jira_ticket_id="SEC-1234",
        jira_ticket_url="https://example.atlassian.net/browse/SEC-1234",
        title="S3 Bucket 'prod-logs-bucket' has public access enabled",
        description=(
            "The S3 bucket prod-logs-bucket in account 123456789012 "
            "region us-east-1 has Block Public Access settings disabled. "
            "This allows potential public access to bucket contents."
        ),
        severity="Critical",
        created_at=datetime.now(timezone.utc),
        custom_fields={},
    )


class TestAnalyzerAgent:
    """Tests for the AnalyzerAgent class."""

    def test_init_default_settings(self):
        """Test initializing with default settings."""
        agent = AnalyzerAgent()
        # Default is now gemini-1.5-flash for free tier
        assert agent.model == "gemini-1.5-flash"
        assert agent.temperature == 0.0

    def test_init_custom_settings(self):
        """Test initializing with custom settings."""
        agent = AnalyzerAgent(model="gpt-4", temperature=0.5)
        assert agent.model == "gpt-4"
        assert agent.temperature == 0.5

    def test_parse_vulnerability_type_exact(self):
        """Test parsing exact vulnerability type matches."""
        agent = AnalyzerAgent()
        
        assert agent._parse_vulnerability_type("s3_public_access") == VulnerabilityType.S3_PUBLIC_ACCESS
        assert agent._parse_vulnerability_type("security_group_open_ssh") == VulnerabilityType.SECURITY_GROUP_OPEN_SSH
        assert agent._parse_vulnerability_type("rds_publicly_accessible") == VulnerabilityType.RDS_PUBLICLY_ACCESSIBLE

    def test_parse_vulnerability_type_fuzzy(self):
        """Test fuzzy matching for vulnerability types."""
        agent = AnalyzerAgent()
        
        # These should map to known types
        assert agent._parse_vulnerability_type("s3 public access") == VulnerabilityType.S3_PUBLIC_ACCESS
        assert agent._parse_vulnerability_type("open ssh") == VulnerabilityType.SECURITY_GROUP_OPEN_SSH
        assert agent._parse_vulnerability_type("bucket public") == VulnerabilityType.S3_PUBLIC_ACCESS

    def test_parse_vulnerability_type_unknown(self):
        """Test parsing unknown vulnerability types."""
        agent = AnalyzerAgent()
        
        result = agent._parse_vulnerability_type("something_completely_different")
        assert result == VulnerabilityType.UNKNOWN

    def test_parse_severity(self):
        """Test parsing severity strings."""
        agent = AnalyzerAgent()
        
        assert agent._parse_severity("critical") == Severity.CRITICAL
        assert agent._parse_severity("HIGH") == Severity.HIGH
        assert agent._parse_severity("Medium") == Severity.MEDIUM
        assert agent._parse_severity("low") == Severity.LOW
        
        # Unknown should default to Medium
        assert agent._parse_severity("unknown") == Severity.MEDIUM

    @pytest.mark.asyncio
    async def test_analyze_tokenizes_finding(self, sample_finding):
        """Test that analyze properly tokenizes the finding."""
        agent = AnalyzerAgent()
        
        # Mock the LLM call
        mock_response = {
            "vulnerability_type": "s3_public_access",
            "resource_type": "AWS::S3::Bucket",
            "severity": "Critical",
            "search_query": "S3 bucket public access Block Public Access",
            "confidence": 0.95,
            "reasoning": "S3 bucket with public access disabled",
        }
        
        with patch.object(agent, '_llm_analyze', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            result = await agent.analyze(sample_finding)
            
            # Check tokenization happened
            assert "{{BUCKET_NAME}}" in result.sanitized_title
            assert "{{ACCOUNT_ID}}" in result.sanitized_description
            
            # Check analysis
            assert result.vulnerability_type == VulnerabilityType.S3_PUBLIC_ACCESS
            assert result.severity == Severity.CRITICAL
            assert result.analysis_confidence == 0.95

    @pytest.mark.asyncio
    async def test_analyze_stores_tokens(self, sample_finding):
        """Test that analyze stores token mapping."""
        agent = AnalyzerAgent()
        
        mock_response = {
            "vulnerability_type": "s3_public_access",
            "resource_type": "AWS::S3::Bucket",
            "severity": "Critical",
            "search_query": "test query",
            "confidence": 0.9,
            "reasoning": "test",
        }
        
        with patch.object(agent, '_llm_analyze', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            result = await agent.analyze(sample_finding)
            
            # Check tokens were stored
            mapping = agent.get_token_mapping("SEC-1234")
            assert mapping is not None
            assert "BUCKET_NAME" in mapping.tokens
            assert mapping.tokens["BUCKET_NAME"] == "prod-logs-bucket"

    @pytest.mark.asyncio
    async def test_analyze_handles_llm_error(self, sample_finding):
        """Test that analyze handles LLM errors gracefully."""
        agent = AnalyzerAgent()
        
        with patch.object(agent, '_llm_analyze', new_callable=AsyncMock) as mock_llm:
            # Simulate LLM returning error response
            mock_llm.return_value = {
                "vulnerability_type": "unknown",
                "resource_type": "Unknown",
                "severity": "Medium",
                "search_query": sample_finding.title,
                "confidence": 0.5,
                "reasoning": "Analysis failed",
            }
            
            result = await agent.analyze(sample_finding)
            
            # Should still return a valid result
            assert result.finding_id == "SEC-1234"
            assert result.vulnerability_type == VulnerabilityType.UNKNOWN
            assert result.analysis_confidence == 0.5


class TestAnalysisOutput:
    """Tests for the AnalysisOutput model."""

    def test_valid_output(self):
        """Test creating valid analysis output."""
        output = AnalysisOutput(
            vulnerability_type="s3_public_access",
            resource_type="AWS::S3::Bucket",
            severity="Critical",
            search_query="S3 public access remediation",
            confidence=0.95,
            reasoning="Clear S3 public access violation",
        )
        
        assert output.vulnerability_type == "s3_public_access"
        assert output.confidence == 0.95

    def test_confidence_bounds(self):
        """Test that confidence must be between 0 and 1."""
        with pytest.raises(ValueError):
            AnalysisOutput(
                vulnerability_type="test",
                resource_type="test",
                severity="Medium",
                search_query="test",
                confidence=1.5,  # Invalid
                reasoning="test",
            )


class TestSystemPrompt:
    """Tests for the analyzer system prompt."""

    def test_prompt_contains_vulnerability_types(self):
        """Test that prompt contains all vulnerability types."""
        prompt = ANALYZER_SYSTEM_PROMPT
        
        assert "s3_public_access" in prompt
        assert "security_group_open_ssh" in prompt
        assert "rds_publicly_accessible" in prompt
        assert "ebs_unencrypted" in prompt

    def test_prompt_mentions_tokenization(self):
        """Test that prompt explains tokenization."""
        prompt = ANALYZER_SYSTEM_PROMPT
        
        assert "TOKENIZED" in prompt or "tokenized" in prompt.lower()
        assert "{{BUCKET_NAME}}" in prompt or "{{" in prompt
