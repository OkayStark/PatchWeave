#!/usr/bin/env python3
"""
PatchWeave Demo Runner

A scripted demonstration of PatchWeave's end-to-end security remediation workflow.
This script simulates the demo scenarios documented in docs/DEMO_SCENARIO.md.
"""

import asyncio
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from patchweave.logging import get_logger

log = get_logger(__name__)


@dataclass
class DemoScenario:
    """A demo scenario to execute."""
    
    name: str
    ticket_id: str
    title: str
    description: str
    severity: str
    expected_vuln_type: str
    expected_playbook: str


# Pre-defined demo scenarios
DEMO_SCENARIOS = [
    DemoScenario(
        name="S3 Public Access (HIGH Confidence)",
        ticket_id="DEMO-001",
        title="S3 Bucket 'prod-logs-bucket' has public access enabled",
        description="""CRITICAL SECURITY FINDING

Resource: arn:aws:s3:::prod-logs-bucket
Account: 123456789012
Region: us-east-1

The S3 bucket prod-logs-bucket has Block Public Access disabled, 
potentially exposing sensitive log data to the internet.

Detected by: Wiz
First seen: 2026-01-15""",
        severity="Critical",
        expected_vuln_type="s3_public_access",
        expected_playbook="pb-s3-public-access-001",
    ),
    DemoScenario(
        name="S3 Encryption Disabled (HIGH Confidence)",
        ticket_id="DEMO-002",
        title="S3 bucket 'data-archive' does not have encryption enabled",
        description="""SECURITY FINDING

Resource: arn:aws:s3:::data-archive
Account: 123456789012
Region: eu-west-1

S3 bucket data-archive does not have default encryption enabled.
Data at rest is not protected.

Detected by: Prisma Cloud
First seen: 2026-01-16""",
        severity="High",
        expected_vuln_type="s3_encryption_disabled",
        expected_playbook="pb-s3-encrypt-001",
    ),
    DemoScenario(
        name="Security Group SSH Open (MODERATE Confidence)",
        ticket_id="DEMO-003",
        title="Security Group allows SSH from 0.0.0.0/0",
        description="""SECURITY FINDING

Resource: sg-0123456789abcdef0
Account: 123456789012
Region: us-west-2

Security group sg-0123456789abcdef0 has an inbound rule 
allowing SSH (port 22) from any IP address (0.0.0.0/0).

Detected by: AWS Security Hub
First seen: 2026-01-16""",
        severity="High",
        expected_vuln_type="security_group_open_port",
        expected_playbook="pb-sg-restrict-001",
    ),
]


def print_banner():
    """Print demo banner."""
    print()
    print("=" * 70)
    print("    🔐 PatchWeave Demo - Intelligent Cloud Security Remediation")
    print("=" * 70)
    print()


def print_scenario_header(scenario: DemoScenario, index: int, total: int):
    """Print scenario header."""
    print()
    print("-" * 70)
    print(f"  SCENARIO {index}/{total}: {scenario.name}")
    print("-" * 70)
    print()


def simulate_jira_ticket(scenario: DemoScenario) -> dict:
    """Simulate a Jira ticket for the scenario."""
    return {
        "jira_ticket_id": scenario.ticket_id,
        "jira_ticket_url": f"https://demo.atlassian.net/browse/{scenario.ticket_id}",
        "title": scenario.title,
        "description": scenario.description,
        "severity": scenario.severity,
        "created_at": datetime.utcnow().isoformat(),
    }


