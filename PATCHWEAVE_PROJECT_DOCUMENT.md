# PatchWeave: Intelligent Cloud Security Remediation System

## Complete Project Documentation

**Version**: 1.0.0  
**Date**: January 16, 2026  
**Status**: Phase 1 Implementation  
**Classification**: Final Year Capstone Project

---

# Table of Contents

1. [Executive & Technical Overview](#1-executive--technical-overview)
2. [Final System Architecture](#2-final-system-architecture)
3. [Architectural & Technical Decisions](#3-architectural--technical-decisions)
4. [Project Phases & Milestones](#4-project-phases--milestones)
5. [Detailed Implementation Blueprint](#5-detailed-implementation-blueprint)
6. [End-to-End System Workflow](#6-end-to-end-system-workflow)
7. [Final Architecture & Decision Summary](#7-final-architecture--decision-summary)

---

# 1. Executive & Technical Overview

## 1.1 Problem Statement and Motivation

### The Cloud Security Challenge

Organizations operating in cloud environments face an escalating volume of security misconfigurations. Cloud Security Posture Management (CSPM) tools such as Wiz, Prisma Cloud, and AWS Security Hub continuously scan infrastructure and generate findings—alerts indicating deviations from security best practices or compliance requirements.

### The Scale Problem

A typical enterprise environment generates **10,000+ security findings** that require remediation. Each finding represents a potential vulnerability: an S3 bucket with public access, an unencrypted database, a security group allowing unrestricted SSH access, or disabled audit logging.

### The Manual Remediation Bottleneck

Current remediation workflows are predominantly manual:

| Metric | Current State |
|--------|---------------|
| Average time per finding | **7-9 hours** |
| Total manual effort (10K findings) | **80,000 hours** |
| Resource requirement | Skilled cloud security engineers |
| Error rate | Variable (human-dependent) |
| Consistency | Low (different engineers, different approaches) |

The 7-9 hour remediation time includes:
- Triaging and understanding the finding
- Researching the appropriate fix
- Testing the fix in a safe environment
- Obtaining change approval
- Applying the fix to production
- Verifying the remediation worked
- Documenting the change

### Why Automation Is Difficult

Previous automation attempts have failed due to:

1. **Safety Concerns**: Blindly auto-remediating can break production systems
2. **Context Sensitivity**: The "right" fix depends on business context
3. **Validation Gap**: No way to verify fixes work before production
4. **Compliance Requirements**: Many organizations require human approval for infrastructure changes
5. **Knowledge Silos**: Remediation expertise is trapped in individuals, not systems

### The Opportunity

If remediation time could be reduced from **7-9 hours to 25-30 minutes**, organizations would save approximately **76,000 hours** of engineering effort per 10,000 findings—while maintaining safety through human-in-the-loop approval.

---

## 1.2 Project Objectives and Constraints

### Primary Objective

Build an intelligent, multi-agent system that automates the cloud security remediation workflow while maintaining human oversight for production changes.

### Quantitative Targets

| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| Mean Time to Remediation (MTTR) | 7-9 hours | 25-30 minutes | ~94% reduction |
| Manual effort per finding | 7-9 hours | <5 minutes (approval only) | ~99% reduction |
| Total effort (10K findings) | 80,000 hours | ~4,000 hours | 76,000 hours saved |

### Functional Objectives

1. **Automated Ingestion**: Consume security findings from Jira tickets created by CSPM tools
2. **Intelligent Analysis**: Parse unstructured finding data into actionable, structured format
3. **Knowledge Reuse**: Match new findings to previously successful remediations
4. **Safe Validation**: Test remediation code in isolated environments before production
5. **Human Approval**: Require explicit approval before any production changes
6. **Automated Deployment**: Apply validated, approved fixes to target cloud environments
7. **Continuous Learning**: Store successful remediations for future reuse

### Non-Functional Objectives

1. **Safety**: No production changes without human approval
2. **Auditability**: Complete audit trail of all actions and decisions
3. **Reliability**: Graceful failure handling with clear escalation paths
4. **Extensibility**: Architecture supports future multi-cloud expansion
5. **Maintainability**: Clean separation of concerns, comprehensive documentation

### Project Constraints

| Constraint | Description |
|------------|-------------|
| **Timeline** | University capstone project timeline |
| **Team Size** | 4 team members + faculty mentor |
| **Budget** | Limited cloud credits; cost-conscious design required |
| **Cloud Scope** | AWS only for Phase 1 |
| **Approval Requirement** | Human-in-the-loop mandatory; no fully autonomous deployment |
| **Academic Requirements** | Must demonstrate understanding of system design principles |

### Explicit Non-Goals (Phase 1)

The following are explicitly **out of scope** for Phase 1:

- Dynamic playbook generation using LLMs
- Multi-cloud support (Azure, GCP)
- Custom web dashboard UI
- Concurrent/parallel finding processing
- Automated playbook deprecation
- Integration with Slack, Teams, or other notification systems

---

## 1.3 Target Users and Use Cases

### Primary Users

#### 1. Cloud Security Engineers

**Profile**: Technical professionals responsible for maintaining secure cloud infrastructure.

**Pain Points**:
- Overwhelmed by volume of CSPM findings
- Repetitive remediation tasks
- Context-switching between multiple tools
- Pressure to remediate quickly while avoiding mistakes

**How PatchWeave Helps**:
- Automates repetitive analysis and remediation
- Provides validated fixes ready for approval
- Maintains context in Jira (familiar tool)
- Reduces cognitive load

#### 2. Security Operations Center (SOC) Analysts

**Profile**: First-line responders who triage security alerts.

**Pain Points**:
- Must escalate cloud findings to specialized engineers
- Limited visibility into remediation progress
- Difficulty prioritizing findings

**How PatchWeave Helps**:
- Clear status visibility through Jira workflow
- Automatic processing without manual escalation
- Prioritization by severity (Critical findings processed first in queue)

#### 3. Compliance Officers / Auditors

**Profile**: Professionals responsible for ensuring regulatory compliance.

**Pain Points**:
- Need proof that findings were addressed
- Require audit trails for compliance frameworks
- Must verify changes were approved appropriately

**How PatchWeave Helps**:
- Complete audit trail in structured logs
- Jira history shows approval workflow
- Validation evidence documented in comments

### Use Cases

#### UC-1: Standard Remediation Flow

**Trigger**: CSPM tool detects S3 bucket with public access enabled.

**Flow**:
1. Jira ticket created automatically by CSPM tool
2. PatchWeave ingests ticket, sanitizes sensitive data
3. Analyzer identifies vulnerability type: `s3_public_access`
4. ChromaDB search finds matching playbook (92% match)
5. Validation workflow confirms fix works in test environment
6. Security engineer approves via Jira status transition
7. Deployment agent applies fix to production S3 bucket
8. Ticket marked RESOLVED

**Outcome**: 25-minute end-to-end, vs. 8 hours manual.

#### UC-2: No Matching Playbook

**Trigger**: CSPM tool detects novel misconfiguration with no existing playbook.

**Flow**:
1. Jira ticket created
2. PatchWeave ingests and analyzes
3. ChromaDB search returns <70% match
4. Ticket status set to NO PLAYBOOK
5. Human security engineer notified to handle manually
6. (Phase 2: Generator Agent would create new playbook)

**Outcome**: Fast triage; human handles exception cases.

#### UC-3: Validation Failure

**Trigger**: Playbook found but remediation fails validation.

**Flow**:
1. Finding matches playbook at 88%
2. Playbook Verification Agent approves match
3. Validation workflow creates test environment
4. Pre-check confirms vulnerability exists
5. Remediation applied
6. Post-check fails (fix didn't work)
7. Test environment cleaned up
8. Ticket status set to VALIDATION FAILED
9. Human security engineer investigates

**Outcome**: Unsafe fix caught before production; no damage.

#### UC-4: Rejection by Approver

**Trigger**: Validated fix rejected by human approver.

**Flow**:
1. Finding processed, validated successfully
2. Ticket moves to PENDING APPROVAL
3. Approver reviews remediation code
4. Approver determines fix is inappropriate for this specific resource
5. Approver transitions to REJECTED with comment explaining reason
6. PatchWeave logs rejection, no deployment occurs

**Outcome**: Human judgment preserved; business context respected.

---

## 1.4 Success Criteria

### Phase 1 Success Criteria

| Criterion | Measurement | Target |
|-----------|-------------|--------|
| End-to-end demo | Complete workflow from Jira ticket to deployment | Working demo with 3+ vulnerability types |
| Playbook coverage | Number of curated playbooks | 10-15 playbooks |
| MTTR (excluding approval time) | Time from ingestion to PENDING APPROVAL | <15 minutes |
| Validation reliability | Successful validation when playbook matches | >90% |
| False positive rate | Wrong playbook matched and validated | <5% |
| System uptime during demo | No crashes during evaluation | 100% |

### Academic Success Criteria

| Criterion | Evidence |
|-----------|----------|
| System design understanding | Architecture documentation, decision rationale |
| Implementation competency | Working code, clean structure |
| Problem-solving | Handling of edge cases, failure scenarios |
| Documentation quality | This document, code comments, API docs |
| Presentation | Clear demo, ability to answer technical questions |

---

*End of Section 1: Executive & Technical Overview*

---

# 2. Final System Architecture

## 2.1 High-Level Architecture Overview

PatchWeave is an **agent-orchestrated cloud remediation pipeline** that follows a detect → analyze → match → validate → approve → deploy lifecycle. The system is built on a multi-agent architecture coordinated by LangGraph, with Jira serving as both the input source and primary user interface.

### System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SYSTEMS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐         ┌─────────────┐         ┌─────────────────────┐   │
│  │ CSPM Tools  │         │    Jira     │         │   AWS Cloud         │   │
│  │ (Wiz,       │────────▶│  (Tickets)  │◀───────▶│   (Test + Prod)     │   │
│  │ Prisma,     │ Creates │             │ Status  │                     │   │
│  │ Security    │ Tickets │             │ Updates │                     │   │
│  │ Hub)        │         │             │         │                     │   │
│  └─────────────┘         └──────┬──────┘         └──────────┬──────────┘   │
│                                 │                           │              │
│                                 │ API                       │ Boto3        │
│                                 │                           │              │
├─────────────────────────────────┼───────────────────────────┼──────────────┤
│                           PATCHWEAVE SYSTEM                 │              │
│                                 │                           │              │
│                                 ▼                           ▼              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                                                                      │  │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │  │
│  │   │ Jira Client │───▶│ Tokenizer   │───▶│ Analyzer Agent          │ │  │
│  │   │ (jira-python)│    │             │    │                         │ │  │
│  │   └─────────────┘    └─────────────┘    └───────────┬─────────────┘ │  │
│  │                                                     │               │  │
│  │                                                     ▼               │  │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │  │
│  │   │ Deployment  │◀───│ Validation  │◀───│ ChromaDB + Playbook     │ │  │
│  │   │ Agent       │    │ Workflow    │    │ Verification Agent      │ │  │
│  │   └─────────────┘    └─────────────┘    └─────────────────────────┘ │  │
│  │                                                                      │  │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │  │
│  │   │ FastAPI     │    │ Structured  │    │ Finding Queue           │ │  │
│  │   │ REST API    │    │ Logging     │    │ (FIFO)                  │ │  │
│  │   └─────────────┘    └─────────────┘    └─────────────────────────┘ │  │
│  │                                                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2.2 Complete Component Breakdown

### 2.2.1 Ingestion Layer

#### Jira Client

**Purpose**: Interface between PatchWeave and Jira for bidirectional communication.

**Responsibilities**:
- Poll Jira for new tickets in OPEN status
- Read ticket details (title, description, custom fields)
- Update ticket status through the 12-state workflow
- Post comments with validation results and approval requests
- Fetch ticket status to detect approval/rejection

**Technology**: jira-python (official Atlassian-supported library)

**Interfaces**:
| Operation | Direction | Data |
|-----------|-----------|------|
| Fetch new tickets | Jira → PatchWeave | Ticket metadata, description |
| Update status | PatchWeave → Jira | New status value |
| Post comment | PatchWeave → Jira | Markdown-formatted text |
| Read status | Jira → PatchWeave | Current status value |

**Configuration**:
```
JIRA_BASE_URL: Jira instance URL
JIRA_EMAIL: Service account email
JIRA_API_TOKEN: API authentication token
JIRA_PROJECT_KEY: Project to monitor
JIRA_POLL_INTERVAL_SECONDS: Polling frequency (default: 60)
```

---

#### Tokenizer (Sanitization Module)

**Purpose**: Protect sensitive data from LLM exposure while preserving information needed for deployment.

**Responsibilities**:
- Identify sensitive values in ticket data (account IDs, resource ARNs, etc.)
- Replace sensitive values with tokens (e.g., `{{ACCOUNT_ID}}`)
- Store token-to-value mappings securely in memory
- Provide token substitution service for deployment phase

**Token Types**:
| Token | Pattern | Example Original | Example Tokenized |
|-------|---------|------------------|-------------------|
| `{{ACCOUNT_ID}}` | 12-digit number | `123456789012` | `{{ACCOUNT_ID}}` |
| `{{AWS_REGION}}` | AWS region code | `us-east-1` | `{{AWS_REGION}}` |
| `{{RESOURCE_ARN}}` | ARN format | `arn:aws:s3:::my-bucket` | `{{RESOURCE_ARN}}` |
| `{{BUCKET_NAME}}` | S3 bucket name | `prod-logs-bucket` | `{{BUCKET_NAME}}` |
| `{{INSTANCE_ID}}` | EC2 instance ID | `i-0abcd1234efgh5678` | `{{INSTANCE_ID}}` |
| `{{SECURITY_GROUP_ID}}` | SG ID | `sg-0123456789abcdef0` | `{{SECURITY_GROUP_ID}}` |
| `{{VPC_ID}}` | VPC ID | `vpc-0123456789abcdef0` | `{{VPC_ID}}` |
| `{{DB_INSTANCE_ID}}` | RDS identifier | `prod-database` | `{{DB_INSTANCE_ID}}` |

**Data Flow**:
```
Raw Ticket Data
    │
    ▼
┌─────────────────────────────────────────┐
│ Tokenizer                               │
│ ┌─────────────────────────────────────┐ │
│ │ 1. Regex pattern matching           │ │
│ │ 2. Replace with tokens              │ │
│ │ 3. Store mapping: token → value     │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
    │
    ├──────────────────────┐
    ▼                      ▼
Sanitized Data         Token Mapping
(safe for LLM)         (secure storage)
```

---

### 2.2.2 Analysis Layer

#### Analyzer Agent

**Purpose**: Transform unstructured Jira ticket content into structured, actionable data.

**Responsibilities**:
- Parse ticket title and description
- Classify vulnerability using fixed taxonomy
- Extract resource metadata
- Generate optimized search query for ChromaDB
- Assess analysis confidence

**Technology**: LangGraph agent with LLM backbone

**Input**: Sanitized ticket data from Tokenizer

**Output**: `AnalyzedFinding` structured object

**Fixed Vulnerability Taxonomy**:
```python
VULNERABILITY_TYPES = [
    "s3_public_access",
    "s3_encryption_disabled",
    "security_group_open_ssh",
    "security_group_open_rdp",
    "ebs_unencrypted",
    "rds_publicly_accessible",
    "rds_unencrypted",
    "cloudtrail_disabled",
    "vpc_flow_logs_disabled",
    "iam_root_account_usage",
    "unknown"  # Fallback for unclassified findings
]
```

**Classification Logic**:
1. LLM analyzes sanitized description
2. Maps to known taxonomy type
3. If no confident match → `"unknown"`
4. Unknown findings rely purely on semantic search

---

### 2.2.3 Knowledge Layer

#### ChromaDB Knowledge Base

**Purpose**: Store and retrieve remediation playbooks using semantic similarity.

**Responsibilities**:
- Store playbook embeddings and metadata
- Perform semantic similarity search
- Return ranked matches with similarity scores
- Support playbook CRUD operations

**Technology**: ChromaDB (vector database)

**Storage Schema**:
```
Collection: playbooks
├── id: UUID
├── embedding: vector (from search_text)
├── metadata:
│   ├── name: string
│   ├── vulnerability_type: string
│   ├── cloud_provider: string
│   ├── resource_type: string
│   ├── severity: string
│   ├── created_at: datetime
│   ├── version: string
│   └── required_permissions: list[string]
└── document: full playbook YAML
```

**Search Behavior**:
```python
# Query ChromaDB
results = collection.query(
    query_embeddings=[finding_embedding],
    n_results=5,
    include=["documents", "metadatas", "distances"]
)

# Convert distance to similarity (ChromaDB uses L2 distance)
similarity = 1 / (1 + distance)
```

---

#### Three-Tier Matching Logic

**Purpose**: Route findings based on playbook match confidence.

| Similarity Score | Action | Rationale |
|------------------|--------|-----------|
| **≥ 90%** | Proceed directly to Validation | High confidence; exact or near-exact match |
| **70% - 89%** | Route to Playbook Verification Agent | Moderate confidence; needs review |
| **< 70%** | Mark as NO PLAYBOOK; escalate | Low confidence; no suitable playbook exists |

**Multiple Match Handling**:
- If multiple playbooks score ≥ 90%, use highest similarity
- If multiple playbooks in 70-89% range, Verification Agent reviews top match

---

#### Playbook Verification Agent

**Purpose**: Lightweight review of moderate-confidence playbook matches.

**Responsibilities**:
- Analyze if retrieved playbook logically matches the finding
- Make go/no-go decision before expensive validation
- Does NOT execute any code—semantic/logical check only

**Technology**: LangGraph agent with LLM backbone

**Input**:
- `AnalyzedFinding` from Analyzer Agent
- Candidate playbook from ChromaDB

**Output**:
- `APPROVED`: Playbook matches; proceed to validation
- `REJECTED`: Playbook does not match; escalate as NO PLAYBOOK

**Decision Criteria**:
1. Does vulnerability type align?
2. Does resource type match?
3. Does remediation action address the finding?
4. Are there any obvious mismatches?

---

### 2.2.4 Validation Layer

#### Validation Workflow (LangGraph Orchestrated)

**Purpose**: Safely test remediation code before production deployment.

**Sub-Agents**:

| Agent | Responsibility |
|-------|----------------|
| **Orchestrator Agent** | Coordinates validation sequence; manages state |
| **Environment Replication Agent** | Generates Terraform to create test environment |
| **Pre-Remediation Verification Agent** | Confirms vulnerability exists in test |
| **Remediation Executor** | Applies playbook code in test environment |
| **Post-Remediation Verification Agent** | Confirms fix resolved the issue |
| **Cleanup Agent** | Destroys all test infrastructure |

**Execution Environment**:
- **Development**: LocalStack (local AWS simulation)
- **Production/Demo**: Dedicated AWS Test Account (when funded)

**Fail-Fast Behavior**:
```python
try:
    environment = create_test_environment()    # Terraform apply
    verify_vulnerability_exists(environment)   # Pre-check
    apply_remediation(environment, playbook)   # Execute fix
    verify_fix_worked(environment)             # Post-check
except Exception as failure:
    escalate_to_jira(finding_id, failure)
    raise
finally:
    cleanup_environment(environment)           # ALWAYS executes
```

**Critical Invariant**: Cleanup ALWAYS runs, regardless of success or failure.

---

### 2.2.5 Approval Layer

#### Human Approval Mechanism

**Purpose**: Ensure human oversight before any production changes.

**Implementation**: Jira status transitions with polling detection

**Approval Request Format** (posted as Jira comment):
```markdown
## PatchWeave Remediation Approval Request

**Finding**: S3 bucket with public access enabled
**Resource**: {{BUCKET_NAME}} in {{AWS_REGION}}
**Severity**: Critical

### Validation Results ✅
- Pre-check: Vulnerability confirmed in test environment
- Remediation: Applied successfully
- Post-check: Fix verified working
- Cleanup: Test environment destroyed

### Remediation Code
```python
s3.put_public_access_block(
    Bucket='{{BUCKET_NAME}}',
    PublicAccessBlockConfiguration={...}
)
```

### Actions
- Transition to **Approved** to deploy
- Transition to **Rejected** to cancel (add reason in comment)
```

**Detection Mechanism**:
- PatchWeave polls Jira every 60 seconds
- Checks for status transition from PENDING APPROVAL
- On APPROVED: Proceed to deployment
- On REJECTED: Log rejection reason, end pipeline

**Timeout Policy**: None (wait indefinitely for human decision)

---

### 2.2.6 Deployment Layer

#### Deployment Agent

**Purpose**: Apply validated, approved remediations to production cloud environment.

**Responsibilities**:
- Substitute tokens with actual values
- Execute Python/Boto3 remediation code
- Capture execution results
- Update Jira with deployment outcome
- Store successful remediation in ChromaDB

**Token Substitution**:
```python
def substitute_tokens(code: str, token_mapping: dict) -> str:
    result = code
    for token, value in token_mapping.items():
        result = result.replace(f"{{{{{token}}}}}", value)
    return result

# Example:
# Input:  s3.put_public_access_block(Bucket='{{BUCKET_NAME}}')
# Output: s3.put_public_access_block(Bucket='prod-logs-bucket')
```

**Execution**:
```python
# Remediation code is executed with production AWS credentials
exec(substituted_code, {"boto3": boto3, "__builtins__": {}})
```

**Post-Deployment**:
1. Update Jira status to RESOLVED
2. Post success comment with execution details
3. Store finding + playbook association in ChromaDB for future matching

---

### 2.2.7 Supporting Components

#### Finding Queue

**Purpose**: Manage incoming findings for sequential processing.

**Implementation**: Simple FIFO queue

```python
class FindingQueue:
    def __init__(self):
        self._queue = []
    
    def add(self, finding: AnalyzedFinding):
        self._queue.append(finding)
    
    def next(self) -> Optional[AnalyzedFinding]:
        if self._queue:
            return self._queue.pop(0)
        return None
    
    def size(self) -> int:
        return len(self._queue)
```

**Behavior**:
- Strict FIFO ordering
- One finding processed at a time
- No priority ordering (Phase 1)
- No concurrency (Phase 1)

---

#### FastAPI REST API

**Purpose**: Provide programmatic access to system status and operations.

**Endpoints**:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Health check |
| GET | `/queue` | Queue status (pending count, current processing) |
| GET | `/findings/{finding_id}` | Individual finding status |
| GET | `/playbooks` | List all playbooks |
| GET | `/playbooks/{playbook_id}` | Playbook details |
| GET | `/stats` | System statistics |
| POST | `/findings/{finding_id}/retry` | Re-queue finding for processing |

**Documentation**: Auto-generated Swagger UI at `/docs`

---

#### Structured Logging

**Purpose**: Comprehensive observability with audit trail.

**Implementation**: `structlog` with JSON output to console + file

**Log Categories**:
| Category | Events | Level |
|----------|--------|-------|
| Pipeline | Finding received, status transitions, completion | INFO |
| Agents | Agent start/end, decisions, confidence scores | INFO |
| ChromaDB | Searches, match scores, results | DEBUG |
| Validation | Environment lifecycle, check results | INFO |
| Approval | Requests, approvals, rejections | INFO (Audit) |
| Deployment | Start, success/failure, resources modified | INFO (Audit) |
| Errors | Exceptions, failures | ERROR |

**Audit Trail**: Events marked `_audit=True` for compliance.

---

## 2.3 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                       │
└─────────────────────────────────────────────────────────────────────────────┘

[1] CSPM Tool creates Jira Ticket
         │
         ▼
┌─────────────────┐
│ Raw Ticket Data │
│ • Title         │
│ • Description   │
│ • Custom fields │
└────────┬────────┘
         │
         ▼
[2] Jira Client fetches ticket
         │
         ▼
[3] Tokenizer sanitizes data
         │
         ├─────────────────────────────────────┐
         ▼                                     ▼
┌─────────────────┐                 ┌─────────────────┐
│ Sanitized Data  │                 │ Token Mapping   │
│ (LLM-safe)      │                 │ (secure store)  │
└────────┬────────┘                 └────────┬────────┘
         │                                   │
         ▼                                   │
[4] Analyzer Agent processes                 │
         │                                   │
         ▼                                   │
┌─────────────────────┐                      │
│ AnalyzedFinding     │                      │
│ • finding_id        │                      │
│ • vulnerability_type│                      │
│ • search_query      │                      │
│ • tokens (keys)     │                      │
│ • sanitized_desc    │                      │
└────────┬────────────┘                      │
         │                                   │
         ▼                                   │
[5] ChromaDB semantic search                 │
         │                                   │
         ├──────────────────┬────────────────┤
         ▼                  ▼                │
    ≥90% match         70-89% match          │
         │                  │                │
         │                  ▼                │
         │        [6] Verification Agent     │
         │                  │                │
         │         ┌───────┴───────┐         │
         │         ▼               ▼         │
         │      Approved       Rejected      │
         │         │               │         │
         ▼         ▼               ▼         │
┌─────────────────────┐    ┌──────────────┐  │
│ Matched Playbook    │    │ NO PLAYBOOK  │  │
│ • playbook_id       │    │ (escalate)   │  │
│ • remediation_code  │    └──────────────┘  │
│ • pre_check_code    │                      │
│ • post_check_code   │                      │
└────────┬────────────┘                      │
         │                                   │
         ▼                                   │
[7] Validation Workflow                      │
         │                                   │
         ▼                                   │
┌─────────────────────┐                      │
│ ValidationResult    │                      │
│ • pre_check: ✓      │                      │
│ • remediation: ✓    │                      │
│ • post_check: ✓     │                      │
│ • cleanup: ✓        │                      │
└────────┬────────────┘                      │
         │                                   │
         ▼                                   │
[8] Human Approval (Jira)                    │
         │                                   │
         ├──────────────────┐                │
         ▼                  ▼                │
     Approved           Rejected             │
         │                  │                │
         │                  ▼                │
         │           ┌──────────────┐        │
         │           │ REJECTED     │        │
         │           │ (end state)  │        │
         │           └──────────────┘        │
         ▼                                   │
[9] Deployment Agent ◀───────────────────────┘
         │                    (token mapping retrieved)
         ▼
┌─────────────────────┐
│ Substituted Code    │
│ (real values)       │
└────────┬────────────┘
         │
         ▼
[10] Execute on Production AWS
         │
         ▼
┌─────────────────────┐
│ DeploymentResult    │
│ • status: success   │
│ • resources_changed │
└────────┬────────────┘
         │
         ├─────────────────────────────────────┐
         ▼                                     ▼
[11] Update Jira: RESOLVED          [12] Store in ChromaDB
                                    (finding → playbook association)
```

---

## 2.4 State Transition Diagram (Jira Workflow)

```
                                    ┌─────────────┐
                                    │    OPEN     │ ◀─── Ticket created by CSPM
                                    └──────┬──────┘
                                           │
                               PatchWeave picks up ticket
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │  ANALYZING  │
                                    └──────┬──────┘
                                           │
                                  Analyzer completes
                                           │
                                           ▼
                                    ┌──────────────────┐
                                    │ PLAYBOOK SEARCH  │
                                    └──────┬───────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
                 <70%                   70-89%                  ≥90%
                    │                      │                      │
                    ▼                      ▼                      │
             ┌─────────────┐        ┌─────────────┐               │
             │ NO PLAYBOOK │        │  VERIFYING  │               │
             └─────────────┘        └──────┬──────┘               │
                   ▲                       │                      │
                   │              ┌────────┴────────┐             │
                   │              ▼                 ▼             │
                   │          Rejected          Approved          │
                   │              │                 │             │
                   └──────────────┘                 │             │
                                                   │             │
                                    ┌──────────────┴─────────────┘
                                    │
                                    ▼
                             ┌─────────────┐
                             │ VALIDATING  │
                             └──────┬──────┘
                                    │
                         ┌──────────┴──────────┐
                         ▼                     ▼
                     Success               Failure
                         │                     │
                         ▼                     ▼
              ┌───────────────────┐    ┌──────────────────┐
              │ PENDING APPROVAL  │    │ VALIDATION FAILED│
              └─────────┬─────────┘    └──────────────────┘
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
         Approved              Rejected
             │                     │
             ▼                     ▼
      ┌─────────────┐       ┌─────────────┐
      │  DEPLOYING  │       │  REJECTED   │
      └──────┬──────┘       └─────────────┘
             │
    ┌────────┴────────┐
    ▼                 ▼
 Success           Failure
    │                 │
    ▼                 ▼
┌─────────────┐  ┌───────────────────┐
│  RESOLVED   │  │ DEPLOYMENT FAILED │
└─────────────┘  └───────────────────┘
```

**Terminal States**:
- `RESOLVED`: Success - finding remediated
- `REJECTED`: Human rejected the remediation
- `NO PLAYBOOK`: No suitable playbook; requires manual handling
- `VALIDATION FAILED`: Playbook validation failed; requires investigation
- `DEPLOYMENT FAILED`: Production deployment failed; requires investigation

---

## 2.5 Error Handling Strategy

### Fail-Fast Principle

PatchWeave implements a **fail-fast with mandatory cleanup** strategy:

1. **Any failure immediately stops the pipeline**
2. **Failure details are escalated to Jira**
3. **Test environment cleanup ALWAYS executes**
4. **No automatic retries** (Phase 1)

### Error Categories and Responses

| Error Category | Example | Response | Jira Status |
|----------------|---------|----------|-------------|
| **Jira API Error** | Connection timeout | Log error, retry on next poll cycle | No change |
| **Analysis Failure** | LLM parsing error | Escalate with error details | VALIDATION FAILED |
| **ChromaDB Error** | Database unavailable | Escalate; system cannot function | VALIDATION FAILED |
| **Terraform Error** | Resource creation failed | Cleanup, escalate | VALIDATION FAILED |
| **Pre-Check Failure** | Vulnerability not reproduced | Cleanup, escalate | VALIDATION FAILED |
| **Remediation Error** | Boto3 API error in test | Cleanup, escalate | VALIDATION FAILED |
| **Post-Check Failure** | Fix didn't work | Cleanup, escalate | VALIDATION FAILED |
| **Cleanup Failure** | Resources not deleted | **CRITICAL ALERT** + manual intervention | Status unchanged |
| **Deployment Error** | Production API error | Escalate | DEPLOYMENT FAILED |

### Cleanup Failure Handling

Cleanup failures are treated as **critical** because orphaned cloud resources:
- Incur ongoing costs
- May pose security risks
- Indicate system malfunction

```python
try:
    cleanup_environment(environment)
except CleanupError as e:
    log.critical("cleanup_failed", 
                 environment_id=environment.id,
                 error=str(e),
                 _audit=True)
    # Alert operations team
    send_critical_alert(f"CLEANUP FAILED: {environment.id}")
    # Continue - do not block pipeline, but ensure visibility
```

---

## 2.6 Scalability Considerations

### Phase 1 Constraints

| Aspect | Phase 1 Approach | Limitation |
|--------|------------------|------------|
| **Concurrency** | Sequential (1 at a time) | ~48 findings/day max |
| **Queue** | In-memory FIFO | Lost on restart |
| **ChromaDB** | Single instance | No replication |
| **API** | Single FastAPI instance | Limited request capacity |

### Phase 2 Scalability Enhancements (Planned)

| Enhancement | Benefit |
|-------------|---------|
| Priority queue | Critical findings first |
| Parallel validation (N=3) | 3x throughput |
| Persistent queue (Redis) | Survive restarts |
| ChromaDB clustering | High availability |
| Load-balanced API | Handle more clients |

### Theoretical Throughput

| Mode | Processing Time | Daily Capacity |
|------|-----------------|----------------|
| Sequential (Phase 1) | ~30 min/finding | ~48 findings |
| Parallel N=3 (Phase 2) | ~30 min/3 findings | ~144 findings |
| Parallel N=10 (Future) | ~30 min/10 findings | ~480 findings |

---

## 2.7 Security Considerations

### Threat Model

| Threat | Mitigation |
|--------|------------|
| **LLM prompt injection** | Tokenization removes sensitive data before LLM processing |
| **Credential exposure** | Environment variables, never logged, separate test/prod creds |
| **Malicious playbook code** | Human approval required; validation in isolated environment |
| **Test environment escape** | Separate AWS account (when funded); LocalStack for dev |
| **Unauthorized deployment** | Jira approval with permission controls |
| **Audit log tampering** | Append-only file logging; `_audit=True` events |

### Credential Isolation

```
┌─────────────────────────────────────────────────────────────────┐
│                     CREDENTIAL BOUNDARIES                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐      ┌─────────────────┐                  │
│  │ JIRA_API_TOKEN  │      │ AWS_TEST_*      │                  │
│  │                 │      │                 │                  │
│  │ • Read tickets  │      │ • LocalStack    │                  │
│  │ • Update status │      │ • Test account  │                  │
│  │ • Post comments │      │ • Validation    │                  │
│  └─────────────────┘      └─────────────────┘                  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ AWS_PROD_*                                               │   │
│  │                                                          │   │
│  │ • Production account                                     │   │
│  │ • Used ONLY by Deployment Agent                          │   │
│  │ • Used ONLY after human approval                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Least Privilege IAM

Playbooks document required IAM permissions. Production IAM roles should grant only the permissions needed by the playbooks in use.

Example for S3 playbooks:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetPublicAccessBlock",
                "s3:PutPublicAccessBlock",
                "s3:GetBucketEncryption",
                "s3:PutBucketEncryption"
            ],
            "Resource": "*"
        }
    ]
}
```

---

*End of Section 2: Final System Architecture*

---

# 3. Architectural & Technical Decisions

This section documents all architectural and technical decisions made during the design phase. Each decision includes alternatives considered, rationale, trade-offs, and impact analysis.

---

## Decision 1: Project Naming

### Decision
Use **PatchWeave** as the single official project name.

### Context
Source documents used two different names:
- "CloudSafe" in one technical document
- "PatchWeave" in academic documents (report and presentation)

### Alternatives Considered

| Option | Description |
|--------|-------------|
| **A: PatchWeave** | Use academic name consistently |
| **B: CloudSafe** | Use industry-focused name |
| **C: Dual naming** | Different names for different contexts |
| **D: Combined** | "PatchWeave (CloudSafe)" or vice versa |

### Rationale
- This is a university capstone project—academic consistency matters for grading
- PatchWeave is more distinctive and memorable
- The name should match submitted academic documents
- Avoids confusion for evaluators

### Trade-offs
| Aspect | Impact |
|--------|--------|
| **Academic alignment** | ✅ Consistent with submissions |
| **Branding** | Neutral - PatchWeave is equally professional |
| **Codebase** | All code uses PatchWeave naming |

### Impact Analysis
| Dimension | Impact |
|-----------|--------|
| Scalability | None |
| Security | None |
| Maintainability | Positive - single consistent name |
| Cost | None |

---

## Decision 2: Sanitization Strategy

### Decision
Use **Tokenization** approach—replace sensitive values with placeholders like `{{ACCOUNT_ID}}`, `{{BUCKET_NAME}}`, etc., and substitute back before deployment.

### Context
The system must sanitize sensitive data before LLM processing for safety, but the Deployment Agent needs actual values to apply fixes to production.

### Alternatives Considered

| Option | Description |
|--------|-------------|
| **A: Metadata Separation** | Store sensitive data in separate secure store, rejoin at deployment |
| **B: Tokenization** | Replace with tokens, substitute at deployment |
| **C: Late Binding** | Sanitize for analysis only, re-fetch original data at deployment |
| **D: Scoped Sanitization** | Only sanitize LLM prompts, keep full data in internal objects |

### Rationale
- Simplest to implement for a university project
- Single data object flows through entire pipeline (easier debugging)
- Clear pattern that's well-understood
- Generated remediation code naturally includes tokens
- Token substitution is straightforward string replacement

### Trade-offs
| Aspect | Impact |
|--------|--------|
| **Simplicity** | ✅ Very simple implementation |
| **Security** | ✅ Sensitive data never reaches LLM |
| **Debugging** | ✅ Can trace data flow with tokens visible |
| **Risk** | ⚠️ Tokens could leak in logs (mitigated by careful logging) |

### Impact Analysis
| Dimension | Impact |
|-----------|--------|
| Scalability | Neutral - token map grows linearly with findings |
| Security | Positive - clear data isolation |
| Maintainability | Positive - simple, understandable pattern |
| Cost | None |

### Implementation Pattern
```python
# Tokenization
sanitized = "S3 bucket {{BUCKET_NAME}} in {{AWS_REGION}}"
token_map = {
    "BUCKET_NAME": "prod-logs-bucket",
    "AWS_REGION": "us-east-1"
}

# Substitution at deployment
for token, value in token_map.items():
    code = code.replace(f"{{{{{token}}}}}", value)
```

---

## Decision 3: Failure Handling Strategy

### Decision
Implement **Fail-Fast with Manual Escalation** and **always attempt cleanup** of test environments regardless of where failure occurred.

### Context
The validation workflow has multiple failure points (Terraform, pre-check, remediation, post-check, cleanup). A strategy is needed for handling failures.

### Alternatives Considered

| Option | Description |
|--------|-------------|
| **A: Fail-Fast** | Stop immediately on any failure, escalate to human |
| **B: Retry with Backoff** | Automatic retry with exponential backoff, then escalate |
| **C: Selective Retry** | Retry transient failures, escalate logic failures |
| **D: Full Rollback** | Execute compensating actions to restore state |

### Rationale
- Simplest to implement correctly
- Predictable behavior for debugging and demos
- Avoids complexity of retry logic and failure classification
- Human intervention ensures correct resolution
- **Critical**: Cleanup always runs to prevent cost leaks and orphaned resources

### Trade-offs
| Aspect | Impact |
|--------|--------|
| **Simplicity** | ✅ Very simple implementation |
| **Self-healing** | ❌ No automatic recovery |
| **Human load** | ⚠️ Every failure needs human attention |
| **Resource safety** | ✅ Cleanup always attempted |

### Impact Analysis
| Dimension | Impact |
|-----------|--------|
| Scalability | Negative - humans become bottleneck on failures |
| Security | Positive - no automated retry of potentially harmful actions |
| Maintainability | Positive - simple, predictable behavior |
| Cost | Positive - aggressive cleanup prevents resource leaks |

### Implementation Pattern
```python
try:
    create_environment()
    verify_pre_remediation()
    apply_remediation()
    verify_post_remediation()
except Exception as failure:
    escalate_to_jira(finding_id, failure_details)
    raise
finally:
    cleanup_environment()  # ALWAYS runs
```

---

## Decision 4: Test Environment Isolation

### Decision
Use **LocalStack** for development and testing. Architect for easy transition to **Dedicated AWS Test Account** when funding is available.

### Context
Validation requires creating temporary cloud environments to safely test remediations. The approach for isolation must be defined.

### Alternatives Considered

| Option | Description |
|--------|-------------|
| **A: Same Account, Separate VPC** | Isolated VPC within same AWS account |
| **B: Dedicated Test Account** | Separate AWS account for validation |
| **C: LocalStack/Mocking** | Local AWS simulation |
| **D: On-Demand Sandbox** | Temporary AWS accounts per validation |

### Rationale
- LocalStack is free—critical for budget-constrained capstone project
- Fast iteration during development (no cloud latency)
- Architecture abstracted so switching to real AWS is configuration change
- Demonstrates cloud interaction without cloud costs
- Real AWS validation can be added when funding available

### Trade-offs
| Aspect | Impact |
|--------|--------|
| **Cost** | ✅ Zero cloud cost for development |
| **Speed** | ✅ Fast local execution |
| **Fidelity** | ⚠️ LocalStack may differ from real AWS |
| **Demo credibility** | ⚠️ "Worked on LocalStack" is weaker than real AWS |

### Impact Analysis
| Dimension | Impact |
|-----------|--------|
| Scalability | Positive - LocalStack handles any volume locally |
| Security | Positive - no real cloud resources at risk |
| Maintainability | Positive - easy local development |
| Cost | Positive - zero cloud spend for development |

### Implementation Pattern
```python
# Configuration-driven environment selection
if config.PATCHWEAVE_ENV == "development":
    endpoint_url = config.LOCALSTACK_ENDPOINT  # http://localhost:4566
else:
    endpoint_url = None  # Use real AWS

s3 = boto3.client('s3', endpoint_url=endpoint_url)
```

---

## Decision 5: Knowledge Base Match Threshold

### Decision
Implement **three-tier matching**:
- **≥90%**: Proceed directly to validation
- **70-90%**: Route to Playbook Verification Agent
- **<70%**: No playbook exists, escalate

Additionally, a **Playbook Verification Agent** reviews moderate-confidence matches before validation.

### Context
ChromaDB returns similarity scores for playbook matches. A threshold strategy is needed to determine when to use a match vs. escalate.

### Alternatives Considered

| Option | Threshold | Description |
|--------|-----------|-------------|
| **A: High** | ≥90% | Only near-exact matches |
| **B: Medium** | ≥80% | Balanced approach |
| **C: Low** | ≥70% | Aggressive matching |
| **D: Adaptive** | Variable | Start high, lower if no match |

### Rationale
- 90% threshold provides high confidence for direct processing
- 70-90% range gets additional verification (safety net)
- <70% means no suitable playbook—better to escalate than guess
- Verification Agent is lightweight—semantic check, not execution
- Clear decision boundaries reduce ambiguity

### Trade-offs
| Aspect | Impact |
|--------|--------|
| **Safety** | ✅ Three-tier provides multiple checkpoints |
| **Throughput** | ⚠️ 70-90% range adds verification step |
| **Accuracy** | ✅ Verification catches mismatches |
| **Complexity** | ⚠️ Additional agent to implement |

### Impact Analysis
| Dimension | Impact |
|-----------|--------|
| Scalability | Slight negative - verification adds latency |
| Security | Positive - reduces wrong playbook application |
| Maintainability | Neutral - clear logic, one more component |
| Cost | Neutral - verification is fast LLM call |

---

## Decision 6: Phase 1 Scope

### Decision
Phase 1 includes **Deployment Agent with real execution** and **real AWS validation environment** (when funded). Multi-cloud support is Phase 2.

### Context
Documents had conflicting definitions of Phase 1 vs Phase 2 scope. Clear boundaries needed.

### Phase 1 Scope (Confirmed)
| Component | Included |
|-----------|----------|
| Jira ingestion | ✅ |
| Tokenization/Sanitization | ✅ |
| Analyzer Agent | ✅ |
| ChromaDB + semantic search | ✅ |
| Three-tier matching | ✅ |
| Playbook Verification Agent | ✅ |
| Validation Workflow | ✅ |
| Real AWS validation | ✅ |
| Human approval via Jira | ✅ |
| Deployment Agent (real) | ✅ |
| FastAPI REST API | ✅ |
| Structured logging | ✅ |

### Phase 2 Scope (Deferred)
| Component | Status |
|-----------|--------|
| Dynamic playbook generation | Deferred |
| Multi-cloud (Azure, GCP) | Deferred |
| Priority queue | Deferred |
| Concurrent processing | Deferred |
| Full web dashboard | Deferred |
| Centralized logging | Deferred |

### Rationale
- Complete end-to-end flow demonstrates full system capability
- Real deployment is the ultimate proof of value
- Multi-cloud adds significant complexity without changing core architecture
- Phase 1 is ambitious but achievable for capstone

### Impact Analysis
| Dimension | Impact |
|-----------|--------|
| Scalability | Deferred to Phase 2 |
| Security | Real deployment requires careful credential management |
| Maintainability | Clear phase boundary aids planning |
| Cost | Real AWS usage when funded |

---

## Decision 7: Knowledge Base Seeding

### Decision
**Manual Curation** of 10-15 remediation playbooks for common AWS misconfigurations.

### Context
ChromaDB needs initial playbooks before the system can function. Strategy for populating the knowledge base is needed.

### Alternatives Considered

| Option | Description |
|--------|-------------|
| **A: Manual Curation** | Team writes and tests playbooks |
| **B: Import Existing** | Convert from public sources |
| **C: Synthetic Generation** | LLM generates initial playbooks |
| **D: Hybrid** | Manual core + imported supplementary |

### Rationale
- Guarantees high quality—team verifies each playbook
- Team deeply understands playbook format through creation
- Ensures demo works perfectly with known playbooks
- Avoids quality issues from unverified external sources
- Does not use LLM generation (would undermine project premise)

### Target Playbooks (10-15)

| # | Vulnerability Type | Description |
|---|-------------------|-------------|
| 1 | `s3_public_access` | Block public access on S3 buckets |
| 2 | `s3_encryption_disabled` | Enable S3 bucket encryption |
| 3 | `security_group_open_ssh` | Remove 0.0.0.0/0 SSH access |
| 4 | `security_group_open_rdp` | Remove 0.0.0.0/0 RDP access |
| 5 | `ebs_unencrypted` | Document EBS encryption requirement |
| 6 | `rds_publicly_accessible` | Disable RDS public accessibility |
| 7 | `rds_unencrypted` | Enable RDS encryption |
| 8 | `cloudtrail_disabled` | Enable CloudTrail logging |
| 9 | `vpc_flow_logs_disabled` | Enable VPC Flow Logs |
| 10 | `iam_root_account_usage` | Alert-only (no auto-fix) |

### Trade-offs
| Aspect | Impact |
|--------|--------|
| **Quality** | ✅ Highest quality, verified |
| **Quantity** | ⚠️ Limited to team capacity |
| **Expertise required** | ⚠️ Team needs AWS knowledge |
| **Time investment** | ⚠️ Significant upfront effort |

### Impact Analysis
| Dimension | Impact |
|-----------|--------|
| Scalability | Limited by manual creation rate |
| Security | Positive - verified, trusted playbooks |
| Maintainability | Positive - team owns and understands all playbooks |
| Cost | Team time only |

---

## Decision 8: Playbook Code Format

### Decision
Use **Python/Boto3 scripts** as the remediation code format, stored in YAML playbook files.

### Context
Playbooks need a code format that can be executed for remediation. Options include Python, Terraform, AWS CLI, or Lambda functions.

### Alternatives Considered

| Option | Description |
|--------|-------------|
| **A: Python/Boto3** | Python scripts using AWS SDK |
| **B: Terraform** | Declarative IaC definitions |
| **C: AWS CLI** | Shell commands |
| **D: Lambda** | Deployable Lambda functions |
| **E: Multi-Format** | Support multiple formats |

### Rationale
- PatchWeave is already Python-based (consistency)
- Boto3 is the standard AWS SDK with full service coverage
- Easy to test locally with LocalStack
- Team has Python experience
- Token substitution is trivial string replacement
- Error handling and logging are straightforward

### Playbook Schema
```yaml
playbook:
  id: string (UUID)
  name: string
  description: string
  vulnerability_type: string
  cloud_provider: "AWS"
  resource_type: string
  severity: string
  search_text: string  # For embedding
  remediation_code: string  # Python/Boto3
  pre_check_code: string
  post_check_code: string
  created_at: datetime
  created_by: string
  version: string
  required_permissions: list[string]
  estimated_execution_time: int
```

### Trade-offs
| Aspect | Impact |
|--------|--------|
| **Flexibility** | ✅ Full SDK access |
| **Testability** | ✅ Easy unit testing |
| **Runtime requirement** | ⚠️ Needs Python environment |
| **Safety** | ⚠️ Arbitrary code execution |

### Impact Analysis
| Dimension | Impact |
|-----------|--------|
| Scalability | Neutral |
| Security | Requires sandboxing for execution |
| Maintainability | Positive - single language |
| Cost | None |

---

## Decision 9: Analyzer Output Schema

### Decision
Use **Fixed Taxonomy** for vulnerability type classification. Analyzer maps findings to predefined types.

### Context
The Analyzer Agent must classify findings consistently for playbook matching.

### Alternatives Considered

| Option | Description |
|--------|-------------|
| **A: Fixed Taxonomy** | Predefined enum of vulnerability types |
| **B: Free-Form** | LLM generates type as free text |
| **C: Hybrid** | Try fixed mapping, fall back to free-form |

### Rationale
- Playbooks are curated with specific `vulnerability_type` values
- Fixed taxonomy enables exact-match lookup before semantic search
- Reduces LLM hallucination risk
- Unknown findings classified as `"unknown"` → pure semantic search

### Fixed Taxonomy
```python
VULNERABILITY_TYPES = [
    "s3_public_access",
    "s3_encryption_disabled",
    "security_group_open_ssh",
    "security_group_open_rdp",
    "ebs_unencrypted",
    "rds_publicly_accessible",
    "rds_unencrypted",
    "cloudtrail_disabled",
    "vpc_flow_logs_disabled",
    "iam_root_account_usage",
    "unknown"
]
```

### Analyzer Output Schema
```yaml
analyzed_finding:
  finding_id: string
  vulnerability_type: string  # From taxonomy
  cloud_provider: string
  resource_type: string
  severity: string
  search_query: string
  tokens:
    ACCOUNT_ID: string
    AWS_REGION: string
    RESOURCE_ARN: string
    # ... resource-specific tokens
  sanitized_description: string
  source_ticket_url: string
  detected_at: datetime
  analyzed_at: datetime
  analysis_confidence: float
```

### Impact Analysis
| Dimension | Impact |
|-----------|--------|
| Scalability | Positive - fast exact matching |
| Security | Positive - reduces misclassification |
| Maintainability | Taxonomy grows with playbooks |
| Cost | Slight reduction in LLM tokens |

---

## Decision 10: Human Approval Mechanism

### Decision
Use **Jira Status Transition** for approval with **polling-based detection**. Rejection requires a comment explaining the reason.

### Context
Human approval is required before production deployment. The mechanism must integrate with existing Jira workflow.

### Alternatives Considered

**Approval Mechanism**:
| Option | Description |
|--------|-------------|
| **A: Status Transition** | Jira workflow status change |
| **B: Comment Convention** | "/approve" or "/reject" comments |
| **C: Custom Field** | Dedicated Jira field |
| **D: External UI** | Separate approval dashboard |

**Detection Method**:
| Option | Description |
|--------|-------------|
| **i: Polling** | Periodic Jira API checks |
| **ii: Webhook** | Jira fires event on change |
| **iii: Manual Trigger** | Approver calls PatchWeave API |

### Rationale
- Status transitions are native Jira workflow (familiar UX)
- Clear audit trail (who transitioned when)
- Permission-controlled via Jira
- Polling is simple (no public endpoint needed)
- No timeout—human decisions shouldn't be rushed

### Approval Request Format
```markdown
## PatchWeave Remediation Approval Request

**Finding**: S3 bucket with public access enabled
**Resource**: {{BUCKET_NAME}} in {{AWS_REGION}}
**Severity**: Critical

### Validation Results ✅
- Pre-check: Vulnerability confirmed in test environment
- Remediation: Applied successfully
- Post-check: Fix verified working
- Cleanup: Test environment destroyed

### Remediation Code
[code block with playbook]

### Actions
- Transition to **Approved** to deploy
- Transition to **Rejected** to cancel (add reason in comment)
```

### Trade-offs
| Aspect | Impact |
|--------|--------|
| **UX** | ✅ Familiar Jira workflow |
| **Audit trail** | ✅ Built into Jira |
| **Latency** | ⚠️ Polling adds up to 60s delay |
| **Dependencies** | ⚠️ Requires Jira workflow configuration |

### Impact Analysis
| Dimension | Impact |
|-----------|--------|
| Scalability | Polling frequency limits responsiveness |
| Security | Jira permissions control access |
| Maintainability | Standard Jira, well-understood |
| Cost | None |

---

## Decision 11: Jira Workflow States

### Decision
Implement **Full Granularity** with all 12 Jira statuses for complete pipeline visibility.

### Context
The number and granularity of Jira statuses affects visibility and workflow configuration complexity.

### Alternatives Considered

| Option | Statuses | Description |
|--------|----------|-------------|
| **A: Full** | 12 | Complete visibility of each stage |
| **B: Simplified** | 7 | Combine intermediate steps |
| **C: Minimal** | 4 | Basic states only |

### Final Status Set
```python
JIRA_STATUSES = [
    "OPEN",               # New finding
    "ANALYZING",          # Analyzer Agent working
    "PLAYBOOK SEARCH",    # Querying ChromaDB
    "VERIFYING",          # Playbook Verification Agent
    "NO PLAYBOOK",        # No suitable playbook found
    "VALIDATING",         # Validation workflow running
    "VALIDATION FAILED",  # Validation failed
    "PENDING APPROVAL",   # Awaiting human
    "REJECTED",           # Human rejected
    "DEPLOYING",          # Deployment in progress
    "DEPLOYMENT FAILED",  # Deployment failed
    "RESOLVED"            # Success
]
```

### Rationale
- Maximum visibility into pipeline progress
- Clear audit trail for compliance
- Each status represents distinct system state
- Easy to diagnose where issues occur
- Demonstrates sophisticated workflow to evaluators

### Trade-offs
| Aspect | Impact |
|--------|--------|
| **Visibility** | ✅ Complete pipeline transparency |
| **Jira setup** | ⚠️ More complex workflow configuration |
| **Status churn** | ⚠️ Rapid status changes during processing |

### Impact Analysis
| Dimension | Impact |
|-----------|--------|
| Scalability | Neutral |
| Security | Positive - detailed audit trail |
| Maintainability | More states to handle in code |
| Cost | None |

---

## Decision 12: Concurrent Processing

### Decision
**Sequential Processing** only—one finding at a time, strict FIFO queue.

### Context
Strategy needed for handling multiple findings arriving simultaneously.

### Alternatives Considered

| Option | Description |
|--------|-------------|
| **A: Sequential** | One at a time, FIFO |
| **B: Limited Concurrency** | Process N in parallel |
| **C: Unlimited** | Process all as they arrive |
| **D: Priority Queue** | Sequential but severity-ordered |

### Rationale
- Simplest to implement correctly
- Predictable behavior for debugging and demos
- Avoids race conditions and resource contention
- Easy to demonstrate to evaluators
- Concurrency can be added in Phase 2

### Implementation
```python
class FindingQueue:
    def __init__(self):
        self._queue = []
    
    def add(self, finding):
        self._queue.append(finding)
    
    def next(self):
        return self._queue.pop(0) if self._queue else None
```

### Trade-offs
| Aspect | Impact |
|--------|--------|
| **Simplicity** | ✅ Very simple |
| **Throughput** | ❌ Limited (~48/day at 30min each) |
| **Debugging** | ✅ Easy to trace |
| **Scalability** | ❌ Serial bottleneck |

### Impact Analysis
| Dimension | Impact |
|-----------|--------|
| Scalability | Negative - fundamentally serial |
| Security | Positive - no concurrency bugs |
| Maintainability | Positive - simple logic |
| Cost | Neutral |

---

## Decision 13: Credentials Management

### Decision
Use **Environment Variables** for all credentials, loaded from `.env` file (gitignored).

### Context
PatchWeave requires credentials for Jira, AWS (test), and AWS (production).

### Alternatives Considered

| Option | Description |
|--------|-------------|
| **A: Environment Variables** | Standard env vars |
| **B: Config File** | `.env` or YAML |
| **C: AWS Secrets Manager** | Cloud-native secret storage |
| **D: HashiCorp Vault** | Dedicated secrets management |
| **E: Mixed** | Env for dev, Secrets Manager for prod |

### Rationale
- Simplest approach that works everywhere
- Standard practice for containerized/cloud applications
- No additional infrastructure needed
- Works identically on laptops and demo servers
- Document that production would use Secrets Manager

### Required Environment Variables
```bash
# Jira Configuration
JIRA_BASE_URL=
JIRA_EMAIL=
JIRA_API_TOKEN=
JIRA_PROJECT_KEY=

# AWS Test Environment
AWS_TEST_ACCESS_KEY_ID=
AWS_TEST_SECRET_ACCESS_KEY=
AWS_TEST_REGION=

# AWS Production Environment
AWS_PROD_ACCESS_KEY_ID=
AWS_PROD_SECRET_ACCESS_KEY=
AWS_PROD_REGION=

# LocalStack
LOCALSTACK_ENDPOINT=http://localhost:4566

# Application
PATCHWEAVE_ENV=development
LOG_LEVEL=INFO
JIRA_POLL_INTERVAL_SECONDS=60
```

### Security Best Practices
1. Never log environment variables
2. Use `.env` file locally (gitignored)
3. Commit `.env.example` with variable names only
4. Separate credentials for test vs production
5. Use least-privilege IAM policies

### Trade-offs
| Aspect | Impact |
|--------|--------|
| **Simplicity** | ✅ Universal, simple |
| **Security** | ⚠️ No encryption at rest |
| **Rotation** | ⚠️ Manual process |
| **Local dev** | ✅ Works everywhere |

### Impact Analysis
| Dimension | Impact |
|-----------|--------|
| Scalability | Neutral |
| Security | Adequate for capstone; document production improvements |
| Maintainability | Simple to understand |
| Cost | None |

---

## Decision 14: Logging Strategy

### Decision
Use **Structured Logging (JSON)** to both console and file using `structlog`.

### Context
Logging strategy needed for debugging, monitoring, and audit trail.

### Alternatives Considered

| Option | Description |
|--------|-------------|
| **A: Basic Python** | Standard library logging |
| **B: Structured** | JSON-formatted logs |
| **C: Centralized** | Ship to CloudWatch/ELK |
| **D: Structured + File** | JSON to console + file |

### Rationale
- `structlog` is lightweight and Pythonic
- JSON format enables parsing and future centralization
- Console output for development visibility
- File output for post-demo analysis
- Grep/jq friendly for debugging
- Demonstrates production-ready practices

### Log Categories
| Category | Events | Level |
|----------|--------|-------|
| Pipeline | Finding received, status transitions | INFO |
| Agents | Decisions, confidence scores | INFO |
| ChromaDB | Searches, match scores | DEBUG |
| Validation | Environment lifecycle, checks | INFO |
| Approval | Requests, approvals, rejections | INFO (Audit) |
| Deployment | Execution, results | INFO (Audit) |
| Errors | Exceptions, failures | ERROR |

### Audit Events
Events marked `_audit=True` are security-sensitive:
- Approval granted/rejected
- Deployment executed
- Resources modified

### Trade-offs
| Aspect | Impact |
|--------|--------|
| **Queryability** | ✅ JSON is parseable |
| **Persistence** | ✅ File survives process restart |
| **Disk space** | ⚠️ Logs grow over time |
| **Real-time** | ⚠️ No centralized alerting |

### Impact Analysis
| Dimension | Impact |
|-----------|--------|
| Scalability | Neutral - file-based |
| Security | Positive - audit trail |
| Maintainability | Positive - searchable logs |
| Cost | Disk space only |

---

## Decision 15: API and User Interface

### Decision
**API Only** using FastAPI, with Jira as the primary user interface. No custom web dashboard.

### Context
Documents mentioned FastAPI and WebSockets for "real-time updates," but the actual UI requirements were unclear.

### Alternatives Considered

| Option | Description |
|--------|-------------|
| **A: No API/UI** | Jira only |
| **B: API Only** | REST API, no UI |
| **C: Simple Dashboard** | Basic web UI |
| **D: Full Dashboard** | Rich real-time UI |

### Rationale
- Jira already provides full visibility (12 statuses, comments)
- Building UI is significant frontend effort
- API enables programmatic access and future UI
- FastAPI provides automatic Swagger documentation
- Demo: Jira + Swagger UI + logs is sufficient

### API Endpoints
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Health check |
| GET | `/queue` | Queue status |
| GET | `/findings/{id}` | Finding status |
| GET | `/playbooks` | List playbooks |
| GET | `/playbooks/{id}` | Playbook details |
| GET | `/stats` | System statistics |
| POST | `/findings/{id}/retry` | Re-queue finding |

### WebSocket Decision
WebSockets are **not needed** for Phase 1:
- No UI to receive real-time updates
- API polling sufficient for integrations
- Reduces complexity

### Trade-offs
| Aspect | Impact |
|--------|--------|
| **Demo visual appeal** | ⚠️ Less impressive than dashboard |
| **Development effort** | ✅ Significantly reduced |
| **Functionality** | ✅ Full programmatic access |
| **Jira dependency** | ⚠️ Primary UI is external system |

### Impact Analysis
| Dimension | Impact |
|-----------|--------|
| Scalability | Neutral |
| Security | API needs authentication (future) |
| Maintainability | Positive - less code |
| Cost | Reduced development time |

---

## Decision Summary Matrix

| # | Decision | Choice | Primary Rationale |
|---|----------|--------|-------------------|
| 1 | Project Name | PatchWeave | Academic consistency |
| 2 | Sanitization | Tokenization | Simple, single data flow |
| 3 | Failure Handling | Fail-Fast + Cleanup | Predictable, safe |
| 4 | Test Environment | LocalStack → AWS | Cost-effective development |
| 5 | Match Threshold | Three-tier (90/70/reject) | Balance safety and automation |
| 6 | Phase 1 Scope | Full deployment included | Complete demo capability |
| 7 | KB Seeding | Manual curation | Quality guarantee |
| 8 | Playbook Format | Python/Boto3 | Stack consistency |
| 9 | Analyzer Output | Fixed taxonomy | Reliable matching |
| 10 | Approval | Jira status + polling | Familiar workflow |
| 11 | Jira States | Full 12 statuses | Maximum visibility |
| 12 | Concurrency | Sequential FIFO | Simplicity |
| 13 | Credentials | Environment variables | Universal, simple |
| 14 | Logging | Structured JSON + file | Queryable, persistent |
| 15 | API/UI | API only, Jira UI | Reduced scope |

---

*End of Section 3: Architectural & Technical Decisions*

---

# 4. Project Phases & Milestones

## 4.1 Phase Overview

PatchWeave is developed in two distinct phases, with Phase 1 representing the capstone project deliverable and Phase 2 representing future enhancements.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PROJECT TIMELINE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PHASE 1: Core Implementation (Capstone)                                    │
│  ══════════════════════════════════════                                     │
│                                                                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐  │
│  │  M1     │ │  M2     │ │  M3     │ │  M4     │ │  M5     │ │  M6      │  │
│  │Foundation│ │Analysis │ │Knowledge│ │Validate │ │Deploy   │ │Demo &    │  │
│  │& Infra  │ │Pipeline │ │Base     │ │Workflow │ │& Polish │ │Document  │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └──────────┘  │
│                                                                             │
│  PHASE 2: Enhancements (Post-Capstone)                                      │
│  ═════════════════════════════════════                                      │
│                                                                             │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐   │
│  │ Generator     │ │ Multi-Cloud   │ │ Dashboard     │ │ Enterprise    │   │
│  │ Agent         │ │ Support       │ │ & Analytics   │ │ Features      │   │
│  └───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4.2 Phase 1: Core Implementation (Capstone Deliverable)

### Phase 1 Objective
Deliver a fully functional end-to-end cloud security remediation system that ingests Jira tickets, matches playbooks, validates fixes, obtains human approval, and deploys to AWS.

### Phase 1 Scope Summary

| In Scope | Out of Scope |
|----------|--------------|
| Jira integration (jira-python) | Dynamic playbook generation |
| Tokenization/Sanitization | Multi-cloud (Azure, GCP) |
| Analyzer Agent | Web dashboard UI |
| ChromaDB + semantic search | Concurrent processing |
| Three-tier matching | Priority queue |
| Playbook Verification Agent | Centralized logging |
| Validation Workflow | Secrets Manager integration |
| LocalStack + Real AWS | Automated playbook deprecation |
| Human approval via Jira | Slack/Teams notifications |
| Deployment Agent | A/B testing of remediations |
| FastAPI REST API | |
| Structured logging | |
| 10-15 curated playbooks | |

---

### Milestone 1: Foundation & Infrastructure

**Duration**: 2 weeks

**Objective**: Establish project foundation, development environment, and core infrastructure.

#### Deliverables

| Deliverable | Description |
|-------------|-------------|
| Repository structure | Organized Python project with proper packaging |
| Development environment | Python 3.11+, virtual environment, dependencies |
| LocalStack setup | Docker-based local AWS simulation |
| Configuration system | Environment variable loading with python-dotenv |
| Logging infrastructure | structlog setup with JSON output |
| CI/CD basics | Linting, formatting, basic test structure |

#### Technical Tasks

```
M1.1 Project Initialization
├── Initialize git repository
├── Create Python package structure
├── Set up virtual environment
├── Create requirements.txt / pyproject.toml
├── Configure .gitignore
└── Create .env.example

M1.2 Development Environment
├── Install Python 3.11+
├── Install Docker (for LocalStack)
├── Configure IDE (VS Code settings)
├── Set up pre-commit hooks
└── Configure linting (ruff/black)

M1.3 LocalStack Setup
├── Create docker-compose.yml
├── Configure LocalStack services (S3, EC2, RDS, etc.)
├── Verify LocalStack connectivity
├── Create test script for AWS operations
└── Document LocalStack usage

M1.4 Configuration & Logging
├── Implement config.py with env var loading
├── Create .env.example with all variables
├── Set up structlog configuration
├── Implement log file rotation
└── Create logging utility module

M1.5 Project Structure
├── Create src/patchweave/ package
├── Create tests/ directory
├── Create playbooks/ directory
├── Create docs/ directory
└── Create README.md with setup instructions
```

#### Success Criteria
- [ ] `docker-compose up` starts LocalStack successfully
- [ ] Python application loads configuration from `.env`
- [ ] Logs output in JSON format to console and file
- [ ] Basic Boto3 operations work against LocalStack
- [ ] All team members can run the development environment

#### Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| LocalStack compatibility issues | Medium | Medium | Document workarounds; have real AWS fallback |
| Environment differences across team | Medium | Low | Use Docker for consistent environment |
| Dependency conflicts | Low | Medium | Pin all dependency versions |

---

### Milestone 2: Analysis Pipeline

**Duration**: 3 weeks

**Objective**: Implement Jira ingestion, tokenization, and the Analyzer Agent.

#### Deliverables

| Deliverable | Description |
|-------------|-------------|
| Jira client | jira-python based Jira integration |
| Tokenizer module | Sensitive data replacement with tokens |
| Analyzer Agent | LLM-based finding analysis |
| Data models | Pydantic schemas for all data structures |
| Jira status updates | Bidirectional Jira communication |

#### Technical Tasks

```
M2.1 Data Models
├── Define AnalyzedFinding schema
├── Define TokenMapping schema
├── Define PlaybookMatch schema
├── Define ValidationResult schema
└── Define all Jira status enums

M2.2 Jira Integration
├── Implement Jira client using jira-python library
├── Implement ticket fetching (poll for OPEN status)
├── Implement status transition updates
├── Implement comment posting
├── Handle Jira API rate limits
└── Write integration tests

M2.3 Tokenizer
├── Define token patterns (regex for AWS identifiers)
├── Implement token extraction
├── Implement token replacement
├── Implement token mapping storage
├── Implement token substitution (for deployment)
└── Write unit tests

M2.4 Analyzer Agent
├── Set up LangGraph agent structure
├── Define vulnerability taxonomy enum
├── Implement LLM prompt for classification
├── Implement search query generation
├── Implement confidence scoring
├── Handle "unknown" classification
└── Write unit tests with mock LLM

M2.5 Pipeline Integration
├── Wire Jira → Tokenizer → Analyzer flow
├── Implement status updates at each stage
├── Add structured logging for pipeline events
├── Create end-to-end test with sample ticket
└── Document pipeline flow
```

#### Success Criteria
- [ ] Jira tickets in OPEN status are automatically fetched
- [ ] Sensitive data is correctly tokenized
- [ ] Analyzer classifies findings to taxonomy types
- [ ] Jira status updates to ANALYZING → PLAYBOOK SEARCH
- [ ] Pipeline logs all events in structured format

#### Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Jira API access issues | Medium | High | Get credentials early; have mock mode |
| LLM classification accuracy | Medium | Medium | Tune prompts; use examples in prompt |
| Token pattern misses edge cases | Medium | Low | Iteratively improve regex patterns |

---

### Milestone 3: Knowledge Base & Matching

**Duration**: 3 weeks

**Objective**: Implement ChromaDB knowledge base, playbook storage, semantic matching, and Playbook Verification Agent.

#### Deliverables

| Deliverable | Description |
|-------------|-------------|
| ChromaDB integration | Vector database setup and operations |
| Playbook schema | YAML-based playbook format |
| 10-15 curated playbooks | Manually written, tested playbooks |
| Semantic search | Embedding-based similarity matching |
| Three-tier routing | 90%/70-90%/<70% logic |
| Playbook Verification Agent | Moderate-match review agent |

#### Technical Tasks

```
M3.1 ChromaDB Setup
├── Install and configure ChromaDB
├── Create playbooks collection
├── Implement embedding generation
├── Implement CRUD operations
├── Configure persistence
└── Write integration tests

M3.2 Playbook Schema
├── Define YAML schema specification
├── Implement playbook loader
├── Implement schema validation
├── Create playbook template
└── Document playbook format

M3.3 Playbook Curation
├── Write s3_public_access playbook
├── Write s3_encryption_disabled playbook
├── Write security_group_open_ssh playbook
├── Write security_group_open_rdp playbook
├── Write ebs_unencrypted playbook
├── Write rds_publicly_accessible playbook
├── Write rds_unencrypted playbook
├── Write cloudtrail_disabled playbook
├── Write vpc_flow_logs_disabled playbook
├── Write iam_root_account_usage playbook
├── Test each playbook against LocalStack
└── Load playbooks into ChromaDB

M3.4 Semantic Search
├── Implement search query embedding
├── Implement similarity search
├── Implement score normalization
├── Implement three-tier routing logic
└── Write unit tests

M3.5 Playbook Verification Agent
├── Set up LangGraph agent structure
├── Implement match verification prompt
├── Implement approve/reject decision
├── Wire into pipeline after 70-90% matches
└── Write unit tests

M3.6 Pipeline Integration
├── Wire Analyzer → ChromaDB → Routing flow
├── Update Jira status for VERIFYING, NO PLAYBOOK
├── Add logging for match scores
└── Create end-to-end test
```

#### Success Criteria
- [ ] All 10+ playbooks loaded in ChromaDB
- [ ] Semantic search returns relevant playbooks
- [ ] Three-tier routing works correctly
- [ ] Verification Agent approves/rejects appropriately
- [ ] Jira status reflects matching outcome

#### Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Poor embedding quality | Medium | High | Test multiple embedding models |
| Playbook writing takes too long | Medium | Medium | Parallelize across team members |
| Verification Agent too strict/lenient | Medium | Medium | Tune prompt with examples |

---

### Milestone 4: Validation Workflow

**Duration**: 3 weeks

**Objective**: Implement the multi-agent validation workflow including environment replication, pre/post checks, and cleanup.

#### Deliverables

| Deliverable | Description |
|-------------|-------------|
| Orchestrator Agent | Validation workflow coordinator |
| Environment Replication Agent | Terraform generation for test environments |
| Pre-Check Verification | Vulnerability existence confirmation |
| Remediation Executor | Playbook code execution |
| Post-Check Verification | Fix success confirmation |
| Cleanup Agent | Test environment destruction |

#### Technical Tasks

```
M4.1 Orchestrator Agent
├── Set up LangGraph workflow structure
├── Define validation state machine
├── Implement agent coordination
├── Implement fail-fast logic
├── Implement finally cleanup guarantee
└── Write unit tests

M4.2 Environment Replication Agent
├── Create Terraform templates per resource type
├── Implement dynamic Terraform generation
├── Implement terraform init/apply execution
├── Handle Terraform errors gracefully
├── Store environment metadata
└── Write integration tests with LocalStack

M4.3 Pre-Check Verification
├── Extract pre_check_code from playbook
├── Implement token substitution for test env
├── Execute pre-check against test environment
├── Parse assertion results
├── Update Jira with pre-check status
└── Write unit tests

M4.4 Remediation Executor
├── Extract remediation_code from playbook
├── Implement secure code execution sandbox
├── Execute remediation against test environment
├── Capture execution logs
├── Handle execution errors
└── Write unit tests

M4.5 Post-Check Verification
├── Extract post_check_code from playbook
├── Execute post-check against test environment
├── Parse assertion results
├── Update Jira with post-check status
└── Write unit tests

M4.6 Cleanup Agent
├── Implement terraform destroy execution
├── Implement resource verification (ensure deleted)
├── Implement retry logic for cleanup
├── Implement critical alerting on cleanup failure
├── Ensure cleanup runs in finally block
└── Write integration tests

M4.7 Pipeline Integration
├── Wire full validation workflow
├── Update Jira status for VALIDATING, VALIDATION FAILED
├── Post validation results to Jira comment
├── Add comprehensive logging
└── Create end-to-end test
```

#### Success Criteria
- [ ] Test environment created via Terraform on LocalStack
- [ ] Pre-check correctly identifies vulnerability
- [ ] Remediation code executes successfully
- [ ] Post-check confirms fix worked
- [ ] Cleanup destroys all test resources
- [ ] Cleanup runs even when validation fails

#### Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Terraform complexity | High | High | Start with simple templates; iterate |
| Code execution security | Medium | High | Restrict builtins; sandbox execution |
| Cleanup failures | Medium | High | Aggressive retry; alerting; manual fallback |
| LocalStack Terraform gaps | Medium | Medium | Document limitations; test thoroughly |

---

### Milestone 5: Deployment & Integration

**Duration**: 2 weeks

**Objective**: Implement human approval flow, Deployment Agent, ChromaDB learning, and full system integration.

#### Deliverables

| Deliverable | Description |
|-------------|-------------|
| Approval flow | Jira polling for PENDING APPROVAL status |
| Deployment Agent | Production remediation execution |
| Learning loop | Store successful remediations |
| FastAPI REST API | System status and control endpoints |
| Full integration | End-to-end working system |

#### Technical Tasks

```
M5.1 Approval Flow
├── Implement approval request comment formatting
├── Post approval request to Jira
├── Update status to PENDING APPROVAL
├── Implement polling for status change
├── Handle APPROVED transition
├── Handle REJECTED transition (with comment parsing)
└── Write integration tests

M5.2 Deployment Agent
├── Retrieve token mapping for finding
├── Implement token substitution
├── Configure production AWS credentials
├── Implement remediation code execution
├── Capture deployment results
├── Update Jira status to DEPLOYING, RESOLVED, DEPLOYMENT FAILED
├── Post deployment results to Jira
└── Write integration tests (with mock AWS)

M5.3 Learning Loop
├── On successful deployment, extract finding + playbook
├── Store association in ChromaDB
├── Update playbook usage statistics
└── Write unit tests

M5.4 FastAPI REST API
├── Implement /health endpoint
├── Implement /queue endpoint
├── Implement /findings/{id} endpoint
├── Implement /playbooks endpoint
├── Implement /stats endpoint
├── Implement /findings/{id}/retry endpoint
├── Add OpenAPI documentation
├── Write API tests
└── Document API usage

M5.5 Full System Integration
├── Wire all components together
├── Implement main application entry point
├── Implement FIFO queue and processing loop
├── Add graceful shutdown handling
├── Comprehensive end-to-end testing
└── Performance testing
```

#### Success Criteria
- [ ] Approval request appears correctly in Jira
- [ ] System detects approval/rejection via polling
- [ ] Deployment Agent executes remediation (in test mode)
- [ ] Successful remediations stored in ChromaDB
- [ ] API endpoints return correct data
- [ ] Full end-to-end flow works with sample finding

#### Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Production credential access | Medium | High | Start with dry-run mode |
| Jira workflow not configured | Medium | High | Document requirements; configure early |
| Integration bugs | High | Medium | Extensive integration testing |

---

### Milestone 6: Demo & Documentation

**Duration**: 2 weeks

**Objective**: Prepare compelling demo, complete documentation, and finalize for capstone submission.

#### Deliverables

| Deliverable | Description |
|-------------|-------------|
| Demo scenario | Scripted end-to-end demonstration |
| User documentation | Setup and usage guides |
| Technical documentation | Architecture and API docs |
| Presentation materials | Slides and talking points |
| Final testing | Comprehensive system validation |

#### Technical Tasks

```
M6.1 Demo Preparation
├── Create demo Jira project with sample tickets
├── Script demo walkthrough
├── Prepare 3 vulnerability scenarios for demo
├── Practice demo execution
├── Prepare backup plans for demo failures
└── Record video backup of demo

M6.2 Documentation
├── Complete README.md with full setup guide
├── Document all environment variables
├── Create playbook authoring guide
├── Document API with examples
├── Create troubleshooting guide
├── Complete this project document
└── Generate API documentation from OpenAPI

M6.3 Testing & Hardening
├── Run full regression test suite
├── Test failure scenarios
├── Test edge cases
├── Fix any discovered bugs
├── Performance optimization if needed
└── Security review

M6.4 Presentation
├── Create presentation slides
├── Prepare architecture diagrams
├── Prepare demo talking points
├── Practice presentation
└── Prepare for Q&A
```

#### Success Criteria
- [ ] Demo runs smoothly end-to-end
- [ ] All documentation is complete and accurate
- [ ] System handles failure scenarios gracefully
- [ ] Presentation is polished and professional
- [ ] Team can answer technical questions

#### Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Demo failure during presentation | Medium | High | Video backup; practice extensively |
| Documentation gaps discovered late | Medium | Medium | Start documentation early |
| Last-minute bugs | Medium | Medium | Feature freeze before demo prep |

---

## 4.3 Phase 1 Risk Summary

### Critical Risks

| Risk | Probability | Impact | Mitigation | Owner |
|------|-------------|--------|------------|-------|
| Jira API access unavailable | Medium | Critical | Get credentials in M1; mock fallback | Team Lead |
| LLM costs exceed budget | Medium | High | Use cost-effective models; set limits | Team Lead |
| Terraform/LocalStack incompatibility | Medium | High | Test early; document workarounds | DevOps Lead |
| Cleanup failures causing cost leaks | Medium | High | Aggressive alerting; manual procedures | DevOps Lead |
| Team member unavailability | Low | High | Knowledge sharing; documentation | All |

### Risk Monitoring

Weekly risk review during team meetings:
1. Review current risk status
2. Identify new risks
3. Update mitigation strategies
4. Escalate blockers

---

## 4.4 Phase 2: Future Enhancements (Post-Capstone)

Phase 2 represents enhancements beyond the capstone scope, to be implemented if the project continues.

### Phase 2.1: Generator Agent (Dynamic Playbook Creation)

**Objective**: Automatically generate new playbooks for findings without matches.

#### Key Features
- LLM-based remediation code generation
- Generated code validation before use
- Confidence scoring for generated playbooks
- Human review workflow for new playbooks

#### Technical Approach
```
Finding with <70% match
    │
    ▼
Generator Agent (LLM)
    │
    ├── Generate remediation_code
    ├── Generate pre_check_code
    ├── Generate post_check_code
    │
    ▼
Generated Playbook Review
    │
    ├── Static analysis
    ├── Security scanning
    ├── Human review
    │
    ▼
Validation Workflow (same as existing)
    │
    ▼
On Success: Add to ChromaDB as verified playbook
```

#### Risks
- LLM hallucination generating incorrect code
- Security risks from generated code
- Quality control complexity

---

### Phase 2.2: Multi-Cloud Support

**Objective**: Extend PatchWeave to support Azure and GCP in addition to AWS.

#### Key Features
- Cloud provider abstraction layer
- Azure playbooks (Azure SDK for Python)
- GCP playbooks (Google Cloud Python client)
- Provider-specific tokenization patterns

#### Technical Approach
```python
# Cloud Provider Abstraction
class CloudProvider(ABC):
    @abstractmethod
    def get_client(self, service: str) -> Any: ...
    
    @abstractmethod
    def get_token_patterns(self) -> List[TokenPattern]: ...

class AWSProvider(CloudProvider): ...
class AzureProvider(CloudProvider): ...
class GCPProvider(CloudProvider): ...
```

#### Effort Estimate
- Azure support: 4-6 weeks
- GCP support: 4-6 weeks
- Abstraction layer: 2 weeks

---

### Phase 2.3: Full Dashboard & Analytics

**Objective**: Build a comprehensive web UI for system monitoring and management.

#### Key Features
- Real-time pipeline status (WebSocket)
- Finding queue management
- Playbook management (CRUD)
- Analytics and reporting
- Trend visualization

#### Technical Approach
- Frontend: React or Vue.js
- Real-time: WebSocket integration
- Charts: Recharts or Chart.js
- State management: Redux or Pinia

#### Wireframe
```
┌─────────────────────────────────────────────────────────────────────┐
│  PatchWeave Dashboard                               [User ▼] [⚙️]   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 📊 Overview                                                   │  │
│  ├──────────────┬──────────────┬──────────────┬─────────────────┤  │
│  │ Resolved     │ Pending      │ Failed       │ Avg MTTR        │  │
│  │    127       │     3        │     5        │   28 min        │  │
│  └──────────────┴──────────────┴──────────────┴─────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────┐ ┌────────────────────────────┐│
│  │ 📋 Recent Findings              │ │ 📈 Resolution Trend        ││
│  │ ┌─────────────────────────────┐ │ │                            ││
│  │ │ JIRA-1234 VALIDATING   🔵  │ │ │    [Line Chart]            ││
│  │ │ JIRA-1235 PENDING APPR 🟡  │ │ │                            ││
│  │ │ JIRA-1236 RESOLVED     🟢  │ │ │                            ││
│  │ └─────────────────────────────┘ │ │                            ││
│  └─────────────────────────────────┘ └────────────────────────────┘│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Phase 2.4: Enterprise Features

**Objective**: Add features required for enterprise deployment.

#### Key Features

| Feature | Description |
|---------|-------------|
| **Priority Queue** | Process Critical findings before Low severity |
| **Concurrent Processing** | Parallel validation (N=3-10) |
| **Centralized Logging** | Ship to CloudWatch, ELK, or Datadog |
| **Secrets Manager** | AWS Secrets Manager / HashiCorp Vault integration |
| **RBAC** | Role-based access control for API |
| **SSO** | SAML/OIDC authentication |
| **Audit Export** | Compliance report generation |
| **SLA Monitoring** | MTTR tracking and alerting |

---

### Phase 2 Roadmap Summary

| Phase | Feature | Effort | Priority |
|-------|---------|--------|----------|
| 2.1 | Generator Agent | 6-8 weeks | High |
| 2.2 | Multi-Cloud | 10-14 weeks | Medium |
| 2.3 | Dashboard | 6-8 weeks | Medium |
| 2.4 | Enterprise Features | 8-12 weeks | Low |

---

## 4.5 Milestone Dependencies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MILESTONE DEPENDENCIES                                │
└─────────────────────────────────────────────────────────────────────────────┘

M1: Foundation ──────┐
                     │
                     ▼
M2: Analysis ────────┤
                     │
                     ▼
M3: Knowledge ───────┤
                     │
                     ▼
M4: Validation ──────┤
                     │
                     ▼
M5: Deployment ──────┤
                     │
                     ▼
M6: Demo & Docs ─────┘

Legend:
═══════
• All milestones are sequential (each depends on previous)
• Playbook curation (M3) can start in parallel with M2
• Documentation should be ongoing throughout
```

---

## 4.6 Resource Allocation

### Team Structure (4 Members)

| Role | Primary Responsibilities | Milestones |
|------|-------------------------|------------|
| **Tech Lead** | Architecture, code review, integration | All |
| **Backend Dev 1** | Jira integration, Analyzer, API | M2, M5 |
| **Backend Dev 2** | ChromaDB, playbooks, matching | M3 |
| **DevOps/Infra** | LocalStack, Terraform, validation | M1, M4 |

### Parallel Work Opportunities

| Milestone | Parallelizable Tasks |
|-----------|---------------------|
| M1 | Environment setup (all team members) |
| M2 | Data models, Jira client, Tokenizer, Analyzer (split) |
| M3 | Playbook writing (all), ChromaDB, Verification Agent |
| M4 | Terraform templates, each validation agent |
| M5 | API, Approval flow, Deployment Agent (split) |
| M6 | Documentation, demo prep, testing (all) |

---

*End of Section 4: Project Phases & Milestones*

---

# 5. Detailed Implementation Blueprint

## 5.1 Technology Stack

### Core Technologies

| Category | Technology | Version | Purpose |
|----------|------------|---------|---------|
| **Language** | Python | 3.11+ | Primary development language |
| **Agent Framework** | LangGraph | 0.1.x | Multi-agent orchestration |
| **LLM Integration** | LangChain | 0.2.x | LLM abstractions for agents |
| **Jira Client** | jira-python | 3.x | Official Atlassian Jira library |
| **Vector Database** | ChromaDB | 0.4.x | Playbook storage and semantic search |
| **API Framework** | FastAPI | 0.109.x | REST API endpoints |
| **HTTP Client** | httpx | 0.26.x | Async HTTP for Jira API |
| **Data Validation** | Pydantic | 2.x | Schema definitions and validation |
| **AWS SDK** | Boto3 | 1.34.x | AWS service interactions |
| **Infrastructure** | Terraform | 1.7.x | Test environment provisioning |
| **Local AWS** | LocalStack | 3.x | Local AWS simulation |
| **Logging** | structlog | 24.x | Structured JSON logging |
| **Config** | python-dotenv | 1.0.x | Environment variable loading |
| **Testing** | pytest | 8.x | Test framework |
| **Async** | asyncio | stdlib | Asynchronous operations |

### Development Tools

| Tool | Purpose |
|------|---------|
| Docker / Docker Compose | LocalStack and service containers |
| Git | Version control |
| VS Code | Recommended IDE |
| ruff | Python linting and formatting |
| pre-commit | Git hooks for code quality |
| pytest-cov | Test coverage |
| pytest-asyncio | Async test support |

### Dependency Specification

```toml
# pyproject.toml
[project]
name = "patchweave"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = [
    "langchain>=0.2.0",
    "langgraph>=0.1.0",
    "langchain-openai>=0.1.0",
    "chromadb>=0.4.0",
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "httpx>=0.26.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "boto3>=1.34.0",
    "structlog>=24.0.0",
    "python-dotenv>=1.0.0",
    "pyyaml>=6.0.0",
    "tenacity>=8.2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.2.0",
    "pre-commit>=3.6.0",
    "moto>=5.0.0",
]
```

---

## 5.2 Project Structure

```
patchweave/
├── .env.example                 # Environment variable template
├── .gitignore                   # Git ignore patterns
├── docker-compose.yml           # LocalStack and services
├── pyproject.toml               # Project configuration
├── README.md                    # Project documentation
├── Makefile                     # Common commands
│
├── src/
│   └── patchweave/
│       ├── __init__.py
│       ├── main.py              # Application entry point
│       ├── config.py            # Configuration management
│       │
│       ├── models/              # Pydantic data models
│       │   ├── __init__.py
│       │   ├── finding.py       # AnalyzedFinding, RawFinding
│       │   ├── playbook.py      # Playbook, PlaybookMatch
│       │   ├── validation.py    # ValidationResult, ValidationState
│       │   ├── deployment.py    # DeploymentResult
│       │   └── enums.py         # JiraStatus, VulnerabilityType, etc.
│       │
│       ├── agents/              # LangGraph agents
│       │   ├── __init__.py
│       │   ├── analyzer.py      # Analyzer Agent
│       │   ├── verifier.py      # Playbook Verification Agent
│       │   ├── orchestrator.py  # Validation Orchestrator
│       │   ├── environment.py   # Environment Replication Agent
│       │   ├── checker.py       # Pre/Post Check Agents
│       │   ├── executor.py      # Remediation Executor
│       │   ├── cleanup.py       # Cleanup Agent
│       │   └── deployer.py      # Deployment Agent
│       │
│       ├── integrations/        # External service integrations
│       │   ├── __init__.py
│       │   ├── jira_client.py   # Jira client (jira-python)
│       │   ├── chromadb.py      # ChromaDB operations
│       │   └── aws.py           # AWS/Boto3 utilities
│       │
│       ├── core/                # Core business logic
│       │   ├── __init__.py
│       │   ├── tokenizer.py     # Tokenization/sanitization
│       │   ├── matcher.py       # Three-tier matching logic
│       │   ├── queue.py         # Finding queue
│       │   └── pipeline.py      # Main processing pipeline
│       │
│       ├── api/                 # FastAPI application
│       │   ├── __init__.py
│       │   ├── app.py           # FastAPI app instance
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── health.py
│       │   │   ├── queue.py
│       │   │   ├── findings.py
│       │   │   ├── playbooks.py
│       │   │   └── stats.py
│       │   └── dependencies.py  # FastAPI dependencies
│       │
│       ├── logging/             # Logging configuration
│       │   ├── __init__.py
│       │   └── setup.py         # structlog setup
│       │
│       └── utils/               # Utility functions
│           ├── __init__.py
│           ├── terraform.py     # Terraform execution helpers
│           └── code_executor.py # Safe code execution
│
├── playbooks/                   # Curated remediation playbooks
│   ├── s3_public_access.yaml
│   ├── s3_encryption_disabled.yaml
│   ├── security_group_open_ssh.yaml
│   ├── security_group_open_rdp.yaml
│   ├── ebs_unencrypted.yaml
│   ├── rds_publicly_accessible.yaml
│   ├── rds_unencrypted.yaml
│   ├── cloudtrail_disabled.yaml
│   ├── vpc_flow_logs_disabled.yaml
│   └── iam_root_account_usage.yaml
│
├── terraform/                   # Terraform templates
│   ├── modules/
│   │   ├── s3_bucket/
│   │   ├── security_group/
│   │   ├── rds_instance/
│   │   └── ...
│   └── templates/
│       └── test_environment/
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures
│   ├── unit/
│   │   ├── test_tokenizer.py
│   │   ├── test_matcher.py
│   │   ├── test_models.py
│   │   └── ...
│   ├── integration/
│   │   ├── test_jira_client.py
│   │   ├── test_chromadb.py
│   │   ├── test_validation.py
│   │   └── ...
│   └── e2e/
│       └── test_full_pipeline.py
│
└── docs/
    ├── setup.md                 # Setup guide
    ├── playbook_authoring.md    # How to write playbooks
    ├── api.md                   # API documentation
    └── troubleshooting.md       # Common issues
```

---

## 5.3 Data Models (Pydantic Schemas)

### Enumerations

```python
# src/patchweave/models/enums.py

from enum import Enum

class JiraStatus(str, Enum):
    """All possible Jira workflow statuses."""
    OPEN = "OPEN"
    ANALYZING = "ANALYZING"
    PLAYBOOK_SEARCH = "PLAYBOOK SEARCH"
    VERIFYING = "VERIFYING"
    NO_PLAYBOOK = "NO PLAYBOOK"
    VALIDATING = "VALIDATING"
    VALIDATION_FAILED = "VALIDATION FAILED"
    PENDING_APPROVAL = "PENDING APPROVAL"
    REJECTED = "REJECTED"
    DEPLOYING = "DEPLOYING"
    DEPLOYMENT_FAILED = "DEPLOYMENT FAILED"
    RESOLVED = "RESOLVED"

class VulnerabilityType(str, Enum):
    """Fixed taxonomy of supported vulnerability types."""
    S3_PUBLIC_ACCESS = "s3_public_access"
    S3_ENCRYPTION_DISABLED = "s3_encryption_disabled"
    SECURITY_GROUP_OPEN_SSH = "security_group_open_ssh"
    SECURITY_GROUP_OPEN_RDP = "security_group_open_rdp"
    EBS_UNENCRYPTED = "ebs_unencrypted"
    RDS_PUBLICLY_ACCESSIBLE = "rds_publicly_accessible"
    RDS_UNENCRYPTED = "rds_unencrypted"
    CLOUDTRAIL_DISABLED = "cloudtrail_disabled"
    VPC_FLOW_LOGS_DISABLED = "vpc_flow_logs_disabled"
    IAM_ROOT_ACCOUNT_USAGE = "iam_root_account_usage"
    UNKNOWN = "unknown"

class Severity(str, Enum):
    """Finding severity levels."""
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class CloudProvider(str, Enum):
    """Supported cloud providers."""
    AWS = "AWS"
    # Future: AZURE = "Azure"
    # Future: GCP = "GCP"

class MatchTier(str, Enum):
    """Three-tier matching result."""
    HIGH_CONFIDENCE = "high_confidence"      # ≥90%
    MODERATE_CONFIDENCE = "moderate_confidence"  # 70-89%
    NO_MATCH = "no_match"                    # <70%

class VerificationDecision(str, Enum):
    """Playbook Verification Agent decision."""
    APPROVED = "approved"
    REJECTED = "rejected"

class ValidationStage(str, Enum):
    """Validation workflow stages."""
    ENVIRONMENT_CREATION = "environment_creation"
    PRE_CHECK = "pre_check"
    REMEDIATION = "remediation"
    POST_CHECK = "post_check"
    CLEANUP = "cleanup"
```

### Finding Models

```python
# src/patchweave/models/finding.py

from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel, Field
from .enums import VulnerabilityType, Severity, CloudProvider, JiraStatus

class RawFinding(BaseModel):
    """Raw finding data from Jira ticket before processing."""
    
    jira_ticket_id: str = Field(..., description="Jira ticket ID (e.g., JIRA-1234)")
    jira_ticket_url: str = Field(..., description="Full URL to Jira ticket")
    title: str = Field(..., description="Ticket title")
    description: str = Field(..., description="Ticket description (may contain sensitive data)")
    severity: Optional[str] = Field(None, description="Severity from ticket")
    created_at: datetime = Field(..., description="Ticket creation timestamp")
    custom_fields: Dict[str, str] = Field(default_factory=dict, description="Additional custom fields")

class TokenMapping(BaseModel):
    """Mapping of tokens to actual sensitive values."""
    
    finding_id: str = Field(..., description="Associated finding ID")
    tokens: Dict[str, str] = Field(
        default_factory=dict,
        description="Token name to actual value mapping"
    )
    # Example: {"ACCOUNT_ID": "123456789012", "BUCKET_NAME": "prod-logs"}
    
    def substitute(self, text: str) -> str:
        """Replace tokens in text with actual values."""
        result = text
        for token, value in self.tokens.items():
            result = result.replace(f"{{{{{token}}}}}", value)
        return result

class AnalyzedFinding(BaseModel):
    """Structured finding after Analyzer Agent processing."""
    
    # Identification
    finding_id: str = Field(..., description="Jira ticket ID")
    
    # Classification
    vulnerability_type: VulnerabilityType = Field(..., description="Classified vulnerability type")
    cloud_provider: CloudProvider = Field(default=CloudProvider.AWS)
    resource_type: str = Field(..., description="AWS resource type (e.g., AWS::S3::Bucket)")
    severity: Severity = Field(..., description="Normalized severity")
    
    # Semantic search
    search_query: str = Field(..., description="Generated query for ChromaDB lookup")
    
    # Sanitized content
    sanitized_title: str = Field(..., description="Title with tokens")
    sanitized_description: str = Field(..., description="Description with tokens")
    
    # Token reference (actual values stored separately)
    token_keys: list[str] = Field(default_factory=list, description="List of token names used")
    
    # Metadata
    source_ticket_url: str
    detected_at: datetime
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    analysis_confidence: float = Field(..., ge=0.0, le=1.0, description="Analyzer confidence score")
    
    # Current status
    status: JiraStatus = Field(default=JiraStatus.ANALYZING)
```

### Playbook Models

```python
# src/patchweave/models/playbook.py

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from .enums import VulnerabilityType, Severity, CloudProvider

class Playbook(BaseModel):
    """Remediation playbook definition."""
    
    # Identification
    id: str = Field(..., description="Unique playbook ID (UUID)")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Detailed description of what this playbook does")
    
    # Classification
    vulnerability_type: VulnerabilityType = Field(..., description="Type of vulnerability this fixes")
    cloud_provider: CloudProvider = Field(default=CloudProvider.AWS)
    resource_type: str = Field(..., description="AWS resource type")
    severity: Severity = Field(..., description="Typical severity of this vulnerability")
    
    # Semantic search content
    search_text: str = Field(..., description="Text used for embedding and semantic search")
    
    # Executable code (Python/Boto3)
    remediation_code: str = Field(..., description="Python code to fix the vulnerability")
    pre_check_code: str = Field(..., description="Python code to verify vulnerability exists")
    post_check_code: str = Field(..., description="Python code to verify fix worked")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(default="PatchWeave Team")
    version: str = Field(default="1.0.0")
    
    # Requirements
    required_permissions: list[str] = Field(
        default_factory=list,
        description="IAM permissions required to execute this playbook"
    )
    estimated_execution_time_seconds: int = Field(default=30)

class PlaybookMatch(BaseModel):
    """Result of playbook matching from ChromaDB."""
    
    playbook: Playbook = Field(..., description="Matched playbook")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score (0-1)")
    match_tier: str = Field(..., description="high_confidence, moderate_confidence, or no_match")
    
    @property
    def is_high_confidence(self) -> bool:
        return self.similarity_score >= 0.90
    
    @property
    def is_moderate_confidence(self) -> bool:
        return 0.70 <= self.similarity_score < 0.90
    
    @property
    def is_no_match(self) -> bool:
        return self.similarity_score < 0.70
```

### Validation Models

```python
# src/patchweave/models/validation.py

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from .enums import ValidationStage

class TestEnvironment(BaseModel):
    """Represents a temporary test environment."""
    
    environment_id: str = Field(..., description="Unique environment ID")
    finding_id: str = Field(..., description="Associated finding")
    terraform_state_path: str = Field(..., description="Path to Terraform state file")
    resources_created: list[str] = Field(default_factory=list, description="List of created resource IDs")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_cleaned_up: bool = Field(default=False)

class StageResult(BaseModel):
    """Result of a single validation stage."""
    
    stage: ValidationStage
    success: bool
    message: str
    duration_seconds: float
    error: Optional[str] = None
    logs: list[str] = Field(default_factory=list)

class ValidationResult(BaseModel):
    """Complete result of validation workflow."""
    
    finding_id: str
    playbook_id: str
    
    # Stage results
    environment_creation: Optional[StageResult] = None
    pre_check: Optional[StageResult] = None
    remediation: Optional[StageResult] = None
    post_check: Optional[StageResult] = None
    cleanup: Optional[StageResult] = None
    
    # Overall result
    success: bool = False
    failure_stage: Optional[ValidationStage] = None
    failure_reason: Optional[str] = None
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    total_duration_seconds: Optional[float] = None
    
    def mark_complete(self, success: bool):
        self.success = success
        self.completed_at = datetime.utcnow()
        self.total_duration_seconds = (self.completed_at - self.started_at).total_seconds()
```

### Deployment Models

```python
# src/patchweave/models/deployment.py

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class DeploymentResult(BaseModel):
    """Result of production deployment."""
    
    finding_id: str
    playbook_id: str
    
    # Execution details
    success: bool
    executed_code: str = Field(..., description="Actual code executed (with real values)")
    
    # Results
    resources_modified: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Approval info
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
```

---

## 5.4 Configuration Management

```python
# src/patchweave/config.py

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    # Application
    patchweave_env: str = Field(default="development", description="development or production")
    log_level: str = Field(default="INFO")
    log_file: str = Field(default="patchweave.log")
    
    # Jira Configuration
    jira_base_url: str = Field(..., description="Jira instance URL")
    jira_email: str = Field(..., description="Jira service account email")
    jira_api_token: str = Field(..., description="Jira API token")
    jira_project_key: str = Field(..., description="Jira project to monitor")
    jira_poll_interval_seconds: int = Field(default=60)
    
    # AWS Test Environment
    aws_test_access_key_id: str = Field(..., description="AWS test account access key")
    aws_test_secret_access_key: str = Field(..., description="AWS test account secret key")
    aws_test_region: str = Field(default="us-east-1")
    
    # AWS Production Environment
    aws_prod_access_key_id: str = Field(..., description="AWS prod account access key")
    aws_prod_secret_access_key: str = Field(..., description="AWS prod account secret key")
    aws_prod_region: str = Field(default="us-east-1")
    
    # LocalStack (for development)
    localstack_endpoint: str = Field(default="http://localhost:4566")
    use_localstack: bool = Field(default=True, description="Use LocalStack instead of real AWS")
    
    # ChromaDB
    chroma_persist_directory: str = Field(default="./chroma_data")
    
    # LLM Configuration
    openai_api_key: Optional[str] = Field(default=None)
    llm_model: str = Field(default="gpt-4-turbo-preview")
    llm_temperature: float = Field(default=0.0)
    
    # Playbooks
    playbooks_directory: str = Field(default="./playbooks")
    
    # Matching thresholds
    high_confidence_threshold: float = Field(default=0.90)
    moderate_confidence_threshold: float = Field(default=0.70)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def is_development(self) -> bool:
        return self.patchweave_env == "development"
    
    @property
    def is_production(self) -> bool:
        return self.patchweave_env == "production"
    
    def get_aws_config(self, environment: str) -> dict:
        """Get AWS configuration for test or production."""
        if environment == "test":
            config = {
                "aws_access_key_id": self.aws_test_access_key_id,
                "aws_secret_access_key": self.aws_test_secret_access_key,
                "region_name": self.aws_test_region,
            }
            if self.use_localstack:
                config["endpoint_url"] = self.localstack_endpoint
            return config
        elif environment == "production":
            return {
                "aws_access_key_id": self.aws_prod_access_key_id,
                "aws_secret_access_key": self.aws_prod_secret_access_key,
                "region_name": self.aws_prod_region,
            }
        else:
            raise ValueError(f"Unknown environment: {environment}")

# Global settings instance
settings = Settings()
```

### Environment Variables Template

```bash
# .env.example

# =============================================================================
# PatchWeave Configuration
# =============================================================================
# Copy this file to .env and fill in the values
# NEVER commit .env to version control
# =============================================================================

# -----------------------------------------------------------------------------
# Application Settings
# -----------------------------------------------------------------------------
PATCHWEAVE_ENV=development          # development | production
LOG_LEVEL=INFO                       # DEBUG | INFO | WARNING | ERROR
LOG_FILE=patchweave.log

# -----------------------------------------------------------------------------
# Jira Configuration
# -----------------------------------------------------------------------------
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_EMAIL=patchweave-service@your-org.com
JIRA_API_TOKEN=                      # Generate at https://id.atlassian.com/manage/api-tokens
JIRA_PROJECT_KEY=SEC                 # Project key to monitor for findings
JIRA_POLL_INTERVAL_SECONDS=60

# -----------------------------------------------------------------------------
# AWS Test Environment
# Used for validation workflow (LocalStack or dedicated test account)
# -----------------------------------------------------------------------------
AWS_TEST_ACCESS_KEY_ID=test          # Use 'test' for LocalStack
AWS_TEST_SECRET_ACCESS_KEY=test      # Use 'test' for LocalStack
AWS_TEST_REGION=us-east-1

# -----------------------------------------------------------------------------
# AWS Production Environment
# Used by Deployment Agent for actual remediation
# -----------------------------------------------------------------------------
AWS_PROD_ACCESS_KEY_ID=
AWS_PROD_SECRET_ACCESS_KEY=
AWS_PROD_REGION=us-east-1

# -----------------------------------------------------------------------------
# LocalStack Configuration
# -----------------------------------------------------------------------------
LOCALSTACK_ENDPOINT=http://localhost:4566
USE_LOCALSTACK=true                  # Set to false for real AWS

# -----------------------------------------------------------------------------
# ChromaDB Configuration
# -----------------------------------------------------------------------------
CHROMA_PERSIST_DIRECTORY=./chroma_data

# -----------------------------------------------------------------------------
# LLM Configuration
# -----------------------------------------------------------------------------
OPENAI_API_KEY=                      # Required for Analyzer and Verification agents
LLM_MODEL=gpt-4-turbo-preview
LLM_TEMPERATURE=0.0

# -----------------------------------------------------------------------------
# Playbooks
# -----------------------------------------------------------------------------
PLAYBOOKS_DIRECTORY=./playbooks

# -----------------------------------------------------------------------------
# Matching Thresholds
# -----------------------------------------------------------------------------
HIGH_CONFIDENCE_THRESHOLD=0.90
MODERATE_CONFIDENCE_THRESHOLD=0.70
```

---

## 5.5 Core Component Implementations

### Tokenizer

```python
# src/patchweave/core/tokenizer.py

import re
from typing import Dict, Tuple
from ..models.finding import RawFinding, TokenMapping
import structlog

log = structlog.get_logger()

class Tokenizer:
    """Sanitizes sensitive data by replacing with tokens."""
    
    # Token patterns for AWS identifiers
    PATTERNS = {
        "ACCOUNT_ID": r"\b\d{12}\b",
        "AWS_REGION": r"\b(us|eu|ap|sa|ca|me|af)-(north|south|east|west|central)-\d\b",
        "BUCKET_NAME": r"(?<=bucket[:\s'\"])[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]",
        "RESOURCE_ARN": r"arn:aws:[a-z0-9\-]+:[a-z0-9\-]*:\d{12}:[a-zA-Z0-9\-_/:.]+",
        "INSTANCE_ID": r"\bi-[a-f0-9]{8,17}\b",
        "SECURITY_GROUP_ID": r"\bsg-[a-f0-9]{8,17}\b",
        "VPC_ID": r"\bvpc-[a-f0-9]{8,17}\b",
        "SUBNET_ID": r"\bsubnet-[a-f0-9]{8,17}\b",
        "DB_INSTANCE_ID": r"(?<=db instance[:\s'\"])[a-zA-Z][a-zA-Z0-9\-]{0,62}",
    }
    
    def __init__(self):
        self._compiled_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.PATTERNS.items()
        }
    
    def tokenize(self, finding: RawFinding) -> Tuple[str, str, TokenMapping]:
        """
        Tokenize sensitive data in finding.
        
        Returns:
            Tuple of (sanitized_title, sanitized_description, token_mapping)
        """
        token_mapping = TokenMapping(finding_id=finding.jira_ticket_id)
        
        # Combine text for tokenization
        full_text = f"{finding.title}\n{finding.description}"
        
        # Extract and replace each pattern
        for token_name, pattern in self._compiled_patterns.items():
            matches = pattern.findall(full_text)
            for i, match in enumerate(set(matches)):  # Deduplicate
                # Create unique token if multiple matches of same type
                token_key = token_name if i == 0 else f"{token_name}_{i+1}"
                token_mapping.tokens[token_key] = match
                
                # Replace in text
                placeholder = f"{{{{{token_key}}}}}"
                full_text = full_text.replace(match, placeholder)
        
        # Split back into title and description
        parts = full_text.split("\n", 1)
        sanitized_title = parts[0]
        sanitized_description = parts[1] if len(parts) > 1 else ""
        
        log.info(
            "tokenization_complete",
            finding_id=finding.jira_ticket_id,
            tokens_found=len(token_mapping.tokens),
            token_types=list(token_mapping.tokens.keys())
        )
        
        return sanitized_title, sanitized_description, token_mapping
```

### Three-Tier Matcher

```python
# src/patchweave/core/matcher.py

from typing import Optional, List
from ..models.playbook import Playbook, PlaybookMatch
from ..models.enums import MatchTier
from ..integrations.chromadb import ChromaDBClient
from ..config import settings
import structlog

log = structlog.get_logger()

class PlaybookMatcher:
    """Implements three-tier matching logic for playbook retrieval."""
    
    def __init__(self, chromadb_client: ChromaDBClient):
        self.chromadb = chromadb_client
        self.high_threshold = settings.high_confidence_threshold
        self.moderate_threshold = settings.moderate_confidence_threshold
    
    def find_match(self, search_query: str, vulnerability_type: str) -> PlaybookMatch:
        """
        Find best matching playbook using three-tier logic.
        
        Returns:
            PlaybookMatch with tier classification
        """
        # First try exact vulnerability_type match
        exact_matches = self.chromadb.find_by_vulnerability_type(vulnerability_type)
        
        if exact_matches:
            log.debug("exact_type_match_found", vulnerability_type=vulnerability_type)
            # Return highest scoring exact match
            best_match = max(exact_matches, key=lambda m: m.similarity_score)
            return self._classify_match(best_match)
        
        # Fall back to semantic search
        semantic_matches = self.chromadb.semantic_search(search_query, n_results=5)
        
        if not semantic_matches:
            log.info("no_matches_found", search_query=search_query[:100])
            return PlaybookMatch(
                playbook=None,
                similarity_score=0.0,
                match_tier=MatchTier.NO_MATCH
            )
        
        best_match = semantic_matches[0]
        return self._classify_match(best_match)
    
    def _classify_match(self, match: PlaybookMatch) -> PlaybookMatch:
        """Classify match into appropriate tier."""
        if match.similarity_score >= self.high_threshold:
            match.match_tier = MatchTier.HIGH_CONFIDENCE
            log.info(
                "high_confidence_match",
                playbook_id=match.playbook.id,
                score=match.similarity_score
            )
        elif match.similarity_score >= self.moderate_threshold:
            match.match_tier = MatchTier.MODERATE_CONFIDENCE
            log.info(
                "moderate_confidence_match",
                playbook_id=match.playbook.id,
                score=match.similarity_score
            )
        else:
            match.match_tier = MatchTier.NO_MATCH
            log.info(
                "no_match",
                best_score=match.similarity_score,
                threshold=self.moderate_threshold
            )
        
        return match
```

### Finding Queue

```python
# src/patchweave/core/queue.py

from typing import Optional, List
from threading import Lock
from ..models.finding import AnalyzedFinding
import structlog

log = structlog.get_logger()

class FindingQueue:
    """Thread-safe FIFO queue for findings."""
    
    def __init__(self):
        self._queue: List[AnalyzedFinding] = []
        self._lock = Lock()
        self._processing: Optional[AnalyzedFinding] = None
    
    def add(self, finding: AnalyzedFinding) -> None:
        """Add finding to end of queue."""
        with self._lock:
            self._queue.append(finding)
            log.info(
                "finding_queued",
                finding_id=finding.finding_id,
                queue_size=len(self._queue)
            )
    
    def next(self) -> Optional[AnalyzedFinding]:
        """Get next finding from queue (FIFO)."""
        with self._lock:
            if self._queue:
                self._processing = self._queue.pop(0)
                log.info(
                    "finding_dequeued",
                    finding_id=self._processing.finding_id,
                    remaining=len(self._queue)
                )
                return self._processing
            return None
    
    def mark_complete(self) -> None:
        """Mark current finding as complete."""
        with self._lock:
            if self._processing:
                log.info(
                    "finding_complete",
                    finding_id=self._processing.finding_id
                )
                self._processing = None
    
    @property
    def size(self) -> int:
        """Current queue size."""
        with self._lock:
            return len(self._queue)
    
    @property
    def current(self) -> Optional[AnalyzedFinding]:
        """Currently processing finding."""
        with self._lock:
            return self._processing
    
    def status(self) -> dict:
        """Get queue status for API."""
        with self._lock:
            return {
                "pending_count": len(self._queue),
                "currently_processing": self._processing.finding_id if self._processing else None,
                "current_status": self._processing.status.value if self._processing else None
            }
```

---

## 5.6 Playbook Format Specification

### Playbook YAML Schema

```yaml
# playbooks/s3_public_access.yaml
# PatchWeave Playbook v1.0

playbook:
  # ============================================================================
  # IDENTIFICATION
  # ============================================================================
  id: "550e8400-e29b-41d4-a716-446655440001"
  name: "S3 Block Public Access"
  description: |
    Enables S3 Block Public Access settings on a bucket that is currently 
    publicly accessible. This is a critical security control that prevents
    accidental public exposure of S3 bucket contents.

  # ============================================================================
  # CLASSIFICATION
  # ============================================================================
  vulnerability_type: "s3_public_access"
  cloud_provider: "AWS"
  resource_type: "AWS::S3::Bucket"
  severity: "Critical"

  # ============================================================================
  # SEMANTIC SEARCH
  # Text used for embedding - should include various phrasings
  # ============================================================================
  search_text: |
    S3 bucket public access enabled
    publicly accessible bucket
    S3 bucket ACL public
    block public access disabled
    S3 public read write access
    bucket policy allows public
    S3 bucket exposed to internet

  # ============================================================================
  # EXECUTABLE CODE
  # All code uses {{TOKEN}} placeholders for sensitive values
  # ============================================================================
  
  # Pre-check: Verify the vulnerability exists
  # Should raise AssertionError if vulnerability NOT present
  pre_check_code: |
    import boto3
    
    s3 = boto3.client('s3', region_name='{{AWS_REGION}}')
    
    try:
        response = s3.get_public_access_block(Bucket='{{BUCKET_NAME}}')
        config = response['PublicAccessBlockConfiguration']
        
        # Check if ALL settings are True (fully blocked)
        is_fully_blocked = all([
            config.get('BlockPublicAcls', False),
            config.get('IgnorePublicAcls', False),
            config.get('BlockPublicPolicy', False),
            config.get('RestrictPublicBuckets', False)
        ])
        
        assert not is_fully_blocked, "VULNERABILITY CONFIRMED: Public access not fully blocked"
        
    except s3.exceptions.NoSuchPublicAccessBlockConfiguration:
        # No public access block config = vulnerable
        assert True, "VULNERABILITY CONFIRMED: No public access block configuration exists"

  # Remediation: Fix the vulnerability
  remediation_code: |
    import boto3
    
    s3 = boto3.client('s3', region_name='{{AWS_REGION}}')
    
    # Enable all Block Public Access settings
    s3.put_public_access_block(
        Bucket='{{BUCKET_NAME}}',
        PublicAccessBlockConfiguration={
            'BlockPublicAcls': True,
            'IgnorePublicAcls': True,
            'BlockPublicPolicy': True,
            'RestrictPublicBuckets': True
        }
    )
    
    print(f"Successfully enabled Block Public Access for bucket: {{BUCKET_NAME}}")

  # Post-check: Verify the fix worked
  # Should raise AssertionError if fix did NOT work
  post_check_code: |
    import boto3
    
    s3 = boto3.client('s3', region_name='{{AWS_REGION}}')
    
    response = s3.get_public_access_block(Bucket='{{BUCKET_NAME}}')
    config = response['PublicAccessBlockConfiguration']
    
    # Verify ALL settings are now True
    assert config.get('BlockPublicAcls', False), "BlockPublicAcls not enabled"
    assert config.get('IgnorePublicAcls', False), "IgnorePublicAcls not enabled"
    assert config.get('BlockPublicPolicy', False), "BlockPublicPolicy not enabled"
    assert config.get('RestrictPublicBuckets', False), "RestrictPublicBuckets not enabled"
    
    print("REMEDIATION VERIFIED: All Block Public Access settings are enabled")

  # ============================================================================
  # METADATA
  # ============================================================================
  created_at: "2026-01-16T00:00:00Z"
  created_by: "PatchWeave Team"
  version: "1.0.0"
  
  # IAM permissions required to execute this playbook
  required_permissions:
    - "s3:GetPublicAccessBlock"
    - "s3:PutPublicAccessBlock"
  
  # Estimated time to execute remediation (seconds)
  estimated_execution_time_seconds: 5
```

### Playbook Loader

```python
# src/patchweave/core/playbook_loader.py

import os
import yaml
from pathlib import Path
from typing import List
from ..models.playbook import Playbook
from ..config import settings
import structlog

log = structlog.get_logger()

class PlaybookLoader:
    """Loads and validates playbooks from YAML files."""
    
    def __init__(self, playbooks_dir: str = None):
        self.playbooks_dir = Path(playbooks_dir or settings.playbooks_directory)
    
    def load_all(self) -> List[Playbook]:
        """Load all playbooks from the playbooks directory."""
        playbooks = []
        
        if not self.playbooks_dir.exists():
            log.warning("playbooks_directory_not_found", path=str(self.playbooks_dir))
            return playbooks
        
        for yaml_file in self.playbooks_dir.glob("*.yaml"):
            try:
                playbook = self.load_file(yaml_file)
                playbooks.append(playbook)
                log.info("playbook_loaded", 
                         playbook_id=playbook.id,
                         name=playbook.name,
                         vulnerability_type=playbook.vulnerability_type)
            except Exception as e:
                log.error("playbook_load_failed",
                          file=str(yaml_file),
                          error=str(e))
        
        log.info("all_playbooks_loaded", count=len(playbooks))
        return playbooks
    
    def load_file(self, file_path: Path) -> Playbook:
        """Load a single playbook from YAML file."""
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        playbook_data = data.get('playbook', data)
        return Playbook(**playbook_data)
```

---

## 5.7 API Specification

### FastAPI Application

```python
# src/patchweave/api/app.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import health, queue, findings, playbooks, stats

app = FastAPI(
    title="PatchWeave API",
    description="Cloud Security Remediation System API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(queue.router, prefix="/queue", tags=["Queue"])
app.include_router(findings.router, prefix="/findings", tags=["Findings"])
app.include_router(playbooks.router, prefix="/playbooks", tags=["Playbooks"])
app.include_router(stats.router, prefix="/stats", tags=["Statistics"])
```

### API Endpoints Detail

#### Health Check

```python
# src/patchweave/api/routes/health.py

from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    components: dict

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check system health and component status."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.utcnow(),
        components={
            "jira": "connected",
            "chromadb": "connected",
            "queue": "active"
        }
    )
```

#### Queue Status

```python
# src/patchweave/api/routes/queue.py

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class QueueStatus(BaseModel):
    pending_count: int
    currently_processing: Optional[str]
    current_status: Optional[str]

@router.get("", response_model=QueueStatus)
async def get_queue_status():
    """Get current queue status."""
    from ...core.queue import finding_queue
    return finding_queue.status()
```

#### Findings

```python
# src/patchweave/api/routes/findings.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter()

class FindingStatus(BaseModel):
    finding_id: str
    status: str
    vulnerability_type: str
    severity: str
    playbook_matched: bool
    playbook_id: Optional[str]
    match_score: Optional[float]
    created_at: datetime
    updated_at: datetime

class RetryResponse(BaseModel):
    finding_id: str
    action: str
    message: str

@router.get("/{finding_id}", response_model=FindingStatus)
async def get_finding_status(finding_id: str):
    """Get status of a specific finding."""
    # Implementation retrieves from state store
    raise HTTPException(status_code=404, detail="Finding not found")

@router.post("/{finding_id}/retry", response_model=RetryResponse)
async def retry_finding(finding_id: str):
    """Re-queue a finding for processing."""
    # Implementation resets finding to OPEN and adds to queue
    return RetryResponse(
        finding_id=finding_id,
        action="queued_for_retry",
        message=f"Finding {finding_id} has been re-queued for processing"
    )
```

#### Playbooks

```python
# src/patchweave/api/routes/playbooks.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter()

class PlaybookSummary(BaseModel):
    id: str
    name: str
    vulnerability_type: str
    severity: str
    version: str

class PlaybookListResponse(BaseModel):
    count: int
    playbooks: List[PlaybookSummary]

@router.get("", response_model=PlaybookListResponse)
async def list_playbooks():
    """List all available playbooks."""
    from ...integrations.chromadb import chromadb_client
    playbooks = chromadb_client.get_all_playbooks()
    return PlaybookListResponse(
        count=len(playbooks),
        playbooks=[
            PlaybookSummary(
                id=p.id,
                name=p.name,
                vulnerability_type=p.vulnerability_type,
                severity=p.severity,
                version=p.version
            )
            for p in playbooks
        ]
    )

@router.get("/{playbook_id}")
async def get_playbook(playbook_id: str):
    """Get details of a specific playbook."""
    from ...integrations.chromadb import chromadb_client
    playbook = chromadb_client.get_playbook(playbook_id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return playbook
```

#### Statistics

```python
# src/patchweave/api/routes/stats.py

from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class SystemStats(BaseModel):
    resolved_today: int
    resolved_total: int
    failed_total: int
    pending_approval: int
    avg_resolution_minutes: float
    playbook_hit_rate: float
    uptime_hours: float

@router.get("", response_model=SystemStats)
async def get_statistics():
    """Get system-wide statistics."""
    # Implementation retrieves from metrics store
    return SystemStats(
        resolved_today=5,
        resolved_total=42,
        failed_total=3,
        pending_approval=2,
        avg_resolution_minutes=28.5,
        playbook_hit_rate=0.85,
        uptime_hours=168.5
    )
```

---

## 5.8 Docker Configuration

### Docker Compose

```yaml
# docker-compose.yml

version: '3.8'

services:
  # LocalStack for AWS simulation
  localstack:
    image: localstack/localstack:3.0
    ports:
      - "4566:4566"            # LocalStack gateway
      - "4510-4559:4510-4559"  # External services
    environment:
      - SERVICES=s3,ec2,rds,iam,cloudtrail,logs,sts
      - DEBUG=1
      - PERSISTENCE=1
    volumes:
      - "./localstack_data:/var/lib/localstack"
      - "/var/run/docker.sock:/var/run/docker.sock"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4566/_localstack/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ChromaDB for vector storage
  chromadb:
    image: chromadb/chroma:0.4.22
    ports:
      - "8000:8000"
    volumes:
      - "./chroma_data:/chroma/chroma"
    environment:
      - ANONYMIZED_TELEMETRY=false

  # PatchWeave Application (optional - can also run locally)
  patchweave:
    build: .
    ports:
      - "8080:8080"
    environment:
      - PATCHWEAVE_ENV=development
      - LOCALSTACK_ENDPOINT=http://localstack:4566
      - USE_LOCALSTACK=true
      - CHROMA_HOST=chromadb
      - CHROMA_PORT=8000
    depends_on:
      localstack:
        condition: service_healthy
      chromadb:
        condition: service_started
    volumes:
      - "./.env:/app/.env"
      - "./playbooks:/app/playbooks"
```

### Dockerfile

```dockerfile
# Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Terraform
RUN curl -fsSL https://releases.hashicorp.com/terraform/1.7.0/terraform_1.7.0_linux_amd64.zip -o terraform.zip \
    && unzip terraform.zip \
    && mv terraform /usr/local/bin/ \
    && rm terraform.zip

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy application code
COPY src/ ./src/
COPY playbooks/ ./playbooks/

# Create non-root user
RUN useradd -m patchweave
USER patchweave

# Expose API port
EXPOSE 8080

# Run application
CMD ["uvicorn", "patchweave.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## 5.9 Environment Setup Guide

### Prerequisites

1. **Python 3.11+**: Download from python.org or use pyenv
2. **Docker & Docker Compose**: For LocalStack and ChromaDB
3. **Git**: Version control
4. **Terraform 1.7+**: For validation environments

### Setup Steps

```bash
# 1. Clone repository
git clone https://github.com/your-org/patchweave.git
cd patchweave

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Copy environment template
cp .env.example .env
# Edit .env with your configuration

# 5. Start infrastructure services
docker-compose up -d localstack chromadb

# 6. Wait for services to be healthy
docker-compose ps

# 7. Load playbooks into ChromaDB
python -m patchweave.scripts.load_playbooks

# 8. Run the application
python -m patchweave.main

# 9. (Alternative) Run with uvicorn for API
uvicorn patchweave.api.app:app --reload --port 8080

# 10. Access Swagger documentation
# Open http://localhost:8080/docs in browser
```

### Verification Commands

```bash
# Check LocalStack health
curl http://localhost:4566/_localstack/health

# List S3 buckets (should work even if empty)
aws --endpoint-url=http://localhost:4566 s3 ls

# Check ChromaDB
curl http://localhost:8000/api/v1/heartbeat

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=patchweave --cov-report=html
```

---

*End of Section 5: Detailed Implementation Blueprint*

---

# 6. End-to-End System Workflow

## 6.1 Complete Happy Path Workflow

This section traces a complete successful remediation from CSPM finding to production deployment.

### Scenario: S3 Bucket with Public Access

**Initial Condition**: A CSPM tool (Wiz) detects that an S3 bucket named `prod-logs-bucket` in AWS account `123456789012` has Block Public Access disabled.

---

### Step 1: Finding Creation (External)

**Actor**: CSPM Tool (Wiz)

**Action**: Wiz creates a Jira ticket in the configured project.

```
Jira Ticket: SEC-1234
Status: OPEN
Title: S3 Bucket 'prod-logs-bucket' has public access enabled
Description:
  The S3 bucket prod-logs-bucket in account 123456789012 (us-east-1) 
  has Block Public Access disabled, allowing potential public exposure.
  
  Resource: arn:aws:s3:::prod-logs-bucket
  Account: 123456789012
  Region: us-east-1
  
  Compliance: CIS AWS 2.1.1
  
Severity: Critical
Created: 2026-01-16 10:00:00 UTC
```

**Time**: T+0

---

### Step 2: Finding Ingestion

**Actor**: Jira Client (polling every 60 seconds)

**Action**: 
1. Poll Jira for tickets with status `OPEN` in project `SEC`
2. Fetch ticket SEC-1234 details
3. Create `RawFinding` object
4. Add to processing queue

**Log Output**:
```json
{"event": "jira_poll_complete", "new_tickets": 1, "level": "info", "timestamp": "2026-01-16T10:00:45Z"}
{"event": "finding_received", "finding_id": "SEC-1234", "severity": "Critical", "level": "info", "timestamp": "2026-01-16T10:00:45Z"}
{"event": "finding_queued", "finding_id": "SEC-1234", "queue_size": 1, "level": "info", "timestamp": "2026-01-16T10:00:45Z"}
```

**Jira Update**: Status changed to `ANALYZING`

**Time**: T+45 seconds (next poll cycle)

---

### Step 3: Tokenization

**Actor**: Tokenizer

**Action**:
1. Parse raw finding text
2. Identify sensitive patterns using regex
3. Replace with tokens
4. Store token mapping

**Before Tokenization**:
```
Title: S3 Bucket 'prod-logs-bucket' has public access enabled
Description: The S3 bucket prod-logs-bucket in account 123456789012 (us-east-1)...
```

**After Tokenization**:
```
Title: S3 Bucket '{{BUCKET_NAME}}' has public access enabled
Description: The S3 bucket {{BUCKET_NAME}} in account {{ACCOUNT_ID}} ({{AWS_REGION}})...
```

**Token Mapping Stored**:
```python
{
    "finding_id": "SEC-1234",
    "tokens": {
        "BUCKET_NAME": "prod-logs-bucket",
        "ACCOUNT_ID": "123456789012",
        "AWS_REGION": "us-east-1",
        "RESOURCE_ARN": "arn:aws:s3:::prod-logs-bucket"
    }
}
```

**Log Output**:
```json
{"event": "tokenization_complete", "finding_id": "SEC-1234", "tokens_found": 4, "token_types": ["BUCKET_NAME", "ACCOUNT_ID", "AWS_REGION", "RESOURCE_ARN"], "level": "info", "timestamp": "2026-01-16T10:00:46Z"}
```

**Time**: T+46 seconds

---

### Step 4: Analysis

**Actor**: Analyzer Agent (LangGraph + LLM)

**Action**:
1. Receive sanitized finding
2. Classify vulnerability type using fixed taxonomy
3. Extract resource metadata
4. Generate search query for ChromaDB
5. Create `AnalyzedFinding` object

**LLM Prompt** (simplified):
```
Analyze this security finding and classify it.

Finding:
Title: S3 Bucket '{{BUCKET_NAME}}' has public access enabled
Description: The S3 bucket {{BUCKET_NAME}} in account {{ACCOUNT_ID}} ({{AWS_REGION}}) has Block Public Access disabled...

Classify into one of: s3_public_access, s3_encryption_disabled, security_group_open_ssh, ...

Respond with JSON: {"vulnerability_type": "...", "resource_type": "...", "confidence": 0.0-1.0}
```

**LLM Response**:
```json
{
    "vulnerability_type": "s3_public_access",
    "resource_type": "AWS::S3::Bucket",
    "confidence": 0.98
}
```

**Generated Search Query**:
```
S3 bucket public access Block Public Access disabled publicly accessible bucket exposure
```

**Output** (`AnalyzedFinding`):
```python
AnalyzedFinding(
    finding_id="SEC-1234",
    vulnerability_type=VulnerabilityType.S3_PUBLIC_ACCESS,
    cloud_provider=CloudProvider.AWS,
    resource_type="AWS::S3::Bucket",
    severity=Severity.CRITICAL,
    search_query="S3 bucket public access Block Public Access disabled publicly accessible bucket exposure",
    sanitized_title="S3 Bucket '{{BUCKET_NAME}}' has public access enabled",
    sanitized_description="The S3 bucket {{BUCKET_NAME}} in account {{ACCOUNT_ID}}...",
    token_keys=["BUCKET_NAME", "ACCOUNT_ID", "AWS_REGION", "RESOURCE_ARN"],
    analysis_confidence=0.98,
    status=JiraStatus.PLAYBOOK_SEARCH
)
```

**Jira Update**: Status changed to `PLAYBOOK SEARCH`

**Log Output**:
```json
{"event": "analyzer_complete", "finding_id": "SEC-1234", "vulnerability_type": "s3_public_access", "confidence": 0.98, "level": "info", "timestamp": "2026-01-16T10:00:48Z"}
{"event": "status_transition", "finding_id": "SEC-1234", "from_status": "ANALYZING", "to_status": "PLAYBOOK SEARCH", "level": "info", "timestamp": "2026-01-16T10:00:48Z"}
```

**Time**: T+48 seconds

---

### Step 5: Playbook Matching

**Actor**: PlaybookMatcher + ChromaDB

**Action**:
1. First, attempt exact match on `vulnerability_type`
2. Query ChromaDB for playbooks with `vulnerability_type = "s3_public_access"`
3. Calculate similarity scores
4. Apply three-tier classification

**ChromaDB Query**:
```python
# Exact type match query
collection.get(
    where={"vulnerability_type": "s3_public_access"}
)
```

**Result**: Playbook `550e8400-e29b-41d4-a716-446655440001` ("S3 Block Public Access") found

**Similarity Calculation**:
- Semantic similarity between search query and playbook `search_text`: **0.94**
- Classification: **HIGH_CONFIDENCE** (≥0.90)

**Output** (`PlaybookMatch`):
```python
PlaybookMatch(
    playbook=Playbook(id="550e8400-...", name="S3 Block Public Access", ...),
    similarity_score=0.94,
    match_tier=MatchTier.HIGH_CONFIDENCE
)
```

**Decision**: Score ≥ 0.90 → **Proceed directly to Validation** (skip Verification Agent)

**Log Output**:
```json
{"event": "chromadb_search", "query": "S3 bucket public access...", "results_count": 1, "level": "debug", "timestamp": "2026-01-16T10:00:49Z"}
{"event": "high_confidence_match", "finding_id": "SEC-1234", "playbook_id": "550e8400-...", "score": 0.94, "level": "info", "timestamp": "2026-01-16T10:00:49Z"}
```

**Time**: T+49 seconds

---

### Step 6: Validation Workflow

**Actor**: Validation Orchestrator (LangGraph multi-agent workflow)

**Jira Update**: Status changed to `VALIDATING`

#### Step 6a: Environment Creation

**Actor**: Environment Replication Agent

**Action**:
1. Generate Terraform configuration for test S3 bucket
2. Configure bucket to mimic the vulnerability (Block Public Access disabled)
3. Execute `terraform init` and `terraform apply`

**Generated Terraform**:
```hcl
# Generated for validation of SEC-1234
provider "aws" {
  region                      = "us-east-1"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  
  endpoints {
    s3 = "http://localhost:4566"  # LocalStack
  }
}

resource "aws_s3_bucket" "test_bucket" {
  bucket = "patchweave-test-sec-1234-${random_id.suffix.hex}"
}

resource "aws_s3_bucket_public_access_block" "test_bucket" {
  bucket = aws_s3_bucket.test_bucket.id
  
  # Intentionally insecure to replicate vulnerability
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "random_id" "suffix" {
  byte_length = 4
}

output "bucket_name" {
  value = aws_s3_bucket.test_bucket.id
}
```

**Terraform Execution**:
```bash
$ terraform init
$ terraform apply -auto-approve

Apply complete! Resources: 3 added, 0 changed, 0 destroyed.

Outputs:
bucket_name = "patchweave-test-sec-1234-a1b2c3d4"
```

**Test Environment Created**:
```python
TestEnvironment(
    environment_id="env-sec-1234-a1b2c3d4",
    finding_id="SEC-1234",
    terraform_state_path="/tmp/patchweave/SEC-1234/terraform.tfstate",
    resources_created=["aws_s3_bucket.test_bucket", "aws_s3_bucket_public_access_block.test_bucket"],
    created_at="2026-01-16T10:01:00Z"
)
```

**Log Output**:
```json
{"event": "validation_stage_start", "finding_id": "SEC-1234", "stage": "environment_creation", "level": "info", "timestamp": "2026-01-16T10:00:50Z"}
{"event": "terraform_apply_complete", "finding_id": "SEC-1234", "resources_created": 3, "level": "info", "timestamp": "2026-01-16T10:01:00Z"}
{"event": "validation_stage_complete", "finding_id": "SEC-1234", "stage": "environment_creation", "success": true, "duration_seconds": 10, "level": "info", "timestamp": "2026-01-16T10:01:00Z"}
```

**Time**: T+60 seconds

---

#### Step 6b: Pre-Check Verification

**Actor**: Pre-Check Verification Agent

**Action**:
1. Extract `pre_check_code` from playbook
2. Substitute tokens for test environment values
3. Execute code against test environment
4. Verify vulnerability exists (assertion should pass)

**Token Substitution for Test**:
```python
# Test environment tokens (NOT production values)
test_tokens = {
    "BUCKET_NAME": "patchweave-test-sec-1234-a1b2c3d4",
    "AWS_REGION": "us-east-1"
}
```

**Executed Pre-Check Code**:
```python
import boto3

s3 = boto3.client('s3', 
                   region_name='us-east-1',
                   endpoint_url='http://localhost:4566')

try:
    response = s3.get_public_access_block(Bucket='patchweave-test-sec-1234-a1b2c3d4')
    config = response['PublicAccessBlockConfiguration']
    
    is_fully_blocked = all([
        config.get('BlockPublicAcls', False),
        config.get('IgnorePublicAcls', False),
        config.get('BlockPublicPolicy', False),
        config.get('RestrictPublicBuckets', False)
    ])
    
    assert not is_fully_blocked, "VULNERABILITY CONFIRMED: Public access not fully blocked"
except Exception as e:
    # NoSuchPublicAccessBlockConfiguration = vulnerable
    pass
```

**Result**: Assertion passes → Vulnerability confirmed in test environment ✓

**Log Output**:
```json
{"event": "validation_stage_start", "finding_id": "SEC-1234", "stage": "pre_check", "level": "info", "timestamp": "2026-01-16T10:01:01Z"}
{"event": "pre_check_result", "finding_id": "SEC-1234", "vulnerability_confirmed": true, "level": "info", "timestamp": "2026-01-16T10:01:02Z"}
{"event": "validation_stage_complete", "finding_id": "SEC-1234", "stage": "pre_check", "success": true, "duration_seconds": 1, "level": "info", "timestamp": "2026-01-16T10:01:02Z"}
```

**Time**: T+62 seconds

---

#### Step 6c: Remediation Execution

**Actor**: Remediation Executor

**Action**:
1. Extract `remediation_code` from playbook
2. Substitute tokens for test environment
3. Execute remediation code
4. Capture results

**Executed Remediation Code**:
```python
import boto3

s3 = boto3.client('s3',
                   region_name='us-east-1',
                   endpoint_url='http://localhost:4566')

s3.put_public_access_block(
    Bucket='patchweave-test-sec-1234-a1b2c3d4',
    PublicAccessBlockConfiguration={
        'BlockPublicAcls': True,
        'IgnorePublicAcls': True,
        'BlockPublicPolicy': True,
        'RestrictPublicBuckets': True
    }
)

print("Successfully enabled Block Public Access for bucket: patchweave-test-sec-1234-a1b2c3d4")
```

**Result**: Code executes successfully ✓

**Log Output**:
```json
{"event": "validation_stage_start", "finding_id": "SEC-1234", "stage": "remediation", "level": "info", "timestamp": "2026-01-16T10:01:03Z"}
{"event": "remediation_executed", "finding_id": "SEC-1234", "playbook_id": "550e8400-...", "level": "info", "timestamp": "2026-01-16T10:01:04Z"}
{"event": "validation_stage_complete", "finding_id": "SEC-1234", "stage": "remediation", "success": true, "duration_seconds": 1, "level": "info", "timestamp": "2026-01-16T10:01:04Z"}
```

**Time**: T+64 seconds

---

#### Step 6d: Post-Check Verification

**Actor**: Post-Check Verification Agent

**Action**:
1. Extract `post_check_code` from playbook
2. Execute against test environment
3. Verify fix was successful (assertion should pass)

**Executed Post-Check Code**:
```python
import boto3

s3 = boto3.client('s3',
                   region_name='us-east-1',
                   endpoint_url='http://localhost:4566')

response = s3.get_public_access_block(Bucket='patchweave-test-sec-1234-a1b2c3d4')
config = response['PublicAccessBlockConfiguration']

assert config.get('BlockPublicAcls', False), "BlockPublicAcls not enabled"
assert config.get('IgnorePublicAcls', False), "IgnorePublicAcls not enabled"
assert config.get('BlockPublicPolicy', False), "BlockPublicPolicy not enabled"
assert config.get('RestrictPublicBuckets', False), "RestrictPublicBuckets not enabled"

print("REMEDIATION VERIFIED: All Block Public Access settings are enabled")
```

**Result**: All assertions pass → Fix verified ✓

**Log Output**:
```json
{"event": "validation_stage_start", "finding_id": "SEC-1234", "stage": "post_check", "level": "info", "timestamp": "2026-01-16T10:01:05Z"}
{"event": "post_check_result", "finding_id": "SEC-1234", "fix_verified": true, "level": "info", "timestamp": "2026-01-16T10:01:06Z"}
{"event": "validation_stage_complete", "finding_id": "SEC-1234", "stage": "post_check", "success": true, "duration_seconds": 1, "level": "info", "timestamp": "2026-01-16T10:01:06Z"}
```

**Time**: T+66 seconds

---

#### Step 6e: Cleanup

**Actor**: Cleanup Agent

**Action**:
1. Execute `terraform destroy`
2. Verify all resources deleted
3. Remove temporary files

**Terraform Destroy**:
```bash
$ terraform destroy -auto-approve

Destroy complete! Resources: 3 destroyed.
```

**Log Output**:
```json
{"event": "validation_stage_start", "finding_id": "SEC-1234", "stage": "cleanup", "level": "info", "timestamp": "2026-01-16T10:01:07Z"}
{"event": "terraform_destroy_complete", "finding_id": "SEC-1234", "resources_destroyed": 3, "level": "info", "timestamp": "2026-01-16T10:01:12Z"}
{"event": "validation_stage_complete", "finding_id": "SEC-1234", "stage": "cleanup", "success": true, "duration_seconds": 5, "level": "info", "timestamp": "2026-01-16T10:01:12Z"}
```

**Time**: T+72 seconds

---

#### Validation Complete

**Validation Result**:
```python
ValidationResult(
    finding_id="SEC-1234",
    playbook_id="550e8400-...",
    environment_creation=StageResult(stage="environment_creation", success=True, duration_seconds=10),
    pre_check=StageResult(stage="pre_check", success=True, duration_seconds=1),
    remediation=StageResult(stage="remediation", success=True, duration_seconds=1),
    post_check=StageResult(stage="post_check", success=True, duration_seconds=1),
    cleanup=StageResult(stage="cleanup", success=True, duration_seconds=5),
    success=True,
    total_duration_seconds=18
)
```

**Log Output**:
```json
{"event": "validation_complete", "finding_id": "SEC-1234", "success": true, "total_duration_seconds": 18, "level": "info", "timestamp": "2026-01-16T10:01:12Z"}
```

**Time**: T+72 seconds

---

### Step 7: Human Approval Request

**Actor**: Approval Handler

**Action**:
1. Format approval request comment
2. Post to Jira ticket
3. Update status to PENDING APPROVAL
4. Begin polling for approval

**Jira Comment Posted**:
```markdown
## PatchWeave Remediation Approval Request

**Finding**: S3 bucket with public access enabled
**Resource**: {{BUCKET_NAME}} in {{AWS_REGION}}
**Severity**: Critical

### Validation Results ✅
- Pre-check: Vulnerability confirmed in test environment
- Remediation: Applied successfully  
- Post-check: Fix verified working
- Cleanup: Test environment destroyed

### Remediation Code
```python
s3.put_public_access_block(
    Bucket='{{BUCKET_NAME}}',
    PublicAccessBlockConfiguration={
        'BlockPublicAcls': True,
        'IgnorePublicAcls': True,
        'BlockPublicPolicy': True,
        'RestrictPublicBuckets': True
    }
)
```

### Required Permissions
- s3:GetPublicAccessBlock
- s3:PutPublicAccessBlock

### Actions
- Transition to **Approved** to deploy to production
- Transition to **Rejected** to cancel (add reason in comment)
```

**Jira Update**: Status changed to `PENDING APPROVAL`

**Log Output**:
```json
{"event": "approval_requested", "finding_id": "SEC-1234", "level": "info", "timestamp": "2026-01-16T10:01:13Z", "_audit": true}
{"event": "status_transition", "finding_id": "SEC-1234", "from_status": "VALIDATING", "to_status": "PENDING APPROVAL", "level": "info", "timestamp": "2026-01-16T10:01:13Z"}
```

**Time**: T+73 seconds

---

### Step 8: Human Approval (External)

**Actor**: Security Engineer (Human)

**Action**: 
1. Receive notification of pending approval
2. Review Jira ticket and validation results
3. Verify remediation is appropriate for this resource
4. Transition ticket status to `Approved`

**Time**: T+15 minutes (human review time varies)

---

### Step 9: Approval Detection

**Actor**: Approval Handler (polling every 60 seconds)

**Action**:
1. Poll Jira for status of SEC-1234
2. Detect status change to `Approved`
3. Identify approver from Jira audit log
4. Proceed to deployment

**Jira Response**:
```json
{
    "key": "SEC-1234",
    "fields": {
        "status": {"name": "Approved"}
    },
    "changelog": {
        "histories": [{
            "author": {"emailAddress": "john.security@company.com"},
            "items": [{"field": "status", "toString": "Approved"}]
        }]
    }
}
```

**Log Output**:
```json
{"event": "approval_detected", "finding_id": "SEC-1234", "level": "info", "timestamp": "2026-01-16T10:16:30Z"}
{"event": "approval_granted", "finding_id": "SEC-1234", "approver": "john.security@company.com", "level": "info", "timestamp": "2026-01-16T10:16:30Z", "_audit": true}
```

**Jira Update**: Status changed to `DEPLOYING`

**Time**: T+16 minutes

---

### Step 10: Production Deployment

**Actor**: Deployment Agent

**Action**:
1. Retrieve token mapping for SEC-1234
2. Substitute tokens with actual production values
3. Configure production AWS credentials
4. Execute remediation code against production

**Token Substitution (Production)**:
```python
# Production values from token mapping
production_tokens = {
    "BUCKET_NAME": "prod-logs-bucket",
    "AWS_REGION": "us-east-1"
}
```

**Executed Production Code**:
```python
import boto3

s3 = boto3.client('s3',
                   region_name='us-east-1',
                   aws_access_key_id=PROD_ACCESS_KEY,
                   aws_secret_access_key=PROD_SECRET_KEY)

s3.put_public_access_block(
    Bucket='prod-logs-bucket',
    PublicAccessBlockConfiguration={
        'BlockPublicAcls': True,
        'IgnorePublicAcls': True,
        'BlockPublicPolicy': True,
        'RestrictPublicBuckets': True
    }
)
```

**Result**: Production remediation successful ✓

**Deployment Result**:
```python
DeploymentResult(
    finding_id="SEC-1234",
    playbook_id="550e8400-...",
    success=True,
    resources_modified=["arn:aws:s3:::prod-logs-bucket"],
    approved_by="john.security@company.com",
    duration_seconds=2
)
```

**Log Output**:
```json
{"event": "deployment_started", "finding_id": "SEC-1234", "level": "info", "timestamp": "2026-01-16T10:16:31Z", "_audit": true}
{"event": "deployment_complete", "finding_id": "SEC-1234", "success": true, "resources_modified": ["arn:aws:s3:::prod-logs-bucket"], "level": "info", "timestamp": "2026-01-16T10:16:33Z", "_audit": true}
```

**Time**: T+16 minutes 3 seconds

---

### Step 11: Resolution & Learning

**Actor**: Pipeline Completion Handler

**Action**:
1. Update Jira status to RESOLVED
2. Post deployment summary comment
3. Store successful finding-playbook association in ChromaDB
4. Update statistics
5. Mark finding complete in queue

**Jira Comment Posted**:
```markdown
## ✅ Remediation Deployed Successfully

**Deployed**: 2026-01-16 10:16:33 UTC
**Approved by**: john.security@company.com
**Resources modified**: arn:aws:s3:::prod-logs-bucket

The S3 bucket now has Block Public Access enabled with all four settings activated.

---
*Automated by PatchWeave*
```

**Jira Update**: Status changed to `RESOLVED`

**ChromaDB Update**: Store association for future matching improvement

**Log Output**:
```json
{"event": "status_transition", "finding_id": "SEC-1234", "from_status": "DEPLOYING", "to_status": "RESOLVED", "level": "info", "timestamp": "2026-01-16T10:16:34Z"}
{"event": "finding_resolved", "finding_id": "SEC-1234", "total_duration_minutes": 16.5, "level": "info", "timestamp": "2026-01-16T10:16:34Z", "_audit": true}
{"event": "knowledge_base_updated", "finding_id": "SEC-1234", "playbook_id": "550e8400-...", "level": "info", "timestamp": "2026-01-16T10:16:34Z"}
{"event": "finding_complete", "finding_id": "SEC-1234", "level": "info", "timestamp": "2026-01-16T10:16:34Z"}
```

**Final Time**: T+16 minutes 34 seconds

---

### Workflow Summary

| Step | Duration | Cumulative | Status After |
|------|----------|------------|--------------|
| 1. Finding Creation | - | T+0 | OPEN |
| 2. Ingestion | 45s | T+45s | ANALYZING |
| 3. Tokenization | 1s | T+46s | ANALYZING |
| 4. Analysis | 2s | T+48s | PLAYBOOK SEARCH |
| 5. Matching | 1s | T+49s | PLAYBOOK SEARCH |
| 6. Validation | 23s | T+72s | VALIDATING |
| 7. Approval Request | 1s | T+73s | PENDING APPROVAL |
| 8. Human Approval | ~15min | T+15min | Approved |
| 9. Approval Detection | 30s | T+16min | DEPLOYING |
| 10. Deployment | 3s | T+16min 3s | DEPLOYING |
| 11. Resolution | 1s | T+16min 34s | RESOLVED |

**Total Time**: ~16.5 minutes (including ~15 minutes human review)
**Automated Time**: ~1.5 minutes

---

## 6.2 Alternative Flows

### Flow A: Moderate Confidence Match (70-89%)

When the playbook match score is between 70% and 89%, an additional verification step occurs.

```
┌─────────────┐
│ ChromaDB    │ Match score: 0.82 (82%)
│ Search      │
└──────┬──────┘
       │
       ▼ Moderate confidence
┌──────────────────────┐
│ Playbook Verification │
│ Agent                 │
│                       │
│ "Does this playbook   │
│  logically match the  │
│  finding?"            │
└──────┬───────────────┘
       │
       ├─── Approved ───────▶ Continue to Validation
       │
       └─── Rejected ───────▶ Status: NO PLAYBOOK
                             (Manual intervention)
```

**Verification Agent Prompt**:
```
Analyze whether this playbook is appropriate for the finding.

Finding:
- Type: security_group_open_ssh
- Description: Security group sg-abc123 allows inbound SSH from 0.0.0.0/0

Playbook:
- Name: Security Group Remove Open SSH
- Description: Removes inbound rules allowing SSH (port 22) from 0.0.0.0/0

Does this playbook address the finding? Respond with JSON:
{"decision": "approved" | "rejected", "reason": "..."}
```

---

### Flow B: No Playbook Match (<70%)

When no suitable playbook exists, the system escalates to human intervention.

```
┌─────────────┐
│ ChromaDB    │ Best match score: 0.58 (58%)
│ Search      │
└──────┬──────┘
       │
       ▼ Below threshold
┌──────────────────────┐
│ No suitable playbook │
│                      │
│ Status → NO PLAYBOOK │
│                      │
│ Jira comment:        │
│ "No automated        │
│  remediation         │
│  available for this  │
│  finding type."      │
└──────────────────────┘
```

**Jira Comment**:
```markdown
## ⚠️ No Automated Remediation Available

PatchWeave could not find a suitable remediation playbook for this finding.

**Finding Type**: (analyzed as) unknown
**Best Match Score**: 58% (threshold: 70%)

**Manual intervention required.**

This finding requires manual remediation by a security engineer.

---
*If you create a manual fix, consider contributing it as a new playbook.*
```

---

### Flow C: Approval Rejection

When a human reviewer rejects the remediation.

```
┌───────────────────┐
│ PENDING APPROVAL  │
└─────────┬─────────┘
          │
          ▼ Human rejects
┌───────────────────────────────┐
│ Approver transitions to       │
│ "Rejected" with comment:      │
│                               │
│ "This bucket is intentionally │
│  public for static website    │
│  hosting. Do not remediate."  │
└───────────────────┬───────────┘
                    │
                    ▼
┌───────────────────────────────┐
│ Status → REJECTED             │
│                               │
│ Log rejection reason          │
│ No deployment occurs          │
│ Finding marked complete       │
└───────────────────────────────┘
```

**Log Output**:
```json
{"event": "approval_rejected", "finding_id": "SEC-1234", "rejector": "john.security@company.com", "reason": "This bucket is intentionally public for static website hosting.", "level": "info", "timestamp": "2026-01-16T10:20:00Z", "_audit": true}
```

---

## 6.3 Failure Scenarios

### Failure 1: Terraform Environment Creation Fails

**Scenario**: AWS API rate limit or resource quota exceeded during test environment creation.

```
┌────────────────────┐
│ Environment        │
│ Replication Agent  │
└─────────┬──────────┘
          │
          ▼ terraform apply fails
┌────────────────────────────────────────┐
│ Error: Error creating S3 bucket:       │
│ TooManyBuckets: You have attempted to  │
│ create more buckets than allowed       │
└─────────┬──────────────────────────────┘
          │
          ▼ Fail-fast triggered
┌────────────────────────────────────────┐
│ 1. Log error details                   │
│ 2. Status → VALIDATION FAILED          │
│ 3. Post error to Jira                  │
│ 4. Cleanup attempted (nothing to clean)│
│ 5. Finding complete (failed)           │
└────────────────────────────────────────┘
```

**Jira Comment**:
```markdown
## ❌ Validation Failed

**Stage**: Environment Creation
**Error**: Terraform apply failed

```
Error creating S3 bucket: TooManyBuckets
You have attempted to create more buckets than allowed
```

**Manual investigation required.**

Possible causes:
- AWS account bucket limit reached
- Orphaned test resources from previous runs
- AWS service disruption

---
*PatchWeave Validation Workflow*
```

---

### Failure 2: Pre-Check Verification Fails

**Scenario**: The vulnerability cannot be reproduced in the test environment (test environment doesn't match production configuration).

```
┌────────────────────┐
│ Pre-Check          │
│ Verification       │
└─────────┬──────────┘
          │
          ▼ Assertion fails
┌────────────────────────────────────────┐
│ AssertionError:                        │
│ Vulnerability NOT confirmed -          │
│ Public access is already blocked       │
└─────────┬──────────────────────────────┘
          │
          ▼ Fail-fast triggered
┌────────────────────────────────────────┐
│ 1. Log error details                   │
│ 2. Status → VALIDATION FAILED          │
│ 3. Post error to Jira                  │
│ 4. Cleanup executes (always)           │
│ 5. Test environment destroyed          │
└────────────────────────────────────────┘
```

**Analysis**: This usually indicates the test environment template doesn't correctly replicate the vulnerability. The playbook or Terraform template may need adjustment.

---

### Failure 3: Post-Check Verification Fails

**Scenario**: The remediation executed but the fix didn't actually work.

```
┌────────────────────┐
│ Post-Check         │
│ Verification       │
└─────────┬──────────┘
          │
          ▼ Assertion fails
┌────────────────────────────────────────┐
│ AssertionError:                        │
│ BlockPublicAcls not enabled            │
└─────────┬──────────────────────────────┘
          │
          ▼ Fail-fast triggered
┌────────────────────────────────────────┐
│ 1. Log error details                   │
│ 2. Status → VALIDATION FAILED          │
│ 3. Post error to Jira                  │
│ 4. Cleanup executes (always)           │
│ 5. Remediation NOT deployed            │
└────────────────────────────────────────┘
```

**Analysis**: The playbook remediation code may have a bug, or AWS API behavior changed. Playbook needs investigation and update.

---

### Failure 4: Cleanup Fails (CRITICAL)

**Scenario**: Test environment resources cannot be destroyed.

```
┌────────────────────┐
│ Cleanup Agent      │
└─────────┬──────────┘
          │
          ▼ terraform destroy fails
┌────────────────────────────────────────┐
│ Error: Error deleting S3 bucket:       │
│ BucketNotEmpty: The bucket you tried   │
│ to delete is not empty                 │
└─────────┬──────────────────────────────┘
          │
          ▼ Retry cleanup (up to 3 times)
          │
          ▼ Still failing
┌────────────────────────────────────────┐
│ CRITICAL ALERT                         │
│                                        │
│ 1. Log critical error                  │
│ 2. Send alert (future: Slack/email)    │
│ 3. Continue pipeline (don't block)     │
│ 4. Manual cleanup required             │
└────────────────────────────────────────┘
```

**Log Output**:
```json
{"event": "cleanup_failed", "finding_id": "SEC-1234", "environment_id": "env-sec-1234-a1b2c3d4", "error": "BucketNotEmpty", "level": "critical", "timestamp": "2026-01-16T10:01:15Z", "_audit": true}
```

**Impact**: Orphaned cloud resources will incur costs and potentially pose security risks. Manual cleanup procedure must be followed.

---

### Failure 5: Deployment Fails

**Scenario**: Production deployment fails due to permission issues or resource state change.

```
┌────────────────────┐
│ Deployment Agent   │
└─────────┬──────────┘
          │
          ▼ boto3 API call fails
┌────────────────────────────────────────┐
│ AccessDenied: User is not authorized   │
│ to perform: s3:PutPublicAccessBlock    │
└─────────┬──────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────┐
│ 1. Log error with full details         │
│ 2. Status → DEPLOYMENT FAILED          │
│ 3. Post error to Jira                  │
│ 4. Alert team                          │
│ 5. NO rollback (nothing to roll back)  │
└────────────────────────────────────────┘
```

**Analysis**: Production IAM role doesn't have required permissions. This is a configuration issue requiring IAM policy update.

---

### Failure 6: Jira API Unavailable

**Scenario**: Jira is down or API rate limited.

```
┌────────────────────┐
│ Jira Client        │
└─────────┬──────────┘
          │
          ▼ HTTP 503 Service Unavailable
┌────────────────────────────────────────┐
│ Cannot connect to Jira API             │
└─────────┬──────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────┐
│ 1. Log warning                         │
│ 2. Wait for next poll cycle (60s)      │
│ 3. Retry on next cycle                 │
│ 4. Currently processing finding        │
│    continues if possible               │
└────────────────────────────────────────┘
```

**Note**: Jira unavailability blocks new finding ingestion and status updates, but doesn't crash the system.

---

## 6.4 Edge Cases

### Edge Case 1: Duplicate Finding

**Scenario**: Same vulnerability reported in multiple Jira tickets.

**Behavior**: PatchWeave processes each ticket independently. Both will match the same playbook and (if approved) both will attempt remediation. The second remediation is idempotent—applying Block Public Access when it's already enabled has no negative effect.

**Recommendation**: Configure CSPM tool to avoid duplicate findings, or implement deduplication in Phase 2.

---

### Edge Case 2: Finding Updated While Processing

**Scenario**: Human modifies the Jira ticket while PatchWeave is processing it.

**Behavior**: PatchWeave uses the ticket state captured at ingestion time. Changes made during processing are not reflected until the finding is complete or re-queued.

---

### Edge Case 3: Very Long Approval Wait

**Scenario**: Approver doesn't respond for days.

**Behavior**: PatchWeave continues polling indefinitely. The finding remains in PENDING APPROVAL state. Other findings are not blocked (sequential queue continues processing new items while waiting).

**Note**: Decision was made to have no timeout. Consider implementing escalation alerts in Phase 2.

---

### Edge Case 4: Playbook Matches Wrong Vulnerability

**Scenario**: Semantic similarity matches an inappropriate playbook.

**Safeguards**:
1. Three-tier matching requires 90% confidence for direct execution
2. 70-89% range goes through Verification Agent
3. Validation workflow confirms the fix works
4. Human approval is final checkpoint

**If all safeguards fail**: The fix is applied to production. It may not solve the issue but (for well-designed playbooks) shouldn't cause harm. The finding would likely be re-reported by CSPM.

---

### Edge Case 5: Token Not Found in Ticket

**Scenario**: Expected token (e.g., ACCOUNT_ID) cannot be extracted from ticket.

**Behavior**: 
- Tokenizer logs warning about missing expected token
- Analysis continues with available tokens
- If critical token is missing for playbook execution, remediation code will fail during validation pre-check
- Finding escalated as VALIDATION FAILED

---

### Edge Case 6: Empty ChromaDB (Cold Start)

**Scenario**: System starts with no playbooks loaded.

**Behavior**:
- All findings will get <70% match (nothing to match against)
- All findings go to NO PLAYBOOK status
- System is functional but provides no automation value

**Prevention**: Playbook loading is part of system startup. Application should fail to start if playbooks directory is empty or ChromaDB population fails.

---

*End of Section 6: End-to-End System Workflow*

---

# 7. Final Architecture & Decision Summary

## 7.1 Consolidated Architecture

### System Overview

PatchWeave is an intelligent, multi-agent cloud security remediation system that automates the process of fixing cloud misconfigurations detected by CSPM tools. The system bridges the gap between vulnerability detection and remediation through a sophisticated pipeline of AI agents, knowledge-based playbook matching, and validated deployments.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              PATCHWEAVE SYSTEM                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐     ┌──────────────────────────────────────────────────────┐  │
│  │   EXTERNAL   │     │                    CORE PIPELINE                      │  │
│  │              │     │                                                       │  │
│  │  ┌────────┐  │     │  ┌───────────┐   ┌──────────┐   ┌────────────────┐   │  │
│  │  │  Wiz   │──┼────▶│  │ Tokenizer │──▶│ Analyzer │──▶│ PlaybookMatcher│   │  │
│  │  │ (CSPM) │  │     │  └───────────┘   └──────────┘   └───────┬────────┘   │  │
│  │  └────────┘  │     │                                         │            │  │
│  │              │     │  ┌──────────────────────────────────────┼──────────┐ │  │
│  │  ┌────────┐  │     │  │         VALIDATION WORKFLOW          ▼          │ │  │
│  │  │  Jira  │◀─┼─────│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ │ │  │
│  │  │        │  │     │  │  │ Env     │▶│Pre-Check│▶│Remediate│▶│Post-   │ │ │  │
│  │  └────────┘  │     │  │  │ Create  │ │         │ │         │ │Check   │ │ │  │
│  │      ▲       │     │  │  └─────────┘ └─────────┘ └─────────┘ └───┬────┘ │ │  │
│  │      │       │     │  │                                          │      │ │  │
│  │  ┌───┴────┐  │     │  │  ┌─────────┐◀────────────────────────────┘      │ │  │
│  │  │ Human  │  │     │  │  │ Cleanup │  (Always executes)                 │ │  │
│  │  │Approver│  │     │  │  └─────────┘                                    │ │  │
│  │  └────────┘  │     │  └─────────────────────────────────────────────────┘ │  │
│  │              │     │                                                       │  │
│  └──────────────┘     │  ┌───────────────┐   ┌────────────────────────────┐  │  │
│                       │  │   Deployment  │◀──│   Human Approval Handler   │  │  │
│  ┌──────────────┐     │  │     Agent     │   │   (Jira Status Polling)    │  │  │
│  │   AWS PROD   │◀────│  └───────────────┘   └────────────────────────────┘  │  │
│  │              │     │                                                       │  │
│  └──────────────┘     └──────────────────────────────────────────────────────┘  │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                           DATA STORES                                     │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────────────┐ │   │
│  │  │   ChromaDB     │  │  Token Store   │  │    Structured Logs          │ │   │
│  │  │  (Playbooks)   │  │   (In-Memory)  │  │  (JSON + File Rotation)     │ │   │
│  │  └────────────────┘  └────────────────┘  └─────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         TEST ENVIRONMENT                                  │   │
│  │  ┌────────────────┐  ┌────────────────┐                                  │   │
│  │  │   LocalStack   │  │   Terraform    │                                  │   │
│  │  │  (AWS Sim)     │  │   (IaC)        │                                  │   │
│  │  └────────────────┘  └────────────────┘                                  │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Core Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Human-in-the-Loop** | All production deployments require explicit human approval via Jira status transition |
| **Fail-Fast** | Any validation failure immediately stops the pipeline and triggers cleanup |
| **Always Cleanup** | Test environment destruction runs regardless of success or failure |
| **Tokenization for Safety** | Sensitive data never exposed to LLMs; placeholders enable playbook generalization |
| **Validation Before Production** | Every remediation proven in test environment before production deployment |
| **Auditability** | Complete structured logging of all decisions, approvals, and deployments |

### Data Flow Summary

```
1. INGESTION
   Jira Ticket → Jira Client → RawFinding → Queue

2. ANALYSIS
   RawFinding → Tokenizer → SanitizedFinding → Analyzer → AnalyzedFinding

3. MATCHING
   AnalyzedFinding → ChromaDB Query → PlaybookMatch (with confidence tier)

4. VALIDATION
   PlaybookMatch → Environment Creation → Pre-Check → Remediation → Post-Check → Cleanup
   
5. APPROVAL
   ValidationResult → Jira Comment → Human Review → Approval/Rejection

6. DEPLOYMENT
   Approval → Token Substitution → Production Execution → Resolution
```

---

## 7.2 Complete Decision Registry

All 15 architectural decisions made during planning, with full context.

### Decision 1: Project Name
| Aspect | Detail |
|--------|--------|
| **Decision** | Use "PatchWeave" as the official project name |
| **Alternatives Considered** | CloudSafe |
| **Rationale** | Evokes the idea of weaving together patches (fixes) for cloud infrastructure; more distinctive and memorable |
| **Impact** | All documentation, code, and branding use PatchWeave consistently |

### Decision 2: Sanitization Strategy
| Aspect | Detail |
|--------|--------|
| **Decision** | Tokenization with substitution placeholders |
| **Alternatives Considered** | Redaction (complete removal), No sanitization |
| **Rationale** | Tokens enable: (1) semantic analysis by LLM without exposure, (2) playbook reusability across accounts, (3) production deployment via substitution |
| **Token Format** | `{{TOKEN_TYPE}}` (e.g., `{{ACCOUNT_ID}}`, `{{BUCKET_NAME}}`) |
| **Impact** | Enables both security and functionality; adds tokenization/detokenization complexity |

### Decision 3: Failure Handling Strategy
| Aspect | Detail |
|--------|--------|
| **Decision** | Fail-Fast with Always Cleanup |
| **Alternatives Considered** | Best-effort continue, Retry with backoff |
| **Rationale** | Security-critical system should not proceed with partial/uncertain states; cleanup prevents resource leaks |
| **Implementation** | Any validation stage failure → immediate stop → cleanup → VALIDATION FAILED status |
| **Impact** | Prioritizes safety over completion rate; simpler error handling logic |

### Decision 4: Test Environment Strategy
| Aspect | Detail |
|--------|--------|
| **Decision** | LocalStack for development; real isolated AWS account when funded |
| **Alternatives Considered** | Real AWS from start, Mock objects only |
| **Rationale** | LocalStack provides realistic AWS API simulation at zero cost; real AWS planned for production-grade testing |
| **Transition Plan** | Terraform configurations work unchanged; only endpoint configuration changes |
| **Impact** | Enables immediate development; validation fidelity improves with real AWS |

### Decision 5: Playbook Match Threshold
| Aspect | Detail |
|--------|--------|
| **Decision** | Three-tier system |
| **Tier 1** | ≥90%: High confidence → proceed directly to validation |
| **Tier 2** | 70-89%: Moderate → Verification Agent review required |
| **Tier 3** | <70%: Low → no suitable playbook, human intervention |
| **Alternatives Considered** | Single threshold, Binary match/no-match |
| **Rationale** | Balances automation speed with accuracy; provides safety net for uncertain matches |
| **Impact** | Most findings processed automatically; edge cases get additional review |

### Decision 6: Phase 1 Scope
| Aspect | Detail |
|--------|--------|
| **Decision** | Include Deployment Agent and real AWS validation in Phase 1 |
| **Alternatives Considered** | Defer deployment to Phase 2, Validation only without deployment |
| **Rationale** | End-to-end demonstration is essential for capstone; proves complete value proposition |
| **Constraint** | Requires AWS credentials and permissions for target account |
| **Impact** | Phase 1 delivers complete remediation capability, not just validation |

### Decision 7: Knowledge Base Seeding
| Aspect | Detail |
|--------|--------|
| **Decision** | Manual curation of 10-15 high-value playbooks |
| **Alternatives Considered** | Automated generation from documentation, Large-scale seeding |
| **Rationale** | Quality over quantity; curated playbooks ensure reliability for demo scenarios |
| **Initial Playbooks** | S3 (3), Security Groups (3), IAM (2), EBS (2), RDS (2), KMS (2) |
| **Impact** | Manageable scope; each playbook thoroughly tested before inclusion |

### Decision 8: Playbook Format
| Aspect | Detail |
|--------|--------|
| **Decision** | Python/Boto3 executable scripts |
| **Alternatives Considered** | AWS CLI commands, Terraform modules, Cloud-native remediation APIs |
| **Rationale** | Python provides: flexibility, error handling, conditional logic, easy testing, team expertise |
| **Structure** | YAML metadata + embedded Python code for pre-check, remediation, post-check |
| **Impact** | Maximum flexibility; requires Python execution environment in agents |

### Decision 9: Analyzer Output Format
| Aspect | Detail |
|--------|--------|
| **Decision** | Fixed taxonomy of vulnerability types |
| **Alternatives Considered** | Free-form LLM classification, Hierarchical taxonomy |
| **Rationale** | Fixed enum enables: reliable matching, consistent logging, bounded playbook coverage |
| **Initial Taxonomy** | 15 types covering S3, IAM, Security Groups, EBS, RDS, KMS vulnerabilities |
| **Impact** | New vulnerability types require code changes; provides predictability |

### Decision 10: Approval Mechanism
| Aspect | Detail |
|--------|--------|
| **Decision** | Jira status transition with polling |
| **Alternatives Considered** | Webhooks, Slack integration, Custom approval UI |
| **Rationale** | Uses existing Jira workflow that teams already use; no additional infrastructure |
| **Implementation** | Post comment with details → status to PENDING APPROVAL → poll for Approved/Rejected |
| **Poll Interval** | 60 seconds |
| **Impact** | Latency of up to 60s for approval detection; acceptable for human-speed workflows |

### Decision 11: Jira Workflow Granularity
| Aspect | Detail |
|--------|--------|
| **Decision** | Full granularity with 12 distinct statuses |
| **Statuses** | OPEN, ANALYZING, PLAYBOOK SEARCH, VERIFYING, VALIDATING, VALIDATION FAILED, PENDING APPROVAL, Approved, Rejected, DEPLOYING, DEPLOYMENT FAILED, RESOLVED |
| **Alternatives Considered** | Simplified (5-6 statuses), Minimal (3 statuses) |
| **Rationale** | Detailed statuses enable: precise tracking, debugging, SLA measurement, audit trail |
| **Impact** | Requires Jira workflow configuration; provides maximum visibility |

### Decision 12: Concurrency Model
| Aspect | Detail |
|--------|--------|
| **Decision** | Sequential FIFO processing |
| **Alternatives Considered** | Parallel processing, Priority queue |
| **Rationale** | Simplicity for Phase 1; avoids resource contention, race conditions, complex coordination |
| **Future** | Priority queue planned for Phase 2 (critical findings processed first) |
| **Impact** | Throughput limited to one finding at a time; predictable resource usage |

### Decision 13: Credential Management
| Aspect | Detail |
|--------|--------|
| **Decision** | Environment variables |
| **Alternatives Considered** | AWS Secrets Manager, HashiCorp Vault, Configuration files |
| **Rationale** | Simplest approach for Phase 1; standard practice for containerized applications |
| **Required Variables** | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `JIRA_API_TOKEN`, `OPENAI_API_KEY` |
| **Future** | Secrets Manager integration planned for Phase 2 production hardening |
| **Impact** | Developer responsibility to secure environment; no secrets in code/config |

### Decision 14: Logging Strategy
| Aspect | Detail |
|--------|--------|
| **Decision** | Structured JSON logging with file output |
| **Library** | structlog |
| **Output** | Console (development) + rotating file (production) |
| **Alternatives Considered** | Plain text, ELK Stack, CloudWatch Logs |
| **Rationale** | Structured logs enable: parsing, searching, alerting; file output for persistence |
| **Audit Fields** | `_audit=true` flag on security-relevant events |
| **Impact** | Easy log analysis; no cloud integration overhead in Phase 1 |

### Decision 15: API/UI Strategy
| Aspect | Detail |
|--------|--------|
| **Decision** | API only; Jira serves as UI |
| **Framework** | FastAPI |
| **Endpoints** | Health check, playbook management, queue status, finding status |
| **Alternatives Considered** | Full web dashboard, CLI only |
| **Rationale** | Jira provides adequate visibility for operators; API enables integration/automation |
| **Future** | Full Dashboard planned for Phase 2 |
| **Impact** | Operators use familiar Jira interface; API available for scripting |

---

## 7.3 Deferred Decisions (Phase 2+)

Decisions explicitly postponed to maintain Phase 1 scope.

| Topic | Deferred Decision | Phase 2 Plan |
|-------|-------------------|--------------|
| **Dashboard** | No custom web UI | Full React dashboard with real-time status, analytics, playbook editor |
| **Centralized Logging** | Local file logging only | ELK Stack or AWS CloudWatch integration |
| **Priority Queue** | FIFO processing | Priority-based queue (Critical > High > Medium > Low) |
| **Multi-Cloud** | AWS only | Azure and GCP support with provider abstraction layer |
| **Secrets Management** | Environment variables | AWS Secrets Manager or HashiCorp Vault |
| **Notifications** | Jira comments only | Slack, email, PagerDuty integration |
| **Metrics** | Log-based metrics | Prometheus + Grafana dashboards |
| **Auto-Scaling** | Single instance | Kubernetes deployment with HPA |
| **Playbook Versioning** | Latest only | Git-based versioning with rollback |
| **Finding Deduplication** | Process all | Hash-based dedup with time window |

---

## 7.4 Success Metrics

### Phase 1 Demo Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| **End-to-End Demo** | 1 complete flow | Jira ticket → analysis → validation → approval → deployment |
| **Playbook Coverage** | 10-15 playbooks | Count of tested, production-ready playbooks |
| **Validation Success Rate** | 100% for demo scenarios | All curated playbooks pass validation |
| **MTTR (Demo)** | < 30 minutes | Time from finding to resolution (including human approval) |
| **System Uptime** | No crashes during demo | Graceful handling of all errors |

### Production Success Criteria (Future)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **MTTR** | < 25-30 minutes average | Compared to 7-9 hours manual baseline |
| **Automation Rate** | > 70% of findings | Findings with matching playbooks / total findings |
| **False Positive Rate** | < 5% | Rejected remediations / approved remediations |
| **Time Savings** | 76,000 hours annually | Based on 80,000 baseline - 4,000 residual |
| **Playbook Match Rate** | > 80% at ≥70% confidence | High/medium confidence matches / total findings |

---

## 7.5 Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **LLM hallucination in analysis** | Medium | High | Fixed taxonomy constrains output; validation catches incorrect matches |
| **Playbook causes unintended changes** | Low | Critical | Pre/post checks verify behavior; human approval required; test-first approach |
| **LocalStack doesn't match AWS behavior** | Medium | Medium | Critical playbooks tested against real AWS before demo |
| **Jira API rate limiting** | Low | Medium | Configurable poll intervals; exponential backoff |
| **Test environment resource leaks** | Medium | Low | Always-cleanup policy; periodic orphan resource audit |
| **Credential exposure** | Low | Critical | Tokenization; no secrets in logs; environment variable discipline |
| **Scope creep** | High | Medium | Strict Phase 1 boundary; defer list maintained |

---

## 7.6 Glossary

| Term | Definition |
|------|------------|
| **CSPM** | Cloud Security Posture Management - tools that scan cloud environments for misconfigurations |
| **Finding** | A security vulnerability or misconfiguration detected by a CSPM tool |
| **Playbook** | A reusable remediation template containing pre-check, fix, and post-check logic |
| **Tokenization** | The process of replacing sensitive values with placeholders (tokens) |
| **Validation** | Testing a playbook against a simulated environment before production |
| **MTTR** | Mean Time To Remediation - average time from detection to fix |
| **LangGraph** | Framework for building multi-agent LLM applications with state machines |
| **ChromaDB** | Open-source vector database for semantic similarity search |
| **LocalStack** | Local AWS cloud emulator for development and testing |
| **MCP** | Model Context Protocol - standard for LLM tool integration |

---

## 7.7 Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-16 | PatchWeave Team | Initial comprehensive document |

---

## 7.8 Appendix: Quick Reference Cards

### Agent Responsibilities

| Agent | Input | Output | Key Action |
|-------|-------|--------|------------|
| **Tokenizer** | RawFinding | SanitizedFinding + TokenMapping | Replace sensitive data with `{{TOKENS}}` |
| **Analyzer** | SanitizedFinding | AnalyzedFinding | Classify vulnerability type |
| **PlaybookMatcher** | AnalyzedFinding | PlaybookMatch | Query ChromaDB, calculate similarity |
| **Verification** | PlaybookMatch (70-89%) | Approved/Rejected | LLM review of moderate matches |
| **Environment** | Playbook | TestEnvironment | Generate and apply Terraform |
| **Pre-Check** | TestEnvironment | StageResult | Confirm vulnerability exists |
| **Executor** | Playbook + TestEnv | StageResult | Run remediation code |
| **Post-Check** | TestEnvironment | StageResult | Confirm fix applied |
| **Cleanup** | TestEnvironment | StageResult | Terraform destroy |
| **Deployment** | Approval + TokenMapping | DeploymentResult | Execute against production |

### Status Transition Quick Reference

```
OPEN ──▶ ANALYZING ──▶ PLAYBOOK SEARCH ──┬──▶ VERIFYING ──┬──▶ VALIDATING
                                         │               │
                                         │               └──▶ NO PLAYBOOK
                                         │
                                         └──────────────────▶ VALIDATING

VALIDATING ──┬──▶ VALIDATION FAILED
             │
             └──▶ PENDING APPROVAL ──┬──▶ Approved ──▶ DEPLOYING ──┬──▶ RESOLVED
                                     │                             │
                                     │                             └──▶ DEPLOYMENT FAILED
                                     │
                                     └──▶ Rejected
```

### Environment Variables Checklist

```bash
# Required
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="us-east-1"
export JIRA_URL="https://company.atlassian.net"
export JIRA_API_TOKEN="..."
export JIRA_PROJECT_KEY="SEC"
export OPENAI_API_KEY="..."

# Optional
export PATCHWEAVE_LOG_LEVEL="INFO"
export PATCHWEAVE_POLL_INTERVAL="60"
export LOCALSTACK_ENDPOINT="http://localhost:4566"
```

---

# Document Complete

This document represents the complete technical specification for PatchWeave Phase 1, incorporating all decisions made during the planning process. It serves as the single source of truth for implementation.

**Total Sections**: 7
**Decisions Documented**: 15
**Playbook Types Planned**: 10-15
**Estimated Implementation**: 160 hours (4 weeks at 40 hrs/week)

---

*End of PatchWeave Project Document*

---

*Document generated: January 16, 2026*
*Version: 1.0*
