#!/usr/bin/env bash
# AWS Deployment Script for TDS Challan Processor
# Usage: ./deploy-to-aws.sh [production|staging]

set -e

ENVIRONMENT=${1:-production}
AWS_REGION=${AWS_REGION:-us-east-1}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PROJECT_NAME="tds-challan-processor"

echo "=================================================="
echo "TDS Challan Processor - AWS Deployment"
echo "=================================================="
echo "Environment: $ENVIRONMENT"
echo "AWS Region: $AWS_REGION"
echo "AWS Account: $AWS_ACCOUNT_ID"
echo "=================================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found. Please install AWS CLI."
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker not found. Please install Docker."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured. Run 'aws configure'."
        exit 1
    fi
    
    print_info "Prerequisites check passed!"
}

# Create ECR repositories
create_ecr_repos() {
    print_info "Creating ECR repositories..."
    
    for repo in "tds-streamlit" "tds-api"; do
        if aws ecr describe-repositories --repository-names $repo --region $AWS_REGION 2>&1 | grep -q RepositoryNotFoundException; then
            print_info "Creating repository: $repo"
            aws ecr create-repository \
                --repository-name $repo \
                --region $AWS_REGION \
                --image-scanning-configuration scanOnPush=true \
                --encryption-configuration encryptionType=AES256
        else
            print_info "Repository $repo already exists"
        fi
    done
}

# Build and push Docker images
build_and_push_images() {
    print_info "Building and pushing Docker images..."
    
    # Login to ECR
    print_info "Logging in to ECR..."
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
    
    # Build Streamlit image
    print_info "Building Streamlit image..."
    docker build -t tds-streamlit:latest -f Dockerfile .
    docker tag tds-streamlit:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-streamlit:latest
    docker tag tds-streamlit:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-streamlit:$ENVIRONMENT
    
    print_info "Pushing Streamlit image..."
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-streamlit:latest
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-streamlit:$ENVIRONMENT
    
    # Build API image
    print_info "Building API image..."
    docker build -t tds-api:latest -f Dockerfile.api .
    docker tag tds-api:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-api:latest
    docker tag tds-api:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-api:$ENVIRONMENT
    
    print_info "Pushing API image..."
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-api:latest
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-api:$ENVIRONMENT
    
    print_info "Docker images pushed successfully!"
}

# Deploy using CloudFormation
deploy_cloudformation() {
    print_info "Deploying infrastructure using CloudFormation..."
    
    STACK_NAME="$PROJECT_NAME-$ENVIRONMENT"
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION &> /dev/null; then
        ACTION="update-stack"
        print_info "Updating existing stack: $STACK_NAME"
    else
        ACTION="create-stack"
        print_info "Creating new stack: $STACK_NAME"
    fi
    
    # Get VPC ID (use default VPC or prompt user)
    DEFAULT_VPC=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text --region $AWS_REGION)
    VPC_ID=${VPC_ID:-$DEFAULT_VPC}
    
    # Get subnet IDs
    SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query "Subnets[*].SubnetId" --output text --region $AWS_REGION | tr '\t' ',')
    
    print_info "Using VPC: $VPC_ID"
    print_info "Using Subnets: $SUBNET_IDS"
    
    # Deploy stack
    aws cloudformation $ACTION \
        --stack-name $STACK_NAME \
        --template-body file://aws/cloudformation-ecs.yaml \
        --parameters \
            ParameterKey=VpcId,ParameterValue=$VPC_ID \
            ParameterKey=SubnetIds,ParameterValue=\"$SUBNET_IDS\" \
            ParameterKey=StreamlitImageUri,ParameterValue=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-streamlit:$ENVIRONMENT \
            ParameterKey=ApiImageUri,ParameterValue=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-api:$ENVIRONMENT \
        --capabilities CAPABILITY_IAM \
        --region $AWS_REGION
    
    print_info "Waiting for stack operation to complete..."
    aws cloudformation wait stack-${ACTION//-stack/}-complete --stack-name $STACK_NAME --region $AWS_REGION
    
    # Get outputs
    ALB_URL=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerURL'].OutputValue" --output text --region $AWS_REGION)
    
    print_info "Deployment completed successfully!"
    echo ""
    echo "=================================================="
    echo "Application URL: $ALB_URL"
    echo "=================================================="
}

# Deploy using App Runner (simpler alternative)
deploy_app_runner() {
    print_info "Deploying using AWS App Runner..."
    
    SERVICE_NAME="$PROJECT_NAME-$ENVIRONMENT"
    
    # Create App Runner service
    aws apprunner create-service \
        --service-name $SERVICE_NAME \
        --source-configuration '{
            "ImageRepository": {
                "ImageIdentifier": "'$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/tds-streamlit:$ENVIRONMENT'",
                "ImageRepositoryType": "ECR",
                "ImageConfiguration": {
                    "Port": "8501",
                    "RuntimeEnvironmentVariables": {
                        "TDS_APP_UPLOADS_DIR": "/app/uploads",
                        "TDS_APP_OUTPUT_DIR": "/app/output",
                        "TDS_APP_LOGS_DIR": "/app/logs"
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
    
    print_info "App Runner service created. Waiting for it to be ready..."
    
    # Wait for service to be running
    aws apprunner wait service-running --service-arn $(aws apprunner list-services --query "ServiceSummaryList[?ServiceName=='$SERVICE_NAME'].ServiceArn" --output text --region $AWS_REGION) --region $AWS_REGION
    
    SERVICE_URL=$(aws apprunner describe-service --service-arn $(aws apprunner list-services --query "ServiceSummaryList[?ServiceName=='$SERVICE_NAME'].ServiceArn" --output text --region $AWS_REGION) --query "Service.ServiceUrl" --output text --region $AWS_REGION)
    
    print_info "Deployment completed successfully!"
    echo ""
    echo "=================================================="
    echo "Application URL: https://$SERVICE_URL"
    echo "=================================================="
}

# Main menu
show_menu() {
    echo ""
    echo "Select deployment option:"
    echo "1) ECS Fargate with Load Balancer (Recommended for production)"
    echo "2) AWS App Runner (Simple, fully managed)"
    echo "3) Only build and push Docker images"
    echo "4) Exit"
    echo ""
    read -p "Enter choice [1-4]: " choice
    
    case $choice in
        1)
            check_prerequisites
            create_ecr_repos
            build_and_push_images
            deploy_cloudformation
            ;;
        2)
            check_prerequisites
            create_ecr_repos
            build_and_push_images
            deploy_app_runner
            ;;
        3)
            check_prerequisites
            create_ecr_repos
            build_and_push_images
            ;;
        4)
            print_info "Exiting..."
            exit 0
            ;;
        *)
            print_error "Invalid choice. Please try again."
            show_menu
            ;;
    esac
}

# Run main menu
show_menu
