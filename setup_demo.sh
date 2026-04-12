#!/bin/bash
set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     PatchWeave Demo - Complete Setup                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# STEP 1: Reset LocalStack
echo "STEP 1/4: Resetting LocalStack PROD environment..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api list-buckets --query 'Buckets[].Name' --output text 2>/dev/null | sed 's/\t/\n/g' | while read bucket; do
  if [ -n "$bucket" ]; then
    echo "  🗑️  Deleting bucket: $bucket"
    AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
    aws --endpoint-url=http://localhost:4567 s3 rm "s3://$bucket" --recursive 2>/dev/null || true
    AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
    aws --endpoint-url=http://localhost:4567 s3api list-object-versions --bucket "$bucket" \
    --query 'Versions[].{Key:Key,VersionId:VersionId}' --output text 2>/dev/null | while read key vid; do
      [ -n "$key" ] && AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
      aws --endpoint-url=http://localhost:4567 s3api delete-object --bucket "$bucket" --key "$key" --version-id "$vid" 2>/dev/null || true
    done || true
    AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
    aws --endpoint-url=http://localhost:4567 s3api delete-bucket --bucket "$bucket" 2>/dev/null || true
  fi
done
echo "✅ LocalStack PROD cleaned"
echo ""

# STEP 2: Create vulnerable resources
echo "STEP 2/4: Creating vulnerable resources in PROD..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "1️⃣  test-vulnerable-bucket"
echo "   Vulnerability: PUBLIC ACCESS (no public access block)"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api create-bucket --bucket test-vulnerable-bucket 2>/dev/null
echo "   ✓ Created"
echo ""

echo "2️⃣  prod-data-bucket"
echo "   Vulnerability: NO VERSIONING"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api create-bucket --bucket prod-data-bucket 2>/dev/null
echo "   ✓ Created"
echo ""

echo "3️⃣  unencrypted-data-bucket"
echo "   Vulnerability: NO ENCRYPTION"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api create-bucket --bucket unencrypted-data-bucket 2>/dev/null
echo "   ✓ Created"
echo ""

echo "✅ All vulnerable resources created"
echo ""

# STEP 3: Verify vulnerabilities
echo "STEP 3/4: Verifying vulnerabilities..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📦 All buckets in PROD LocalStack (port 4567):"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api list-buckets --query 'Buckets[].Name' --output table
echo ""

echo "Vulnerability checks:"
echo "---"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api get-public-access-block --bucket test-vulnerable-bucket 2>&1 || echo "✗ test-vulnerable-bucket: No public access block (VULNERABLE)"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api get-bucket-versioning --bucket prod-data-bucket 2>&1 | grep -q "Status" || echo "✗ prod-data-bucket: Versioning disabled (VULNERABLE)"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api get-bucket-encryption --bucket unencrypted-data-bucket 2>&1 || echo "✗ unencrypted-data-bucket: No encryption (VULNERABLE)"
echo ""
echo "✅ All vulnerabilities confirmed!"
echo ""

# STEP 4: Instructions
echo "STEP 4/4: Next steps..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 CREATE THESE JIRA TICKETS in your KAN project:"
echo ""
echo "Ticket 1:"
echo "  Title: [CRITICAL] S3 Bucket 'test-vulnerable-bucket' has public access enabled"
echo "  Description: See SETUP_DEMO_TICKETS.md for full text"
echo ""
echo "Ticket 2:"
echo "  Title: [HIGH] S3 Bucket 'prod-data-bucket' does not have versioning enabled"
echo "  Description: See SETUP_DEMO_TICKETS.md for full text"
echo ""
echo "Ticket 3:"
echo "  Title: [HIGH] S3 Bucket 'unencrypted-data-bucket' does not have server-side encryption enabled"
echo "  Description: See SETUP_DEMO_TICKETS.md for full text"
echo ""
echo "📖 Full ticket templates are in: SETUP_DEMO_TICKETS.md"
echo ""
echo "🚀 THEN RUN PATCHWEAVE:"
echo "   cd /home/stark/PatchWeave"
echo "   source .venv/bin/activate"
echo "   python -m patchweave.main"
echo ""
echo "PatchWeave will:"
echo "  1. Poll Jira for the tickets you created"
echo "  2. Analyze each vulnerability using LLM"
echo "  3. Match to remediation playbooks"
echo "  4. Test fixes in LocalStack TEST environment"
echo "  5. Post approval requests on Jira"
echo "  6. After your approval, deploy fixes to PROD"
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  ✅ Setup complete! Now create the 3 Jira tickets above       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
