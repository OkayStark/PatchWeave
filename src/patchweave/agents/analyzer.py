"""
Analyzer Agent for PatchWeave.

Uses an LLM to analyze security findings and:
1. Classify the vulnerability type
2. Extract resource information
3. Generate semantic search queries
4. Determine severity
"""

from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from patchweave.config import settings
from patchweave.core.tokenizer import get_tokenizer, get_token_store
from patchweave.logging import get_logger
from patchweave.models.enums import (
    CloudProvider,
    Severity,
    VulnerabilityType,
)
from patchweave.models.finding import AnalyzedFinding, RawFinding, TokenMapping

log = get_logger(__name__)


class AnalysisOutput(BaseModel):
    """Structured output from the LLM analysis."""
    
    vulnerability_type: str = Field(
        description="The type of vulnerability from the fixed taxonomy"
    )
    resource_type: str = Field(
        description="AWS resource type (e.g., AWS::S3::Bucket)"
    )
    severity: str = Field(
        description="Severity level: Critical, High, Medium, Low"
    )
    search_query: str = Field(
        description="Semantic search query for finding remediation playbooks"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score for this analysis (0.0 to 1.0)"
    )
    reasoning: str = Field(
        description="Brief explanation of the classification"
    )


# System prompt for the analyzer agent
ANALYZER_SYSTEM_PROMPT = """You are a cloud security analyst specializing in AWS vulnerabilities.
Your job is to analyze security findings and classify them for automated remediation.

You will receive a TOKENIZED finding where sensitive values have been replaced with placeholders like {{BUCKET_NAME}}, {{ACCOUNT_ID}}, etc.
Do NOT try to guess or fill in the actual values - work with the tokens as-is.

Classify the vulnerability into ONE of these types:
- s3_public_access: S3 bucket has public access enabled or Block Public Access disabled
- s3_encryption_disabled: S3 bucket lacks server-side encryption
- s3_versioning_disabled: S3 bucket has versioning disabled
- security_group_open_ssh: Security group allows unrestricted SSH (port 22) access
- security_group_open_rdp: Security group allows unrestricted RDP (port 3389) access  
- security_group_unrestricted_egress: Security group has unrestricted outbound rules
- ebs_unencrypted: EBS volume is not encrypted
- rds_publicly_accessible: RDS instance is publicly accessible
- rds_unencrypted: RDS instance storage is not encrypted
- rds_no_backup: RDS instance has no automated backups configured
- iam_overly_permissive: IAM policy or role has overly permissive permissions
- cloudtrail_disabled: CloudTrail is not enabled or configured properly
- kms_key_rotation_disabled: KMS key does not have automatic rotation enabled
- lambda_public: Lambda function has public access
- sns_public: SNS topic allows public access
- unknown: Cannot determine the vulnerability type

For resource_type, use AWS CloudFormation format (e.g., AWS::S3::Bucket, AWS::EC2::SecurityGroup).

For the search_query, create a concise query (5-15 words) that would match a remediation playbook.
Focus on the vulnerability type and remediation action, NOT the specific resource.

Output your analysis as JSON with these fields:
- vulnerability_type: string (from the list above)
- resource_type: string (AWS::Service::Resource format)
- severity: string (Critical, High, Medium, or Low)
- search_query: string (for semantic search)
- confidence: float (0.0 to 1.0, how confident you are in this classification)
- reasoning: string (brief explanation)
"""


