#!/bin/bash
# =============================================================================
# PatchWeave Setup Script
# =============================================================================
# This script sets up the complete PatchWeave development environment
# Usage: ./scripts/setup.sh
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║                                                                   ║"
echo "║   ██████╗  █████╗ ████████╗ ██████╗██╗  ██╗██╗    ██╗███████╗     ║"
echo "║   ██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██║  ██║██║    ██║██╔════╝     ║"
echo "║   ██████╔╝███████║   ██║   ██║     ███████║██║ █╗ ██║█████╗       ║"
echo "║   ██╔═══╝ ██╔══██║   ██║   ██║     ██╔══██║██║███╗██║██╔══╝       ║"
echo "║   ██║     ██║  ██║   ██║   ╚██████╗██║  ██║╚███╔███╔╝███████╗     ║"
echo "║   ╚═╝     ╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚══════╝     ║"
echo "║                                                                   ║"
echo "║   Setup Script - Intelligent Cloud Security Remediation           ║"
echo "║                                                                   ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# -----------------------------------------------------------------------------
# Check Prerequisites
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[1/7] Checking prerequisites...${NC}"

check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}✗ $1 is not installed${NC}"
        echo "  Please install $1 and try again"
        echo "  $2"
        exit 1
    else
        echo -e "${GREEN}✓ $1 is installed${NC}"
    fi
}

check_command "python3" "Install from https://www.python.org/downloads/"
check_command "docker" "Install from https://docs.docker.com/get-docker/"
check_command "docker-compose" "Install from https://docs.docker.com/compose/install/"
check_command "terraform" "Install from https://developer.hashicorp.com/terraform/downloads"
check_command "aws" "Install from https://aws.amazon.com/cli/"

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.11"
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}✗ Python $REQUIRED_VERSION or higher required (found $PYTHON_VERSION)${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python version $PYTHON_VERSION${NC}"

# -----------------------------------------------------------------------------
# Create Virtual Environment
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[2/7] Setting up Python virtual environment...${NC}"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "${GREEN}✓ Created virtual environment${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# Activate virtual environment
source .venv/bin/activate
echo -e "${GREEN}✓ Activated virtual environment${NC}"

# -----------------------------------------------------------------------------
# Install Dependencies
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[3/7] Installing Python dependencies...${NC}"

pip install --upgrade pip -q
pip install -e . -q
echo -e "${GREEN}✓ Installed all Python dependencies${NC}"

# -----------------------------------------------------------------------------
# Setup Environment File
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[4/7] Setting up environment configuration...${NC}"

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env from .env.example${NC}"
    echo -e "${YELLOW}  ⚠ Please edit .env and add your credentials:${NC}"
    echo "    - JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY"
    echo "    - GOOGLE_API_KEY (get from https://aistudio.google.com/apikey)"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# -----------------------------------------------------------------------------
# Start Docker Services
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[5/7] Starting Docker services...${NC}"

docker-compose up -d localstack-test localstack-prod chromadb
echo -e "${GREEN}✓ Started LocalStack (TEST:4566, PROD:4567) and ChromaDB${NC}"

# Wait for services to be ready
echo "  Waiting for services to be healthy..."
sleep 10

# -----------------------------------------------------------------------------
# Verify Services
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[6/7] Verifying services...${NC}"

# Check LocalStack TEST
if curl -s http://localhost:4566/_localstack/health | grep -q "running"; then
    echo -e "${GREEN}✓ LocalStack TEST (port 4566) is healthy${NC}"
else
    echo -e "${RED}✗ LocalStack TEST is not responding${NC}"
fi

# Check LocalStack PROD
if curl -s http://localhost:4567/_localstack/health | grep -q "running"; then
    echo -e "${GREEN}✓ LocalStack PROD (port 4567) is healthy${NC}"
else
    echo -e "${RED}✗ LocalStack PROD is not responding${NC}"
fi

# Check ChromaDB
if curl -s http://localhost:8000/api/v1/heartbeat | grep -q "nanosecond"; then
    echo -e "${GREEN}✓ ChromaDB (port 8000) is healthy${NC}"
else
    echo -e "${RED}✗ ChromaDB is not responding${NC}"
fi

# -----------------------------------------------------------------------------
# Create Test Resources
# -----------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[7/7] Creating test resources...${NC}"

# Create a test bucket on both LocalStack instances
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
    aws --endpoint-url=http://localhost:4566 s3 mb s3://test-bucket 2>/dev/null || true
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
    aws --endpoint-url=http://localhost:4567 s3 mb s3://test-bucket 2>/dev/null || true
echo -e "${GREEN}✓ Created test buckets on both LocalStack instances${NC}"

# -----------------------------------------------------------------------------
# Done!
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    Setup Complete! 🎉                              ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. ${YELLOW}Edit .env${NC} - Add your Jira and Gemini API credentials"
echo -e "  2. ${YELLOW}Create a Jira ticket${NC} - With a security finding (see README.md)"
echo -e "  3. ${YELLOW}Run PatchWeave${NC}:"
echo ""
echo -e "     ${BLUE}source .venv/bin/activate${NC}"
echo -e "     ${BLUE}python -m patchweave${NC}"
echo ""
echo -e "For more commands, run: ${BLUE}make help${NC}"
