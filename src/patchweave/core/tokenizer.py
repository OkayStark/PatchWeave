"""
Tokenizer service for PatchWeave.

Handles extraction and replacement of sensitive data with tokens.
This is critical for:
1. Preventing sensitive data from reaching LLMs
2. Enabling playbook reuse across different resources
3. Safe storage and logging
"""

import re
from dataclasses import dataclass, field

from patchweave.logging import get_logger
from patchweave.models.finding import TokenMapping

log = get_logger(__name__)


@dataclass
class TokenPattern:
    """Definition of a pattern to tokenize."""
    
    name: str
    pattern: re.Pattern[str]
    token_name: str
    description: str = ""
    
    def __post_init__(self):
        if isinstance(self.pattern, str):
            self.pattern = re.compile(self.pattern)


# Common patterns for AWS resource identification
AWS_PATTERNS: list[TokenPattern] = [
    # AWS Account IDs (12 digits)
    TokenPattern(
        name="aws_account_id",
        pattern=re.compile(r'\b(\d{12})\b'),
        token_name="ACCOUNT_ID",
        description="AWS Account ID",
    ),
    # S3 Bucket names (between quotes or standalone)
    TokenPattern(
        name="s3_bucket_quoted",
        pattern=re.compile(r"['\"]([a-z0-9][a-z0-9.\-]{1,61}[a-z0-9])['\"]"),
        token_name="BUCKET_NAME",
        description="S3 Bucket Name (quoted)",
    ),
    TokenPattern(
        name="s3_bucket_arn",
        pattern=re.compile(r'arn:aws:s3:::([a-z0-9][a-z0-9.\-]{1,61}[a-z0-9])'),
        token_name="BUCKET_NAME",
        description="S3 Bucket Name (from ARN)",
    ),
    # S3 Bucket names after "Bucket" or "Resource:" labels
    TokenPattern(
        name="s3_bucket_labeled",
        pattern=re.compile(r'(?:S3 [Bb]ucket|Resource:)\s*([a-z0-9][a-z0-9.\-]{1,61}[a-z0-9])'),
        token_name="BUCKET_NAME",
        description="S3 Bucket Name (labeled)",
    ),
    # EC2 Instance IDs
    TokenPattern(
        name="ec2_instance_id",
        pattern=re.compile(r'\b(i-[0-9a-f]{8,17})\b'),
        token_name="INSTANCE_ID",
        description="EC2 Instance ID",
    ),
    # Security Group IDs
    TokenPattern(
        name="security_group_id",
        pattern=re.compile(r'\b(sg-[0-9a-f]{8,17})\b'),
        token_name="SECURITY_GROUP_ID",
        description="Security Group ID",
    ),
    # VPC IDs
    TokenPattern(
        name="vpc_id",
        pattern=re.compile(r'\b(vpc-[0-9a-f]{8,17})\b'),
        token_name="VPC_ID",
        description="VPC ID",
    ),
    # Subnet IDs
    TokenPattern(
        name="subnet_id",
        pattern=re.compile(r'\b(subnet-[0-9a-f]{8,17})\b'),
        token_name="SUBNET_ID",
        description="Subnet ID",
    ),
    # RDS Instance identifiers
    TokenPattern(
        name="rds_instance",
        pattern=re.compile(r'DB instance[:\s]+["\']?([a-zA-Z][a-zA-Z0-9\-]{0,62})["\']?', re.IGNORECASE),
        token_name="RDS_INSTANCE_ID",
        description="RDS Instance Identifier",
    ),
    # EBS Volume IDs
    TokenPattern(
        name="ebs_volume_id",
        pattern=re.compile(r'\b(vol-[0-9a-f]{8,17})\b'),
        token_name="VOLUME_ID",
        description="EBS Volume ID",
    ),
    # AWS Regions
    TokenPattern(
        name="aws_region",
        pattern=re.compile(r'\b(us-east-1|us-east-2|us-west-1|us-west-2|eu-west-1|eu-west-2|eu-west-3|eu-central-1|eu-north-1|ap-southeast-1|ap-southeast-2|ap-northeast-1|ap-northeast-2|ap-northeast-3|ap-south-1|sa-east-1|ca-central-1|me-south-1|af-south-1)\b'),
        token_name="AWS_REGION",
        description="AWS Region",
    ),
    # IP Addresses (IPv4)
    TokenPattern(
        name="ipv4_address",
        pattern=re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'),
        token_name="IP_ADDRESS",
        description="IPv4 Address",
    ),
    # CIDR blocks
    TokenPattern(
        name="cidr_block",
        pattern=re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2})\b'),
        token_name="CIDR_BLOCK",
        description="CIDR Block",
    ),
    # ARNs (generic)
    TokenPattern(
        name="aws_arn",
        pattern=re.compile(r'(arn:aws:[a-z0-9\-]+:[a-z0-9\-]*:\d{12}:[a-zA-Z0-9\-_/:.]+)'),
        token_name="RESOURCE_ARN",
        description="AWS ARN",
    ),
    # IAM Role names
    TokenPattern(
        name="iam_role",
        pattern=re.compile(r'role[/:\s]+([a-zA-Z_][a-zA-Z0-9_+=,.@\-]{0,63})', re.IGNORECASE),
        token_name="IAM_ROLE",
        description="IAM Role Name",
    ),
    # KMS Key IDs
    TokenPattern(
        name="kms_key_id",
        pattern=re.compile(r'\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b'),
        token_name="KMS_KEY_ID",
        description="KMS Key ID (UUID format)",
    ),
]


@dataclass
class TokenizerResult:
    """Result of tokenization operation."""
    
    tokenized_text: str
    tokens: dict[str, str] = field(default_factory=dict)
    token_count: int = 0
    patterns_matched: list[str] = field(default_factory=list)