class AnalyzerAgent:
    """
    Agent that analyzes security findings using an LLM.
    
    Takes raw findings, tokenizes them, then uses GPT-4 to:
    - Classify the vulnerability type
    - Determine severity
    - Generate search queries for playbook matching
    """

    def __init__(
        self,
        model: str | None = None,
        temperature: float | None = None,
    ):
        """
        Initialize the analyzer agent.
        
        Args:
            model: LLM model to use (defaults to settings.llm_model)
            temperature: Temperature for generation (defaults to settings.llm_temperature)
        """
        self.model = model or settings.llm_model
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        
        self._llm = None  # Will be created lazily based on provider
        self._parser = JsonOutputParser(pydantic_object=AnalysisOutput)
        self._tokenizer = get_tokenizer()
        self._token_store = get_token_store()
        
        log.info(
            "analyzer_agent_initialized",
            model=self.model,
            temperature=self.temperature,
            provider=settings.llm_provider,
        )

    # Class-level key rotation state
    _current_key_index = 0
    _key_rotation_lock = None
    
    @classmethod
    def _get_next_gemini_key(cls) -> str:
        """Get the next Gemini API key using round-robin rotation."""
        keys = [k for k in [settings.google_api_key, settings.google_api_key_2,settings.google_api_key_3] if k]
        if not keys:
            raise ValueError(
                "GOOGLE_API_KEY not configured. "
                "Set it in .env or environment variables."
            )
        
        # Simple round-robin rotation
        key = keys[cls._current_key_index % len(keys)]
        cls._current_key_index += 1
        
        log.debug(
            "gemini_key_rotation",
            key_index=(cls._current_key_index - 1) % len(keys) + 1,
            total_keys=len(keys),
        )
        return key
    
    def _create_llm(self):
        """Create the appropriate LLM based on configuration."""
        provider = settings.llm_provider.lower()
        
        if provider == "gemini":
            api_key = self._get_next_gemini_key()
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=self.model,
                temperature=self.temperature,
                google_api_key=api_key,
            )
        elif provider == "openai":
            if not settings.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY not configured. "
                    "Set it in .env or environment variables."
                )
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                api_key=settings.openai_api_key,
            )
        else:
            raise ValueError(f"Unknown LLM provider: {provider}. Use 'gemini' or 'openai'.")

    @property
    def llm(self):
        """Get or create the LLM instance."""
        if self._llm is None:
            self._llm = self._create_llm()
        return self._llm

    def _rotate_llm(self):
        """Force creation of new LLM with rotated API key."""
        self._llm = self._create_llm()
        return self._llm

    async def _invoke_with_retry(self, messages, finding_id: str, max_retries: int = 3):
        """
        Invoke LLM with automatic retry and key rotation on rate limit errors.
        
        Args:
            messages: Messages to send to the LLM
            finding_id: Finding ID for logging
            max_retries: Maximum number of retries
            
        Returns:
            LLM response
        """
        import asyncio
        
        last_error = None
        for attempt in range(max_retries):
            try:
                return await self.llm.ainvoke(messages)
            except Exception as e:
                error_str = str(e).lower()
                # Check for rate limit errors (various providers use different messages)
                if any(keyword in error_str for keyword in ['rate limit', 'quota', '429', 'resource exhausted', 'too many requests']):
                    log.warning(
                        "rate_limit_hit_rotating_key",
                        finding_id=finding_id,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        error=str(e),
                    )
                    # Rotate to next key and retry
                    self._rotate_llm()
                    # Small delay before retry
                    await asyncio.sleep(1)
                    last_error = e
                else:
                    # Non-rate-limit error, re-raise immediately
                    raise
        
        # All retries exhausted
        raise last_error or Exception("All API key retries exhausted")

    def _parse_vulnerability_type(self, type_str: str) -> VulnerabilityType:
        """Parse vulnerability type string to enum."""
        type_str = type_str.lower().strip()
        
        # Try direct match
        for vtype in VulnerabilityType:
            if vtype.value == type_str:
                return vtype
        
        # Fuzzy matching for common variations
        mappings = {
            "s3 public access": VulnerabilityType.S3_PUBLIC_ACCESS,
            "s3_public": VulnerabilityType.S3_PUBLIC_ACCESS,
            "public s3": VulnerabilityType.S3_PUBLIC_ACCESS,
            "bucket public": VulnerabilityType.S3_PUBLIC_ACCESS,
            "s3 encryption": VulnerabilityType.S3_ENCRYPTION_DISABLED,
            "bucket encryption": VulnerabilityType.S3_ENCRYPTION_DISABLED,
            "security group ssh": VulnerabilityType.SECURITY_GROUP_OPEN_SSH,
            "open ssh": VulnerabilityType.SECURITY_GROUP_OPEN_SSH,
            "security group rdp": VulnerabilityType.SECURITY_GROUP_OPEN_RDP,
            "open rdp": VulnerabilityType.SECURITY_GROUP_OPEN_RDP,
            "ebs encryption": VulnerabilityType.EBS_UNENCRYPTED,
            "rds public": VulnerabilityType.RDS_PUBLICLY_ACCESSIBLE,
        }
        
        for key, value in mappings.items():
            if key in type_str:
                return value
        
        return VulnerabilityType.UNKNOWN

    def _parse_severity(self, severity_str: str) -> Severity:
        """Parse severity string to enum."""
        severity_str = severity_str.lower().strip()
        
        for severity in Severity:
            if severity.value.lower() == severity_str:
                return severity
        
        # Default to medium if unknown
        return Severity.MEDIUM

    async def analyze(self, finding: RawFinding) -> AnalyzedFinding:
        """
        Analyze a raw finding and produce a structured analysis.
        
        Args:
            finding: Raw finding from Jira
            
        Returns:
            AnalyzedFinding with classification and search query
        """
        log.info(
            "analyzing_finding",
            finding_id=finding.jira_ticket_id,
        )

        # Step 1: Tokenize the finding
        tokenized_title, tokenized_description, token_mapping = (
            self._tokenizer.tokenize_finding(
                title=finding.title,
                description=finding.description,
                finding_id=finding.jira_ticket_id,
            )
        )
        
        # Store token mapping separately
        self._token_store.store(token_mapping)

        # Step 2: Send to LLM for analysis
        analysis = await self._llm_analyze(
            title=tokenized_title,
            description=tokenized_description,
            finding_id=finding.jira_ticket_id,
        )

        # Step 3: Build the AnalyzedFinding
        analyzed = AnalyzedFinding(
            finding_id=finding.jira_ticket_id,
            vulnerability_type=self._parse_vulnerability_type(
                analysis.get("vulnerability_type", "unknown")
            ),
            cloud_provider=CloudProvider.AWS,  # Default to AWS for now
            resource_type=analysis.get("resource_type", "Unknown"),
            severity=self._parse_severity(
                analysis.get("severity", finding.severity or "Medium")
            ),
            search_query=analysis.get("search_query", tokenized_title),
            sanitized_title=tokenized_title,
            sanitized_description=tokenized_description,
            token_keys=list(token_mapping.tokens.keys()),
            source_ticket_url=finding.jira_ticket_url,
            detected_at=finding.created_at,
            analyzed_at=datetime.now(timezone.utc),
            analysis_confidence=analysis.get("confidence", 0.8),
        )

        log.info(
            "finding_analyzed",
            finding_id=finding.jira_ticket_id,
            vulnerability_type=analyzed.vulnerability_type.value,
            severity=analyzed.severity.value,
            confidence=analyzed.analysis_confidence,
        )

        return analyzed

    async def _llm_analyze(
        self,
        title: str,
        description: str,
        finding_id: str,
    ) -> dict[str, Any]:
        """
        Use LLM to analyze the tokenized finding.
        
        Args:
            title: Tokenized title
            description: Tokenized description
            finding_id: Finding ID for logging
            
        Returns:
            Dictionary with analysis results
        """
        # Build the prompt
        user_message = f"""Analyze this security finding:

**Title:** {title}

**Description:**
{description}

Provide your analysis as JSON."""

        messages = [
            SystemMessage(content=ANALYZER_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]

        try:
            response = await self._invoke_with_retry(messages, finding_id)
            
            # Parse the JSON response
            content = response.content
            if isinstance(content, str):
                # Try to extract JSON from the response
                import json
                import re
                
                # Look for JSON in code blocks or raw
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
                if json_match:
                    content = json_match.group(1)
                
                result = json.loads(content)
            else:
                result = content

            log.debug(
                "llm_analysis_complete",
                finding_id=finding_id,
                result=result,
            )
            return result

        except Exception as e:
            log.error(
                "llm_analysis_failed",
                finding_id=finding_id,
                error=str(e),
            )
            # Return default analysis on failure
            return {
                "vulnerability_type": "unknown",
                "resource_type": "Unknown",
                "severity": "Medium",
                "search_query": title,
                "confidence": 0.5,
                "reasoning": f"Analysis failed: {e}",
            }

    def analyze_sync(self, finding: RawFinding) -> AnalyzedFinding:
        """
        Synchronous wrapper for analyze().
        
        Args:
            finding: Raw finding from Jira
            
        Returns:
            AnalyzedFinding with classification
        """
        import asyncio
        return asyncio.run(self.analyze(finding))

    def get_token_mapping(self, finding_id: str) -> TokenMapping | None:
        """
        Retrieve the token mapping for a finding.
        
        Args:
            finding_id: Finding ID
            
        Returns:
            TokenMapping or None if not found
        """
        return self._token_store.get(finding_id)


# Singleton instance
_analyzer_agent: AnalyzerAgent | None = None


def get_analyzer_agent() -> AnalyzerAgent:
    """Get or create the global analyzer agent instance."""
    global _analyzer_agent
    if _analyzer_agent is None:
        _analyzer_agent = AnalyzerAgent()
    return _analyzer_agent
