# PatchWeave Demo Scenario

## Overview

This document provides a scripted demonstration of PatchWeave's end-to-end security remediation workflow. The demo showcases three vulnerability scenarios that demonstrate the full capabilities of the system.

## Pre-Demo Setup

### 1. Start Services

```bash
# Terminal 1: Start LocalStack for AWS simulation
docker-compose up -d localstack

# Terminal 2: Start ChromaDB for playbook matching
docker-compose up -d chromadb

# Terminal 3: Start PatchWeave API
python -m patchweave --mode api-only --host 0.0.0.0 --port 8000
```

### 2. Verify Services

```bash
# Check LocalStack
curl http://localhost:4566/_localstack/health

# Check ChromaDB
curl http://localhost:8001/api/v1/heartbeat

# Check PatchWeave API
curl http://localhost:8000/health
```

### 3. Load Playbooks

```bash
# Load all playbooks into ChromaDB
python -c "
from patchweave.knowledge.loader import PlaybookLoader
from patchweave.knowledge.chromadb_client import ChromaDBClient

loader = PlaybookLoader()
playbooks = loader.load_all()
print(f'Loaded {len(playbooks)} playbooks')

client = ChromaDBClient()
client.add_playbooks(playbooks)
print('Playbooks indexed in ChromaDB')
"
```

---

## Demo Scenario 1: S3 Public Access (HIGH Severity)

### Story
"A security scanner detected an S3 bucket with public access enabled. This is a critical finding that could lead to data exposure."

### Jira Ticket (Simulated)

```json
{
  "ticket_id": "SEC-1001",
  "title": "S3 Bucket 'prod-logs-bucket' has public access enabled",
  "description": "CRITICAL SECURITY FINDING\n\nResource: arn:aws:s3:::prod-logs-bucket\nAccount: 123456789012\nRegion: us-east-1\n\nThe S3 bucket prod-logs-bucket has Block Public Access disabled, potentially exposing sensitive log data to the internet.\n\nDetected by: Wiz\nFirst seen: 2026-01-15",
  "severity": "Critical",
  "status": "Open"
}
```

### Expected Flow

1. **Ingestion**: PatchWeave polls Jira and retrieves the ticket
2. **Tokenization**: Sensitive data is replaced with tokens:
   - `123456789012` → `{{ACCOUNT_ID}}`
   - `us-east-1` → `{{AWS_REGION}}`
   - `prod-logs-bucket` → `{{BUCKET_NAME}}`
3. **Analysis**: Analyzer Agent classifies as `s3_public_access` with HIGH severity
4. **Matching**: ChromaDB returns `pb-s3-public-access-001` with 95% confidence
5. **Validation**: LocalStack validates the playbook against simulated S3
6. **Approval**: Comment posted to Jira requesting approval
7. **Deployment**: After approval, remediation is deployed

### Demo Commands

```bash
# Submit finding through API
curl -X POST http://localhost:8000/api/v1/findings/submit \
  -H "Content-Type: application/json" \
  -d '{
    "jira_ticket_id": "SEC-1001",
    "jira_ticket_url": "https://demo.atlassian.net/browse/SEC-1001",
    "title": "S3 Bucket '\''prod-logs-bucket'\'' has public access enabled",
    "description": "CRITICAL SECURITY FINDING\n\nResource: arn:aws:s3:::prod-logs-bucket\nAccount: 123456789012\nRegion: us-east-1\n\nThe S3 bucket prod-logs-bucket has Block Public Access disabled.",
    "severity": "Critical"
  }'

# Check workflow status
curl http://localhost:8000/api/v1/findings/SEC-1001

# View detailed stats
curl http://localhost:8000/api/v1/stats/detailed
```

### Talking Points

- "Notice how the system automatically classified this as an S3 public access issue"
- "The tokenizer protected the account ID and bucket name from being exposed to the LLM"
- "With 95% match confidence, this went directly to validation without human review"
- "The validation ran against LocalStack to ensure the playbook works correctly"

---

