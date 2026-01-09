# Playbook Authoring Guide

This guide explains how to create remediation playbooks for PatchWeave.

## Table of Contents

1. [Overview](#overview)
2. [Playbook Structure](#playbook-structure)
3. [Required Fields](#required-fields)
4. [Code Sections](#code-sections)
5. [Best Practices](#best-practices)
6. [Examples](#examples)
7. [Testing Playbooks](#testing-playbooks)

---

## Overview

Playbooks are YAML files that define how PatchWeave should remediate specific security vulnerabilities. Each playbook contains:

- **Metadata**: Identification and classification information
- **Search Text**: Keywords for semantic matching
- **Remediation Code**: Python code to fix the vulnerability
- **Pre/Post Checks**: Verification code
- **Rollback Code**: Recovery code if remediation fails

## Playbook Structure

```yaml
# Unique identifier - format: pb-{resource}-{action}-{version}
id: pb-s3-encrypt-001

# Human-readable name
name: Enable S3 Default Encryption

# Description (appears in Jira approval comments)
description: |
  Enables AES-256 server-side encryption on an S3 bucket
  using AWS managed keys (SSE-S3).

# Semantic version
version: "1.0.0"

# Must match a VulnerabilityType enum value
vulnerability_type: s3_encryption_disabled

# AWS resource type (CloudFormation format)
resource_type: AWS::S3::Bucket

# Severity: Critical, High, Medium, Low, Informational
severity: High

# Cloud provider
cloud_provider: AWS

# Keywords for ChromaDB semantic search
search_text: |
  S3 bucket encryption disabled SSE AES-256
  server side encryption not enabled
  unencrypted bucket data at rest

# Python code to apply the fix
remediation_code: |
  import boto3
  
  def remediate(bucket_name: str, region: str = "us-east-1") -> dict:
      """Enable default encryption on S3 bucket."""
      s3 = boto3.client("s3", region_name=region)
      
      s3.put_bucket_encryption(
          Bucket=bucket_name,
          ServerSideEncryptionConfiguration={
              "Rules": [{
                  "ApplyServerSideEncryptionByDefault": {
                      "SSEAlgorithm": "AES256"
                  }
              }]
          }
      )
      
      return {"status": "success", "bucket": bucket_name}

# Code to verify the vulnerability exists
pre_check_code: |
  import boto3
  from botocore.exceptions import ClientError
  
  def pre_check(bucket_name: str, region: str = "us-east-1") -> bool:
      """Return True if bucket needs encryption (vulnerability exists)."""
      s3 = boto3.client("s3", region_name=region)
      
      try:
          s3.get_bucket_encryption(Bucket=bucket_name)
          return False  # Already encrypted
      except ClientError as e:
          if e.response["Error"]["Code"] == "ServerSideEncryptionConfigurationNotFoundError":
              return True  # Needs encryption
          raise

# Code to verify remediation succeeded
post_check_code: |
  import boto3
  from botocore.exceptions import ClientError
  
  def post_check(bucket_name: str, region: str = "us-east-1") -> bool:
      """Return True if bucket is now encrypted."""
      s3 = boto3.client("s3", region_name=region)
      
      try:
          response = s3.get_bucket_encryption(Bucket=bucket_name)
          rules = response.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
          return len(rules) > 0
      except ClientError:
          return False

# Code to revert the change if needed
rollback_code: |
  import boto3
  
  def rollback(bucket_name: str, region: str = "us-east-1") -> dict:
      """Remove encryption configuration (for rollback)."""
      s3 = boto3.client("s3", region_name=region)
      
      s3.delete_bucket_encryption(Bucket=bucket_name)
      
      return {"status": "rolled_back", "bucket": bucket_name}

# Search tags (optional)
tags:
  - s3
  - encryption
  - data-protection
  - sse

# Compliance frameworks this addresses (optional)
compliance_frameworks:
  - CIS AWS 2.1.1
  - SOC2
  - PCI-DSS

# Required IAM permissions
required_permissions:
  - s3:PutBucketEncryption
  - s3:GetBucketEncryption
  - s3:DeleteBucketEncryption

# Estimated time to execute (seconds)
estimated_execution_time_seconds: 30
```

---

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier (format: `pb-{resource}-{action}-{version}`) |
| `name` | string | Human-readable name |
| `description` | string | What the playbook does |
| `vulnerability_type` | enum | Must match `VulnerabilityType` enum |
| `resource_type` | string | AWS resource type (CloudFormation format) |
| `severity` | enum | Critical, High, Medium, Low, Informational |
| `search_text` | string | Keywords for semantic matching |
| `remediation_code` | string | Python code to fix the issue |

### Vulnerability Types

The `vulnerability_type` must be one of:

```python
class VulnerabilityType(str, Enum):
    S3_PUBLIC_ACCESS = "s3_public_access"
    S3_ENCRYPTION_DISABLED = "s3_encryption_disabled"
    SECURITY_GROUP_OPEN_PORT = "security_group_open_port"
    RDS_PUBLIC_ACCESS = "rds_public_access"
    RDS_ENCRYPTION_DISABLED = "rds_encryption_disabled"
    EC2_IMDSV1 = "ec2_imdsv1"
    IAM_USER_NO_MFA = "iam_user_no_mfa"
    KMS_KEY_ROTATION = "kms_key_rotation"
    EBS_ENCRYPTION = "ebs_encryption"
    CLOUDTRAIL_DISABLED = "cloudtrail_disabled"
    GUARDDUTY_DISABLED = "guardduty_disabled"
    VPC_FLOW_LOGS = "vpc_flow_logs"
    UNKNOWN = "unknown"
```

---

## Code Sections

### Remediation Code

The main fix logic. Must define a `remediate()` function:

```python
def remediate(**kwargs) -> dict:
    """
    Apply the remediation.
    
    Args:
        **kwargs: Token values substituted at runtime
            - bucket_name, instance_id, etc.
            - region (always provided)
    
    Returns:
        dict with at least {"status": "success"} or {"status": "failed", "error": "..."}
    """
    # Your remediation logic
    return {"status": "success"}
```

### Pre-Check Code

Verify the vulnerability exists before attempting remediation:

```python
def pre_check(**kwargs) -> bool:
    """
    Check if vulnerability exists.
    
    Returns:
        True if vulnerability exists (should remediate)
        False if already fixed (skip remediation)
    """
    # Check current state
    return needs_remediation
```

### Post-Check Code

Verify remediation was successful:

```python
def post_check(**kwargs) -> bool:
    """
    Verify remediation succeeded.
    
    Returns:
        True if remediation was successful
        False if remediation failed (triggers rollback)
    """
    # Verify fixed state
    return is_fixed
```

### Rollback Code

Revert changes if post-check fails:

```python
def rollback(**kwargs) -> dict:
    """
    Revert the remediation.
    
    Returns:
        dict with status of rollback
    """
    # Undo the changes
    return {"status": "rolled_back"}
```

---

## Best Practices

### 1. Search Text Optimization

Write search text that matches how security findings are described:

```yaml
# Good: Varied terminology
search_text: |
  S3 bucket public access Block Public Access disabled
  publicly accessible storage bucket policy
  open S3 bucket ACL permissions

# Bad: Limited keywords
search_text: |
  S3 public access
```

### 2. Idempotent Operations

Ensure remediation can be run multiple times safely:

```python
def remediate(bucket_name: str) -> dict:
    s3 = boto3.client("s3")
    
    # Check if already configured
    try:
        existing = s3.get_bucket_encryption(Bucket=bucket_name)
        if existing:  # Already encrypted
            return {"status": "success", "message": "Already encrypted"}
    except ClientError:
        pass
    
    # Apply fix
    s3.put_bucket_encryption(...)
    return {"status": "success"}
```

### 3. Comprehensive Error Handling

```python
def remediate(instance_id: str) -> dict:
    ec2 = boto3.client("ec2")
    
    try:
        ec2.modify_instance_metadata_options(
            InstanceId=instance_id,
            HttpTokens="required"
        )
        return {"status": "success", "instance": instance_id}
    
    except ec2.exceptions.IncorrectInstanceState as e:
        return {
            "status": "failed",
            "error": f"Instance not in correct state: {e}"
        }
    
    except ClientError as e:
        return {
            "status": "failed", 
            "error": str(e)
        }
```

### 4. Logging

Use logging for visibility:

```python
import logging

log = logging.getLogger(__name__)

def remediate(bucket_name: str) -> dict:
    log.info(f"Starting encryption for bucket: {bucket_name}")
    
    s3 = boto3.client("s3")
    s3.put_bucket_encryption(...)
    
    log.info(f"Successfully encrypted bucket: {bucket_name}")
    return {"status": "success"}
```

### 5. Token Usage

Use token placeholders that PatchWeave will substitute:

```yaml
remediation_code: |
  def remediate(bucket_name: str, account_id: str, region: str) -> dict:
      # bucket_name, account_id, region are substituted from tokens
      # {{BUCKET_NAME}}, {{ACCOUNT_ID}}, {{AWS_REGION}}
      ...
```

---

## Examples

### Security Group - Restrict Open Port

```yaml
id: pb-sg-restrict-ssh-001
name: Restrict SSH Access to Security Group
description: Removes 0.0.0.0/0 SSH (port 22) access from security group
version: "1.0.0"
vulnerability_type: security_group_open_port
resource_type: AWS::EC2::SecurityGroup
severity: High
cloud_provider: AWS

search_text: |
  security group SSH port 22 open 0.0.0.0/0
  unrestricted SSH access inbound rule
  publicly accessible SSH

remediation_code: |
  import boto3
  
  def remediate(security_group_id: str, region: str = "us-east-1") -> dict:
      ec2 = boto3.client("ec2", region_name=region)
      
      # Revoke the 0.0.0.0/0 SSH rule
      ec2.revoke_security_group_ingress(
          GroupId=security_group_id,
          IpPermissions=[{
              "IpProtocol": "tcp",
              "FromPort": 22,
              "ToPort": 22,
              "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
          }]
      )
      
      return {"status": "success", "security_group": security_group_id}

pre_check_code: |
  import boto3
  
  def pre_check(security_group_id: str, region: str = "us-east-1") -> bool:
      ec2 = boto3.client("ec2", region_name=region)
      
      response = ec2.describe_security_groups(GroupIds=[security_group_id])
      
      for permission in response["SecurityGroups"][0].get("IpPermissions", []):
          if permission.get("FromPort") == 22 and permission.get("ToPort") == 22:
              for ip_range in permission.get("IpRanges", []):
                  if ip_range.get("CidrIp") == "0.0.0.0/0":
                      return True
      return False

post_check_code: |
  import boto3
  
  def post_check(security_group_id: str, region: str = "us-east-1") -> bool:
      ec2 = boto3.client("ec2", region_name=region)
      
      response = ec2.describe_security_groups(GroupIds=[security_group_id])
      
      for permission in response["SecurityGroups"][0].get("IpPermissions", []):
          if permission.get("FromPort") == 22 and permission.get("ToPort") == 22:
              for ip_range in permission.get("IpRanges", []):
                  if ip_range.get("CidrIp") == "0.0.0.0/0":
                      return False  # Still has open access
      return True  # No open SSH access

tags:
  - security-group
  - ssh
  - network-security

required_permissions:
  - ec2:DescribeSecurityGroups
  - ec2:RevokeSecurityGroupIngress
```

### RDS - Disable Public Access

```yaml
id: pb-rds-private-001
name: Disable RDS Public Accessibility
description: Disables public accessibility on RDS instance
version: "1.0.0"
vulnerability_type: rds_public_access
resource_type: AWS::RDS::DBInstance
severity: Critical
cloud_provider: AWS

search_text: |
  RDS database publicly accessible
  RDS instance public access enabled
  database exposed to internet

remediation_code: |
  import boto3
  
  def remediate(db_instance_id: str, region: str = "us-east-1") -> dict:
      rds = boto3.client("rds", region_name=region)
      
      rds.modify_db_instance(
          DBInstanceIdentifier=db_instance_id,
          PubliclyAccessible=False,
          ApplyImmediately=True
      )
      
      return {"status": "success", "db_instance": db_instance_id}

pre_check_code: |
  import boto3
  
  def pre_check(db_instance_id: str, region: str = "us-east-1") -> bool:
      rds = boto3.client("rds", region_name=region)
      
      response = rds.describe_db_instances(DBInstanceIdentifier=db_instance_id)
      
      return response["DBInstances"][0].get("PubliclyAccessible", False)

post_check_code: |
  import boto3
  import time
  
  def post_check(db_instance_id: str, region: str = "us-east-1") -> bool:
      rds = boto3.client("rds", region_name=region)
      
      # Wait for modification to complete
      max_attempts = 30
      for _ in range(max_attempts):
          response = rds.describe_db_instances(DBInstanceIdentifier=db_instance_id)
          instance = response["DBInstances"][0]
          
          if instance["DBInstanceStatus"] == "available":
              return not instance.get("PubliclyAccessible", True)
          
          time.sleep(10)
      
      return False

tags:
  - rds
  - database
  - network-security

required_permissions:
  - rds:DescribeDBInstances
  - rds:ModifyDBInstance
```

---

## Testing Playbooks

### 1. Validate YAML Syntax

```bash
python -c "
import yaml
with open('playbooks/your-playbook.yaml') as f:
    playbook = yaml.safe_load(f)
    print('Valid YAML:', playbook['id'])
"
```

### 2. Load and Validate

```bash
python -c "
from patchweave.knowledge.loader import PlaybookLoader

loader = PlaybookLoader()
playbooks = loader.load_all()

for pb in playbooks:
    print(f'{pb.id}: {pb.name} - {pb.vulnerability_type}')
"
```

### 3. Test Against LocalStack

```bash
# Start LocalStack
docker-compose up -d localstack

# Create test resource
aws --endpoint-url=http://localhost:4566 s3 mb s3://test-bucket

# Run playbook test
python -c "
from patchweave.agents.validator import ValidatorAgent
from patchweave.knowledge.loader import PlaybookLoader

loader = PlaybookLoader()
playbooks = loader.load_from_file('playbooks/s3-encryption.yaml')

validator = ValidatorAgent()
result = validator.validate(playbooks[0], {'bucket_name': 'test-bucket'})
print(result)
"
```

### 4. Test Semantic Matching

```bash
python -c "
from patchweave.knowledge.chromadb_client import ChromaDBClient
from patchweave.knowledge.loader import PlaybookLoader

# Load playbooks
loader = PlaybookLoader()
playbooks = loader.load_all()

# Index in ChromaDB
client = ChromaDBClient()
client.add_playbooks(playbooks)

# Test search
results = client.search('S3 bucket without encryption enabled', n_results=3)
for r in results:
    print(f'{r.playbook.id}: {r.similarity_score:.2f}')
"
```

---

## File Organization

Place playbooks in the `playbooks/` directory:

```
playbooks/
├── s3/
│   ├── s3-public-access.yaml
│   ├── s3-encryption.yaml
│   └── s3-versioning.yaml
├── ec2/
│   ├── ec2-imdsv2.yaml
│   └── ec2-public-ip.yaml
├── rds/
│   ├── rds-public-access.yaml
│   └── rds-encryption.yaml
├── iam/
│   └── iam-user-mfa.yaml
└── security-groups/
    ├── sg-restrict-ssh.yaml
    └── sg-restrict-rdp.yaml
```

The playbook loader will recursively find all `.yaml` files.

---

## Troubleshooting

### Playbook Not Found in Search

1. Check `vulnerability_type` matches the finding classification
2. Improve `search_text` with more varied keywords
3. Verify playbook is loaded: `loader.load_all()`

### Pre-Check Fails

1. Verify the resource exists
2. Check IAM permissions
3. Test with LocalStack first

### Remediation Fails

1. Check error logs for specific failure
2. Verify IAM permissions
3. Test code independently with boto3

### Post-Check Fails

1. Some changes take time (RDS modifications)
2. Add appropriate waits/retries
3. Verify the check logic matches the remediation
