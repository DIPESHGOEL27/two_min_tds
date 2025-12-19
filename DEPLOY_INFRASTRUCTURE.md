# Deploy AWS Infrastructure

## Current Issue

The GitHub Actions workflow is failing because it's trying to update an ECS service that doesn't exist yet. **GitHub Actions only updates existing infrastructure - it doesn't create it.**

## Solution: Deploy CloudFormation Stack First

### Step 1: Configure AWS Credentials Locally

```powershell
# Configure AWS CLI with your credentials
aws configure

# You'll be prompted for:
# AWS Access Key ID: [Your AWS Access Key]
# AWS Secret Access Key: [Your AWS Secret Key]
# Default region name: us-east-1
# Default output format: json
```

### Step 2: Deploy the CloudFormation Stack

Run the PowerShell deployment script:

```powershell
cd C:\Users\Dipesh_Goel\two_min_tds
.\deploy-to-aws.ps1
```

Or manually deploy with AWS CLI:

```powershell
# Deploy the CloudFormation stack
aws cloudformation create-stack `
  --stack-name tds-challan-processor `
  --template-body file://aws/cloudformation-ecs.yaml `
  --parameters ParameterKey=EnvironmentName,ParameterValue=staging `
               ParameterKey=StreamlitImageUri,ParameterValue=977098995841.dkr.ecr.us-east-1.amazonaws.com/tds-streamlit:latest `
               ParameterKey=ApiImageUri,ParameterValue=977098995841.dkr.ecr.us-east-1.amazonaws.com/tds-api:latest `
  --capabilities CAPABILITY_IAM `
  --region us-east-1

# Wait for stack creation to complete (takes 5-10 minutes)
aws cloudformation wait stack-create-complete `
  --stack-name tds-challan-processor `
  --region us-east-1

# Get the Application URL
aws cloudformation describe-stacks `
  --stack-name tds-challan-processor `
  --region us-east-1 `
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerUrl`].OutputValue' `
  --output text
```

### Step 3: Verify Deployment

```powershell
# Check if stack is created successfully
aws cloudformation describe-stacks --stack-name tds-challan-processor --region us-east-1

# Check ECS cluster
aws ecs list-clusters --region us-east-1

# Check ECS services
aws ecs list-services --cluster tds-challan-processor --region us-east-1
```

### Step 4: Re-run GitHub Actions

Once the infrastructure is deployed:

1. Go to: https://github.com/DIPESHGOEL27/two_min_tds/actions
2. Select the failed workflow run
3. Click "Re-run failed jobs"

Or push a new commit to trigger the workflow:

```powershell
git commit --allow-empty -m "Trigger workflow after infrastructure deployment"
git push origin main
```

## What Gets Created

The CloudFormation stack creates:

- ✅ ECS Cluster: `tds-challan-processor`
- ✅ ECS Service: `tds-challan-processor-service`
- ✅ Task Definition: `tds-challan-processor`
- ✅ Application Load Balancer (ALB)
- ✅ EFS File System (for persistent storage)
- ✅ VPC, Subnets, Security Groups
- ✅ Auto-scaling policies
- ✅ CloudWatch log groups

## Workflow After Infrastructure Exists

Once infrastructure is deployed, the GitHub Actions workflow will:

1. ✅ Build Docker images
2. ✅ Push images to ECR
3. ✅ Update ECS task definition with new image tags
4. ✅ Deploy updated task definition to ECS service
5. ✅ Service automatically rolls out new containers

## Troubleshooting

### If AWS credentials are not configured:

```powershell
aws configure
```

### If CloudFormation stack fails:

```powershell
# Check stack events for errors
aws cloudformation describe-stack-events --stack-name tds-challan-processor --region us-east-1 --max-items 20

# Delete failed stack and retry
aws cloudformation delete-stack --stack-name tds-challan-processor --region us-east-1
```

### If you need to update the stack:

```powershell
aws cloudformation update-stack `
  --stack-name tds-challan-processor `
  --template-body file://aws/cloudformation-ecs.yaml `
  --parameters ParameterKey=EnvironmentName,ParameterValue=staging `
  --capabilities CAPABILITY_IAM `
  --region us-east-1
```
