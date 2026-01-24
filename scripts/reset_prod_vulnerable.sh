#!/bin/bash
# ============================================================================
# PatchWeave - Reset PROD Environment to Vulnerable State
# Makes all 5 resources vulnerable for demo/presentation purposes
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
NC='\033[0m'

echo ""
echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║  RESETTING PROD ENVIRONMENT TO VULNERABLE STATE             ║${NC}"
echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
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
echo -e "${YELLOW}4. Opening SSH (port 22) to 0.0.0.0/0 on sg-a0b773a428b1cc158...${NC}"
# First revoke existing SSH rules
aws --endpoint-url=$ENDPOINT ec2 revoke-security-group-ingress \
    --group-id sg-a0b773a428b1cc158 \
    --protocol tcp \
    --port 22 \
    --cidr 10.0.0.0/8 2>/dev/null || true

# Add vulnerable SSH rule
aws --endpoint-url=$ENDPOINT ec2 authorize-security-group-ingress \
    --group-id sg-a0b773a428b1cc158 \
    --protocol tcp \
    --port 22 \
    --cidr 0.0.0.0/0 2>/dev/null || true
echo -e "   ${RED}❌ VULNERABLE${NC} - SSH open to 0.0.0.0/0"
echo ""

# 5. EBS Volume - Note about encryption
echo -e "${YELLOW}5. EBS Volume vol-3dbee0135891be189...${NC}"
echo -e "   ${RED}❌ VULNERABLE${NC} - Already unencrypted (cannot un-encrypt a volume)"
echo ""

echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║  PROD ENVIRONMENT IS NOW VULNERABLE!                        ║${NC}"
echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Resources ready for PatchWeave demo:"
echo "  • test-vulnerable-bucket    - No public access block"
echo "  • prod-data-bucket          - Versioning suspended"
echo "  • unencrypted-data-bucket   - No encryption"
echo "  • sg-a0b773a428b1cc158      - SSH open to 0.0.0.0/0"
echo "  • vol-3dbee0135891be189     - Unencrypted"
echo ""
