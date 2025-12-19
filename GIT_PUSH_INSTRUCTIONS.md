# Git Commit & Push Instructions

This guide helps you commit all the AWS deployment files and push them to your GitHub repository.

## What's Been Added

### AWS Deployment Files

- ✅ `aws/cloudformation-ecs.yaml` - Infrastructure as Code
- ✅ `aws/task-definition-ecs.json` - ECS task configuration
- ✅ `aws/README.md` - AWS deployment documentation
- ✅ `deploy-to-aws.sh` - Bash deployment script
- ✅ `deploy-to-aws.ps1` - PowerShell deployment script
- ✅ `.dockerignore` - Docker build optimization
- ✅ `AWS_DEPLOYMENT.md` - Comprehensive deployment guide
- ✅ `QUICKSTART_AWS.md` - Quick start guide
- ✅ `.github/workflows/deploy-aws.yml` - GitHub Actions CI/CD

### Updated Files

- ✅ `README.md` - Added AWS deployment section
- ✅ `config/settings.py` - Fixed Pydantic configuration
- ✅ `export/excel_writer.py` - Fixed merged cell bug

## Step-by-Step: Push to GitHub

### 1. Check Git Status

```bash
cd C:\Users\Dipesh_Goel\two_min_tds

git status
```

You should see all the new files listed as "Untracked" or "Modified".

### 2. Stage All Changes

```bash
# Add all new AWS deployment files
git add aws/
git add deploy-to-aws.sh
git add deploy-to-aws.ps1
git add .dockerignore
git add AWS_DEPLOYMENT.md
git add QUICKSTART_AWS.md
git add .github/workflows/deploy-aws.yml

# Add updated files
git add README.md
git add config/settings.py
git add export/excel_writer.py
```

Or add everything at once:

```bash
git add .
```

### 3. Commit Changes

```bash
git commit -m "Add AWS deployment configuration and CI/CD

Features:
- AWS ECS Fargate CloudFormation template
- Automated deployment scripts (bash & PowerShell)
- GitHub Actions workflow for CI/CD
- Comprehensive deployment documentation
- EFS persistent storage configuration
- Application Load Balancer setup
- Auto-scaling configuration
- CloudWatch monitoring

Fixes:
- Pydantic settings configuration for directory paths
- Excel export merged cell handling
- All 72 tests passing

Deployment:
- Run ./deploy-to-aws.sh or .\deploy-to-aws.ps1
- See QUICKSTART_AWS.md for quick start
- See AWS_DEPLOYMENT.md for full guide"
```

### 4. Push to GitHub

```bash
# Push to main branch
git push origin main
```

If you want to push to a specific branch:

```bash
# Create and push to a feature branch
git checkout -b feature/aws-deployment
git push origin feature/aws-deployment
```

### 5. Verify on GitHub

1. Go to https://github.com/DIPESHGOEL27/two_min_tds
2. Check that all files are present
3. Review the updated README.md

## Set Up GitHub Actions

### Required: Add AWS Secrets

For GitHub Actions to work, you need to add AWS credentials:

1. **Go to GitHub repository settings:**

   - Navigate to: `Settings > Secrets and variables > Actions`

2. **Click "New repository secret"**

3. **Add these secrets:**

   | Secret Name             | Where to Get It                                  |
   | ----------------------- | ------------------------------------------------ |
   | `AWS_ACCESS_KEY_ID`     | AWS Console > IAM > Users > Security Credentials |
   | `AWS_SECRET_ACCESS_KEY` | Same as above                                    |

4. **Create AWS IAM User (if needed):**

   ```bash
   # Create IAM user for GitHub Actions
   aws iam create-user --user-name github-actions-tds

   # Attach policies
   aws iam attach-user-policy \
       --user-name github-actions-tds \
       --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess

   aws iam attach-user-policy \
       --user-name github-actions-tds \
       --policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess

   aws iam attach-user-policy \
       --user-name github-actions-tds \
       --policy-arn arn:aws:iam::aws:policy/CloudFormationFullAccess

   # Create access keys
   aws iam create-access-key --user-name github-actions-tds
   ```

### GitHub Actions Workflows

Once secrets are configured:

#### Automatic Triggers

