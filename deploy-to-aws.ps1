# AWS Deployment Script for TDS Challan Processor (PowerShell)
# Usage: .\deploy-to-aws.ps1 -Environment production

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("production", "staging")]
    [string]$Environment = "production",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "TDS Challan Processor - AWS Deployment" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Environment: $Environment" -ForegroundColor Yellow
Write-Host "AWS Region: $Region" -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Cyan

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Check prerequisites
function Test-Prerequisites {
    Write-Info "Checking prerequisites..."
    
    # Check AWS CLI
    if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
        Write-Error "AWS CLI not found. Please install AWS CLI."
        exit 1
    }
    
    # Check Docker
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker not found. Please install Docker."
        exit 1
    }

    # Ensure Docker daemon is running (Docker Desktop on Windows)
    try {
        docker info | Out-Null
    }
    catch {
        Write-Error "Docker is installed but not running. Please start Docker Desktop and retry."
        exit 1
    }
    
    # Check AWS credentials
    try {
        $null = aws sts get-caller-identity
        Write-Info "Prerequisites check passed!"
    }
    catch {
        Write-Error "AWS credentials not configured. Run 'aws configure'."
        exit 1
    }
}

# Get AWS Account ID
function Get-AccountId {
    return (aws sts get-caller-identity --query Account --output text)
}

# Create ECR repositories
function New-ECRRepositories {
    param([string]$Region)
    
    Write-Info "Creating ECR repositories..."
    
    $repositories = @("tds-streamlit", "tds-api")
    
    foreach ($repo in $repositories) {
        try {
            $null = aws ecr describe-repositories --repository-names $repo --region $Region 2>&1
            Write-Info "Repository $repo already exists"
        }
        catch {
            Write-Info "Creating repository: $repo"
            aws ecr create-repository `
                --repository-name $repo `
                --region $Region `
                --image-scanning-configuration scanOnPush=true `
                --encryption-configuration encryptionType=AES256
        }
    }
}

# Build and push Docker images
function Publish-DockerImages {
    param(
        [string]$AccountId,
        [string]$Region,
        [string]$Environment
    )
    
    Write-Info "Building and pushing Docker images..."
    
    # Login to ECR
    Write-Info "Logging in to ECR..."
    $loginPassword = aws ecr get-login-password --region $Region
    $loginPassword | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com"
    
    # Build and push Streamlit image
    Write-Info "Building Streamlit image..."
    docker build -t tds-streamlit:latest -f Dockerfile .
    docker tag tds-streamlit:latest "$AccountId.dkr.ecr.$Region.amazonaws.com/tds-streamlit:latest"
    docker tag tds-streamlit:latest "$AccountId.dkr.ecr.$Region.amazonaws.com/tds-streamlit:$Environment"
    
    Write-Info "Pushing Streamlit image..."
    docker push "$AccountId.dkr.ecr.$Region.amazonaws.com/tds-streamlit:latest"
    docker push "$AccountId.dkr.ecr.$Region.amazonaws.com/tds-streamlit:$Environment"
    
    # Build and push API image
    Write-Info "Building API image..."
    docker build -t tds-api:latest -f Dockerfile.api .
    docker tag tds-api:latest "$AccountId.dkr.ecr.$Region.amazonaws.com/tds-api:latest"
    docker tag tds-api:latest "$AccountId.dkr.ecr.$Region.amazonaws.com/tds-api:$Environment"
    
    Write-Info "Pushing API image..."
    docker push "$AccountId.dkr.ecr.$Region.amazonaws.com/tds-api:latest"
    docker push "$AccountId.dkr.ecr.$Region.amazonaws.com/tds-api:$Environment"
    
    Write-Info "Docker images pushed successfully!"
}

