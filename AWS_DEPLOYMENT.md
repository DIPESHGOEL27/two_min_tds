# AWS Deployment Guide - TDS Challan Processor

This guide provides step-by-step instructions for deploying the TDS Challan Processor application to AWS.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Architecture Overview](#architecture-overview)
- [Deployment Options](#deployment-options)
- [Quick Start](#quick-start)
- [Detailed Deployment Steps](#detailed-deployment-steps)
- [Configuration](#configuration)
- [Monitoring & Logging](#monitoring--logging)
- [Troubleshooting](#troubleshooting)
- [Cost Estimation](#cost-estimation)

## Prerequisites

### Required Tools

1. **AWS CLI** (version 2.x or higher)

   ```bash
   # Install AWS CLI
   # Windows: https://awscli.amazonaws.com/AWSCLIV2.msi
   # Linux/Mac: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

   # Verify installation
   aws --version
   ```

2. **Docker** (version 20.x or higher)

   ```bash
   # Verify installation
   docker --version
   ```

3. **AWS Account** with appropriate permissions:
   - EC2, ECS, ECR permissions
   - IAM role creation
   - CloudFormation stack creation
   - EFS (for persistent storage)
   - Application Load Balancer

### AWS Configuration

Configure your AWS credentials:

```bash
aws configure
```

Enter:

- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., `us-east-1`)
- Default output format: `json`

Verify configuration:

```bash
aws sts get-caller-identity
```

## Architecture Overview

### Production Architecture (ECS Fargate)

```
┌─────────────────────────────────────────────────────────────────┐
│                           AWS Cloud                              │
│                                                                  │
│  ┌────────────┐         ┌──────────────────────────────────┐   │
│  │  Internet  │────────▶│  Application Load Balancer       │   │
│  │  Gateway   │         │  (Port 80/443)                   │   │
│  └────────────┘         └──────────────┬───────────────────┘   │
│                                        │                         │
│                         ┌──────────────┴────────────────┐       │
│                         │                                │       │
│                    ┌────▼─────┐                   ┌─────▼────┐  │
│                    │ Target   │                   │ Target   │  │
│                    │ Group    │                   │ Group    │  │
│                    │ :8501    │                   │ :8000    │  │
│                    └────┬─────┘                   └─────┬────┘  │
│                         │                                │       │
│  ┌──────────────────────┴────────────────────────────────┴───┐  │
│  │              ECS Fargate Cluster                          │  │
│  │                                                            │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │         ECS Task (Fargate)                          │  │  │
│  │  │                                                      │  │  │
│  │  │  ┌──────────────┐        ┌───────────────┐         │  │  │
│  │  │  │  Streamlit   │        │   FastAPI     │         │  │  │
│  │  │  │  Container   │        │   Container   │         │  │  │
│  │  │  │  (Port 8501) │        │  (Port 8000)  │         │  │  │
│  │  │  └──────┬───────┘        └───────┬───────┘         │  │  │
│  │  │         │                        │                 │  │  │
│  │  │         └────────────┬───────────┘                 │  │  │
│  │  │                      │                             │  │  │
│  │  └──────────────────────┼─────────────────────────────┘  │  │
│  │                         │                                │  │
│  └─────────────────────────┼────────────────────────────────┘  │
│                            │                                   │
│                    ┌───────▼────────┐                          │
│                    │  Amazon EFS    │                          │
│                    │  (Persistent   │                          │
│                    │   Storage)     │                          │
│                    └────────────────┘                          │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │            CloudWatch Logs & Monitoring                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

1. **Application Load Balancer (ALB)**

   - Routes traffic to Streamlit (UI) and FastAPI (API)
   - SSL/TLS termination
   - Health checks

2. **ECS Fargate**

   - Serverless container orchestration
   - Auto-scaling based on CPU/Memory
   - Multi-AZ deployment

3. **Amazon EFS**

   - Persistent storage for uploads and outputs
   - Shared across containers
   - Automatic backups

4. **CloudWatch**
   - Centralized logging
   - Metrics and alarms
   - Application monitoring

## Deployment Options

### Option 1: ECS Fargate (Recommended for Production)

**Pros:**

- Highly scalable
- No server management
- Integrated load balancing
- Multi-AZ high availability
- Full control over networking

**Cons:**

- More complex setup
- Higher cost for low traffic
- Requires VPC configuration

**Best for:** Production workloads, high traffic, enterprise deployments

### Option 2: AWS App Runner

**Pros:**

- Simplest deployment
- Fully managed
- Auto-scaling included
- Built-in CI/CD

**Cons:**

- Less control over infrastructure
- Limited networking options
- No shared file storage (ephemeral)

**Best for:** Quick prototypes, low-traffic applications, simple deployments

### Option 3: Elastic Beanstalk

**Pros:**

- Managed platform
- Easy updates
- Built-in monitoring

**Cons:**

- Less flexibility than ECS
- Limited customization

**Best for:** Standard web applications

## Quick Start

### Automated Deployment (Recommended)

#### Windows (PowerShell)

```powershell
# Navigate to project directory
cd C:\Users\Dipesh_Goel\two_min_tds

# Run deployment script
.\deploy-to-aws.ps1 -Environment production -Region us-east-1
```

#### Linux/Mac (Bash)

```bash
# Navigate to project directory
cd ~/two_min_tds

# Make script executable
chmod +x deploy-to-aws.sh

# Run deployment script
./deploy-to-aws.sh production
```

The script will:

1. ✅ Check prerequisites (AWS CLI, Docker)
2. ✅ Create ECR repositories
3. ✅ Build Docker images
4. ✅ Push images to ECR
5. ✅ Deploy CloudFormation stack
6. ✅ Output the application URL

## Detailed Deployment Steps

### Step 1: Prepare Your Environment

```bash
# Clone repository (if not already done)
git clone https://github.com/DIPESHGOEL27/two_min_tds.git
cd two_min_tds

# Set AWS region
export AWS_REGION=us-east-1

# Get AWS Account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
```

### Step 2: Create ECR Repositories

```bash
# Create repository for Streamlit image
aws ecr create-repository \
    --repository-name tds-streamlit \
    --region $AWS_REGION \
    --image-scanning-configuration scanOnPush=true

# Create repository for API image
aws ecr create-repository \
    --repository-name tds-api \
    --region $AWS_REGION \
    --image-scanning-configuration scanOnPush=true
```

### Step 3: Build and Push Docker Images

```bash
# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build Streamlit image
docker build -t tds-streamlit:latest -f Dockerfile .
docker tag tds-streamlit:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-streamlit:latest

# Push Streamlit image
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-streamlit:latest

# Build API image
docker build -t tds-api:latest -f Dockerfile.api .
docker tag tds-api:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-api:latest

# Push API image
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-api:latest
```

### Step 4: Deploy Infrastructure

#### Option A: Using CloudFormation (Full Stack)

```bash
# Get VPC and Subnet IDs
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" \
    --query "Vpcs[0].VpcId" --output text --region $AWS_REGION)

SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" \
    --query "Subnets[*].SubnetId" --output text --region $AWS_REGION | tr '\t' ',')

# Deploy stack
aws cloudformation create-stack \
    --stack-name tds-challan-processor-prod \
    --template-body file://aws/cloudformation-ecs.yaml \
    --parameters \
        ParameterKey=VpcId,ParameterValue=$VPC_ID \
        ParameterKey=SubnetIds,ParameterValue="$SUBNET_IDS" \
        ParameterKey=StreamlitImageUri,ParameterValue=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-streamlit:latest \
        ParameterKey=ApiImageUri,ParameterValue=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-api:latest \
    --capabilities CAPABILITY_IAM \
    --region $AWS_REGION

# Wait for stack creation
aws cloudformation wait stack-create-complete \
    --stack-name tds-challan-processor-prod \
    --region $AWS_REGION

# Get application URL
aws cloudformation describe-stacks \
    --stack-name tds-challan-processor-prod \
    --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerURL'].OutputValue" \
    --output text \
    --region $AWS_REGION
```

#### Option B: Using AWS App Runner (Simpler)

```bash
# Create App Runner service
aws apprunner create-service \
    --service-name tds-challan-processor \
    --source-configuration '{
        "ImageRepository": {
            "ImageIdentifier": "'$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-streamlit:latest'",
            "ImageRepositoryType": "ECR",
            "ImageConfiguration": {
                "Port": "8501",
                "RuntimeEnvironmentVariables": {
                    "TDS_APP_UPLOADS_DIR": "/app/uploads",
                    "TDS_APP_OUTPUT_DIR": "/app/output"
                }
            }
        },
        "AutoDeploymentsEnabled": true
    }' \
    --instance-configuration '{
        "Cpu": "1024",
        "Memory": "2048"
    }' \
    --region $AWS_REGION
```

### Step 5: Configure Domain (Optional)

1. **Get ALB DNS name:**

   ```bash
   aws cloudformation describe-stacks \
       --stack-name tds-challan-processor-prod \
       --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerURL'].OutputValue" \
       --output text
   ```

2. **Create Route 53 record:**

   ```bash
   # Create CNAME record pointing to ALB
   aws route53 change-resource-record-sets \
       --hosted-zone-id YOUR_HOSTED_ZONE_ID \
       --change-batch '{
           "Changes": [{
               "Action": "CREATE",
               "ResourceRecordSet": {
                   "Name": "tds.yourdomain.com",
                   "Type": "CNAME",
                   "TTL": 300,
                   "ResourceRecords": [{"Value": "ALB_DNS_NAME"}]
               }
           }]
       }'
   ```

3. **Configure SSL Certificate:**
   ```bash
   # Request certificate
   aws acm request-certificate \
       --domain-name tds.yourdomain.com \
       --validation-method DNS \
       --region $AWS_REGION
   ```

## Configuration

### Environment Variables

Configure the application by setting environment variables:

| Variable                            | Default        | Description                    |
| ----------------------------------- | -------------- | ------------------------------ |
| `TDS_APP_UPLOADS_DIR`               | `/app/uploads` | Directory for uploaded PDFs    |
| `TDS_APP_OUTPUT_DIR`                | `/app/output`  | Directory for Excel exports    |
| `TDS_APP_LOGS_DIR`                  | `/app/logs`    | Directory for application logs |
| `TDS_EXTRACTION_MIN_ROW_CONFIDENCE` | `0.85`         | Minimum confidence threshold   |
| `TDS_APP_API_HOST`                  | `0.0.0.0`      | API host                       |
| `TDS_APP_API_PORT`                  | `8000`         | API port                       |

### Updating Configuration

Update the CloudFormation stack with new environment variables:

```bash
aws cloudformation update-stack \
    --stack-name tds-challan-processor-prod \
    --use-previous-template \
    --parameters \
        ParameterKey=VpcId,UsePreviousValue=true \
        ParameterKey=SubnetIds,UsePreviousValue=true \
        ParameterKey=StreamlitImageUri,UsePreviousValue=true \
        ParameterKey=ApiImageUri,UsePreviousValue=true \
    --capabilities CAPABILITY_IAM
```

## Monitoring & Logging

### CloudWatch Logs

View application logs:

```bash
# List log streams
aws logs describe-log-streams \
    --log-group-name /ecs/tds-challan-processor \
    --region $AWS_REGION

# Tail logs
aws logs tail /ecs/tds-challan-processor --follow --region $AWS_REGION
```

### CloudWatch Metrics

Key metrics to monitor:

- **CPU Utilization** - Target: < 70%
- **Memory Utilization** - Target: < 80%
- **Request Count** - Track usage patterns
- **Target Response Time** - Target: < 2s
- **Healthy Host Count** - Should be ≥ 1

### Setting Up Alarms

```bash
# CPU alarm
aws cloudwatch put-metric-alarm \
    --alarm-name tds-cpu-high \
    --alarm-description "Alert when CPU exceeds 80%" \
    --metric-name CPUUtilization \
    --namespace AWS/ECS \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2
```

## Troubleshooting

### Common Issues

#### 1. Container Fails to Start

**Check logs:**

```bash
aws logs tail /ecs/tds-challan-processor --follow
```

**Common causes:**

- Missing environment variables
- Image not found in ECR
- Insufficient memory/CPU

#### 2. Application Not Accessible

**Check target health:**

```bash
aws elbv2 describe-target-health \
    --target-group-arn TARGET_GROUP_ARN
```

**Common causes:**

- Security group misconfiguration
- Health check path incorrect
- Container not responding on port 8501

#### 3. EFS Mount Issues

**Check EFS mount targets:**

```bash
aws efs describe-mount-targets --file-system-id fs-XXXXXXXX
```

**Common causes:**

- Mount target not in same subnet as task
- Security group doesn't allow NFS traffic (port 2049)

### Debug Commands

```bash
# Check ECS service status
aws ecs describe-services \
    --cluster tds-challan-cluster \
    --services tds-challan-service

# View task details
aws ecs describe-tasks \
    --cluster tds-challan-cluster \
    --tasks TASK_ARN

# Check ALB target health
aws elbv2 describe-target-health \
    --target-group-arn TG_ARN
```

## Cost Estimation

### Monthly Cost Breakdown (Approx.)

**ECS Fargate Deployment:**

| Service                               | Usage   | Monthly Cost (USD) |
| ------------------------------------- | ------- | ------------------ |
| ECS Fargate (1 task, 1 vCPU, 2GB RAM) | 730 hrs | ~$35               |
| Application Load Balancer             | 730 hrs | ~$20               |
| EFS Storage (10 GB)                   | 10 GB   | ~$3                |
| Data Transfer (100 GB out)            | 100 GB  | ~$9                |
| CloudWatch Logs (5 GB)                | 5 GB    | ~$3                |
| **Total**                             |         | **~$70/month**     |

**App Runner Deployment:**

| Service                      | Usage   | Monthly Cost (USD) |
| ---------------------------- | ------- | ------------------ |
| App Runner (1 vCPU, 2GB RAM) | 730 hrs | ~$45               |
| Data Transfer                | 100 GB  | ~$9                |
| **Total**                    |         | **~$54/month**     |

**Cost Optimization Tips:**

1. Use **Fargate Spot** for non-critical workloads (70% savings)
2. Enable **EFS Infrequent Access** for older files (92% savings)
3. Use **S3 instead of EFS** for long-term storage
4. Set up **auto-scaling** to scale down during off-hours
5. Use **CloudWatch Logs Insights** instead of exporting all logs

## Scaling

### Manual Scaling

```bash
# Update desired task count
aws ecs update-service \
    --cluster tds-challan-cluster \
    --service tds-challan-service \
    --desired-count 3
```

### Auto Scaling

Auto-scaling is configured in the CloudFormation template based on:

- CPU utilization (target: 70%)
- Memory utilization (target: 80%)
- Request count per target

## Backup & Disaster Recovery

### EFS Backups

Automatic backups are enabled via AWS Backup.

**Manual backup:**

```bash
aws backup start-backup-job \
    --backup-vault-name Default \
    --resource-arn arn:aws:elasticfilesystem:REGION:ACCOUNT:file-system/fs-XXXXXXXX \
    --iam-role-arn arn:aws:iam::ACCOUNT:role/service-role/AWSBackupDefaultServiceRole
```

### Restore from Backup

```bash
aws backup start-restore-job \
    --recovery-point-arn RECOVERY_POINT_ARN \
    --metadata file-system-id=fs-XXXXXXXX
```

## Cleanup

To remove all AWS resources:

```bash
# Delete CloudFormation stack
aws cloudformation delete-stack \
    --stack-name tds-challan-processor-prod \
    --region $AWS_REGION

# Wait for deletion
aws cloudformation wait stack-delete-complete \
    --stack-name tds-challan-processor-prod \
    --region $AWS_REGION

# Delete ECR images
aws ecr batch-delete-image \
    --repository-name tds-streamlit \
    --image-ids imageTag=latest \
    --region $AWS_REGION

aws ecr batch-delete-image \
    --repository-name tds-api \
    --image-ids imageTag=latest \
    --region $AWS_REGION

# Delete ECR repositories
aws ecr delete-repository \
    --repository-name tds-streamlit \
    --force \
    --region $AWS_REGION

aws ecr delete-repository \
    --repository-name tds-api \
    --force \
    --region $AWS_REGION
```

## Support

For issues or questions:

- Check [Troubleshooting](#troubleshooting) section
- Review CloudWatch logs
- Contact development team

## Additional Resources

- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [AWS App Runner Documentation](https://docs.aws.amazon.com/apprunner/)
- [Docker Documentation](https://docs.docker.com/)
- [Streamlit Cloud Deployment](https://docs.streamlit.io/streamlit-community-cloud)
