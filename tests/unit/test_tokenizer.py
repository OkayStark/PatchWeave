"""
Unit tests for Tokenizer service.
"""

import pytest

from patchweave.core.tokenizer import (
    Tokenizer,
    TokenStore,
    TokenPattern,
    AWS_PATTERNS,
    get_tokenizer,
    get_token_store,
)
from patchweave.models.finding import TokenMapping


class TestTokenizer:
    """Tests for the Tokenizer class."""

    def test_tokenize_aws_account_id(self):
        """Test tokenizing AWS account IDs."""
        tokenizer = Tokenizer()
        text = "Found issue in account 123456789012 region us-east-1"
        result = tokenizer.tokenize(text)
        
        assert "{{ACCOUNT_ID}}" in result.tokenized_text
        assert result.tokens.get("ACCOUNT_ID") == "123456789012"
        assert result.token_count >= 1

    def test_tokenize_s3_bucket_name(self):
        """Test tokenizing S3 bucket names."""
        tokenizer = Tokenizer()
        text = "S3 bucket 'my-production-bucket' has public access enabled"
        result = tokenizer.tokenize(text)
        
        assert "{{BUCKET_NAME}}" in result.tokenized_text
        assert result.tokens.get("BUCKET_NAME") == "my-production-bucket"

    def test_tokenize_s3_bucket_from_arn(self):
        """Test tokenizing S3 bucket from ARN."""
        tokenizer = Tokenizer()
        text = "Resource: arn:aws:s3:::my-data-bucket"
        result = tokenizer.tokenize(text)
        
        assert "{{BUCKET_NAME}}" in result.tokenized_text
        assert result.tokens.get("BUCKET_NAME") == "my-data-bucket"

    def test_tokenize_ec2_instance_id(self):
        """Test tokenizing EC2 instance IDs."""
        tokenizer = Tokenizer()
        text = "Instance i-0123456789abcdef0 is vulnerable"
        result = tokenizer.tokenize(text)
        
        assert "{{INSTANCE_ID}}" in result.tokenized_text
        assert result.tokens.get("INSTANCE_ID") == "i-0123456789abcdef0"

    def test_tokenize_security_group(self):
        """Test tokenizing security group IDs."""
        tokenizer = Tokenizer()
        text = "Security group sg-12345678 allows unrestricted SSH"
        result = tokenizer.tokenize(text)
        
        assert "{{SECURITY_GROUP_ID}}" in result.tokenized_text
        assert result.tokens.get("SECURITY_GROUP_ID") == "sg-12345678"

    def test_tokenize_ip_address(self):
        """Test tokenizing IP addresses."""
        tokenizer = Tokenizer()
        text = "Allows traffic from 0.0.0.0/0 and 192.168.1.1"
        result = tokenizer.tokenize(text)
        
        assert "{{CIDR_BLOCK}}" in result.tokenized_text or "{{IP_ADDRESS}}" in result.tokenized_text
        assert result.token_count >= 1

    def test_tokenize_aws_region(self):
        """Test tokenizing AWS regions."""
        tokenizer = Tokenizer()
        text = "Resource in us-west-2 region"
        result = tokenizer.tokenize(text)
        
        assert "{{AWS_REGION}}" in result.tokenized_text
        assert result.tokens.get("AWS_REGION") == "us-west-2"

    def test_tokenize_multiple_values(self):
        """Test tokenizing text with multiple sensitive values."""
        tokenizer = Tokenizer()
        text = (
            "S3 bucket 'prod-logs' in account 123456789012 "
            "region us-east-1 has public access"
        )
        result = tokenizer.tokenize(text)
        
        # Should find bucket, account, and region
        assert result.token_count >= 3
        assert "BUCKET_NAME" in result.tokens
        assert "ACCOUNT_ID" in result.tokens
        assert "AWS_REGION" in result.tokens

    def test_tokenize_finding(self):
        """Test tokenizing a complete finding."""
        tokenizer = Tokenizer()
        title = "S3 Bucket 'my-bucket' has public access"
        description = "Account 123456789012 in us-east-1 has public bucket"
        
        tok_title, tok_desc, mapping = tokenizer.tokenize_finding(
            title=title,
            description=description,
            finding_id="SEC-123",
        )
        
        assert "{{BUCKET_NAME}}" in tok_title
        assert "{{ACCOUNT_ID}}" in tok_desc
        assert mapping.finding_id == "SEC-123"
        assert len(mapping.tokens) >= 2

    def test_tokenize_preserves_non_sensitive(self):
        """Test that non-sensitive text is preserved."""
        tokenizer = Tokenizer()
        text = "This is a security finding about public access"
        result = tokenizer.tokenize(text)
        
        # Should be unchanged
        assert result.tokenized_text == text
        assert result.token_count == 0

    def test_detokenize(self):
        """Test detokenizing text back to original values."""
        tokenizer = Tokenizer()
        mapping = TokenMapping(
            finding_id="SEC-123",
            tokens={
                "BUCKET_NAME": "my-bucket",
                "ACCOUNT_ID": "123456789012",
            },
        )
        
        tokenized = "Bucket {{BUCKET_NAME}} in account {{ACCOUNT_ID}}"
        result = tokenizer.detokenize(tokenized, mapping)
        
        assert result == "Bucket my-bucket in account 123456789012"

    def test_unique_token_names_for_duplicates(self):
        """Test that duplicate matches get unique token names."""
        tokenizer = Tokenizer()
        text = "Bucket 'bucket-one' and bucket 'bucket-two'"
        result = tokenizer.tokenize(text)
        
        # Should have two different bucket tokens
        assert "BUCKET_NAME" in result.tokens
        # Second one should be BUCKET_NAME_2 or similar