## Demo Scenario 2: Security Group SSH Open (MODERATE Match)

### Story
"A security group was found with SSH port 22 open to the internet. This requires additional verification due to the moderate match confidence."

### Jira Ticket (Simulated)

```json
{
  "ticket_id": "SEC-1002",
  "title": "Security Group allows SSH from 0.0.0.0/0",
  "description": "SECURITY FINDING\n\nResource: sg-0123456789abcdef0\nAccount: 123456789012\nRegion: us-west-2\n\nSecurity group sg-0123456789abcdef0 has an inbound rule allowing SSH (port 22) from any IP address (0.0.0.0/0).\n\nDetected by: AWS Security Hub",
  "severity": "High",
  "status": "Open"
}
```

### Expected Flow

1. **Analysis**: Classified as `security_group_open_port`
2. **Matching**: Returns 78% confidence (MODERATE tier)
3. **Verification**: Playbook Verification Agent reviews the match
4. **Approval**: Detailed review comment posted to Jira
5. **Deployment**: Requires explicit approval due to moderate confidence

### Demo Commands

```bash
# Submit finding
curl -X POST http://localhost:8000/api/v1/findings/submit \
  -H "Content-Type: application/json" \
  -d '{
    "jira_ticket_id": "SEC-1002",
    "jira_ticket_url": "https://demo.atlassian.net/browse/SEC-1002",
    "title": "Security Group allows SSH from 0.0.0.0/0",
    "description": "Security group sg-0123456789abcdef0 has an inbound rule allowing SSH (port 22) from any IP address.",
    "severity": "High"
  }'

# Check status - should show "VERIFICATION" phase
curl http://localhost:8000/api/v1/findings/SEC-1002
```

### Talking Points

- "This match came back at 78% confidence, below our 90% threshold"
- "The Playbook Verification Agent is now reviewing to confirm this is the right playbook"
- "This extra step prevents mismatched remediations from being deployed"

---

## Demo Scenario 3: S3 Encryption Disabled (HIGH Match with Learning)

### Story
"An S3 bucket was found without server-side encryption. This demonstrates the system's learning capabilities."

### Jira Ticket (Simulated)

```json
{
  "ticket_id": "SEC-1003",
  "title": "S3 bucket 'data-archive' does not have encryption enabled",
  "description": "SECURITY FINDING\n\nResource: arn:aws:s3:::data-archive\nAccount: 123456789012\nRegion: eu-west-1\n\nS3 bucket data-archive does not have default encryption enabled.\n\nDetected by: Prisma Cloud",
  "severity": "Medium",
  "status": "Open"
}
```

### Expected Flow

1. **Full pipeline execution**
2. **Learning**: After successful deployment, system records the pattern
3. **Statistics**: Learning endpoint shows remediation recorded

### Demo Commands

```bash
# Submit finding
curl -X POST http://localhost:8000/api/v1/findings/submit \
  -H "Content-Type: application/json" \
  -d '{
    "jira_ticket_id": "SEC-1003",
    "jira_ticket_url": "https://demo.atlassian.net/browse/SEC-1003",
    "title": "S3 bucket '\''data-archive'\'' does not have encryption enabled",
    "description": "S3 bucket data-archive does not have default encryption enabled.",
    "severity": "Medium"
  }'

# After completion, check learning stats
curl http://localhost:8000/api/v1/stats/learning
```

### Talking Points

- "After successful deployment, the system learns from this remediation"
- "The learning loop records which playbooks worked for which finding patterns"
- "This improves matching accuracy over time"

---

## Demo Scenario 4: No Match Found (Escalation)

### Story
"A novel security finding is detected that doesn't match any existing playbooks. This demonstrates the escalation workflow."

### Jira Ticket (Simulated)

```json
{
  "ticket_id": "SEC-1004",
  "title": "Lambda function uses deprecated runtime Python 2.7",
  "description": "SECURITY FINDING\n\nResource: arn:aws:lambda:us-east-1:123456789012:function:legacy-processor\n\nLambda function legacy-processor is using Python 2.7 which is deprecated and no longer receives security patches.",
  "severity": "Medium",
  "status": "Open"
}
```

