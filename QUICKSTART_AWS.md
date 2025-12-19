# Quick Start - AWS Deployment

This is a quick reference guide for deploying the TDS Challan Processor to AWS.

## Prerequisites Checklist

- [ ] AWS Account with admin access
- [ ] AWS CLI installed and configured (`aws configure`)
- [ ] Docker installed and running
- [ ] Git repository cloned

## Option 1: Automated Deployment (Recommended)

### Windows

```powershell
# Open PowerShell in project directory
cd C:\Users\Dipesh_Goel\two_min_tds

# Run deployment script
.\deploy-to-aws.ps1 -Environment production -Region us-east-1

# Follow the menu prompts
# Select option 1 for ECS Fargate deployment
```

### Linux/Mac

```bash
# Open terminal in project directory
cd ~/two_min_tds

# Make script executable
chmod +x deploy-to-aws.sh

# Run deployment
./deploy-to-aws.sh production

# Follow the menu prompts
# Select option 1 for ECS Fargate deployment
```

The script will automatically:

1. Create ECR repositories
2. Build and push Docker images
3. Deploy infrastructure via CloudFormation
4. Output your application URL

⏱️ **Total time:** ~15-20 minutes

## Option 2: Manual Deployment

### Step 1: Configure AWS

```bash
# Set your AWS region
export AWS_REGION=us-east-1

# Verify AWS credentials
aws sts get-caller-identity
```

### Step 2: Create ECR Repositories

```bash
# Get your AWS account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create repositories
aws ecr create-repository --repository-name tds-streamlit --region $AWS_REGION
aws ecr create-repository --repository-name tds-api --region $AWS_REGION
```

### Step 3: Build and Push Images

```bash
# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build Streamlit
docker build -t tds-streamlit:latest -f Dockerfile .
docker tag tds-streamlit:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-streamlit:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-streamlit:latest

# Build API
docker build -t tds-api:latest -f Dockerfile.api .
docker tag tds-api:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-api:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-api:latest
```

### Step 4: Deploy Infrastructure

```bash
# Get VPC and Subnets (using default VPC)
export VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" \
    --query "Vpcs[0].VpcId" --output text --region $AWS_REGION)

export SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" \
    --query "Subnets[*].SubnetId" --output text --region $AWS_REGION | tr '\t' ',')

# Deploy CloudFormation stack
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

# Wait for completion (takes ~10-15 minutes)
aws cloudformation wait stack-create-complete \
    --stack-name tds-challan-processor-prod \
    --region $AWS_REGION
```

### Step 5: Get Application URL

```bash
aws cloudformation describe-stacks \
    --stack-name tds-challan-processor-prod \
    --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerURL'].OutputValue" \
    --output text \
    --region $AWS_REGION
```

Visit the URL in your browser! 🎉

## GitHub Actions Setup

### Required Secrets

Add these secrets to your GitHub repository:
(`Settings > Secrets and variables > Actions > New repository secret`)

| Secret Name             | Value               |
| ----------------------- | ------------------- |
| `AWS_ACCESS_KEY_ID`     | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key |

### Automatic Deployments

Once configured, GitHub Actions will automatically:

- **On push to `main`:** Deploy to staging
- **On push to `production`:** Deploy to production
- **On pull request:** Run tests only

### Manual Deployment

1. Go to GitHub Actions tab
2. Select "Deploy to AWS ECS" workflow
3. Click "Run workflow"
4. Select environment (staging/production)
5. Click "Run workflow"

## Common Commands

### View Logs

```bash
# Tail logs
aws logs tail /ecs/tds-challan-processor --follow --region $AWS_REGION

# Specific container logs
aws logs tail /ecs/tds-challan-processor --follow \
    --filter-pattern "streamlit" --region $AWS_REGION
```

### Update Application

