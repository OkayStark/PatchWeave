# PatchWeave Demo - Complete Setup Guide

This document contains everything needed to:
1. Create Jira tickets with vulnerability findings
2. Reset and prepare LocalStack environments
3. Create vulnerable resources in PROD LocalStack
4. Run PatchWeave to automatically remediate them

---

## Part 1: Jira Tickets to Create

Create these 5 tickets in your Jira project (KAN). Copy the title and description exactly.

### Ticket 1: S3 Public Access Vulnerability

**Title:** `[CRITICAL] S3 Bucket 'test-vulnerable-bucket' has public access enabled`

**Description:**
```
AWS Security Finding

Resource: arn:aws:s3:::test-vulnerable-bucket
Resource Type: AWS::S3::Bucket
Region: us-east-1
Account: 123456789012

Issue: S3 bucket has Block Public Access disabled.

Current Configuration:
- BlockPublicAcls: false
- IgnorePublicAcls: false
- BlockPublicPolicy: false
- RestrictPublicBuckets: false

The bucket is publicly accessible to anyone with the URL.

Severity: CRITICAL
Compliance: CIS AWS 2.1.5, PCI DSS 1.2.1

Remediation: Enable public access block on the bucket
```

---

### Ticket 2: S3 No Versioning

**Title:** `[HIGH] S3 Bucket 'prod-data-bucket' does not have versioning enabled`

**Description:**
```
AWS Security Finding

Resource: arn:aws:s3:::prod-data-bucket
Resource Type: AWS::S3::Bucket
Region: us-east-1
Account: 123456789012

Finding: S3 bucket versioning is not enabled. Without versioning, objects cannot be recovered if accidentally deleted or overwritten. This poses a risk to data durability and compliance requirements.

Severity: HIGH
Compliance: CIS AWS Benchmark 2.1.1, SOC2 CC6.2

Remediation Required: Enable versioning on the S3 bucket to protect against accidental deletion and enable object recovery.
```

---

### Ticket 3: S3 No Encryption

**Title:** `[HIGH] S3 Bucket 'unencrypted-data-bucket' does not have server-side encryption enabled`

**Description:**
```
Security Finding

Resource: S3 Bucket
Bucket Name: unencrypted-data-bucket
Account: 123456789012
Region: us-east-1

Vulnerability Details:
The S3 bucket unencrypted-data-bucket does not have server-side encryption configured. Data stored in this bucket is not encrypted at rest, potentially exposing sensitive information.

Severity: High
Compliance: CIS AWS 2.1.1, SOC 2 CC6.1, HIPAA

Recommended Remediation:
Enable AES-256 server-side encryption (SSE-S3) on the bucket to protect data at rest.
```

---

### Ticket 4: Security Group SSH Open

**Title:** `[CRITICAL] Security Group 'vulnerable-ssh-sg' allows unrestricted SSH access from 0.0.0.0/0`

**Description:**
```
Security Finding

Resource: EC2 Security Group
Security Group Name: vulnerable-ssh-sg
Account: 123456789012
Region: us-east-1

Vulnerability Details:
The security group vulnerable-ssh-sg has an inbound rule allowing SSH (port 22) access from 0.0.0.0/0 (the entire internet). This exposes instances using this security group to potential brute-force attacks and unauthorized access.

Inbound Rule:
- Protocol: TCP
- Port: 22
- Source: 0.0.0.0/0

Severity: Critical
Compliance: CIS AWS 5.2, PCI DSS 1.2.1, NIST 800-53 SC-7

Recommended Remediation:
Restrict SSH access to specific IP ranges or use a bastion host/VPN for remote access.
```

---

### Ticket 5: EBS Not Encrypted

**Title:** `[HIGH] EBS Volume 'vol-unencrypted-001' is not encrypted`

**Description:**
```
Security Finding

Resource: EBS Volume
Volume ID: vol-unencrypted-001
Account: 123456789012
Region: us-east-1
Availability Zone: us-east-1a

Vulnerability Details:
The EBS volume vol-unencrypted-001 is not encrypted. Data stored on this volume is not protected at rest, which may expose sensitive information in case of unauthorized access to the underlying storage.

Volume State: available
Size: 8 GiB

Severity: High
Compliance: CIS AWS 2.2.1, HIPAA 164.312(a)(2)(iv), SOC 2 CC6.1

Recommended Remediation:
Create an encrypted snapshot of the volume and replace the unencrypted volume with an encrypted one.
```

---

## Part 2: Reset LocalStack Environment

Run these commands to clean up any existing resources:

