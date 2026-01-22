#!/bin/bash
# Cleanup TEST LocalStack environment (port 4566)
# This removes any orphaned resources from failed validation runs

set -e

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
ENDPOINT="http://localhost:4566"

echo "=== Cleaning up TEST Environment (LocalStack 4566) ==="

# Delete all S3 buckets
echo -e "\n🗑️  Deleting S3 Buckets..."
BUCKETS=$(aws --endpoint-url=$ENDPOINT s3api list-buckets --query 'Buckets[].Name' --output text 2>/dev/null || echo "")
if [ -n "$BUCKETS" ]; then
    for bucket in $BUCKETS; do
        echo "  Deleting bucket: $bucket"
        # Delete all objects first
        aws --endpoint-url=$ENDPOINT s3 rm "s3://$bucket" --recursive 2>/dev/null || true
        # Delete versions if bucket has versioning
        aws --endpoint-url=$ENDPOINT s3api delete-bucket --bucket "$bucket" 2>/dev/null || true
    done
else
    echo "  No buckets to delete"
fi

# Delete EBS Volumes
echo -e "\n🗑️  Deleting EBS Volumes..."
VOLUMES=$(aws --endpoint-url=$ENDPOINT ec2 describe-volumes --query 'Volumes[].VolumeId' --output text 2>/dev/null || echo "")
if [ -n "$VOLUMES" ]; then
    for vol in $VOLUMES; do
        echo "  Deleting volume: $vol"
        aws --endpoint-url=$ENDPOINT ec2 delete-volume --volume-id "$vol" 2>/dev/null || true
    done
else
    echo "  No volumes to delete"
fi

# Delete Security Groups (except default)
echo -e "\n🗑️  Deleting Security Groups..."
SGS=$(aws --endpoint-url=$ENDPOINT ec2 describe-security-groups --query 'SecurityGroups[?GroupName!=`default`].GroupId' --output text 2>/dev/null || echo "")
if [ -n "$SGS" ]; then
    for sg in $SGS; do
        echo "  Deleting security group: $sg"
        aws --endpoint-url=$ENDPOINT ec2 delete-security-group --group-id "$sg" 2>/dev/null || true
    done
else
    echo "  No non-default security groups to delete"
fi

# Delete VPCs (except default)
echo -e "\n🗑️  Deleting VPCs..."
# First get all subnets and delete them
SUBNETS=$(aws --endpoint-url=$ENDPOINT ec2 describe-subnets --query 'Subnets[].SubnetId' --output text 2>/dev/null || echo "")
for subnet in $SUBNETS; do
    echo "  Deleting subnet: $subnet"
    aws --endpoint-url=$ENDPOINT ec2 delete-subnet --subnet-id "$subnet" 2>/dev/null || true
done

# Get VPCs - skip those with IsDefault=true
VPCS=$(aws --endpoint-url=$ENDPOINT ec2 describe-vpcs --query 'Vpcs[?IsDefault==`false`].VpcId' --output text 2>/dev/null || echo "")
# LocalStack doesn't really have a default VPC, so also check for non-main route tables
ALL_VPCS=$(aws --endpoint-url=$ENDPOINT ec2 describe-vpcs --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo "")
if [ -n "$ALL_VPCS" ]; then
    for vpc in $ALL_VPCS; do
        echo "  Deleting VPC: $vpc"
        # Delete internet gateways
        IGWS=$(aws --endpoint-url=$ENDPOINT ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$vpc" --query 'InternetGateways[].InternetGatewayId' --output text 2>/dev/null || echo "")
        for igw in $IGWS; do
            aws --endpoint-url=$ENDPOINT ec2 detach-internet-gateway --internet-gateway-id "$igw" --vpc-id "$vpc" 2>/dev/null || true
            aws --endpoint-url=$ENDPOINT ec2 delete-internet-gateway --internet-gateway-id "$igw" 2>/dev/null || true
        done
        # Delete security groups in VPC (except default)
        VPC_SGS=$(aws --endpoint-url=$ENDPOINT ec2 describe-security-groups --filters "Name=vpc-id,Values=$vpc" --query 'SecurityGroups[?GroupName!=`default`].GroupId' --output text 2>/dev/null || echo "")
        for sg in $VPC_SGS; do
            aws --endpoint-url=$ENDPOINT ec2 delete-security-group --group-id "$sg" 2>/dev/null || true
        done
        # Delete the VPC
        aws --endpoint-url=$ENDPOINT ec2 delete-vpc --vpc-id "$vpc" 2>/dev/null || true
    done
else
    echo "  No VPCs to delete"
fi

echo -e "\n✅ TEST Environment cleanup complete!"

# Show remaining resources
echo -e "\n=== Remaining Resources ==="
echo "S3 Buckets: $(aws --endpoint-url=$ENDPOINT s3api list-buckets --query 'length(Buckets)' --output text 2>/dev/null || echo "0")"
echo "EBS Volumes: $(aws --endpoint-url=$ENDPOINT ec2 describe-volumes --query 'length(Volumes)' --output text 2>/dev/null || echo "0")"
echo "Security Groups: $(aws --endpoint-url=$ENDPOINT ec2 describe-security-groups --query 'length(SecurityGroups)' --output text 2>/dev/null || echo "0")"
echo "VPCs: $(aws --endpoint-url=$ENDPOINT ec2 describe-vpcs --query 'length(Vpcs)' --output text 2>/dev/null || echo "0")"