```bash
# Rebuild and push images
docker build -t tds-streamlit:latest -f Dockerfile .
docker tag tds-streamlit:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-streamlit:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-streamlit:latest

# Force new deployment
aws ecs update-service \
    --cluster tds-challan-cluster \
    --service tds-challan-service \
    --force-new-deployment \
    --region $AWS_REGION
```

### Scale Application

```bash
# Scale to 3 instances
aws ecs update-service \
    --cluster tds-challan-cluster \
    --service tds-challan-service \
    --desired-count 3 \
    --region $AWS_REGION
```

### Check Status

```bash
# Service status
aws ecs describe-services \
    --cluster tds-challan-cluster \
    --services tds-challan-service \
    --region $AWS_REGION

# Task health
aws elbv2 describe-target-health \
    --target-group-arn $(aws elbv2 describe-target-groups \
        --names tds-streamlit-tg \
        --query 'TargetGroups[0].TargetGroupArn' \
        --output text --region $AWS_REGION) \
    --region $AWS_REGION
```

## Troubleshooting

### Container won't start

```bash
# Check logs
aws logs tail /ecs/tds-challan-processor --follow --region $AWS_REGION

# Check task status
aws ecs describe-tasks \
    --cluster tds-challan-cluster \
    --tasks $(aws ecs list-tasks --cluster tds-challan-cluster \
        --service-name tds-challan-service \
        --query 'taskArns[0]' --output text --region $AWS_REGION) \
    --region $AWS_REGION
```

### Can't access application

1. Check ALB target health (see "Check Status" above)
2. Verify security groups allow inbound traffic on port 80
3. Check container logs for errors

### Out of memory/CPU

```bash
# Update task definition with more resources
# Edit aws/task-definition-ecs.json and update:
# "cpu": "2048",     # 2 vCPU
# "memory": "4096",  # 4 GB

# Then update the service
aws ecs update-service \
    --cluster tds-challan-cluster \
    --service tds-challan-service \
    --force-new-deployment \
    --region $AWS_REGION
```

## Cost Optimization

### Development/Testing

Use Fargate Spot for 70% savings:

```bash
# In CloudFormation template, update:
# CapacityProviders:
#   - FARGATE_SPOT
```

### Auto-scaling

Already configured! Service will automatically scale based on:

- CPU > 70%
- Memory > 80%
- Request rate

### Stop During Off-Hours

```bash
# Scale to 0 (stops all tasks)
aws ecs update-service \
    --cluster tds-challan-cluster \
    --service tds-challan-service \
    --desired-count 0 \
    --region $AWS_REGION

# Scale back up
aws ecs update-service \
    --cluster tds-challan-cluster \
    --service tds-challan-service \
    --desired-count 1 \
    --region $AWS_REGION
```

## Cleanup

To delete all resources and stop charges:

```bash
# Delete CloudFormation stack (removes everything)
aws cloudformation delete-stack \
    --stack-name tds-challan-processor-prod \
    --region $AWS_REGION

# Wait for deletion
aws cloudformation wait stack-delete-complete \
    --stack-name tds-challan-processor-prod \
    --region $AWS_REGION

# Delete ECR images and repositories
aws ecr batch-delete-image \
    --repository-name tds-streamlit \
    --image-ids imageTag=latest \
    --region $AWS_REGION

aws ecr delete-repository \
    --repository-name tds-streamlit \
    --force \
    --region $AWS_REGION

aws ecr batch-delete-image \
    --repository-name tds-api \
    --image-ids imageTag=latest \
    --region $AWS_REGION

aws ecr delete-repository \
    --repository-name tds-api \
    --force \
    --region $AWS_REGION
```

## Next Steps

1. ✅ Application is deployed
2. Set up custom domain (Route 53)
3. Configure SSL certificate (ACM)
4. Set up CloudWatch alarms
5. Configure backup schedules
6. Review security groups

For detailed documentation, see [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md)

## Support

- Detailed Guide: [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md)
- AWS Support: https://console.aws.amazon.com/support/
- GitHub Issues: https://github.com/DIPESHGOEL27/two_min_tds/issues
