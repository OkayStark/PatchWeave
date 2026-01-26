#!/bin/bash
# ============================================================================
# PatchWeave - Create & Reset PROD Environment to Vulnerable State
# Creates all 5 resources (if missing) and makes them vulnerable
# Run this after LocalStack restart to recreate everything
# ============================================================================

set -e

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

ENDPOINT="http://localhost:4567"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  PATCHWEAVE PROD ENVIRONMENT SETUP                          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# PHASE 1: CREATE RESOURCES
# ============================================================================
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  PHASE 1: Creating Resources (if they don't exist)${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 1. Create S3 bucket: test-vulnerable-bucket
echo -e "${YELLOW}1. Creating S3 bucket: test-vulnerable-bucket...${NC}"
if aws --endpoint-url=$ENDPOINT s3api head-bucket --bucket test-vulnerable-bucket 2>/dev/null; then
    echo -e "   ${GREEN}✓${NC} Already exists"
else
    aws --endpoint-url=$ENDPOINT s3 mb s3://test-vulnerable-bucket
    echo -e "   ${GREEN}✓${NC} Created"
fi
echo ""

# 2. Create S3 bucket: prod-data-bucket
echo -e "${YELLOW}2. Creating S3 bucket: prod-data-bucket...${NC}"
if aws --endpoint-url=$ENDPOINT s3api head-bucket --bucket prod-data-bucket 2>/dev/null; then
    echo -e "   ${GREEN}✓${NC} Already exists"
else
    aws --endpoint-url=$ENDPOINT s3 mb s3://prod-data-bucket
    echo -e "   ${GREEN}✓${NC} Created"
fi
echo ""

# 3. Create S3 bucket: unencrypted-data-bucket
echo -e "${YELLOW}3. Creating S3 bucket: unencrypted-data-bucket...${NC}"
if aws --endpoint-url=$ENDPOINT s3api head-bucket --bucket unencrypted-data-bucket 2>/dev/null; then
    echo -e "   ${GREEN}✓${NC} Already exists"
else
    aws --endpoint-url=$ENDPOINT s3 mb s3://unencrypted-data-bucket
    echo -e "   ${GREEN}✓${NC} Created"
fi
echo ""

# 4. Create VPC (required for security group)
echo -e "${YELLOW}4. Creating VPC for security group...${NC}"
VPC_ID=$(aws --endpoint-url=$ENDPOINT ec2 describe-vpcs --query 'Vpcs[0].VpcId' --output text 2>/dev/null)
if [ "$VPC_ID" == "None" ] || [ -z "$VPC_ID" ]; then
    VPC_ID=$(aws --endpoint-url=$ENDPOINT ec2 create-vpc --cidr-block 10.0.0.0/16 --query 'Vpc.VpcId' --output text)
    echo -e "   ${GREEN}✓${NC} Created VPC: $VPC_ID"
else
    echo -e "   ${GREEN}✓${NC} Using existing VPC: $VPC_ID"
fi
echo ""

# 5. Create Security Group: prod-web-sg
echo -e "${YELLOW}5. Creating Security Group: prod-web-sg...${NC}"
SG_ID=$(aws --endpoint-url=$ENDPOINT ec2 describe-security-groups \
    --filters "Name=group-name,Values=prod-web-sg" \
    --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null)

if [ "$SG_ID" == "None" ] || [ -z "$SG_ID" ]; then
    SG_ID=$(aws --endpoint-url=$ENDPOINT ec2 create-security-group \
        --group-name prod-web-sg \
        --description "Production Web Security Group" \
        --vpc-id $VPC_ID \
        --query 'GroupId' --output text)
    echo -e "   ${GREEN}✓${NC} Created: $SG_ID"
else
    echo -e "   ${GREEN}✓${NC} Already exists: $SG_ID"
fi
echo ""

# 6. Create EBS Volume (unencrypted)
echo -e "${YELLOW}6. Creating unencrypted EBS Volume...${NC}"
VOL_ID=$(aws --endpoint-url=$ENDPOINT ec2 describe-volumes \
    --filters "Name=tag:Name,Values=prod-data-volume" \
    --query 'Volumes[0].VolumeId' --output text 2>/dev/null)

if [ "$VOL_ID" == "None" ] || [ -z "$VOL_ID" ]; then
    VOL_ID=$(aws --endpoint-url=$ENDPOINT ec2 create-volume \
        --availability-zone us-east-1a \
        --size 100 \
        --volume-type gp2 \
        --no-encrypted \
        --query 'VolumeId' --output text)
    # Tag it for identification
    aws --endpoint-url=$ENDPOINT ec2 create-tags \
        --resources $VOL_ID \
        --tags Key=Name,Value=prod-data-volume
    echo -e "   ${GREEN}✓${NC} Created: $VOL_ID"
else
    echo -e "   ${GREEN}✓${NC} Already exists: $VOL_ID"
fi
echo ""

# ============================================================================
# PHASE 2: MAKE RESOURCES VULNERABLE
# ============================================================================
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${RED}  PHASE 2: Making Resources Vulnerable${NC}"
echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 1. Remove S3 Public Access Block from test-vulnerable-bucket
echo -e "${YELLOW}1. Removing public access block from test-vulnerable-bucket...${NC}"
aws --endpoint-url=$ENDPOINT s3api delete-public-access-block --bucket test-vulnerable-bucket 2>/dev/null || true
echo -e "   ${RED}❌ VULNERABLE${NC} - Public access block removed"
echo ""

# 2. Disable versioning on prod-data-bucket (suspend it)
echo -e "${YELLOW}2. Suspending versioning on prod-data-bucket...${NC}"
aws --endpoint-url=$ENDPOINT s3api put-bucket-versioning --bucket prod-data-bucket --versioning-configuration Status=Suspended 2>/dev/null || true
echo -e "   ${RED}❌ VULNERABLE${NC} - Versioning suspended"
echo ""

# 3. Remove encryption from unencrypted-data-bucket
echo -e "${YELLOW}3. Removing encryption from unencrypted-data-bucket...${NC}"
aws --endpoint-url=$ENDPOINT s3api delete-bucket-encryption --bucket unencrypted-data-bucket 2>/dev/null || true
echo -e "   ${RED}❌ VULNERABLE${NC} - Encryption removed"
echo ""

# 4. Open SSH to 0.0.0.0/0 on security group
echo -e "${YELLOW}4. Opening SSH (port 22) to 0.0.0.0/0 on $SG_ID...${NC}"
# First revoke any existing SSH rules (ignore errors)
aws --endpoint-url=$ENDPOINT ec2 revoke-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 22 \
    --cidr 10.0.0.0/8 2>/dev/null || true
aws --endpoint-url=$ENDPOINT ec2 revoke-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 22 \
    --cidr 0.0.0.0/0 2>/dev/null || true

# Add vulnerable SSH rule
aws --endpoint-url=$ENDPOINT ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 22 \
    --cidr 0.0.0.0/0 >/dev/null 2>&1 || true
echo -e "   ${RED}❌ VULNERABLE${NC} - SSH open to 0.0.0.0/0"
echo ""

# 5. EBS Volume is already unencrypted
echo -e "${YELLOW}5. EBS Volume $VOL_ID...${NC}"
echo -e "   ${RED}❌ VULNERABLE${NC} - Created without encryption"
echo ""

# ============================================================================
# SUMMARY
# ============================================================================
echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║  PROD ENVIRONMENT IS NOW VULNERABLE!                        ║${NC}"
echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Resources ready for PatchWeave demo:"
echo "  • test-vulnerable-bucket    - No public access block"
echo "  • prod-data-bucket          - Versioning suspended"
echo "  • unencrypted-data-bucket   - No encryption"
echo "  • $SG_ID      - SSH open to 0.0.0.0/0"
echo "  • $VOL_ID     - Unencrypted"
echo ""
echo -e "${YELLOW}NOTE: Security Group and Volume IDs are dynamic after LocalStack restart.${NC}"
echo -e "${YELLOW}      Update check_vuln_status.sh if needed with:${NC}"
echo -e "        SG_ID=$SG_ID"
echo -e "        VOL_ID=$VOL_ID"
echo ""