async def run_demo_scenario(scenario: DemoScenario, dry_run: bool = True):
    """Run a single demo scenario."""
    print(f"📋 Jira Ticket: {scenario.ticket_id}")
    print(f"   Title: {scenario.title}")
    print(f"   Severity: {scenario.severity}")
    print()
    
    # Step 1: Show ticket ingestion
    print("Step 1: INGESTION")
    print("  → Polling Jira for new security findings...")
    await asyncio.sleep(1)
    ticket = simulate_jira_ticket(scenario)
    print(f"  ✓ Found ticket {ticket['jira_ticket_id']}")
    print()
    
    # Step 2: Show tokenization
    print("Step 2: TOKENIZATION")
    print("  → Sanitizing sensitive data...")
    await asyncio.sleep(0.5)
    print("  ✓ Replaced: 123456789012 → {{ACCOUNT_ID}}")
    print("  ✓ Replaced: us-east-1 → {{AWS_REGION}}")
    if "bucket" in scenario.title.lower():
        print("  ✓ Replaced: prod-logs-bucket → {{BUCKET_NAME}}")
    elif "sg-" in scenario.description:
        print("  ✓ Replaced: sg-0123456789abcdef0 → {{SECURITY_GROUP_ID}}")
    print()
    
    # Step 3: Show analysis
    print("Step 3: ANALYSIS")
    print("  → Analyzing finding with LLM...")
    await asyncio.sleep(1)
    print(f"  ✓ Classified as: {scenario.expected_vuln_type}")
    print(f"  ✓ Analysis confidence: 0.95")
    print()
    
    # Step 4: Show matching
    print("Step 4: MATCHING")
    print("  → Searching ChromaDB for matching playbook...")
    await asyncio.sleep(1)
    
    if "MODERATE" in scenario.name:
        match_score = 0.78
        match_tier = "MODERATE_CONFIDENCE"
        print(f"  ⚠️ Match found: {scenario.expected_playbook}")
        print(f"  ⚠️ Similarity: {match_score:.0%} ({match_tier})")
        print("  → Routing to Playbook Verification Agent...")
    else:
        match_score = 0.94
        match_tier = "HIGH_CONFIDENCE"
        print(f"  ✓ Match found: {scenario.expected_playbook}")
        print(f"  ✓ Similarity: {match_score:.0%} ({match_tier})")
    print()
    
    # Step 5: Show verification (for moderate matches)
    if "MODERATE" in scenario.name:
        print("Step 5: VERIFICATION")
        print("  → Playbook Verification Agent reviewing match...")
        await asyncio.sleep(1)
        print("  ✓ Verification: APPROVED")
        print("  ✓ Reason: Port restriction pattern matches finding context")
        print()
    
    # Step 6: Show validation
    print("Step 6: VALIDATION")
    print("  → Setting up LocalStack test environment...")
    await asyncio.sleep(0.5)
    print("  ✓ Environment setup: SUCCESS")
    print("  → Running pre-check...")
    await asyncio.sleep(0.5)
    print("  ✓ Pre-check: PASSED (vulnerability exists)")
    print("  → Executing remediation in sandbox...")
    await asyncio.sleep(1)
    print("  ✓ Remediation: SUCCESS")
    print("  → Running post-check...")
    await asyncio.sleep(0.5)
    print("  ✓ Post-check: PASSED (fix verified)")
    print("  → Cleaning up test environment...")
    print("  ✓ Cleanup: SUCCESS")
    print()
    
    # Step 7: Show approval request
    print("Step 7: APPROVAL")
    print("  → Posting approval request to Jira...")
    await asyncio.sleep(0.5)
    print("  ✓ Comment posted with playbook details")
    print("  ✓ Status updated to: PENDING APPROVAL")
    print()
    
    if dry_run:
        print("  [DRY RUN MODE - Skipping actual deployment]")
        print("  ℹ️  In production, workflow would wait for human approval")
    else:
        # Step 8: Simulate approval
        print("  → Simulating approval...")
        await asyncio.sleep(1)
        print("  ✓ Approval received from: demo@example.com")
        print()
        
        # Step 9: Show deployment
        print("Step 8: DEPLOYMENT")
        print("  → Executing remediation in production...")
        await asyncio.sleep(1)
        print("  ✓ Deployment: SUCCESS")
        print("  → Running production post-check...")
        await asyncio.sleep(0.5)
        print("  ✓ Post-check: PASSED")
        print("  → Posting result to Jira...")
        print("  ✓ Status updated to: RESOLVED")
        print()
        
        # Step 10: Learning
        print("Step 9: LEARNING")
        print("  → Recording successful remediation...")
        await asyncio.sleep(0.5)
        print("  ✓ Pattern recorded in learning loop")
        print(f"  ✓ Playbook {scenario.expected_playbook} success count incremented")
    
    print()
    print("✅ Scenario complete!")


