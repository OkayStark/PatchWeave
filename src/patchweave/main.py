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
import signal
import sys
from datetime import datetime
from typing import Any, NoReturn

import uvicorn

from patchweave.config import settings
from patchweave.logging import setup_logging, get_logger

# Initialize logging first
setup_logging()
log = get_logger(__name__)


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
        
        # Tracking
        self._pending_approvals: dict[str, Any] = {}
        self._processed_tickets: set[str] = set()
    
    def _init_components(self) -> None:
        """Initialize all application components."""
        from patchweave.agents.coordinator import get_coordinator
        from patchweave.agents.deployer import DeployerAgent
        from patchweave.agents.validator import ValidatorAgent
        from patchweave.analyzer import Analyzer
        from patchweave.approval import get_approval_handler
        from patchweave.integrations.jira import JiraClient
        from patchweave.core.loader import get_playbook_loader
        from patchweave.core.matcher import get_playbook_matcher
        from patchweave.learning import get_learning_loop
        from patchweave.queue import get_finding_queue
        
        self._jira_client = JiraClient()
        self._finding_queue = get_finding_queue()
        self._analyzer = Analyzer()
        self._playbook_loader = get_playbook_loader()
        self._playbook_matcher = get_playbook_matcher()
        self._approval_handler = get_approval_handler()
        self._learning_loop = get_learning_loop()
        self._coordinator = get_coordinator()
        self._validator = ValidatorAgent()
        self._deployer = DeployerAgent(dry_run=settings.deployment_dry_run)

    async def startup(self) -> None:
        """Initialize all application components."""
        log.info(
            "starting_patchweave",
            version="1.0.0",
            environment=settings.patchweave_env,
            use_localstack=settings.use_localstack,
        )
        
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
        )
        
        # Load playbooks
        try:
            playbooks = self._playbook_loader.load_all_playbooks()
            log.info("playbooks_loaded", count=len(playbooks))
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
        
        # Get open tickets from Jira
        tickets = self._jira_client.get_open_tickets(
            project_key=settings.jira_project_key,
            max_results=50,
        )
        
        for ticket in tickets:
            ticket_id = ticket.get("key", "")
            
            # Skip if already processed
            if ticket_id in self._processed_tickets:
                continue
            
            # Skip if not in a processable status
            status = ticket.get("status", "").upper()
            if status not in ["OPEN", "TO DO", "NEW"]:
                continue
            
            log.info("new_ticket_found", ticket_id=ticket_id, status=status)
            
            # Add to processing queue
            self._finding_queue.add(ticket)
            self._processed_tickets.add(ticket_id)
    
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
        finding_data = self._finding_queue.get_next()
        
        if finding_data is None:
            return
        
        ticket_id = finding_data.get("key", "")
        
        log.info("processing_finding", ticket_id=ticket_id)
        
        try:
            # Run through workflow
            final_state = await self._run_remediation_workflow(finding_data)
            
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
            self._finding_queue.mark_failed(ticket_id, str(e))
    
    async def _run_remediation_workflow(self, finding_data: dict[str, Any]) -> Any:
        """Run the complete remediation workflow for a finding."""
        from patchweave.agents.state import WorkflowPhase
        
        ticket_id = finding_data.get("key", "")
        
        # 1. Analyze the finding
        analyzed_finding = self._analyzer.analyze(finding_data)
        
        # 2. Match to playbook
        match_result = self._playbook_matcher.find_best_match(analyzed_finding)
        
        # 3. Create workflow state
        state = self._coordinator.start_workflow(
            jira_ticket_id=ticket_id,
            finding=analyzed_finding,
        )
        
        if match_result is None:
            # No matching playbook found
            state.phase = WorkflowPhase.FAILED
            state.add_event("no_playbook_matched", {
                "finding_type": analyzed_finding.vulnerability_type.value
            })
            return state
        
        # 4. Update state with match info
        playbook = match_result.playbook
        state.matched_playbook_id = playbook.id
        state.matched_playbook_name = playbook.name
        state.match_similarity = match_result.similarity_score
        state.match_tier = match_result.match_tier
        
        # 5. Route based on confidence
        route = self._coordinator.route_by_match_tier(state)
        
        if route == "no_playbook":
            state.phase = WorkflowPhase.FAILED
            state.add_event("confidence_too_low", {
                "similarity": match_result.similarity_score
            })
            return state
        
        # 6. Validate in test environment
        state = self._validator.validate_playbook(
            state=state,
            playbook=playbook,
            token_mapping=analyzed_finding.extracted_entities,
        )
        
        if not state.is_validation_successful():
            state.phase = WorkflowPhase.FAILED
            return state
        
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
                
            elif decision == ApprovalDecision.TIMEOUT:
                state = self._approval_handler.process_timeout(state)
                completed.append(ticket_id)
        
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
        
        token_mapping = finding.extracted_entities if finding else {}
        
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
        return {
            "workflow_id": state.workflow_id,
            "jira_ticket_id": state.jira_ticket_id,
            "phase": state.phase.value,
            "vulnerability_type": state.finding_type.value if state.finding_type else "",
            "severity": state.severity.value if state.severity else "",
            "resource_id": state.resource_id or "",
            "matched_playbook_id": state.matched_playbook_id,
            "matched_playbook_name": state.matched_playbook_name,
            "match_similarity": state.match_similarity,
            "match_tier": state.match_tier.value if state.match_tier else None,
            "approval_status": state.approval_status.value if state.approval_status else None,
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
