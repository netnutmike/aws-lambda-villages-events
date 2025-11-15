#!/bin/bash

# Villages Events Sync - Deployment Script
# This script builds and deploys the Lambda function to AWS

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Villages Events Sync - Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    echo "Please install AWS CLI: https://aws.amazon.com/cli/"
    exit 1
fi

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    echo -e "${RED}Error: AWS SAM CLI is not installed${NC}"
    echo "Please install SAM CLI: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"
    exit 1
fi

# Parse command line arguments
GUIDED=false
ENVIRONMENT="dev"

while [[ $# -gt 0 ]]; do
    case $1 in
        --guided)
            GUIDED=true
            shift
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: ./deploy.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --guided          Run deployment in guided mode"
            echo "  --environment ENV Set environment (dev or prod), default: dev"
            echo "  --help            Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${YELLOW}Step 1: Installing Python dependencies${NC}"
echo "Installing dependencies to local directory..."
pip install -r requirements.txt -t .aws-sam/build/dependencies/ --upgrade
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

echo -e "${YELLOW}Step 2: Building SAM application${NC}"
echo "Running sam build..."
sam build
echo -e "${GREEN}✓ Build completed${NC}"
echo ""

echo -e "${YELLOW}Step 3: Validating SAM template${NC}"
echo "Running sam validate..."
sam validate --lint
echo -e "${GREEN}✓ Template validation passed${NC}"
echo ""

echo -e "${YELLOW}Step 4: Deploying to AWS${NC}"
if [ "$GUIDED" = true ]; then
    echo "Running deployment in guided mode..."
    sam deploy --guided
else
    echo "Deploying with environment: ${ENVIRONMENT}"
    sam deploy \
        --parameter-overrides "Environment=${ENVIRONMENT}" \
        --no-confirm-changeset \
        --no-fail-on-empty-changeset
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Deployment completed successfully${NC}"
    echo ""
    
    echo -e "${YELLOW}Step 5: Retrieving stack outputs${NC}"
    STACK_NAME="villages-events-sync"
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Deployment Summary${NC}"
    echo -e "${GREEN}========================================${NC}"
    
    # Get stack outputs
    aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --query 'Stacks[0].Outputs' \
        --output table
    
    echo ""
    echo -e "${GREEN}Deployment complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Test the Lambda function: ./local-test.sh"
    echo "  2. Invoke manually: aws lambda invoke --function-name villages-events-sync-${ENVIRONMENT} output.json"
    echo "  3. View logs: aws logs tail /aws/lambda/villages-events-sync-${ENVIRONMENT} --follow"
else
    echo -e "${RED}✗ Deployment failed${NC}"
    exit 1
fi