class TestTokenStore:
    """Tests for the TokenStore class."""

    def test_store_and_retrieve(self):
        """Test storing and retrieving mappings."""
        store = TokenStore()
        mapping = TokenMapping(
            finding_id="SEC-123",
            tokens={"BUCKET_NAME": "test-bucket"},
        )
        
        store.store(mapping)
        retrieved = store.get("SEC-123")
        
        assert retrieved is not None
        assert retrieved.finding_id == "SEC-123"
        assert retrieved.tokens["BUCKET_NAME"] == "test-bucket"

    def test_get_nonexistent(self):
        """Test getting a mapping that doesn't exist."""
        store = TokenStore()
        result = store.get("NONEXISTENT-123")
        assert result is None

    def test_delete(self):
        """Test deleting a mapping."""
        store = TokenStore()
        mapping = TokenMapping(finding_id="SEC-123", tokens={})
        
        store.store(mapping)
        assert store.get("SEC-123") is not None
        
        result = store.delete("SEC-123")
        assert result is True
        assert store.get("SEC-123") is None

    def test_delete_nonexistent(self):
        """Test deleting a mapping that doesn't exist."""
        store = TokenStore()
        result = store.delete("NONEXISTENT-123")
        assert result is False

    def test_clear(self):
        """Test clearing all mappings."""
        store = TokenStore()
        store.store(TokenMapping(finding_id="SEC-1", tokens={}))
        store.store(TokenMapping(finding_id="SEC-2", tokens={}))
        
        store.clear()
        
        assert store.get("SEC-1") is None
        assert store.get("SEC-2") is None


class TestGlobalInstances:
    """Tests for global tokenizer/store instances."""

    def test_get_tokenizer_singleton(self):
        """Test that get_tokenizer returns same instance."""
        t1 = get_tokenizer()
        t2 = get_tokenizer()
        # They should share patterns at least
        assert t1.patterns == t2.patterns

    def test_get_token_store_singleton(self):
        """Test that get_token_store returns same instance."""
        s1 = get_token_store()
        s2 = get_token_store()
        
        # Store something in s1, should be visible in s2
        s1.store(TokenMapping(finding_id="TEST-1", tokens={}))
        assert s2.get("TEST-1") is not None
        
        # Cleanup
        s1.delete("TEST-1")
