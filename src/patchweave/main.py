"""
PatchWeave Main Application Entry Point.

This module initializes and runs the PatchWeave cloud security remediation system.
"""

import asyncio
import signal
import sys
from typing import NoReturn

from patchweave.config import settings
from patchweave.logging import setup_logging, get_logger

# Initialize logging first
setup_logging()
log = get_logger(__name__)


class PatchWeaveApp:
    """
    Main PatchWeave application.

    Coordinates all components and manages the application lifecycle.
    """

    def __init__(self) -> None:
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def startup(self) -> None:
        """Initialize all application components."""
        log.info(
            "starting_patchweave",
            version="1.0.0",
            environment=settings.patchweave_env,
            use_localstack=settings.use_localstack,
        )

        # Log configuration (without sensitive values)
        log.info(
            "configuration_loaded",
            jira_project=settings.jira_project_key,
            aws_region=settings.aws_test_region,
            chroma_host=settings.chroma_host,
            high_confidence_threshold=settings.high_confidence_threshold,
            moderate_confidence_threshold=settings.moderate_confidence_threshold,
        )

        self._running = True
        log.info("patchweave_started")

    async def shutdown(self) -> None:
        """Gracefully shutdown all components."""
        log.info("shutting_down_patchweave")
        self._running = False
        self._shutdown_event.set()
        log.info("patchweave_shutdown_complete")

    async def run(self) -> None:
        """Run the main application loop."""
        await self.startup()

        try:
            # Main loop - in Phase 1, this would poll Jira and process findings
            while self._running:
                try:
                    # Placeholder for main processing loop
                    # This will be implemented in Phase 2 with:
                    # - Jira polling
                    # - Finding queue processing
                    # - Pipeline orchestration
                    await asyncio.sleep(1)

                    # Check for shutdown
                    if self._shutdown_event.is_set():
                        break

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log.error("main_loop_error", error=str(e), exc_info=True)
                    await asyncio.sleep(5)  # Back off on errors

        finally:
            await self.shutdown()


def setup_signal_handlers(app: PatchWeaveApp) -> None:
    """Setup signal handlers for graceful shutdown."""
    loop = asyncio.get_running_loop()

    def handle_signal(sig: signal.Signals) -> None:
        log.info("received_signal", signal=sig.name)
        asyncio.create_task(app.shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))


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
