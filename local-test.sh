#!/bin/bash

# Villages Events Sync - Local Testing Script
# This script tests the Lambda function locally using SAM CLI

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Villages Events Sync - Local Testing${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    echo -e "${RED}Error: AWS SAM CLI is not installed${NC}"
    echo "Please install SAM CLI: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"
    exit 1
fi

# Check if Docker is running (required for SAM local)
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    echo "SAM local requires Docker to be running. Please start Docker and try again."
    exit 1
fi

# Parse command line arguments
USE_LOCALSTACK=false
USE_DYNAMODB_LOCAL=false
SKIP_BUILD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --localstack)
            USE_LOCALSTACK=true
            shift
            ;;
        --dynamodb-local)
            USE_DYNAMODB_LOCAL=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --help)
            echo "Usage: ./local-test.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --localstack      Use LocalStack for local AWS services"
            echo "  --dynamodb-local  Use DynamoDB Local instead of LocalStack"
            echo "  --skip-build      Skip the sam build step"
            echo "  --help            Show this help message"
            echo ""
            echo "Note: This script requires Docker to be running."
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Build the application if not skipped
if [ "$SKIP_BUILD" = false ]; then
    echo -e "${YELLOW}Step 1: Building SAM application${NC}"
    sam build
    echo -e "${GREEN}✓ Build completed${NC}"
    echo ""
else
    echo -e "${YELLOW}Skipping build step${NC}"
    echo ""
fi

# Setup local services if requested
if [ "$USE_LOCALSTACK" = true ]; then
    echo -e "${YELLOW}Step 2: Starting LocalStack${NC}"
    echo "Checking if LocalStack is running..."
    
    if ! docker ps | grep -q localstack; then
        echo "Starting LocalStack container..."
        docker run -d \
            --name localstack \
            -p 4566:4566 \
            -e SERVICES=dynamodb,lambda \
            localstack/localstack:latest
        
        echo "Waiting for LocalStack to be ready..."
        sleep 10
    else
        echo "LocalStack is already running"
    fi
    
    echo -e "${GREEN}✓ LocalStack ready${NC}"
    echo ""
    
    # Set environment variables for LocalStack
    export AWS_ENDPOINT_URL=http://localhost:4566
    export TABLE_NAME=villages-events-dev
    
    echo -e "${BLUE}Creating DynamoDB table in LocalStack...${NC}"
    aws dynamodb create-table \
        --table-name villages-events-dev \
        --attribute-definitions \
            AttributeName=event_id,AttributeType=S \
            AttributeName=event_date,AttributeType=S \
            AttributeName=start_time,AttributeType=S \
        --key-schema AttributeName=event_id,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --global-secondary-indexes \
            "IndexName=date-index,KeySchema=[{AttributeName=event_date,KeyType=HASH},{AttributeName=start_time,KeyType=RANGE}],Projection={ProjectionType=ALL}" \
        --endpoint-url http://localhost:4566 \
        2>/dev/null || echo "Table may already exist"
    
    echo -e "${GREEN}✓ DynamoDB table ready${NC}"
    echo ""
    
elif [ "$USE_DYNAMODB_LOCAL" = true ]; then
    echo -e "${YELLOW}Step 2: Starting DynamoDB Local${NC}"
    echo "Checking if DynamoDB Local is running..."
    
    if ! docker ps | grep -q dynamodb-local; then
        echo "Starting DynamoDB Local container..."
        docker run -d \
            --name dynamodb-local \
            -p 8000:8000 \
            amazon/dynamodb-local:latest
        
        echo "Waiting for DynamoDB Local to be ready..."
        sleep 5
    else
        echo "DynamoDB Local is already running"
    fi
    
    echo -e "${GREEN}✓ DynamoDB Local ready${NC}"
    echo ""
    
    # Set environment variables for DynamoDB Local
    export AWS_ENDPOINT_URL=http://localhost:8000
    export TABLE_NAME=villages-events-dev
    
    echo -e "${BLUE}Creating DynamoDB table in DynamoDB Local...${NC}"
    aws dynamodb create-table \
        --table-name villages-events-dev \
        --attribute-definitions \
            AttributeName=event_id,AttributeType=S \
            AttributeName=event_date,AttributeType=S \
            AttributeName=start_time,AttributeType=S \
        --key-schema AttributeName=event_id,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --global-secondary-indexes \
            "IndexName=date-index,KeySchema=[{AttributeName=event_date,KeyType=HASH},{AttributeName=start_time,KeyType=RANGE}],Projection={ProjectionType=ALL}" \
        --endpoint-url http://localhost:8000 \
        2>/dev/null || echo "Table may already exist"
    
    echo -e "${GREEN}✓ DynamoDB table ready${NC}"
    echo ""
else
    echo -e "${YELLOW}Step 2: Skipping local service setup${NC}"
    echo "Note: Lambda will attempt to connect to real AWS DynamoDB"
    echo "Make sure you have valid AWS credentials configured"
    echo ""
fi

# Check if event.json exists
if [ ! -f "event.json" ]; then
    echo -e "${RED}Error: event.json not found${NC}"
    echo "Creating a sample event.json file..."
    cat > event.json << 'EOF'
{
  "version": "0",
  "id": "test-event-id",
  "detail-type": "Scheduled Event",
  "source": "aws.events",
  "account": "123456789012",
  "time": "2024-01-01T06:00:00Z",
  "region": "us-east-1",
  "resources": [
    "arn:aws:events:us-east-1:123456789012:rule/villages-events-daily-sync-dev"
  ],
  "detail": {}
}
EOF
    echo -e "${GREEN}✓ Created event.json${NC}"
    echo ""
fi

echo -e "${YELLOW}Step 3: Invoking Lambda function locally${NC}"
echo "Running sam local invoke..."
echo ""

# Set environment variables for the Lambda function
export TABLE_NAME=${TABLE_NAME:-villages-events-dev}
export LOG_LEVEL=DEBUG
export DAYS_AHEAD=90
export TIMEOUT_SECONDS=30

# Invoke the Lambda function
sam local invoke VillagesEventsFunction \
    --event event.json \
    --env-vars <(echo "{
        \"VillagesEventsFunction\": {
            \"TABLE_NAME\": \"${TABLE_NAME}\",
            \"LOG_LEVEL\": \"${LOG_LEVEL}\",
            \"DAYS_AHEAD\": \"${DAYS_AHEAD}\",
            \"TIMEOUT_SECONDS\": \"${TIMEOUT_SECONDS}\"
        }
    }")

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Local test completed${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$USE_LOCALSTACK" = true ] || [ "$USE_DYNAMODB_LOCAL" = true ]; then
    echo "To view the DynamoDB table contents:"
    if [ "$USE_LOCALSTACK" = true ]; then
        echo "  aws dynamodb scan --table-name villages-events-dev --endpoint-url http://localhost:4566"
    else
        echo "  aws dynamodb scan --table-name villages-events-dev --endpoint-url http://localhost:8000"
    fi
    echo ""
    echo "To stop the local services:"
    if [ "$USE_LOCALSTACK" = true ]; then
        echo "  docker stop localstack && docker rm localstack"
    else
        echo "  docker stop dynamodb-local && docker rm dynamodb-local"
    fi
fi