- **Push to `main`** → Runs tests + deploys to staging
- **Push to `production`** → Runs tests + deploys to production
- **Pull Request** → Runs tests only

#### Manual Deployment

1. Go to "Actions" tab on GitHub
2. Select "Deploy to AWS ECS"
3. Click "Run workflow"
4. Choose environment (staging/production)
5. Click "Run workflow"

## Deployment Checklist

Before deploying to AWS:

- [ ] All code pushed to GitHub
- [ ] GitHub Actions secrets configured
- [ ] AWS CLI installed and configured locally
- [ ] Docker installed locally
- [ ] Reviewed deployment costs (~$70/month)
- [ ] Read QUICKSTART_AWS.md
- [ ] VPC and subnets identified

## Deploy Now

### Option 1: Using GitHub Actions (Recommended)

1. Push code to GitHub (steps above)
2. Configure GitHub secrets
3. Trigger workflow manually or push to `main`
4. Monitor deployment in Actions tab

### Option 2: Local Deployment

**Windows:**

```powershell
.\deploy-to-aws.ps1 -Environment production -Region us-east-1
```

**Linux/Mac:**

```bash
chmod +x deploy-to-aws.sh
./deploy-to-aws.sh production
```

## After Deployment

### 1. Get Application URL

```bash
aws cloudformation describe-stacks \
    --stack-name tds-challan-processor-production \
    --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerURL'].OutputValue" \
    --output text \
    --region us-east-1
```

### 2. Test Application

Visit the URL and test:

- Upload a PDF
- Extract data
- Download Excel output

### 3. Monitor

```bash
# View logs
aws logs tail /ecs/tds-challan-processor --follow --region us-east-1

# Check service health
aws ecs describe-services \
    --cluster tds-challan-cluster \
    --services tds-challan-service \
    --region us-east-1
```

### 4. Set Up Monitoring (Optional)

- Create CloudWatch alarms
- Configure SNS notifications
- Set up billing alerts

## Troubleshooting

### Git Push Fails

```bash
# If remote has changes
git pull origin main --rebase
git push origin main

# If authentication fails
git remote -v
git remote set-url origin https://github.com/DIPESHGOEL27/two_min_tds.git
```

### GitHub Actions Fails

1. Check Actions tab for error logs
2. Verify AWS secrets are set correctly
3. Ensure IAM user has required permissions
4. Check CloudWatch logs for container errors

### Deployment Fails

1. Check CloudFormation events in AWS Console
2. Review CloudFormation error messages
3. Verify ECR images exist
4. Check IAM role permissions

## Quick Commands Reference

```bash
# Check what will be committed
git status
git diff

# Commit with detailed message
git commit -m "Your message"

# Push to GitHub
git push origin main

# View commit history
git log --oneline

# Undo last commit (keep changes)
git reset --soft HEAD~1

# View remote repository
git remote -v

# Pull latest changes
git pull origin main
```

## Next Steps

After successful deployment:

1. **Configure Custom Domain**

   - Register domain in Route 53
   - Create DNS records
   - Request SSL certificate from ACM

2. **Set Up Monitoring**

   - CloudWatch dashboards
   - Alarms for critical metrics
   - SNS notifications

3. **Implement Backups**

   - Verify EFS backup schedule
   - Test restore procedures
   - Document recovery process

4. **Security Hardening**

   - Enable WAF on ALB
   - Configure VPC Flow Logs
   - Set up AWS Config rules
   - Enable GuardDuty

5. **Cost Optimization**
   - Review Cost Explorer
   - Set up billing alerts
   - Consider Reserved Instances for steady state
   - Implement auto-scaling policies

## Documentation

All documentation is now in your repository:

- **Quick Start:** [QUICKSTART_AWS.md](QUICKSTART_AWS.md)
- **Full Guide:** [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md)
- **AWS Config:** [aws/README.md](aws/README.md)
- **Main README:** [README.md](README.md)

## Support

- **GitHub Issues:** https://github.com/DIPESHGOEL27/two_min_tds/issues
- **AWS Support:** https://console.aws.amazon.com/support/
- **Documentation:** See files above

---

**Ready to deploy?** Start with Step 1 above! 🚀
