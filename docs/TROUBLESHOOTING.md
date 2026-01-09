# PatchWeave Troubleshooting Guide

This guide covers common issues and their solutions when running PatchWeave.

## Table of Contents

1. [Installation Issues](#installation-issues)
2. [Service Startup Issues](#service-startup-issues)
3. [Jira Integration Issues](#jira-integration-issues)
4. [ChromaDB Issues](#chromadb-issues)
5. [LocalStack Issues](#localstack-issues)
6. [LLM/OpenAI Issues](#llmopenai-issues)
7. [Playbook Issues](#playbook-issues)
8. [Workflow Issues](#workflow-issues)
9. [API Issues](#api-issues)
10. [Performance Issues](#performance-issues)

---

## Installation Issues

### Python Version Error

**Symptom:**
```
ERROR: Package requires Python >=3.11
```

**Solution:**
```bash
# Check Python version
python --version

# Install Python 3.11+ if needed
# Ubuntu/Debian:
sudo apt install python3.11 python3.11-venv

# Create venv with correct version
python3.11 -m venv .venv
source .venv/bin/activate
```

### Dependency Installation Fails

**Symptom:**
```
ERROR: Could not build wheels for chromadb
```

**Solution:**
```bash
# Install build dependencies
sudo apt install build-essential python3-dev

# For ChromaDB specifically
pip install --upgrade pip setuptools wheel
pip install chromadb

# Then install the rest
pip install -e ".[dev]"
```

### Import Errors

**Symptom:**
```python
ModuleNotFoundError: No module named 'patchweave'
```

**Solution:**
```bash
# Make sure you installed in editable mode
pip install -e ".[dev]"

# Verify installation
pip show patchweave

# Check if in correct virtual environment
which python
```

---

## Service Startup Issues

### Docker Services Won't Start

**Symptom:**
```
ERROR: Cannot start service localstack: driver failed
```

**Solution:**
```bash
# Check Docker is running
sudo systemctl status docker

# Clean up Docker
docker system prune -f
docker-compose down -v
docker-compose up -d

# Check logs
docker-compose logs localstack
docker-compose logs chromadb
```

### Port Already in Use

**Symptom:**
```
ERROR: Port 8000 is already in use
```

**Solution:**
```bash
# Find process using port
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use a different port
python -m patchweave --port 8001
```

### Application Won't Start

**Symptom:**
```
ValidationError: OPENAI_API_KEY field required
```

**Solution:**
```bash
# Make sure .env file exists
cp .env.example .env

# Edit and fill in required values
nano .env

# Required fields:
# - OPENAI_API_KEY
# - JIRA_BASE_URL
# - JIRA_EMAIL
# - JIRA_API_TOKEN
# - JIRA_PROJECT_KEY
```

---

## Jira Integration Issues

### Authentication Failed

**Symptom:**
```
JiraClientError: 401 Unauthorized
```

**Solution:**

1. Verify API token is valid:
   - Go to Jira → Profile → Security → API Tokens
   - Create a new token if needed

2. Check credentials in `.env`:
```bash
JIRA_BASE_URL=https://yourorg.atlassian.net  # No trailing slash!
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-token-here
```

3. Test connection:
```bash
curl -u your-email@company.com:your-token \
  https://yourorg.atlassian.net/rest/api/3/myself
```

### Project Not Found

**Symptom:**
```
JiraClientError: Project SEC not found
```

**Solution:**

1. Verify project key exists in Jira
2. Check service account has access to the project
3. Update `JIRA_PROJECT_KEY` in `.env`

### Status Transitions Fail

**Symptom:**
```
JiraClientError: Transition not available
```

**Solution:**

1. Check Jira workflow has required statuses:
   - Open
   - Analyzing
   - Playbook Search
   - Validation
   - Pending Approval
   - Deploying
   - Resolved
   - Manual Review Required

2. Verify transitions are allowed from current status

3. Check service account has permission to transition issues

---

## ChromaDB Issues

### Connection Refused

**Symptom:**
```
ConnectionError: Cannot connect to ChromaDB at localhost:8001
```

**Solution:**
```bash
# Check ChromaDB is running
docker-compose ps chromadb

# Restart ChromaDB
docker-compose restart chromadb

# Check logs
docker-compose logs chromadb

# Verify port
curl http://localhost:8001/api/v1/heartbeat
```

### Playbooks Not Found

**Symptom:**
```
No playbooks matched the query
```

**Solution:**

1. Verify playbooks are loaded:
```python
from patchweave.knowledge.loader import PlaybookLoader
from patchweave.knowledge.chromadb_client import ChromaDBClient

loader = PlaybookLoader()
playbooks = loader.load_all()
print(f"Loaded {len(playbooks)} playbooks")

client = ChromaDBClient()
client.add_playbooks(playbooks)
```

2. Check collection exists:
```python
client = ChromaDBClient()
count = client.count()
print(f"Playbooks in ChromaDB: {count}")
```

3. Test search manually:
```python
results = client.search("S3 public access", n_results=5)
for r in results:
    print(f"{r.playbook.id}: {r.similarity_score:.2f}")
```

### Low Match Scores

**Symptom:**
```
Match score: 0.45 (below threshold)
```

**Solution:**

1. Improve playbook `search_text` with more varied keywords
2. Check finding description has relevant terms
3. Lower threshold for testing (not recommended for production):
```bash
MATCH_THRESHOLD_HIGH=0.85
MATCH_THRESHOLD_MODERATE=0.60
```

---

## LocalStack Issues

### Services Not Ready

**Symptom:**
```
botocore.exceptions.EndpointConnectionError: Could not connect
```

**Solution:**
```bash
# Wait for LocalStack to fully start
docker-compose up -d localstack
sleep 30  # LocalStack takes time to initialize

# Check health
curl http://localhost:4566/_localstack/health

# Check specific service
curl http://localhost:4566/_localstack/health | jq '.services.s3'
```

### Resource Not Found

**Symptom:**
```
NoSuchBucket: The specified bucket does not exist
```

**Solution:**
```bash
# Create test resources in LocalStack
aws --endpoint-url=http://localhost:4566 s3 mb s3://test-bucket

# List resources
aws --endpoint-url=http://localhost:4566 s3 ls
```

### IAM Errors

**Symptom:**
```
AccessDenied: User is not authorized
```

**Solution:**

LocalStack doesn't enforce IAM by default. If you're seeing this:

1. Check if you're hitting real AWS accidentally:
```python
# Verify endpoint URL is LocalStack
import boto3
s3 = boto3.client("s3", endpoint_url="http://localhost:4566")
```

2. Set environment variables:
```bash
export AWS_ENDPOINT_URL=http://localhost:4566
export USE_LOCALSTACK=true
```

---

## LLM/OpenAI Issues

### API Key Invalid

**Symptom:**
```
openai.AuthenticationError: Invalid API Key
```

**Solution:**

1. Verify API key at https://platform.openai.com/api-keys
2. Check `.env` has correct key (no extra spaces)
3. Ensure key has correct permissions

### Rate Limiting

**Symptom:**
```
openai.RateLimitError: Rate limit exceeded
```

**Solution:**

1. Add retry logic (already built into PatchWeave)
2. Reduce polling frequency:
```bash
JIRA_POLL_INTERVAL_SECONDS=120  # Increase from 60
```
3. Upgrade OpenAI plan for higher limits

### Model Not Available

**Symptom:**
```
openai.NotFoundError: Model 'gpt-4' not found
```

**Solution:**

1. Check model availability for your account
2. Use a different model:
```bash
OPENAI_MODEL=gpt-3.5-turbo
```

### Unexpected Responses

**Symptom:**
```
AnalysisError: Failed to parse LLM response
```

**Solution:**

1. Check LLM temperature (should be 0.0 for consistent outputs):
```bash
OPENAI_TEMPERATURE=0.0
```

2. Check logs for the raw response
3. May need to adjust prompts in analyzer

---

## Playbook Issues

### YAML Parse Error

**Symptom:**
```
yaml.scanner.ScannerError: while scanning a simple key
```

**Solution:**

1. Validate YAML syntax:
```bash
python -c "import yaml; yaml.safe_load(open('playbooks/your-playbook.yaml'))"
```

2. Common issues:
   - Incorrect indentation
   - Missing quotes around strings with special characters
   - Incorrect multiline string format

3. Use `|` for code blocks:
```yaml
remediation_code: |
  def remediate():
      pass  # Code here
```

### Missing Required Field

**Symptom:**
```
ValidationError: field 'vulnerability_type' is required
```

**Solution:**

Check playbook has all required fields:
- `id`
- `name`
- `description`
- `vulnerability_type`
- `resource_type`
- `severity`
- `search_text`
- `remediation_code`

### Code Execution Error

**Symptom:**
```
PlaybookExecutionError: name 'boto3' is not defined
```

**Solution:**

1. Add imports to the code:
```yaml
remediation_code: |
  import boto3
  
  def remediate():
      s3 = boto3.client("s3")
```

2. Ensure dependencies are installed:
```bash
pip install boto3
```

---

## Workflow Issues

### Stuck in Phase

**Symptom:**
```
Workflow stuck in VALIDATION phase
```

**Solution:**

1. Check logs for errors:
```bash
tail -f logs/patchweave.log | grep wf-xxx-yyy
```

2. Check LocalStack is responding:
```bash
curl http://localhost:4566/_localstack/health
```

3. Manual status check:
```bash
curl http://localhost:8000/api/v1/findings/SEC-1234
```

### Approval Never Received

**Symptom:**
```
Workflow stuck in PENDING_APPROVAL
```

**Solution:**

1. Check Jira ticket has approval comment
2. Verify Jira polling is working:
```bash
tail -f logs/patchweave.log | grep "approval_poll"
```

3. Check approval timeout hasn't passed (default: 24 hours)

4. Manually approve in Jira by adding comment:
```
APPROVED

Approved by: your.name@company.com
```

### Deployment Fails

**Symptom:**
```
DeploymentError: Post-check failed
```

**Solution:**

1. Check pre-check passed (vulnerability exists)
2. Check remediation code executed successfully
3. Check post-check logic is correct
4. Rollback should trigger automatically

---

## API Issues

### 404 Not Found

**Symptom:**
```
{"detail": "Not Found"}
```

**Solution:**

1. Check endpoint URL is correct
2. Verify API is running:
```bash
curl http://localhost:8000/health
```

3. Check route exists in API documentation:
```
http://localhost:8000/docs
```

### Validation Error

**Symptom:**
```
{"detail": [{"loc": ["body", "severity"], "msg": "field required"}]}
```

**Solution:**

1. Check request body matches schema
2. View required fields in Swagger UI
3. Example correct request:
```bash
curl -X POST http://localhost:8000/api/v1/findings/submit \
  -H "Content-Type: application/json" \
  -d '{
    "jira_ticket_id": "SEC-1234",
    "jira_ticket_url": "https://org.atlassian.net/browse/SEC-1234",
    "title": "S3 bucket has public access",
    "description": "Description here",
    "severity": "Critical"
  }'
```

### Server Error

**Symptom:**
```
{"detail": "Internal Server Error"}
```

**Solution:**

1. Check application logs:
```bash
tail -f logs/patchweave.log
```

2. Look for stack traces
3. Common causes:
   - Database connection issues
   - External service unavailable
   - Unhandled exceptions

---

## Performance Issues

### Slow Response Times

**Symptom:**
```
Response time: 5+ seconds
```

**Solution:**

1. Check ChromaDB performance:
```bash
docker stats chromadb
```

2. Reduce number of playbooks loaded (if too many)

3. Check LLM response time (OpenAI latency)

4. Enable connection pooling for external services

### High Memory Usage

**Symptom:**
```
Container using >4GB memory
```

**Solution:**

1. Limit container memory:
```yaml
# docker-compose.yml
services:
  chromadb:
    mem_limit: 2g
```

2. Reduce ChromaDB collection size

3. Implement pagination for large result sets

### Queue Backlog

**Symptom:**
```
Queue size: 100+ pending findings
```

**Solution:**

1. Increase processing workers (future feature)

2. Reduce polling frequency:
```bash
JIRA_POLL_INTERVAL_SECONDS=120
```

3. Check for stuck workflows

---

## Getting Help

### Collect Debug Information

When reporting issues, include:

1. **Logs:**
```bash
tail -n 100 logs/patchweave.log > debug.log
tail -n 100 logs/error.log >> debug.log
```

2. **Environment:**
```bash
python --version
pip freeze > requirements-debug.txt
docker-compose ps
```

3. **Configuration (sanitized):**
```bash
# Don't include actual tokens/keys
cat .env | grep -v TOKEN | grep -v KEY > config-debug.txt
```

4. **Steps to reproduce:**
- What you were trying to do
- What commands you ran
- What you expected vs what happened

### Log Levels

Increase log verbosity for debugging:

```bash
# In .env
PATCHWEAVE_LOG_LEVEL=DEBUG
```

Or at runtime:
```bash
LOG_LEVEL=DEBUG python -m patchweave
```

### Health Checks

Quick system health check:

```bash
# All services
curl http://localhost:8000/health
curl http://localhost:4566/_localstack/health
curl http://localhost:8001/api/v1/heartbeat

# Run validation
python scripts/validate_phase5.py
```