async def run_statistics_demo():
    """Show statistics demo."""
    print()
    print("-" * 70)
    print("  STATISTICS OVERVIEW")
    print("-" * 70)
    print()
    
    stats = {
        "total_findings": 3,
        "completed": 2,
        "pending": 1,
        "failed": 0,
        "average_time_minutes": 2.5,
        "playbook_matches": {
            "high_confidence": 2,
            "moderate_confidence": 1,
            "no_match": 0,
        },
        "top_vulnerability_types": [
            ("s3_public_access", 1),
            ("s3_encryption_disabled", 1),
            ("security_group_open_port", 1),
        ],
    }
    
    print("📊 System Statistics")
    print()
    print(f"  Total Findings Processed: {stats['total_findings']}")
    print(f"  ├── Completed: {stats['completed']}")
    print(f"  ├── Pending: {stats['pending']}")
    print(f"  └── Failed: {stats['failed']}")
    print()
    print(f"  Average Processing Time: {stats['average_time_minutes']} minutes")
    print()
    print("  Match Confidence Distribution:")
    print(f"  ├── High (≥90%): {stats['playbook_matches']['high_confidence']}")
    print(f"  ├── Moderate (70-89%): {stats['playbook_matches']['moderate_confidence']}")
    print(f"  └── No Match (<70%): {stats['playbook_matches']['no_match']}")
    print()
    print("  Top Vulnerability Types:")
    for vuln_type, count in stats["top_vulnerability_types"]:
        print(f"  ├── {vuln_type}: {count}")
    print()


async def run_demo(dry_run: bool = True, scenarios: list[int] | None = None):
    """Run the full demo."""
    print_banner()
    
    print("🚀 Starting PatchWeave Demo")
    print()
    print(f"   Mode: {'DRY RUN (no actual deployment)' if dry_run else 'FULL (with deployment)'}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check services (simulated)
    print("Checking services...")
    print("  ✓ PatchWeave API: Ready")
    print("  ✓ ChromaDB: Ready (12 playbooks loaded)")
    print("  ✓ LocalStack: Ready")
    print("  ✓ Jira: Ready (simulated)")
    print()
    
    # input("Press Enter to start the demo scenarios...")  # Skip for non-interactive
    
    # Run selected or all scenarios
    scenarios_to_run = scenarios or list(range(len(DEMO_SCENARIOS)))
    total = len(scenarios_to_run)
    
    for i, scenario_idx in enumerate(scenarios_to_run, 1):
        if scenario_idx >= len(DEMO_SCENARIOS):
            print(f"⚠️ Scenario {scenario_idx} not found, skipping")
            continue
            
        scenario = DEMO_SCENARIOS[scenario_idx]
        print_scenario_header(scenario, i, total)
        
        await run_demo_scenario(scenario, dry_run=dry_run)
        
        if i < total:
            print()
            # input("Press Enter for next scenario...")  # Skip for non-interactive
    
    # Show statistics
    await run_statistics_demo()
    
    print()
    print("=" * 70)
    print("    🎉 Demo Complete!")
    print("=" * 70)
    print()
    print("Summary:")
    print(f"  - Scenarios demonstrated: {total}")
    print(f"  - Workflow phases shown: 9")
    print(f"  - Vulnerability types covered: {len(set(s.expected_vuln_type for s in DEMO_SCENARIOS))}")
    print()
    print("Key Takeaways:")
    print("  1. Automated analysis reduces manual triage time")
    print("  2. Semantic matching finds relevant playbooks accurately")
    print("  3. Validation in sandbox ensures safe deployment")
    print("  4. Human approval maintains oversight")
    print("  5. Learning improves matching over time")
    print()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="PatchWeave Demo Runner")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full demo with deployment (default: dry-run)",
    )
    parser.add_argument(
        "--scenario",
        type=int,
        nargs="+",
        help="Run specific scenario(s) by index (0-based)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available scenarios",
    )
    
    args = parser.parse_args()
    
    if args.list:
        print("Available Demo Scenarios:")
        print()
        for i, scenario in enumerate(DEMO_SCENARIOS):
            print(f"  {i}: {scenario.name}")
            print(f"     Ticket: {scenario.ticket_id}")
            print(f"     Type: {scenario.expected_vuln_type}")
            print()
        return
    
    try:
        asyncio.run(run_demo(
            dry_run=not args.full,
            scenarios=args.scenario,
        ))
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")


if __name__ == "__main__":
    main()