### Expected Flow

1. **Analysis**: Classified, but no matching playbook found
2. **Escalation**: Status set to "MANUAL REVIEW REQUIRED"
3. **Comment**: Helpful guidance posted to Jira for manual remediation

### Demo Commands

```bash
# Submit finding
curl -X POST http://localhost:8000/api/v1/findings/submit \
  -H "Content-Type: application/json" \
  -d '{
    "jira_ticket_id": "SEC-1004",
    "jira_ticket_url": "https://demo.atlassian.net/browse/SEC-1004",
    "title": "Lambda function uses deprecated runtime Python 2.7",
    "description": "Lambda function legacy-processor is using Python 2.7 which is deprecated.",
    "severity": "Medium"
  }'

# Check status - should show escalation
curl http://localhost:8000/api/v1/findings/SEC-1004
```

### Talking Points

- "Not every finding has an automated solution"
- "The system gracefully escalates when it can't find a suitable playbook"
- "The Jira comment provides guidance for manual remediation"

---

## System Statistics Demo

### Show Overall Stats

```bash
curl http://localhost:8000/api/v1/stats | jq
```

### Show Detailed Breakdown

```bash
curl http://localhost:8000/api/v1/stats/detailed | jq
```

### Show Learning Progress

```bash
curl http://localhost:8000/api/v1/stats/learning | jq
```

---

## Failure Recovery Demo

### Demonstrate Rollback

```bash
# Trigger a deployment that fails post-check
# (This requires a specially crafted playbook)

# Show the rollback in action
curl http://localhost:8000/api/v1/findings/SEC-ROLLBACK-DEMO
```

### Talking Points

- "The system includes automatic rollback capabilities"
- "If a post-check fails, the rollback code is executed"
- "This prevents broken remediations from persisting"

---

## API Documentation

### Interactive API Explorer

Open in browser: `http://localhost:8000/docs`

- Show Swagger UI
- Demonstrate interactive endpoints
- Show request/response schemas

---

## Q&A Preparation

### Expected Questions

1. **"How does the LLM not see sensitive data?"**
   - Tokenizer replaces all sensitive values before LLM processing
   - Token mappings stored securely in memory
   - Substitution happens at deployment time

2. **"What if the playbook match is wrong?"**
   - Three-tier matching with confidence thresholds
   - Verification agent for moderate matches
   - Human approval required before deployment
   - Rollback capabilities if post-check fails

3. **"How does the system learn?"**
   - Records successful remediations
   - Tracks playbook effectiveness statistics
   - Learns finding patterns for future matching

4. **"What happens if Jira is down?"**
   - Graceful degradation with retry logic
   - Findings queued for later processing
   - System logs all decisions for audit

5. **"How would this scale in production?"**
   - Async processing with queues
   - Horizontal scaling of workers
   - ChromaDB handles vector search efficiently

---

## Demo Checklist

### Before Demo
- [ ] All services running (LocalStack, ChromaDB, PatchWeave)
- [ ] Playbooks loaded into ChromaDB
- [ ] Test API endpoints responding
- [ ] Terminal windows arranged for visibility
- [ ] Browser open to Swagger UI

### During Demo
- [ ] Explain each step as it happens
- [ ] Highlight the workflow phases
- [ ] Show logs for transparency
- [ ] Keep backup video ready

### After Demo
- [ ] Show final statistics
- [ ] Open for questions
- [ ] Provide documentation links

---

## Backup Plans

### If LocalStack Fails
- Use dry-run mode: Set `PATCHWEAVE_DRY_RUN=true`
- Explain validation would happen against real AWS

### If ChromaDB Fails
- Restart: `docker-compose restart chromadb`
- Fall back to exact-match playbook lookup

### If API Crashes
- Show pre-recorded video backup
- Explain the architecture from slides

### If Demo Ticket Fails
- Have backup tickets prepared
- Use different vulnerability type