```bash
#!/bin/bash
# === CLEAR ALL BUCKETS IN PROD ===

echo "🧹 Clearing all buckets from PROD LocalStack (port 4567)..."
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api list-buckets --query 'Buckets[].Name' --output text 2>/dev/null | sed 's/\t/\n/g' | while read bucket; do
  if [ -n "$bucket" ]; then
    echo "  Deleting bucket: $bucket"
    # Delete all objects
    AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
    aws --endpoint-url=http://localhost:4567 s3 rm "s3://$bucket" --recursive 2>/dev/null

    # Delete all object versions
    AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
    aws --endpoint-url=http://localhost:4567 s3api list-object-versions --bucket "$bucket" \
    --query 'Versions[].{Key:Key,VersionId:VersionId}' --output text 2>/dev/null | while read key vid; do
      [ -n "$key" ] && AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
      aws --endpoint-url=http://localhost:4567 s3api delete-object --bucket "$bucket" --key "$key" --version-id "$vid" 2>/dev/null
    done

    # Delete the bucket
    AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
    aws --endpoint-url=http://localhost:4567 s3api delete-bucket --bucket "$bucket" 2>/dev/null
  fi
done

echo "✅ All buckets cleared"
```

---

## Part 3: Create Vulnerable Resources in PROD

Run these commands to create all vulnerable resources:

```bash
#!/bin/bash
echo "🔓 Creating vulnerable resources in PROD LocalStack (port 4567)..."
echo ""

# Vulnerability 1: S3 Public Access (test-vulnerable-bucket)
echo "1️⃣  Creating: test-vulnerable-bucket (NO PUBLIC ACCESS BLOCK)"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api create-bucket --bucket test-vulnerable-bucket 2>/dev/null
echo "   ✓ Created without public access block"
echo ""

# Vulnerability 2: S3 No Versioning (prod-data-bucket)
echo "2️⃣  Creating: prod-data-bucket (NO VERSIONING)"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api create-bucket --bucket prod-data-bucket 2>/dev/null
echo "   ✓ Created without versioning enabled"
echo ""

# Vulnerability 3: S3 No Encryption (unencrypted-data-bucket)
echo "3️⃣  Creating: unencrypted-data-bucket (NO ENCRYPTION)"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api create-bucket --bucket unencrypted-data-bucket 2>/dev/null
echo "   ✓ Created without server-side encryption"
echo ""
```

---

## Part 4: Verify Vulnerable Resources

Run these commands to confirm resources are vulnerable:

```bash
#!/bin/bash
echo "🔍 VERIFYING VULNERABILITIES IN PROD..."
echo ""

# List all buckets
echo "📦 Buckets created:"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api list-buckets --query 'Buckets[].Name' --output table
echo ""

# Check test-vulnerable-bucket public access block
echo "🔓 test-vulnerable-bucket - Public Access Block:"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api get-public-access-block --bucket test-vulnerable-bucket 2>&1 || echo "   ✗ VULNERABLE: No public access block configured"
echo ""

# Check prod-data-bucket versioning
echo "📝 prod-data-bucket - Versioning Status:"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api get-bucket-versioning --bucket prod-data-bucket 2>&1 | grep -E "Status|MFADelete" || echo "   ✗ VULNERABLE: Versioning not enabled"
echo ""

# Check unencrypted-data-bucket encryption
echo "🔐 unencrypted-data-bucket - Encryption:"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api get-bucket-encryption --bucket unencrypted-data-bucket 2>&1 || echo "   ✗ VULNERABLE: No encryption configured"
echo ""

echo "✅ All vulnerabilities confirmed!"
```

---

## Part 5: Complete Setup Script (Run All At Once)

Save this as `setup_demo.sh` and run it:

```bash
#!/bin/bash
set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     PatchWeave Demo - Complete Setup                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# STEP 1: Reset LocalStack
echo "STEP 1: Resetting LocalStack environments..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api list-buckets --query 'Buckets[].Name' --output text 2>/dev/null | sed 's/\t/\n/g' | while read bucket; do
  if [ -n "$bucket" ]; then
    echo "  Deleting bucket: $bucket"
    AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
    aws --endpoint-url=http://localhost:4567 s3 rm "s3://$bucket" --recursive 2>/dev/null
    AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
    aws --endpoint-url=http://localhost:4567 s3api list-object-versions --bucket "$bucket" \
    --query 'Versions[].{Key:Key,VersionId:VersionId}' --output text 2>/dev/null | while read key vid; do
      [ -n "$key" ] && AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
      aws --endpoint-url=http://localhost:4567 s3api delete-object --bucket "$bucket" --key "$key" --version-id "$vid" 2>/dev/null
    done
    AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
    aws --endpoint-url=http://localhost:4567 s3api delete-bucket --bucket "$bucket" 2>/dev/null
  fi
done
echo "✅ LocalStack cleaned"
echo ""

# STEP 2: Create vulnerable resources
echo "STEP 2: Creating vulnerable resources..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "1️⃣  test-vulnerable-bucket (public access vulnerability)"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api create-bucket --bucket test-vulnerable-bucket 2>/dev/null
echo "   ✓ Created"

echo "2️⃣  prod-data-bucket (no versioning vulnerability)"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api create-bucket --bucket prod-data-bucket 2>/dev/null
echo "   ✓ Created"

echo "3️⃣  unencrypted-data-bucket (no encryption vulnerability)"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api create-bucket --bucket unencrypted-data-bucket 2>/dev/null
echo "   ✓ Created"

echo "✅ All vulnerable resources created"
echo ""

# STEP 3: Verify vulnerabilities
echo "STEP 3: Verifying vulnerabilities..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Buckets in PROD:"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api list-buckets --query 'Buckets[].Name' --output table
echo ""
echo "✅ Vulnerabilities verified in LocalStack PROD (port 4567)"
echo ""

# STEP 4: Instructions
echo "STEP 4: Next steps..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Create these Jira tickets in your KAN project:"
echo "   1. [CRITICAL] S3 Bucket 'test-vulnerable-bucket' has public access enabled"
echo "   2. [HIGH] S3 Bucket 'prod-data-bucket' does not have versioning enabled"
echo "   3. [HIGH] S3 Bucket 'unencrypted-data-bucket' does not have server-side encryption enabled"
echo ""
echo "See the full ticket descriptions at the top of this file."
echo ""
echo "🚀 Then run PatchWeave:"
echo "   cd /home/stark/PatchWeave"
echo "   source .venv/bin/activate"
echo "   python -m patchweave.main"
echo ""
```

---

## Part 6: Run PatchWeave to Fix Vulnerabilities

Once you've created the 3 Jira tickets, run this command:

```bash
cd /home/stark/PatchWeave
source .venv/bin/activate
python -m patchweave.main
```

**What will happen:**
1. ✅ PatchWeave polls Jira for "Open" tickets in project KAN
2. ✅ Analyzes each ticket using LLM (classifies vulnerability type)
3. ✅ Matches to remediation playbooks using ChromaDB
4. ✅ Tests the fix in LocalStack TEST environment (port 4566)
5. ✅ Posts approval request to Jira with validation results
6. ⏳ Waits for your approval on Jira
7. ✅ Deploys fix to PROD LocalStack (port 4567)

**You'll see in the terminal:**
```
[INFO] Polling Jira for findings...
[INFO] Found ticket: KAN-1 - S3 Bucket 'test-vulnerable-bucket' has public access enabled
[INFO] Analyzing vulnerability... confidence: 0.95
[INFO] Classified as: s3_public_access
[INFO] Searching for matching playbook...
[INFO] Found: pb-s3-public-access-001 (similarity: 94%)
[INFO] Validating in LocalStack TEST environment...
[INFO] Pre-validation: PASSED (vulnerability confirmed)
[INFO] Executing remediation...
[INFO] Post-validation: PASSED (vulnerability fixed)
[INFO] Posting approval request to Jira...
[✓] Awaiting human approval on KAN-1
```

---

## Quick Reference Commands

### Reset + Setup + Verify (All in One)
```bash
cd /home/stark/PatchWeave && \
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test aws --endpoint-url=http://localhost:4567 s3api list-buckets --query 'Buckets[].Name' --output text 2>/dev/null | sed 's/\t/\n/g' | while read bucket; do [ -n "$bucket" ] && (AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test aws --endpoint-url=http://localhost:4567 s3 rm "s3://$bucket" --recursive 2>/dev/null; AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test aws --endpoint-url=http://localhost:4567 s3api delete-bucket --bucket "$bucket" 2>/dev/null); done && \
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test aws --endpoint-url=http://localhost:4567 s3api create-bucket --bucket test-vulnerable-bucket 2>/dev/null && \
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test aws --endpoint-url=http://localhost:4567 s3api create-bucket --bucket prod-data-bucket 2>/dev/null && \
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test aws --endpoint-url=http://localhost:4567 s3api create-bucket --bucket unencrypted-data-bucket 2>/dev/null && \
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test aws --endpoint-url=http://localhost:4567 s3api list-buckets && \
echo "✅ Ready! Now create the 3 Jira tickets and run: python -m patchweave.main"
```

### Check Status Anytime
```bash
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
aws --endpoint-url=http://localhost:4567 s3api list-buckets --query 'Buckets[].Name' --output table
```

---

## Summary

| Step | Command |
|------|---------|
| 1. Create Jira Tickets | See Part 1 above in your Jira dashboard |
| 2. Reset LocalStack | Run Part 3 script |
| 3. Create Vulnerabilities | Run Part 5 script |
| 4. Verify Setup | Run Part 6 verification |
| 5. Run PatchWeave | `python -m patchweave.main` |
| 6. Approve on Jira | Click "Approve" on tickets when PatchWeave posts requests |

---
