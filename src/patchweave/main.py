"""
PatchWeave Main Application Entry Point.

Main application that orchestrates the full remediation pipeline:
1. Poll Jira for new security findings
2. Analyze and match to playbooks
3. Validate remediations in test environment
4. Request human approval via Jira
5. Deploy approved remediations
6. Record learnings for future improvement
"""

import asyncio
import shutil
import signal
import sys
import threading
from collections import deque
from datetime import datetime
from typing import Any, NoReturn

import requests
import uvicorn

from patchweave.config import settings
from patchweave.logging import setup_logging, get_logger

# Initialize logging first
setup_logging()
log = get_logger(__name__)


# =============================================================================
# RESOURCE LOCK MANAGER
# =============================================================================

class ResourceLockManager:
    """
    Manages resource locks to prevent concurrent processing of the same AWS resource.
    
    Uses FIFO queue for fair ordering when multiple tickets target the same resource.
    """
    
    def __init__(self):
        self._locks: dict[str, str] = {}  # resource_arn -> ticket_id
        self._wait_queues: dict[str, deque[str]] = {}  # resource_arn -> deque of ticket_ids
        self._lock = threading.Lock()
    
    def acquire(self, resource_arn: str, ticket_id: str) -> bool:
        """
        Try to acquire lock for a resource.
        
        Returns True if lock acquired, False if need to wait.
        """
        with self._lock:
            if resource_arn not in self._locks:
                # No one has the lock, acquire it
                self._locks[resource_arn] = ticket_id
                log.info(
                    "lock_acquired",
                    resource_arn=resource_arn,
                    ticket_id=ticket_id,
                )
                return True
            elif self._locks[resource_arn] == ticket_id:
                # We already have the lock
                return True
            else:
                # Someone else has the lock, add to wait queue
                if resource_arn not in self._wait_queues:
                    self._wait_queues[resource_arn] = deque()
                if ticket_id not in self._wait_queues[resource_arn]:
                    self._wait_queues[resource_arn].append(ticket_id)
                    log.info(
                        "lock_queued",
                        resource_arn=resource_arn,
                        ticket_id=ticket_id,
                        holder=self._locks[resource_arn],
                        queue_position=len(self._wait_queues[resource_arn]),
                    )
                return False
    
    def release(self, resource_arn: str, ticket_id: str) -> str | None:
        """
        Release lock for a resource.
        
        Returns the next ticket_id in queue (if any) that should be notified.
        """
        with self._lock:
            if resource_arn in self._locks and self._locks[resource_arn] == ticket_id:
                del self._locks[resource_arn]
                log.info(
                    "lock_released",
                    resource_arn=resource_arn,
                    ticket_id=ticket_id,
                )
                
                # Check if someone is waiting
                if resource_arn in self._wait_queues and self._wait_queues[resource_arn]:
                    next_ticket = self._wait_queues[resource_arn].popleft()
                    self._locks[resource_arn] = next_ticket
                    log.info(
                        "lock_granted_to_next",
                        resource_arn=resource_arn,
                        ticket_id=next_ticket,
                    )
                    return next_ticket
                    
                # Clean up empty queue
                if resource_arn in self._wait_queues and not self._wait_queues[resource_arn]:
                    del self._wait_queues[resource_arn]
            
            return None
    
    def is_locked(self, resource_arn: str) -> bool:
        """Check if a resource is currently locked."""
        with self._lock:
            return resource_arn in self._locks
    
    def get_holder(self, resource_arn: str) -> str | None:
        """Get the ticket_id that holds the lock."""
        with self._lock:
            return self._locks.get(resource_arn)
    
    def get_queue_position(self, resource_arn: str, ticket_id: str) -> int:
        """Get position in wait queue (0 if not waiting, 1+ if waiting)."""
        with self._lock:
            if resource_arn in self._wait_queues:
                try:
                    return list(self._wait_queues[resource_arn]).index(ticket_id) + 1
                except ValueError:
                    return 0
            return 0
    
    @property
    def active_locks(self) -> int:
        """Number of currently held locks."""
        with self._lock:
            return len(self._locks)


# Global lock manager instance
_resource_lock_manager: ResourceLockManager | None = None


def get_resource_lock_manager() -> ResourceLockManager:
    """Get or create the global resource lock manager."""
    global _resource_lock_manager
    if _resource_lock_manager is None:
        _resource_lock_manager = ResourceLockManager()
    return _resource_lock_manager


# =============================================================================
# PREFLIGHT CHECKS
# =============================================================================

class PreflightCheckError(Exception):
    """Raised when a critical preflight check fails."""
    pass