class Tokenizer:
    """
    Service for tokenizing sensitive data in text.
    
    Replaces sensitive values (AWS account IDs, resource names, IPs, etc.)
    with placeholder tokens like {{BUCKET_NAME}}, {{ACCOUNT_ID}}.
    """

    def __init__(self, patterns: list[TokenPattern] | None = None):
        """
        Initialize tokenizer with patterns.
        
        Args:
            patterns: List of patterns to use (defaults to AWS_PATTERNS)
        """
        self.patterns = patterns or AWS_PATTERNS.copy()
        self._token_counters: dict[str, int] = {}
        
    def add_pattern(self, pattern: TokenPattern) -> None:
        """Add a custom pattern to the tokenizer."""
        self.patterns.append(pattern)
        
    def _get_unique_token(self, base_name: str) -> str:
        """
        Generate a unique token name for duplicate patterns.
        
        If we find multiple buckets, we get BUCKET_NAME, BUCKET_NAME_2, etc.
        """
        if base_name not in self._token_counters:
            self._token_counters[base_name] = 1
            return base_name
        else:
            self._token_counters[base_name] += 1
            return f"{base_name}_{self._token_counters[base_name]}"

    def tokenize(
        self,
        text: str,
        finding_id: str | None = None,
    ) -> TokenizerResult:
        """
        Tokenize sensitive data in text.
        
        Args:
            text: Input text containing sensitive data
            finding_id: Optional finding ID for logging
            
        Returns:
            TokenizerResult with tokenized text and token mappings
        """
        self._token_counters.clear()
        result = TokenizerResult(tokenized_text=text)
        
        # Track what we've already replaced to avoid double-processing
        replaced_values: set[str] = set()
        
        for pattern in self.patterns:
            matches = pattern.pattern.findall(text)
            
            for match in matches:
                # Handle tuple results from groups
                value = match if isinstance(match, str) else match[0] if match else None
                if not value or value in replaced_values:
                    continue
                    
                # Skip if it looks like a token already
                if value.startswith("{{") or value.endswith("}}"):
                    continue
                    
                # Generate unique token name
                token_name = self._get_unique_token(pattern.token_name)
                token_placeholder = f"{{{{{token_name}}}}}"
                
                # Replace in text
                result.tokenized_text = result.tokenized_text.replace(
                    value, token_placeholder
                )
                
                # Store mapping
                result.tokens[token_name] = value
                result.token_count += 1
                replaced_values.add(value)
                
                if pattern.name not in result.patterns_matched:
                    result.patterns_matched.append(pattern.name)

        log.debug(
            "tokenization_complete",
            finding_id=finding_id,
            token_count=result.token_count,
            patterns_matched=result.patterns_matched,
        )
        
        return result

    def tokenize_finding(
        self,
        title: str,
        description: str,
        finding_id: str,
    ) -> tuple[str, str, TokenMapping]:
        """
        Tokenize both title and description of a finding.
        
        Args:
            title: Finding title
            description: Finding description
            finding_id: Finding identifier
            
        Returns:
            Tuple of (tokenized_title, tokenized_description, TokenMapping)
        """
        # Combine text for consistent tokenization
        combined = f"{title}\n---SEPARATOR---\n{description}"
        result = self.tokenize(combined, finding_id)
        
        # Split back
        parts = result.tokenized_text.split("\n---SEPARATOR---\n")
        tokenized_title = parts[0] if parts else title
        tokenized_description = parts[1] if len(parts) > 1 else description
        
        # Create token mapping
        mapping = TokenMapping(
            finding_id=finding_id,
            tokens=result.tokens,
        )
        
        log.info(
            "finding_tokenized",
            finding_id=finding_id,
            token_count=len(mapping.tokens),
            token_keys=list(mapping.tokens.keys()),
        )
        
        return tokenized_title, tokenized_description, mapping

    def detokenize(self, text: str, mapping: TokenMapping) -> str:
        """
        Replace tokens with actual values.
        
        Args:
            text: Text containing {{TOKEN}} placeholders
            mapping: TokenMapping with actual values
            
        Returns:
            Text with tokens replaced by actual values
        """
        return mapping.substitute(text)


class TokenStore:
    """
    In-memory store for token mappings.
    
    Keeps token mappings separate from the main data flow
    to prevent accidental exposure of sensitive values.
    """

    def __init__(self):
        self._mappings: dict[str, TokenMapping] = {}

    def store(self, mapping: TokenMapping) -> None:
        """Store a token mapping."""
        self._mappings[mapping.finding_id] = mapping
        log.debug(
            "token_mapping_stored",
            finding_id=mapping.finding_id,
            token_count=len(mapping.tokens),
        )

    def get(self, finding_id: str) -> TokenMapping | None:
        """Retrieve a token mapping by finding ID."""
        return self._mappings.get(finding_id)

    def delete(self, finding_id: str) -> bool:
        """Delete a token mapping."""
        if finding_id in self._mappings:
            del self._mappings[finding_id]
            log.debug("token_mapping_deleted", finding_id=finding_id)
            return True
        return False

    def clear(self) -> None:
        """Clear all stored mappings."""
        self._mappings.clear()
        log.info("token_store_cleared")


# Global instances
_tokenizer: Tokenizer | None = None
_token_store: TokenStore | None = None


def get_tokenizer() -> Tokenizer:
    """Get or create the global tokenizer instance."""
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = Tokenizer()
    return _tokenizer


def get_token_store() -> TokenStore:
    """Get or create the global token store instance."""
    global _token_store
    if _token_store is None:
        _token_store = TokenStore()
    return _token_store