# Deploy using CloudFormation
function Deploy-CloudFormation {
    param(
        [string]$AccountId,
        [string]$Region,
        [string]$Environment
    )
    
    Write-Info "Deploying infrastructure using CloudFormation..."
    
    $stackName = "tds-challan-processor-$Environment"
    
    # Check if stack exists
    $stackExists = aws cloudformation describe-stacks --stack-name $stackName --region $Region 2>&1
    if ($LASTEXITCODE -eq 0) {
        $action = "update-stack"
        $waitCommand = "stack-update-complete"
        Write-Info "Updating existing stack: $stackName"
    }
    else {
        $action = "create-stack"
        $waitCommand = "stack-create-complete"
        Write-Info "Creating new stack: $stackName"
    }
    
    # Get VPC and Subnet information
    $defaultVpc = aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text --region $Region
    $vpcId = if ($env:VPC_ID) { $env:VPC_ID } else { $defaultVpc }
    
    $subnets = aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpcId" --query "Subnets[*].SubnetId" --output text --region $Region
    # Convert space-separated subnets to comma-separated and ensure we have at least 2
    $subnetArray = $subnets -split '\s+'
    if ($subnetArray.Count -lt 2) {
        Write-Error "Need at least 2 subnets for ALB deployment. Found: $($subnetArray.Count)"
        exit 1
    }
    $subnetIds = $subnetArray -join ','
    
    Write-Info "Using VPC: $vpcId"
    Write-Info "Using Subnets: $subnetIds"
    
    # Create a temporary JSON parameters file to avoid PowerShell escaping issues
    $paramsFile = "cfn-params-temp.json"
    $params = @(
        @{ ParameterKey = "VpcId"; ParameterValue = $vpcId },
        @{ ParameterKey = "SubnetIds"; ParameterValue = $subnetIds },
        @{ ParameterKey = "StreamlitImageUri"; ParameterValue = "$AccountId.dkr.ecr.$Region.amazonaws.com/tds-streamlit:$Environment" },
        @{ ParameterKey = "ApiImageUri"; ParameterValue = "$AccountId.dkr.ecr.$Region.amazonaws.com/tds-api:$Environment" }
    )
    $params | ConvertTo-Json -Depth 3 | Set-Content -Path $paramsFile -Encoding UTF8
    
    # Deploy stack using JSON parameters file
    aws cloudformation $action `
        --stack-name $stackName `
        --template-body file://aws/cloudformation-ecs.yaml `
        --parameters file://$paramsFile `
        --capabilities CAPABILITY_IAM `
        --region $Region
    
    # Clean up temp file
    Remove-Item -Path $paramsFile -Force -ErrorAction SilentlyContinue
    
    Write-Info "Waiting for stack operation to complete..."
    aws cloudformation wait $waitCommand --stack-name $stackName --region $Region
    
    # Get outputs
    $albUrl = aws cloudformation describe-stacks --stack-name $stackName --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerURL'].OutputValue" --output text --region $Region
    
    Write-Info "Deployment completed successfully!"
    Write-Host ""
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host "Application URL: $albUrl" -ForegroundColor Green
    Write-Host "==================================================" -ForegroundColor Cyan
}

# Main menu
function Show-Menu {
    Write-Host ""
    Write-Host "Select deployment option:" -ForegroundColor Cyan
    Write-Host "1) ECS Fargate with Load Balancer (Recommended for production)"
    Write-Host "2) Only build and push Docker images"
    Write-Host "3) Exit"
    Write-Host ""
    
    $choice = Read-Host "Enter choice [1-3]"
    
    $accountId = Get-AccountId
    
    switch ($choice) {
        "1" {
            Test-Prerequisites
            New-ECRRepositories -Region $Region
            Publish-DockerImages -AccountId $accountId -Region $Region -Environment $Environment
            Deploy-CloudFormation -AccountId $accountId -Region $Region -Environment $Environment
        }
        "2" {
            Test-Prerequisites
            New-ECRRepositories -Region $Region
            Publish-DockerImages -AccountId $accountId -Region $Region -Environment $Environment
        }
        "3" {
            Write-Info "Exiting..."
            exit 0
        }
        default {
            Write-Error "Invalid choice. Please try again."
            Show-Menu
        }
    }
}

# Run
Show-Menu
