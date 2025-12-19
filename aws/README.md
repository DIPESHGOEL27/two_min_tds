# AWS Deployment Files - Summary

This directory contains all the configuration files needed to deploy the TDS Challan Processor to AWS.

## Files Overview

### Infrastructure as Code

1. **cloudformation-ecs.yaml**

   - Complete CloudFormation template for ECS Fargate deployment
   - Includes: ECS Cluster, ALB, EFS, Security Groups, IAM Roles
   - Production-ready with auto-scaling and health checks

2. **task-definition-ecs.json**
   - ECS task definition for manual deployments
   - Defines container configurations
   - Requires customization with your AWS account details

### Architecture

```
Internet
   ↓
Application Load Balancer (ALB)
   ↓
ECS Fargate Cluster
   ├── Streamlit Container (Port 8501)
   └── FastAPI Container (Port 8000)
   ↓
Amazon EFS (Persistent Storage)
   ↓
CloudWatch (Logs & Monitoring)
```

## Deployment Options

### Option 1: CloudFormation (Recommended)

**Pros:**

- Infrastructure as Code
- Repeatable deployments
- Easy rollback
- Version controlled

**Use When:**

- Production deployments
- Team collaboration
- Infrastructure versioning needed

**Deploy:**

```bash
aws cloudformation create-stack \
    --stack-name tds-challan-processor \
    --template-body file://cloudformation-ecs.yaml \
    --parameters ... \
    --capabilities CAPABILITY_IAM
```

### Option 2: AWS Console

**Pros:**

- Visual interface
- Beginner-friendly
- No CLI required

**Use When:**

- Learning AWS
- Quick testing
- Prefer GUI

**Steps:**

1. Upload template to CloudFormation console
2. Fill in parameters
3. Create stack

### Option 3: Terraform (Not Included)

If you prefer Terraform, convert the CloudFormation template or create equivalent .tf files.

## Cost Breakdown

### ECS Fargate Deployment (~$70/month)

| Component                 | Usage   | Cost |
| ------------------------- | ------- | ---- |
| Fargate (1 vCPU, 2GB)     | 730 hrs | $35  |
| Application Load Balancer | 730 hrs | $20  |
| EFS Storage (10 GB)       | 10 GB   | $3   |
| Data Transfer (100 GB)    | 100 GB  | $9   |
| CloudWatch Logs (5 GB)    | 5 GB    | $3   |

### Cost Optimization

1. **Use Fargate Spot** - Save 70% for dev/staging
2. **Scale to zero** during off-hours
3. **Use EFS IA** for older files (92% savings)
4. **Optimize logs retention** - Keep 7-30 days max

## Security Considerations

### Network Security

- ALB in public subnets
- ECS tasks in private subnets (can use public for simplicity)
- Security groups restrict traffic
- NACLs for additional layer

### Data Security

- EFS encryption at rest (enabled)
- EFS encryption in transit (enabled)
- Secrets stored in AWS Secrets Manager (optional)
- IAM roles with least privilege

### Application Security

- No public SSH access
- Container images scanned for vulnerabilities
- HTTPS/SSL recommended for production
- CloudWatch logs for audit trail

## Customization Guide

### Before Deployment

Replace these placeholders in templates:

1. **In task-definition-ecs.json:**

   - `YOUR_ACCOUNT_ID` → Your AWS account number
   - `YOUR_REGION` → Your AWS region (e.g., us-east-1)
   - `fs-XXXXXXXX` → Your EFS file system ID
   - `fsap-XXXXXXXX` → Your EFS access point ID

2. **In cloudformation-ecs.yaml:**
   - Set appropriate VPC and subnet IDs
   - Configure certificate ARN for HTTPS
   - Adjust CPU/memory if needed

### Common Modifications

**Increase Resources:**

```yaml
# In cloudformation-ecs.yaml
Cpu: "2048" # 2 vCPU
Memory: "4096" # 4 GB RAM
```

**Add Environment Variables:**