class PreflightChecker:
    """
    Performs startup pre-flight checks to ensure all dependencies are available.
    
    Critical checks (block startup):
    - Jira connectivity
    - ChromaDB connectivity
    - LocalStack TEST container
    - LocalStack PROD container
    - Playbooks loaded
    - Sufficient disk space
    
    Warning checks (allow startup):
    - LLM availability
    """
    
    MINIMUM_DISK_SPACE_MB = 500  # Minimum free disk space for Terraform temp dirs
    
    def __init__(self):
        self.results: dict[str, dict[str, Any]] = {}
        self.warnings: list[str] = []
        self.llm_available = False
    
    def run_all_checks(self) -> bool:
        """
        Run all preflight checks.
        
        Returns True if all critical checks pass, False otherwise.
        Raises PreflightCheckError with details if critical check fails.
        """
        log.info("preflight_checks_starting")
        
        # Critical checks
        critical_checks = [
            ("Jira Connectivity", self._check_jira),
            ("ChromaDB Connectivity", self._check_chromadb),
            ("LocalStack TEST", self._check_localstack_test),
            ("LocalStack PROD", self._check_localstack_prod),
            ("Playbooks", self._check_playbooks),
            ("Disk Space", self._check_disk_space),
        ]
        
        for name, check_func in critical_checks:
            try:
                success, message = check_func()
                self.results[name] = {"success": success, "message": message}
                
                if success:
                    log.info(f"preflight_check_passed", check=name, message=message)
                else:
                    log.error(f"preflight_check_failed", check=name, message=message)
                    raise PreflightCheckError(f"❌ {name}: {message}")
                    
            except PreflightCheckError:
                raise
            except Exception as e:
                log.error(f"preflight_check_error", check=name, error=str(e))
                raise PreflightCheckError(f"❌ {name}: {str(e)}")
        
        # Warning check (LLM)
        try:
            success, message = self._check_llm()
            self.results["LLM Availability"] = {"success": success, "message": message}
            self.llm_available = success
            
            if success:
                log.info("preflight_check_passed", check="LLM Availability", message=message)
            else:
                log.warning("preflight_check_warning", check="LLM Availability", message=message)
                self.warnings.append(f"⚠️ LLM Unavailable: {message}. Human playbook selection will be required.")
                
        except Exception as e:
            log.warning("preflight_check_warning", check="LLM Availability", error=str(e))
            self.warnings.append(f"⚠️ LLM check failed: {str(e)}. Human playbook selection will be required.")
            self.llm_available = False
        
        log.info("preflight_checks_complete", passed=len([r for r in self.results.values() if r["success"]]))
        return True
    
    def _check_jira(self) -> tuple[bool, str]:
        """Check Jira connectivity."""
        try:
            from requests.auth import HTTPBasicAuth
            auth = HTTPBasicAuth(settings.jira_email, settings.jira_api_token)
            response = requests.get(
                f"{settings.jira_base_url}rest/api/3/myself",
                auth=auth,
                timeout=10,
            )
            if response.status_code == 200:
                return True, f"Connected to {settings.jira_base_url}"
            else:
                return False, f"HTTP {response.status_code}: {response.text[:100]}"
        except requests.RequestException as e:
            return False, f"Connection failed: {str(e)}"
    
    def _check_chromadb(self) -> tuple[bool, str]:
        """Check ChromaDB connectivity."""
        try:
            # Try the newer API endpoint first, then fall back to older ones
            for endpoint in ["/api/v2/heartbeat", "/api/v1/heartbeat", "/api/v1"]:
                try:
                    response = requests.get(
                        f"http://{settings.chroma_host}:{settings.chroma_port}{endpoint}",
                        timeout=5,
                    )
                    if response.status_code == 200:
                        return True, f"Connected to {settings.chroma_host}:{settings.chroma_port}"
                except requests.RequestException:
                    continue
            
            # Try connecting via chromadb client directly
            import chromadb
            client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
            client.heartbeat()  # Will raise if not connected
            return True, f"Connected to {settings.chroma_host}:{settings.chroma_port}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    def _check_localstack_test(self) -> tuple[bool, str]:
        """Check LocalStack TEST container."""
        try:
            response = requests.get(
                f"{settings.localstack_test_endpoint}/_localstack/health",
                timeout=5,
            )
            if response.status_code == 200:
                return True, f"Running at {settings.localstack_test_endpoint}"
            else:
                return False, f"Unhealthy: HTTP {response.status_code}"
        except requests.RequestException as e:
            return False, f"Not reachable: {str(e)}. Run: docker-compose up localstack-test"
    
    def _check_localstack_prod(self) -> tuple[bool, str]:
        """Check LocalStack PROD container."""
        try:
            response = requests.get(
                f"{settings.localstack_prod_endpoint}/_localstack/health",
                timeout=5,
            )
            if response.status_code == 200:
                return True, f"Running at {settings.localstack_prod_endpoint}"
            else:
                return False, f"Unhealthy: HTTP {response.status_code}"
        except requests.RequestException as e:
            return False, f"Not reachable: {str(e)}. Run: docker-compose up localstack-prod"
    
    def _check_playbooks(self) -> tuple[bool, str]:
        """Check if playbooks are available."""
        try:
            from patchweave.core.loader import get_playbook_loader
            loader = get_playbook_loader()
            playbooks = loader.load_all()
            if playbooks and len(playbooks) > 0:
                return True, f"{len(playbooks)} playbooks loaded"
            else:
                return False, "No playbooks found in playbooks directory"
        except Exception as e:
            return False, f"Failed to load playbooks: {str(e)}"
    
    def _check_disk_space(self) -> tuple[bool, str]:
        """Check available disk space."""
        try:
            import os
            stat = os.statvfs('/')
            free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
            if free_mb >= self.MINIMUM_DISK_SPACE_MB:
                return True, f"{free_mb:.0f} MB available"
            else:
                return False, f"Only {free_mb:.0f} MB available, need {self.MINIMUM_DISK_SPACE_MB} MB"
        except Exception as e:
            return False, f"Could not check: {str(e)}"
    
    def _check_llm(self) -> tuple[bool, str]:
        """Check LLM availability (warning only)."""
        if not settings.use_llm:
            return False, "LLM disabled in settings (USE_LLM=false)"
        
        # Check if at least one API key is configured
        keys = [k for k in [settings.google_api_key, settings.google_api_key_2, settings.google_api_key_3] if k]
        if not keys:
            return False, "No API keys configured"
        
        # Optionally test API key validity (lightweight check)
        # Skip actual API call to avoid rate limits during startup
        return True, f"{len(keys)} API key(s) configured"
    
    def print_summary(self) -> None:
        """Print a summary of all check results."""
        print("\n" + "=" * 60)
        print("PREFLIGHT CHECK RESULTS")
        print("=" * 60)
        
        for name, result in self.results.items():
            status = "✅" if result["success"] else "❌"
            print(f"{status} {name}: {result['message']}")
        
        if self.warnings:
            print("\n⚠️ WARNINGS:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        print("=" * 60 + "\n")


class PatchWeaveApp:
    """
    Main PatchWeave application.

    Coordinates all components and manages the application lifecycle.
    Includes:
    - Jira polling for new security findings
    - Finding queue processing
    - Approval status polling
    - Graceful shutdown handling
    """
    
    # Maximum description size (500KB as per design)
    MAX_DESCRIPTION_SIZE = 500 * 1024  # 500KB in bytes
    
    # LLM retry settings
    LLM_WAIT_INTERVAL_SECONDS = 30  # Check every 30s during wait
    LLM_MAX_WAIT_MINUTES = 10  # Max wait before fallback to human selection

    def __init__(self) -> None:
        self._running = False
        self._shutdown_event = asyncio.Event()
        
        # Core components (initialized lazily)
        self._jira_client = None
        self._finding_queue = None
        self._analyzer = None
        self._playbook_loader = None
        self._playbook_matcher = None
        self._approval_handler = None
        self._learning_loop = None
        self._coordinator = None
        self._validator = None
        self._deployer = None
        
        # Resource lock manager
        self._lock_manager = get_resource_lock_manager()
        
        # LLM availability tracking
        self._llm_available = True
        self._llm_exhausted_since: datetime | None = None
        
        # Tracking
        self._pending_approvals: dict[str, Any] = {}
        self._processed_tickets: set[str] = set()
        self._waiting_for_lock: dict[str, str] = {}  # ticket_id -> resource_arn
    
    def _init_components(self) -> None:
        """Initialize all application components."""
        from patchweave.agents.coordinator import get_coordinator
        from patchweave.agents.deployer import DeployerAgent
        from patchweave.agents.validator import ValidatorAgent
        from patchweave.agents.analyzer import AnalyzerAgent
        from patchweave.approval import get_approval_handler
        from patchweave.integrations.jira import JiraClient
        from patchweave.core.loader import get_playbook_loader
        from patchweave.core.matcher import get_matcher
        from patchweave.learning import get_learning_loop
        from patchweave.core.queue import get_finding_queue
        
        self._jira_client = JiraClient()
        self._finding_queue = get_finding_queue()
        self._analyzer = AnalyzerAgent()
        self._playbook_loader = get_playbook_loader()
        self._playbook_matcher = get_matcher()
        self._approval_handler = get_approval_handler()
        self._learning_loop = get_learning_loop()
        self._coordinator = get_coordinator()
        self._validator = ValidatorAgent()
        self._deployer = DeployerAgent(dry_run=settings.deployment_dry_run)

    async def startup(self) -> None:
        """
        Initialize all application components.
        
        Runs preflight checks before initializing - will exit if critical checks fail.
        """
        log.info(
            "starting_patchweave",
            version="1.0.0",
            environment=settings.patchweave_env,
            use_localstack=settings.use_localstack,
        )
        
        # Run preflight checks FIRST
        preflight = PreflightChecker()
        try:
            preflight.run_all_checks()
            preflight.print_summary()
            self._llm_available = preflight.llm_available
        except PreflightCheckError as e:
            log.critical("preflight_check_failed", error=str(e))
            preflight.print_summary()
            print(f"\n❌ STARTUP ABORTED: {e}\n")
            sys.exit(1)
        
        # Initialize components
        self._init_components()

        # Log configuration (without sensitive values)
        log.info(
            "configuration_loaded",
            jira_project=settings.jira_project_key,
            aws_region=settings.aws_test_region,
            chroma_host=settings.chroma_host,
            high_confidence_threshold=settings.high_confidence_threshold,
            moderate_confidence_threshold=settings.moderate_confidence_threshold,
            deployment_dry_run=settings.deployment_dry_run,
            use_llm=settings.use_llm,
            llm_available=self._llm_available,
        )
        
        # Index playbooks into ChromaDB for semantic search
        # (playbooks already loaded during preflight checks, reuse them)
        try:
            playbooks = self._playbook_loader.load_all()
            # Index playbooks into ChromaDB for semantic search
            if playbooks:
                from patchweave.core.chromadb import get_playbook_store
                store = get_playbook_store()
                store.add_playbooks(playbooks)
                log.info("playbooks_indexed", count=len(playbooks))
        except Exception as e:
            log.error("playbook_loading_failed", error=str(e))

        self._running = True
        log.info("patchweave_started")

    async def shutdown(self) -> None:
        """Gracefully shutdown all components."""
        log.info("shutting_down_patchweave")
        self._running = False
        self._shutdown_event.set()
        log.info("patchweave_shutdown_complete")

    async def run(self) -> None:
        """Run the main application loop with all background tasks."""
        await self.startup()

        # Start background tasks
        tasks = [
            asyncio.create_task(self._jira_polling_loop()),
            asyncio.create_task(self._queue_processing_loop()),
            asyncio.create_task(self._approval_polling_loop()),
        ]

        try:
            # Wait for shutdown signal
            await self._shutdown_event.wait()

        except asyncio.CancelledError:
            pass
        
        finally:
            # Cancel background tasks
            for task in tasks:
                task.cancel()
            
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.shutdown()
    
    async def _jira_polling_loop(self) -> None:
        """Poll Jira for new security findings."""
        log.info("jira_polling_started", interval=settings.jira_poll_interval_seconds)
        
        while self._running:
            try:
                await self._poll_jira()
            except Exception as e:
                log.error("jira_poll_error", error=str(e))
            
            await asyncio.sleep(settings.jira_poll_interval_seconds)
    
    async def _poll_jira(self) -> None:
        """Single Jira poll iteration."""
        log.debug("polling_jira")
        
        # Use the queue's built-in polling which handles RawFinding properly
        try:
            new_findings = await self._finding_queue.poll_once()
            if new_findings:
                log.info("new_findings_discovered", count=len(new_findings))
        except Exception as e:
            log.error("jira_poll_error", error=str(e))
    
    async def _queue_processing_loop(self) -> None:
        """Process findings from the queue."""
        log.info("queue_processing_started")
        
        while self._running:
            try:
                await self._process_queue()
            except Exception as e:
                log.error("queue_process_error", error=str(e))
            
            await asyncio.sleep(1)  # Small delay between processing
    
    async def _process_queue(self) -> None:
        """Process next item from queue."""
        queue_item = self._finding_queue.get_next()
        
        if queue_item is None:
            return
        
        ticket_id = queue_item.finding_id
        raw_finding = queue_item.raw_finding
        
        log.info("processing_finding", ticket_id=ticket_id)
        
        try:
            # Run through workflow
            final_state = await self._run_remediation_workflow(raw_finding)
            
            # Register state for API access
            from patchweave.api.routes.findings import register_workflow
            register_workflow(
                workflow_id=final_state.workflow_id,
                state_dict=self._state_to_dict(final_state),
            )
            
            # Handle based on final phase
            from patchweave.agents.state import WorkflowPhase
            
            if final_state.phase == WorkflowPhase.APPROVAL:
                # Add to pending approvals for polling
                self._pending_approvals[ticket_id] = final_state
            elif final_state.phase == WorkflowPhase.COMPLETE:
                log.info(
                    "remediation_complete",
                    ticket_id=ticket_id,
                    workflow_id=final_state.workflow_id,
                    _audit=True,
                )
            else:
                log.warning(
                    "workflow_ended_unexpectedly",
                    ticket_id=ticket_id,
                    phase=final_state.phase.value,
                )
                
        except Exception as e:
            log.error("workflow_failed", ticket_id=ticket_id, error=str(e))
            self._finding_queue.fail_item(ticket_id, str(e))
    
    async def _create_finding_without_llm(self, raw_finding: Any) -> Any:
        """
        Create an AnalyzedFinding without using LLM.
        
        Used when USE_LLM=false. Creates a basic AnalyzedFinding from
        the raw finding data, allowing ChromaDB to do semantic matching
        directly on the title/description text.
        """
        from patchweave.models.finding import AnalyzedFinding
        from patchweave.models.enums import VulnerabilityType, Severity, CloudProvider
        from patchweave.core.tokenizer import get_tokenizer
        
        ticket_id = raw_finding.jira_ticket_id
        
        # Tokenize the finding to extract sensitive data
        tokenizer = get_tokenizer()
        sanitized_title, sanitized_description, token_mapping = tokenizer.tokenize_finding(
            title=raw_finding.title,
            description=raw_finding.description,
            finding_id=ticket_id,
        )
        
        # Try to infer severity from raw finding
        severity = Severity.MEDIUM
        if raw_finding.severity:
            raw_sev = raw_finding.severity.lower()
            if "critical" in raw_sev:
                severity = Severity.CRITICAL
            elif "high" in raw_sev:
                severity = Severity.HIGH
            elif "low" in raw_sev:
                severity = Severity.LOW
        
        # Try to infer resource type from title/description
        resource_type = "AWS::Unknown::Resource"
        title_lower = raw_finding.title.lower()
        desc_lower = raw_finding.description.lower()
        combined = f"{title_lower} {desc_lower}"
        
        if "s3" in combined or "bucket" in combined:
            resource_type = "AWS::S3::Bucket"
        elif "ec2" in combined or "instance" in combined:
            resource_type = "AWS::EC2::Instance"
        elif "security group" in combined or "securitygroup" in combined:
            resource_type = "AWS::EC2::SecurityGroup"
        elif "rds" in combined or "database" in combined:
            resource_type = "AWS::RDS::DBInstance"
        elif "iam" in combined or "user" in combined or "role" in combined:
            resource_type = "AWS::IAM::User"
        elif "kms" in combined or "key" in combined:
            resource_type = "AWS::KMS::Key"
        elif "ebs" in combined or "volume" in combined:
            resource_type = "AWS::EC2::Volume"
        elif "lambda" in combined or "function" in combined:
            resource_type = "AWS::Lambda::Function"
        elif "elb" in combined or "load balancer" in combined:
            resource_type = "AWS::ElasticLoadBalancing::LoadBalancer"
        elif "cloudtrail" in combined:
            resource_type = "AWS::CloudTrail::Trail"
        
        # Build search query from title and description (for ChromaDB matching)
        search_query = f"{sanitized_title} {sanitized_description}"
        
        # Store token mapping in the token store (same as analyzer does)
        from patchweave.core.tokenizer import get_token_store
        token_store = get_token_store()
        token_store.store(token_mapping)
        
        log.info(
            "finding_created_without_llm",
            ticket_id=ticket_id,
            inferred_resource_type=resource_type,
            inferred_severity=severity.value,
            token_count=len(token_mapping.tokens),
        )
        
        return AnalyzedFinding(
            finding_id=ticket_id,
            vulnerability_type=VulnerabilityType.UNKNOWN,  # Let ChromaDB find the best match
            cloud_provider=CloudProvider.AWS,
            resource_type=resource_type,
            severity=severity,
            search_query=search_query,
            sanitized_title=sanitized_title,
            sanitized_description=sanitized_description,
            token_keys=list(token_mapping.tokens.keys()),
            source_ticket_url=raw_finding.jira_ticket_url,
            detected_at=raw_finding.created_at,
            analysis_confidence=0.5,  # Lower confidence since no LLM analysis
        )
    
    async def _analyze_with_llm_fallback(self, raw_finding: Any) -> tuple[Any, bool]:
        """
        Analyze finding with LLM, with exhaustion handling.
        
        If all API keys are exhausted:
        1. Wait up to 10 minutes with 30-second interval checks
        2. If still unavailable, fall back to non-LLM analysis
        
        Returns:
            Tuple of (AnalyzedFinding, llm_exhausted: bool)
        """
        ticket_id = raw_finding.jira_ticket_id
        llm_exhausted = False
        
        # Check if we're already in an LLM exhaustion state
        if self._llm_exhausted_since is not None:
            wait_time = (datetime.utcnow() - self._llm_exhausted_since).total_seconds()
            if wait_time < self.LLM_MAX_WAIT_MINUTES * 60:
                # Still in wait period
                remaining = self.LLM_MAX_WAIT_MINUTES * 60 - wait_time
                log.info(
                    "llm_exhausted_waiting",
                    ticket_id=ticket_id,
                    remaining_seconds=remaining,
                )
        
        # Try to analyze with LLM
        try:
            analyzed_finding = await self._analyzer.analyze(raw_finding)
            
            # Success - reset exhaustion state
            if self._llm_exhausted_since is not None:
                log.info("llm_recovered", ticket_id=ticket_id)
                self._llm_exhausted_since = None
                self._llm_available = True
            
            return analyzed_finding, False
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if this is an API key exhaustion error (rate limit, quota exceeded)
            is_exhaustion = any(x in error_str for x in [
                "rate limit", "quota", "exceeded", "429", "insufficient_quota",
                "api key", "all keys exhausted"
            ])
            
            if not is_exhaustion:
                # Regular error - re-raise
                raise
            
            # API key exhaustion - start waiting period
            if self._llm_exhausted_since is None:
                self._llm_exhausted_since = datetime.utcnow()
                self._llm_available = False
                log.warning(
                    "llm_exhausted_starting_wait",
                    ticket_id=ticket_id,
                    max_wait_minutes=self.LLM_MAX_WAIT_MINUTES,
                )
            
            # Wait with interval checks
            wait_start = datetime.utcnow()
            while (datetime.utcnow() - wait_start).total_seconds() < self.LLM_MAX_WAIT_MINUTES * 60:
                await asyncio.sleep(self.LLM_WAIT_INTERVAL_SECONDS)
                
                # Try again
                try:
                    analyzed_finding = await self._analyzer.analyze(raw_finding)
                    
                    # Success - reset exhaustion state
                    log.info("llm_recovered_during_wait", ticket_id=ticket_id)
                    self._llm_exhausted_since = None
                    self._llm_available = True
                    return analyzed_finding, False
                    
                except Exception as retry_error:
                    retry_error_str = str(retry_error).lower()
                    if not any(x in retry_error_str for x in [
                        "rate limit", "quota", "exceeded", "429", "insufficient_quota"
                    ]):
                        # Different error - re-raise
                        raise
                    
                    # Still exhausted - continue waiting
                    elapsed = (datetime.utcnow() - wait_start).total_seconds()
                    remaining = self.LLM_MAX_WAIT_MINUTES * 60 - elapsed
                    log.info(
                        "llm_still_exhausted",
                        ticket_id=ticket_id,
                        remaining_seconds=remaining,
                    )
            
            # Timeout reached - fall back to non-LLM analysis
            log.warning(
                "llm_exhausted_timeout_fallback",
                ticket_id=ticket_id,
                wait_minutes=self.LLM_MAX_WAIT_MINUTES,
            )
            
            analyzed_finding = await self._create_finding_without_llm(raw_finding)
            return analyzed_finding, True  # Mark as LLM exhausted
    
    async def _request_human_playbook_selection(
        self,
        state: Any,
        finding: Any,
        match_result: Any,
    ) -> Any:
        """
        Request human selection from top-3 playbooks when LLM is exhausted
        and confidence is moderate (70-89%).
        
        Posts to Jira with the top-3 matched playbooks for human selection.
        """
        ticket_id = state.jira_ticket_id
        
        # Get top 3 playbooks from matcher
        top_playbooks = self._playbook_matcher.get_top_matches(finding, n=3)
        
        if not top_playbooks:
            log.warning(
                "human_selection_no_playbooks",
                ticket_id=ticket_id,
            )
            state.human_selection_pending = False
            return state
        
        # Format playbook options for Jira comment
        playbook_options = []
        for i, (playbook, similarity) in enumerate(top_playbooks, 1):
            playbook_options.append(
                f"{i}. **{playbook.name}** (ID: `{playbook.id}`)\n"
                f"   - Similarity: {similarity:.1%}\n"
                f"   - Description: {playbook.description[:200]}..."
            )
        
        comment = (
            "⚠️ **Human Playbook Selection Required**\n\n"
            "The LLM is currently unavailable and the automatic match confidence is moderate. "
            "Please select one of the following playbooks or reject if none are appropriate:\n\n"
            f"{chr(10).join(playbook_options)}\n\n"
            "**To select a playbook**, reply with:\n"
            "`PATCHWEAVE:SELECT:<playbook_id>`\n\n"
            "**To reject all options**, reply with:\n"
            "`PATCHWEAVE:REJECT`"
        )
        
        self._jira_client.add_comment(ticket_id, comment)
        
        log.info(
            "human_selection_requested",
            ticket_id=ticket_id,
            playbook_count=len(top_playbooks),
        )
        
        # Store the top playbooks in state for later resolution
        state.pending_playbook_options = top_playbooks
        state.human_selection_pending = True
        state.add_event("human_selection_requested", {
            "playbook_ids": [p.id for p, _ in top_playbooks],
        })
        
        return state
    
    async def _run_remediation_workflow(self, raw_finding: Any) -> Any:
        """Run the complete remediation workflow for a finding."""
        from patchweave.agents.state import WorkflowPhase, WorkflowState
        from patchweave.models.finding import RawFinding, AnalyzedFinding
        from patchweave.core.matcher import MatchTier
        from patchweave.models.enums import VulnerabilityType, Severity, CloudProvider
        import uuid
        
        ticket_id = raw_finding.jira_ticket_id
        resource_arn = getattr(raw_finding, 'resource_arn', None) or ticket_id  # Fallback to ticket_id if no ARN
        
        # Check description size and truncate if needed (500KB limit)
        description = raw_finding.description or ""
        if len(description.encode('utf-8')) > self.MAX_DESCRIPTION_SIZE:
            log.warning(
                "description_truncated",
                ticket_id=ticket_id,
                original_size=len(description.encode('utf-8')),
                max_size=self.MAX_DESCRIPTION_SIZE,
            )
            # Truncate to 500KB
            truncated_desc = description[:self.MAX_DESCRIPTION_SIZE // 2]  # Rough char estimate
            while len(truncated_desc.encode('utf-8')) > self.MAX_DESCRIPTION_SIZE:
                truncated_desc = truncated_desc[:-1000]
            truncated_desc += "\n\n[... Description truncated due to size limit ...]"
            raw_finding.description = truncated_desc
            
            # Update Jira with truncation notice
            self._jira_client.add_comment(
                ticket_id,
                f"⚠️ Description was truncated from {len(description.encode('utf-8')):,} bytes to {len(truncated_desc.encode('utf-8')):,} bytes (500KB limit)."
            )
        
        # Acquire resource lock (FIFO queue)
        lock_acquired = False
        try:
            if self._lock_manager.is_locked(resource_arn):
                log.info(
                    "waiting_for_resource_lock",
                    ticket_id=ticket_id,
                    resource_arn=resource_arn,
                )
                self._waiting_for_lock[ticket_id] = resource_arn
            
            # Wait for lock with polling (non-blocking async wait)
            while not self._lock_manager.acquire(resource_arn, ticket_id):
                await asyncio.sleep(1)  # Poll every second
            
            lock_acquired = True
            self._waiting_for_lock.pop(ticket_id, None)
            
            log.info(
                "resource_lock_acquired",
                ticket_id=ticket_id,
                resource_arn=resource_arn,
            )
            
            # Run the actual workflow with lock held
            return await self._run_workflow_with_lock(raw_finding, resource_arn)
            
        finally:
            # Always release lock on exit
            if lock_acquired:
                self._lock_manager.release(resource_arn, ticket_id)
                log.info(
                    "resource_lock_released",
                    ticket_id=ticket_id,
                    resource_arn=resource_arn,
                )
    
    async def _run_workflow_with_lock(self, raw_finding: Any, resource_arn: str) -> Any:
        """Run workflow after acquiring resource lock."""
        from patchweave.agents.state import WorkflowPhase, WorkflowState
        from patchweave.models.finding import RawFinding, AnalyzedFinding
        from patchweave.core.matcher import MatchTier
        from patchweave.models.enums import VulnerabilityType, Severity, CloudProvider
        import uuid
        
        ticket_id = raw_finding.jira_ticket_id
        
        # Update Jira status to Analyzing
        from patchweave.models.enums import JiraStatus
        self._jira_client.update_status(ticket_id, JiraStatus.ANALYZING)
        
        # Check if LLM is enabled and available
        llm_exhausted = False
        if settings.use_llm:
            # Check LLM availability with exhaustion handling
            analyzed_finding, llm_exhausted = await self._analyze_with_llm_fallback(raw_finding)
        else:
            # LLM disabled - create AnalyzedFinding directly and match via ChromaDB
            log.info(
                "llm_disabled_direct_matching",
                ticket_id=ticket_id,
                message="Skipping LLM analysis, using direct ChromaDB matching",
            )
            
            # Create a basic AnalyzedFinding from raw finding for direct matching
            analyzed_finding = await self._create_finding_without_llm(raw_finding)
        
        # 2. Match to playbook
        match_result = self._playbook_matcher.match(analyzed_finding)
        
        # 3. Create workflow state
        state = WorkflowState(
            workflow_id=str(uuid.uuid4()),
            jira_ticket_id=ticket_id,
            analyzed_finding=analyzed_finding,
        )
        state.llm_exhausted = llm_exhausted  # Track if LLM was unavailable
        
        # Get token mapping from the token store (populated during analysis or _create_finding_without_llm)
        from patchweave.core.tokenizer import get_token_store
        token_store = get_token_store()
        token_mapping_obj = token_store.get(ticket_id)
        if token_mapping_obj:
            state.token_mapping = token_mapping_obj.tokens
        
        # Start the workflow
        self._coordinator.start_workflow(state)
        
        if match_result.playbook is None or match_result.tier == MatchTier.LOW:
            # No matching playbook found or confidence too low
            state.phase = WorkflowPhase.FAILED
            state.add_event("no_playbook_matched", {
                "finding_type": analyzed_finding.vulnerability_type.value,
                "similarity": match_result.similarity,
            })
            # Update Jira status to NO_PLAYBOOK
            self._jira_client.update_status(ticket_id, JiraStatus.NO_PLAYBOOK)
            return state
        
        # 4. Update state with match info
        playbook = match_result.playbook
        state.matched_playbook = playbook
        state.match_similarity = match_result.similarity
        state.match_tier = match_result.tier
        
        # 5. Route based on confidence
        route = self._coordinator.route_by_match_tier(state)
        
        if route == "no_playbook":
            state.phase = WorkflowPhase.FAILED
            state.add_event("confidence_too_low", {
                "similarity": match_result.similarity
            })
            # Update Jira status to NO_PLAYBOOK
            self._jira_client.update_status(ticket_id, JiraStatus.NO_PLAYBOOK)
            return state
        
        # Handle moderate confidence with LLM exhaustion - need human selection
        if route == "moderate_confidence" and llm_exhausted:
            # LLM is unavailable and confidence is moderate - request human selection
            state = await self._request_human_playbook_selection(
                state=state,
                finding=analyzed_finding,
                match_result=match_result,
            )
            
            # If human hasn't selected yet, we'll poll for it later
            if state.human_selection_pending:
                return state
            
            # Human selected a playbook - update the match
            if state.human_selected_playbook:
                playbook = state.human_selected_playbook
                state.matched_playbook = playbook
        
        # 6. Validate in test environment (requires Terraform + LocalStack)
        import shutil
        import requests
        
        terraform_available = shutil.which('terraform') is not None
        localstack_available = False
        
        if terraform_available:
            # Check if LocalStack test endpoint is reachable
            try:
                response = requests.get(f"{settings.localstack_test_endpoint}/_localstack/health", timeout=5)
                localstack_available = response.status_code == 200
            except requests.exceptions.RequestException:
                localstack_available = False
        
        if terraform_available and localstack_available:
            # Update Jira status to Validating
            self._jira_client.update_status(ticket_id, JiraStatus.VALIDATING)
            
            log.info(
                "validation_starting",
                workflow_id=state.workflow_id,
                localstack_endpoint=settings.localstack_test_endpoint,
            )
            state = self._validator.validate_playbook(
                state=state,
                playbook=playbook,
                token_mapping=state.token_mapping,
            )
            
            if not state.is_validation_successful():
                state.phase = WorkflowPhase.FAILED
                return state
        else:
            skip_reasons = []
            if not terraform_available:
                skip_reasons.append("terraform_not_installed")
            if not localstack_available:
                skip_reasons.append("localstack_not_reachable")
            
            log.warning(
                "validation_skipped",
                workflow_id=state.workflow_id,
                reasons=skip_reasons,
                message=f"Validation skipped: {', '.join(skip_reasons)}"
            )
            state.add_event("validation_skipped", {"reasons": skip_reasons})
        
        # 7. Request approval
        state = self._approval_handler.request_approval(
            state=state,
            finding=analyzed_finding,
            playbook=playbook,
            match=match_result,
        )
        
        # Store finding and playbook for later deployment
        state._finding = analyzed_finding  # type: ignore
        state._playbook = playbook  # type: ignore
        state._match = match_result  # type: ignore
        
        return state
    
    async def _approval_polling_loop(self) -> None:
        """Poll for approval status changes."""
        log.info("approval_polling_started", interval=settings.approval_poll_interval_seconds)
        
        while self._running:
            try:
                await self._check_pending_approvals()
            except Exception as e:
                log.error("approval_poll_error", error=str(e))
            
            await asyncio.sleep(settings.approval_poll_interval_seconds)
    
    async def _check_pending_approvals(self) -> None:
        """Check status of pending approvals."""
        from patchweave.approval import ApprovalDecision
        
        completed = []
        
        for ticket_id, state in self._pending_approvals.items():
            decision = self._approval_handler.check_approval_status(state)
            
            if decision == ApprovalDecision.APPROVED:
                state = self._approval_handler.process_approval(state)
                await self._deploy_remediation(state)
                completed.append(ticket_id)
                
            elif decision == ApprovalDecision.REJECTED:
                state = self._approval_handler.process_rejection(state)
                completed.append(ticket_id)
            
            # Note: No TIMEOUT handling - approvals wait indefinitely per design
        
        # Remove completed from pending
        for ticket_id in completed:
            del self._pending_approvals[ticket_id]
    
    async def _deploy_remediation(self, state: Any) -> None:
        """Deploy an approved remediation."""
        from patchweave.agents.state import WorkflowPhase
        from patchweave.api.routes.findings import register_workflow
        
        # Get stored finding and playbook
        finding = getattr(state, "_finding", None)
        playbook = getattr(state, "_playbook", None)
        match = getattr(state, "_match", None)
        
        if playbook is None:
            log.error("deployment_failed_no_playbook", workflow_id=state.workflow_id)
            return
        
        # Use token_mapping from state (set during analysis)
        token_mapping = state.token_mapping or {}
        
        try:
            # Execute deployment
            state = self._deployer.deploy(
                state=state,
                playbook=playbook,
                token_mapping=token_mapping,
            )
            
            if state.deployment_success:
                state.phase = WorkflowPhase.COMPLETE
                
                # Record successful remediation for learning
                if finding and match:
                    self._learning_loop.record_successful_remediation(
                        state=state,
                        finding=finding,
                        playbook=playbook,
                        match=match,
                        deployment_details={"dry_run": self._deployer.dry_run},
                    )
                
                # Post success to Jira
                self._approval_handler.post_deployment_result(
                    state=state,
                    success=True,
                    details={"dry_run": self._deployer.dry_run},
                )
            else:
                state.phase = WorkflowPhase.FAILED
                
                # Record failure
                if finding:
                    self._learning_loop.record_failed_remediation(
                        state=state,
                        finding=finding,
                        playbook=playbook,
                        error=state.deployment_error or "Unknown error",
                    )
                
                # Post failure to Jira
                self._approval_handler.post_deployment_result(
                    state=state,
                    success=False,
                    details={"error": state.deployment_error},
                )
                
        except Exception as e:
            log.error("deployment_exception", workflow_id=state.workflow_id, error=str(e))
            state.phase = WorkflowPhase.FAILED
            
            self._approval_handler.post_deployment_result(
                state=state,
                success=False,
                details={"error": str(e)},
            )
        
        # Update API state
        register_workflow(
            workflow_id=state.workflow_id,
            state_dict=self._state_to_dict(state),
        )
    
    def _state_to_dict(self, state: Any) -> dict[str, Any]:
        """Convert workflow state to dictionary for API access."""
        # Get vulnerability type from analyzed_finding if available
        vuln_type = ""
        severity = ""
        resource_id = ""
        if state.analyzed_finding:
            vuln_type = state.analyzed_finding.vulnerability_type.value if state.analyzed_finding.vulnerability_type else ""
            severity = state.analyzed_finding.severity.value if state.analyzed_finding.severity else ""
            resource_id = getattr(state.analyzed_finding, 'resource_id', '') or getattr(state.analyzed_finding, 'finding_id', '') or ""
        
        # Handle match_tier which might be enum or string
        match_tier_value = None
        if state.match_tier:
            match_tier_value = state.match_tier.value if hasattr(state.match_tier, 'value') else str(state.match_tier)
        
        # Handle approval_status which might be enum or string
        approval_value = None
        if state.approval_status:
            approval_value = state.approval_status.value if hasattr(state.approval_status, 'value') else str(state.approval_status)
        
        return {
            "workflow_id": state.workflow_id,
            "jira_ticket_id": state.jira_ticket_id,
            "phase": state.phase.value if hasattr(state.phase, 'value') else str(state.phase),
            "vulnerability_type": vuln_type,
            "severity": severity,
            "resource_id": resource_id,
            "matched_playbook_id": state.matched_playbook.id if state.matched_playbook else None,
            "matched_playbook_name": state.matched_playbook.name if state.matched_playbook else None,
            "match_similarity": state.match_similarity,
            "match_tier": match_tier_value,
            "approval_status": approval_value,
            "approved_by": state.approved_by,
            "validation_success": state.is_validation_successful() if state.stage_results else None,
            "deployment_success": state.deployment_success,
            "stage_results": state.stage_results,
            "events": state.events,
            "created_at": state.created_at.isoformat() if state.created_at else datetime.utcnow().isoformat(),
            "updated_at": state.updated_at.isoformat() if state.updated_at else datetime.utcnow().isoformat(),
        }


def setup_signal_handlers(app: PatchWeaveApp) -> None:
    """Setup signal handlers for graceful shutdown."""
    loop = asyncio.get_running_loop()

    def handle_signal(sig: signal.Signals) -> None:
        log.info("received_signal", signal=sig.name)
        app._shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))


