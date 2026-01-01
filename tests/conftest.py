"""
Pytest configuration and fixtures for PatchWeave tests.
"""

import os
import pytest
from datetime import datetime
from typing import Generator

# Set testing environment before importing application modules
os.environ["PATCHWEAVE_ENV"] = "testing"
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["USE_LOCALSTACK"] = "true"


@pytest.fixture(scope="session")
def test_settings():
    """Provide test settings."""
    from patchweave.config import Settings
    return Settings(
        patchweave_env="testing",
        log_level="DEBUG",
        use_localstack=True,
        jira_base_url="https://test.atlassian.net",
        jira_email="test@test.com",
        jira_api_token="test-token",
        jira_project_key="TEST",
        aws_test_access_key_id="test",
        aws_test_secret_access_key="test",
        chroma_host="localhost",
        chroma_port=8000,
    )


@pytest.fixture
def sample_raw_finding():
    """Provide a sample RawFinding for testing."""
    from patchweave.models import RawFinding
    return RawFinding(
        jira_ticket_id="SEC-1234",
        jira_ticket_url="https://test.atlassian.net/browse/SEC-1234",
        title="S3 Bucket 'prod-logs-bucket' has public access enabled",
        description="""
        The S3 bucket prod-logs-bucket in account 123456789012 (us-east-1)
        has Block Public Access disabled, allowing potential public exposure.
        
        Resource: arn:aws:s3:::prod-logs-bucket
        Account: 123456789012
        Region: us-east-1
        """,
        severity="Critical",
        created_at=datetime(2026, 1, 16, 10, 0, 0),
        custom_fields={"cspm_source": "Wiz"},
    )


@pytest.fixture
def sample_analyzed_finding():
    """Provide a sample AnalyzedFinding for testing."""
    from patchweave.models import (
        AnalyzedFinding,
        VulnerabilityType,
        Severity,
        CloudProvider,
        JiraStatus,
    )
    return AnalyzedFinding(
        finding_id="SEC-1234",
        vulnerability_type=VulnerabilityType.S3_PUBLIC_ACCESS,
        cloud_provider=CloudProvider.AWS,
        resource_type="AWS::S3::Bucket",
        severity=Severity.CRITICAL,
        search_query="S3 bucket public access Block Public Access disabled",
        sanitized_title="S3 Bucket '{{BUCKET_NAME}}' has public access enabled",
        sanitized_description="The S3 bucket {{BUCKET_NAME}} in account {{ACCOUNT_ID}}...",
        token_keys=["BUCKET_NAME", "ACCOUNT_ID", "AWS_REGION"],
        source_ticket_url="https://test.atlassian.net/browse/SEC-1234",
        detected_at=datetime(2026, 1, 16, 10, 0, 0),
        analysis_confidence=0.98,
        status=JiraStatus.ANALYZING,
    )


@pytest.fixture
def sample_token_mapping():
    """Provide a sample TokenMapping for testing."""
    from patchweave.models import TokenMapping
    return TokenMapping(
        finding_id="SEC-1234",
        tokens={
            "ACCOUNT_ID": "123456789012",
            "AWS_REGION": "us-east-1",
            "BUCKET_NAME": "prod-logs-bucket",
            "RESOURCE_ARN": "arn:aws:s3:::prod-logs-bucket",
        },
    )


@pytest.fixture
def sample_playbook():
    """Provide a sample Playbook for testing."""
    from patchweave.models import Playbook, VulnerabilityType, Severity, CloudProvider
    return Playbook(
        id="550e8400-e29b-41d4-a716-446655440001",
        name="S3 Block Public Access",
        description="Enables S3 Block Public Access settings on a bucket",
        vulnerability_type=VulnerabilityType.S3_PUBLIC_ACCESS,
        cloud_provider=CloudProvider.AWS,
        resource_type="AWS::S3::Bucket",
        severity=Severity.CRITICAL,
        search_text="S3 bucket public access Block Public Access disabled publicly accessible",
        remediation_code="""
import boto3
s3 = boto3.client('s3', region_name='{{AWS_REGION}}')
s3.put_public_access_block(
    Bucket='{{BUCKET_NAME}}',
    PublicAccessBlockConfiguration={
        'BlockPublicAcls': True,
        'IgnorePublicAcls': True,
        'BlockPublicPolicy': True,
        'RestrictPublicBuckets': True
    }
)
""",
        pre_check_code="# Pre-check code",
        post_check_code="# Post-check code",
        required_permissions=["s3:GetPublicAccessBlock", "s3:PutPublicAccessBlock"],
    )


@pytest.fixture
def sample_playbook_match(sample_playbook):
    """Provide a sample PlaybookMatch for testing."""
    from patchweave.models import PlaybookMatch, MatchTier
    return PlaybookMatch(
        playbook=sample_playbook,
        similarity_score=0.94,
        match_tier=MatchTier.HIGH_CONFIDENCE,
        search_query="S3 bucket public access",
    )
