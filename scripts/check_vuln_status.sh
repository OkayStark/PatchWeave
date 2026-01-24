#!/bin/bash
# ============================================================================
# PatchWeave - Vulnerability Status Checker
# Checks status of 5 resources in both TEST (4566) and PROD (4567) environments
# ============================================================================

set -e

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

check_environment() {
    local ENV_NAME=$1
    local ENDPOINT=$2
    
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  ${ENV_NAME} ENVIRONMENT (${ENDPOINT})${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # 1. S3 Public Access Block (test-vulnerable-bucket)
    echo -e "${YELLOW}1. S3 Bucket: test-vulnerable-bucket (Public Access Block)${NC}"
    if aws --endpoint-url=$ENDPOINT s3api get-public-access-block --bucket test-vulnerable-bucket >/dev/null 2>&1; then
        echo -e "   ${GREEN}✅ SECURED${NC} - Public access blocked"
    else
        echo -e "   ${RED}❌ VULNERABLE${NC} - No public access block"
    fi
    echo ""
    
    # 2. S3 Versioning (prod-data-bucket)
    echo -e "${YELLOW}2. S3 Bucket: prod-data-bucket (Versioning)${NC}"
    VERS=$(aws --endpoint-url=$ENDPOINT s3api get-bucket-versioning --bucket prod-data-bucket --query 'Status' --output text 2>/dev/null || echo "None")
    if [ "$VERS" = "Enabled" ]; then
        echo -e "   ${GREEN}✅ SECURED${NC} - Versioning enabled"
    else
        echo -e "   ${RED}❌ VULNERABLE${NC} - Versioning not enabled"
    fi
    echo ""
    
    # 3. S3 Encryption (unencrypted-data-bucket)
    echo -e "${YELLOW}3. S3 Bucket: unencrypted-data-bucket (Server-Side Encryption)${NC}"
    ENC_CONFIG=$(aws --endpoint-url=$ENDPOINT s3api get-bucket-encryption --bucket unencrypted-data-bucket 2>&1 || echo "ERROR")
    if echo "$ENC_CONFIG" | grep -q "AES256\|aws:kms"; then
        echo -e "   ${GREEN}✅ SECURED${NC} - Encryption enabled"
    else
        echo -e "   ${RED}❌ VULNERABLE${NC} - No encryption"
    fi
    echo ""
    
    # 4. Security Group SSH (sg-a0b773a428b1cc158)
    echo -e "${YELLOW}4. Security Group: sg-a0b773a428b1cc158 (SSH Access)${NC}"
    CIDR=$(aws --endpoint-url=$ENDPOINT ec2 describe-security-groups --group-ids sg-a0b773a428b1cc158 --query 'SecurityGroups[0].IpPermissions[?FromPort==`22`].IpRanges[].CidrIp' --output text 2>/dev/null || echo "NOT_FOUND")
    if [ "$CIDR" = "0.0.0.0/0" ]; then
        echo -e "   ${RED}❌ VULNERABLE${NC} - SSH open to 0.0.0.0/0"
    elif [ "$CIDR" = "NOT_FOUND" ] || [ -z "$CIDR" ]; then
        echo -e "   ${GREEN}✅ SECURED${NC} - No SSH rule found"
    else
        echo -e "   ${GREEN}✅ SECURED${NC} - SSH restricted to $CIDR"
    fi
    echo ""
    
    # 5. EBS Volume Encryption (vol-3dbee0135891be189)
    echo -e "${YELLOW}5. EBS Volume: vol-3dbee0135891be189 (Encryption)${NC}"
    
    # Check if original volume is encrypted
    ORIG_ENC=$(aws --endpoint-url=$ENDPOINT ec2 describe-volumes --volume-ids vol-3dbee0135891be189 --query 'Volumes[0].Encrypted' --output text 2>/dev/null || echo "NOT_FOUND")
    
    # Check if PatchWeave created an encrypted replacement volume (tagged with CreatedBy: PatchWeave)
    REMEDIATED_VOL=$(aws --endpoint-url=$ENDPOINT ec2 describe-volumes \
        --filters "Name=tag:CreatedBy,Values=PatchWeave" "Name=encrypted,Values=true" \
        --query 'Volumes[0].VolumeId' --output text 2>/dev/null || echo "None")
    
    if [ "$ORIG_ENC" = "True" ]; then
        echo -e "   ${GREEN}✅ SECURED${NC} - Original volume is encrypted"
    elif [ "$REMEDIATED_VOL" != "None" ] && [ -n "$REMEDIATED_VOL" ]; then
        echo -e "   ${GREEN}✅ SECURED${NC} - Encrypted replacement: $REMEDIATED_VOL"
    elif [ "$ORIG_ENC" = "NOT_FOUND" ]; then
        echo -e "   ${YELLOW}⚠️  NOT FOUND${NC} - Volume doesn't exist"
    else
        echo -e "   ${RED}❌ VULNERABLE${NC} - Volume not encrypted (no remediation found)"
    fi
    echo ""
}

echo ""
echo "============================================================"
echo "  PatchWeave - Vulnerability Status Report"
echo "  $(date)"
echo "============================================================"
echo ""

# Check TEST environment
# check_environment "TEST" "http://localhost:4566"

echo ""

# Check PROD environment  
check_environment "PROD" "http://localhost:4567"

echo "============================================================"
echo "  Report Complete"
echo "============================================================"