```yaml
Environment:
  - Name: YOUR_VAR
    Value: YOUR_VALUE
```

**Configure Auto-scaling:**

```yaml
# Already configured for:
# - CPU target: 70%
# - Memory target: 80%
# - Min: 1, Max: 10 tasks
```

## Monitoring Setup

### CloudWatch Alarms (Create Manually)

```bash
# High CPU alert
aws cloudwatch put-metric-alarm \
    --alarm-name tds-cpu-high \
    --metric-name CPUUtilization \
    --namespace AWS/ECS \
    --threshold 80

# High memory alert
aws cloudwatch put-metric-alarm \
    --alarm-name tds-memory-high \
    --metric-name MemoryUtilization \
    --namespace AWS/ECS \
    --threshold 85
```

### Logging

Logs are automatically sent to CloudWatch Logs group:
`/ecs/tds-challan-processor`

**View logs:**

```bash
aws logs tail /ecs/tds-challan-processor --follow
```

## Backup Strategy

### EFS Backups

AWS Backup automatically configured in template:

- Daily backups
- 30-day retention
- Encrypted backups

### Database (if added)

If you add RDS/DynamoDB:

- Enable automated backups
- Multi-AZ for production
- Point-in-time recovery

## High Availability

### Current Setup

- Multi-AZ EFS
- ALB across multiple AZs
- Auto-scaling enabled
- Health checks configured

### For Enhanced HA

1. Deploy across 3+ AZs
2. Use RDS Multi-AZ for database
3. Enable CloudFront CDN
4. Set up Route 53 health checks
5. Configure auto-recovery

## Disaster Recovery

### RTO & RPO

- **RTO (Recovery Time Objective):** ~15 minutes
- **RPO (Recovery Point Objective):** Last EFS backup (24 hrs)

### Recovery Procedures

**Complete Stack Failure:**

```bash
# Recreate from CloudFormation
aws cloudformation create-stack \
    --stack-name tds-challan-processor-recovery \
    --template-body file://cloudformation-ecs.yaml

# Restore EFS from backup if needed
aws backup start-restore-job \
    --recovery-point-arn <ARN>
```

**Data Loss:**

```bash
# Restore from EFS backup
aws efs restore-file-system \
    --source-recovery-point-arn <ARN>
```

## Testing

### Before Production

1. **Load Testing**

   ```bash
   # Use Apache Bench or similar
   ab -n 1000 -c 10 http://your-alb-url/
   ```

2. **Security Testing**

   ```bash
   # Scan with AWS Inspector
   aws inspector2 enable
   ```

3. **Cost Analysis**
   ```bash
   # Review with Cost Explorer
   # Set up billing alerts
   ```

### After Deployment

- Verify health checks passing
- Test file uploads/downloads
- Check logs for errors
- Monitor metrics for anomalies

## Troubleshooting

### Task Won't Start

1. Check CloudWatch logs
2. Verify IAM permissions
3. Confirm ECR image exists
4. Check task definition CPU/memory

### Can't Access Application

1. Check target group health
2. Verify security group rules
3. Confirm ALB listener rules
4. Check container port mapping

### EFS Mount Fails

1. Verify mount targets in same VPC
2. Check security group allows NFS (2049)
3. Confirm EFS access point exists
4. Review IAM task role permissions

## Additional Resources

- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [ECS CloudFormation Reference](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/AWS_ECS.html)
- [Fargate Pricing](https://aws.amazon.com/fargate/pricing/)

## Support

For deployment issues:

1. Check CloudWatch logs first
2. Review [Troubleshooting](#troubleshooting) section
3. Check AWS Service Health Dashboard
4. Contact development team

## Updates

When updating the application:

1. Build new Docker images
2. Push to ECR with new tags
3. Update task definition
4. Deploy via CloudFormation update or ECS service update

```bash
# Update service with new task definition
aws ecs update-service \
    --cluster tds-challan-cluster \
    --service tds-challan-service \
    --force-new-deployment
```