def run_api_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the FastAPI server standalone."""
    from patchweave.api import app as api_app
    
    log.info("starting_api_server", host=host, port=port)
    uvicorn.run(api_app, host=host, port=port)


async def async_main() -> None:
    """Async main entry point."""
    app = PatchWeaveApp()

    # Setup signal handlers
    try:
        setup_signal_handlers(app)
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        pass

    await app.run()


def main() -> NoReturn:
    """Main entry point for PatchWeave."""
    import argparse
    
    parser = argparse.ArgumentParser(description="PatchWeave - Cloud Security Remediation")
    parser.add_argument(
        "--mode",
        choices=["full", "api-only"],
        default="full",
        help="Run mode: 'full' for complete application, 'api-only' for just API server",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="API server host",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API server port",
    )
    
    args = parser.parse_args()
    
    try:
        # Print startup banner
        print(
            """
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║   ██████╗  █████╗ ████████╗ ██████╗██╗  ██╗██╗    ██╗███████╗     ║
║   ██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██║  ██║██║    ██║██╔════╝     ║
║   ██████╔╝███████║   ██║   ██║     ███████║██║ █╗ ██║█████╗       ║
║   ██╔═══╝ ██╔══██║   ██║   ██║     ██╔══██║██║███╗██║██╔══╝       ║
║   ██║     ██║  ██║   ██║   ╚██████╗██║  ██║╚███╔███╔╝███████╗     ║
║   ╚═╝     ╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚══════╝     ║
║                                                                   ║
║   Intelligent Cloud Security Remediation System                   ║
║   Version 1.0.0                                                   ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
"""
        )

        if args.mode == "api-only":
            run_api_server(host=args.host, port=args.port)
        else:
            asyncio.run(async_main())
        
        sys.exit(0)

    except KeyboardInterrupt:
        log.info("keyboard_interrupt")
        sys.exit(0)

    except Exception as e:
        log.critical("fatal_error", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
