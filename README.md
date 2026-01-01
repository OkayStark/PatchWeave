# PatchWeave

<p align="center">
  <b>Intelligent Cloud Security Remediation System</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/version-1.0.0-brightgreen.svg" alt="Version">
</p>

---

## Overview

PatchWeave is a multi-agent system that automates cloud security remediation while maintaining human oversight for production changes. It bridges the gap between vulnerability detection (CSPM tools like Wiz, Prisma Cloud) and actual remediation.

### Key Features

- 🔍 **Automated Ingestion**: Consumes security findings from Jira tickets
- 🧠 **Intelligent Analysis**: LLM-powered classification of vulnerabilities
- 📚 **Knowledge Base**: Semantic playbook matching using ChromaDB
- ✅ **Safe Validation**: Tests fixes in isolated environments before production
- 👥 **Human-in-the-Loop**: Requires approval before any production changes
- 📊 **Complete Audit Trail**: Structured logging of all decisions

### The Problem

Organizations face **10,000+ security findings** that take **7-9 hours each** to remediate manually. PatchWeave reduces this to **25-30 minutes** while maintaining safety.

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- AWS credentials (or LocalStack for development)
- Jira API token

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/patchweave.git
cd patchweave

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows

# Install dependencies
make dev-install

# Copy environment template
cp .env.example .env
# Edit .env with your configuration

# Start infrastructure
make docker-up

# Verify services are healthy
make docker-health

# Run the application
make run
```

### Configuration

Edit `.env` with your settings:

```bash
# Jira
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_EMAIL=patchweave@your-org.com
JIRA_API_TOKEN=your-token
JIRA_PROJECT_KEY=SEC

# AWS (use 'test' for LocalStack)
AWS_TEST_ACCESS_KEY_ID=test
AWS_TEST_SECRET_ACCESS_KEY=test

# LLM
OPENAI_API_KEY=your-openai-key
```

## Architecture

```
┌─────────────┐     ┌───────────┐     ┌────────────────┐
│   Jira      │────▶│ Tokenizer │────▶│    Analyzer    │
│  (CSPM)     │     │           │     │    Agent       │
└─────────────┘     └───────────┘     └───────┬────────┘
                                              │
                                              ▼
┌─────────────┐     ┌───────────┐     ┌────────────────┐
│  Deployment │◀────│ Validation│◀────│   ChromaDB     │
│    Agent    │     │ Workflow  │     │   Matching     │
└─────────────┘     └───────────┘     └────────────────┘
```

### Components

| Component | Purpose |
|-----------|---------|
| **Tokenizer** | Sanitizes sensitive data before LLM processing |
| **Analyzer Agent** | Classifies vulnerabilities using fixed taxonomy |
| **ChromaDB** | Semantic search for playbook matching |
| **Validation Workflow** | Tests fixes in isolated environments |
| **Deployment Agent** | Applies approved fixes to production |

### Jira Workflow States

```
OPEN → ANALYZING → PLAYBOOK SEARCH → VALIDATING → PENDING APPROVAL → DEPLOYING → RESOLVED
                         ↓                 ↓              ↓              ↓
                   NO PLAYBOOK    VALIDATION FAILED    REJECTED    DEPLOYMENT FAILED
```

## Playbooks

Playbooks are YAML files containing remediation code:

```yaml
playbook:
  id: "550e8400-e29b-41d4-a716-446655440001"
  name: "S3 Block Public Access"
  vulnerability_type: "s3_public_access"
  
  remediation_code: |
    import boto3
    s3 = boto3.client('s3')
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

See [playbooks/](playbooks/) for all available playbooks.

## API

PatchWeave exposes a REST API:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/queue` | GET | Queue status |
| `/findings/{id}` | GET | Finding details |
| `/playbooks` | GET | List playbooks |
| `/stats` | GET | System statistics |

Access Swagger documentation at `http://localhost:8080/docs`

## Development

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test types
make test-unit
make test-integration
```

### Code Quality

```bash
# Format code
make format

# Run linting
make lint
```

### Docker Commands

```bash
# Start services
make docker-up

# Stop services
make docker-down

# View logs
make docker-logs

# Clean everything
make docker-clean
```

## Project Structure

```
patchweave/
├── src/patchweave/
│   ├── agents/          # LangGraph agents
│   ├── api/             # FastAPI application
│   ├── core/            # Business logic
│   ├── integrations/    # External services
│   ├── models/          # Pydantic schemas
│   └── logging/         # Structured logging
├── playbooks/           # Remediation playbooks
├── tests/               # Test suite
└── docs/                # Documentation
```

## Security

- **Tokenization**: Sensitive data never reaches LLMs
- **Validation First**: All fixes tested before production
- **Human Approval**: Required for any production changes
- **Audit Trail**: Complete logging of all actions
- **Credential Isolation**: Separate test/production credentials

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

This project was developed as a capstone project demonstrating cloud security automation with human-in-the-loop oversight.
