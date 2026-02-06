#!/bin/bash
# Service Comparison Dashboard - Lambda Deployment Script
# For AWS CloudShell deployment
# Region: ap-south-1

set -e

# Configuration
AWS_REGION="${AWS_REGION:-ap-south-1}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="service-comparison-dashboard"
LAMBDA_FUNCTION_NAME="service-comparison-dashboard"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "=== Service Comparison Dashboard Lambda Deployment ==="
echo "AWS Account: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"
echo "Lambda Function: $LAMBDA_FUNCTION_NAME"
echo "Image Tag: $IMAGE_TAG"
echo ""

# Verify AWS login
echo "Checking AWS credentials..."
if ! aws sts get-caller-identity --region "$AWS_REGION" &>/dev/null; then
    echo "Error: AWS credentials not configured."
    exit 1
fi
echo "AWS credentials OK"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Verify prerequisites
echo "Checking prerequisites..."
for cmd in aws docker; do
    if ! command_exists $cmd; then
        echo "Error: $cmd is not installed"
        exit 1
    fi
done
echo "Prerequisites OK"
echo ""

# Phase 1: Create AWS Resources
create_aws_resources() {
    echo "=== Phase 1: Creating AWS Resources ==="

    # Create ECR Repository
    echo "Creating ECR repository..."
    aws ecr describe-repositories --repository-names $ECR_REPO --region $AWS_REGION 2>/dev/null || \
    aws ecr create-repository \
        --repository-name $ECR_REPO \
        --region $AWS_REGION \
        --image-scanning-configuration scanOnPush=true

    # Create Lambda execution role if not exists
    echo "Checking Lambda execution role..."
    ROLE_NAME="service-comparison-dashboard-lambda-role"
    if ! aws iam get-role --role-name $ROLE_NAME 2>/dev/null; then
        echo "Creating Lambda execution role..."
        aws iam create-role \
            --role-name $ROLE_NAME \
            --assume-role-policy-document '{
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }'

        # Attach basic execution policy
        aws iam attach-role-policy \
            --role-name $ROLE_NAME \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

        # Attach VPC access policy (for RDS access)
        aws iam attach-role-policy \
            --role-name $ROLE_NAME \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole

        echo "Waiting for role to propagate..."
        sleep 10
    fi

    echo "AWS resources created"
    echo ""
}

# Phase 2: Build and Push Docker Image
build_and_push() {
    echo "=== Phase 2: Building and Pushing Docker Image ==="

    # Login to ECR
    echo "Logging in to ECR..."
    aws ecr get-login-password --region $AWS_REGION | \
        docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

    # Build image (linux/amd64 for Lambda)
    echo "Building Docker image..."
    docker build --platform linux/amd64 -t $ECR_REPO:$IMAGE_TAG .

    # Tag image
    docker tag $ECR_REPO:$IMAGE_TAG $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG

    # Push image
    echo "Pushing Docker image..."
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG

    echo "Docker image pushed"
    echo ""
}

# Phase 3: Deploy Lambda Function
deploy_lambda() {
    echo "=== Phase 3: Deploying Lambda Function ==="

    IMAGE_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG"
    ROLE_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:role/service-comparison-dashboard-lambda-role"

    # Check if function exists
    if aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION 2>/dev/null; then
        echo "Updating existing Lambda function..."
        aws lambda update-function-code \
            --function-name $LAMBDA_FUNCTION_NAME \
            --image-uri $IMAGE_URI \
            --region $AWS_REGION

        # Wait for update to complete
        echo "Waiting for function update..."
        aws lambda wait function-updated \
            --function-name $LAMBDA_FUNCTION_NAME \
            --region $AWS_REGION
    else
        echo "Creating new Lambda function..."
        aws lambda create-function \
            --function-name $LAMBDA_FUNCTION_NAME \
            --package-type Image \
            --code ImageUri=$IMAGE_URI \
            --role $ROLE_ARN \
            --timeout 300 \
            --memory-size 1024 \
            --region $AWS_REGION \
            --environment "Variables={DB_HOST=topmate-db-prod-replica.cloiauy88d9t.ap-south-1.rds.amazonaws.com,DB_PORT=5432,DB_NAME=topmate_db_prod,DB_USER=postgres,DB_MODE=direct}"

        # Wait for function to be active
        echo "Waiting for function to be active..."
        aws lambda wait function-active \
            --function-name $LAMBDA_FUNCTION_NAME \
            --region $AWS_REGION
    fi

    echo "Lambda function deployed"
    echo ""
}

# Phase 4: Create Function URL
create_function_url() {
    echo "=== Phase 4: Creating Function URL ==="

    # Check if function URL exists
    if aws lambda get-function-url-config --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION 2>/dev/null; then
        echo "Function URL already exists"
    else
        echo "Creating function URL..."
        aws lambda create-function-url-config \
            --function-name $LAMBDA_FUNCTION_NAME \
            --auth-type NONE \
            --invoke-mode RESPONSE_STREAM \
            --region $AWS_REGION

        # Add permission for public access
        aws lambda add-permission \
            --function-name $LAMBDA_FUNCTION_NAME \
            --statement-id FunctionURLAllowPublicAccess \
            --action lambda:InvokeFunctionUrl \
            --principal "*" \
            --function-url-auth-type NONE \
            --region $AWS_REGION 2>/dev/null || true
    fi

    # Get and display URL
    FUNCTION_URL=$(aws lambda get-function-url-config \
        --function-name $LAMBDA_FUNCTION_NAME \
        --region $AWS_REGION \
        --query 'FunctionUrl' --output text)

    echo ""
    echo "=== Deployment Complete ==="
    echo "Function URL: $FUNCTION_URL"
    echo ""
}

# Phase 5: Verify deployment
verify() {
    echo "=== Phase 5: Verification ==="

    echo "Lambda Function Details:"
    aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION \
        --query '{FunctionName: Configuration.FunctionName, State: Configuration.State, MemorySize: Configuration.MemorySize, Timeout: Configuration.Timeout}'

    echo ""
    echo "Function URL:"
    aws lambda get-function-url-config --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION \
        --query 'FunctionUrl' --output text 2>/dev/null || echo "No function URL configured"

    echo ""
}

# Main execution
case "${1:-all}" in
    aws)
        create_aws_resources
        ;;
    build)
        build_and_push
        ;;
    deploy)
        deploy_lambda
        ;;
    url)
        create_function_url
        ;;
    verify)
        verify
        ;;
    all)
        create_aws_resources
        build_and_push
        deploy_lambda
        create_function_url
        verify
        ;;
    *)
        echo "Usage: $0 {aws|build|deploy|url|verify|all}"
        echo ""
        echo "  aws     - Create AWS resources (ECR, IAM role)"
        echo "  build   - Build and push Docker image"
        echo "  deploy  - Deploy Lambda function"
        echo "  url     - Create function URL"
        echo "  verify  - Verify deployment"
        echo "  all     - Run all phases"
        exit 1
        ;;
esac
