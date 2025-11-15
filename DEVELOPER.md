# Developer Documentation

This document provides detailed information for developers working on the Villages Events Calendar Sync application.

## Table of Contents

- [Project Structure](#project-structure)
- [Code Organization](#code-organization)
- [Environment Variables](#environment-variables)
- [Local Development Setup](#local-development-setup)
- [Running Tests](#running-tests)
- [Deployment Process](#deployment-process)
- [Manual Testing](#manual-testing)
- [Troubleshooting](#troubleshooting)

## Project Structure

```
aws-lambda-villages-events/
├── .kiro/                      # Kiro specs and configuration
│   └── specs/
│       └── villages-events-sync/
│           ├── requirements.md
│           ├── design.md
│           └── tasks.md
├── scraper/                    # Calendar scraping module
│   ├── __init__.py
│   └── villages_calendar.py
├── processor/                  # Event processing module
│   ├── __init__.py
│   ├── models.py
│   └── event_processor.py
├── storage/                    # DynamoDB operations module
│   ├── __init__.py
│   └── dynamodb_manager.py
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── test_villages_calendar.py
│   ├── test_event_processor.py
│   ├── test_dynamodb_manager.py
│   └── test_lambda_function.py
├── lambda_function.py          # Lambda handler entry point
├── template.yaml               # AWS SAM infrastructure template
├── samconfig.toml             # SAM deployment configuration
├── requirements.txt           # Python dependencies
├── deploy.sh                  # Deployment automation script
├── local-test.sh              # Local testing script
├── event.json                 # Sample EventBridge event payload
├── .gitignore                 # Git ignore rules
├── renovate.json              # Renovate dependency management config
└── README.md                  # Project overview
```

## Code Organization

### Module: `scraper/`

**Purpose**: Fetch and parse event data from The Villages calendar website

**Key Components**:

- `VillagesCalendarScraper`: Main scraper class
  - `fetch_events(days_ahead)`: Fetches events from the calendar
  - Implements retry logic with exponential backoff
  - Uses BeautifulSoup4 for HTML parsing
  - Handles network timeouts and errors

**Dependencies**:
- `requests`: HTTP client
- `beautifulsoup4`: HTML parsing
- `dataclasses`: Event data structures

### Module: `processor/`

**Purpose**: Validate, normalize, and transform event data

**Key Components**:

- `models.py`: Data class definitions
  - `Event`: Raw event from scraper
  - `ProcessedEvent`: Validated and normalized event
  - `SyncResult`: Sync operation results

- `event_processor.py`: Event processing logic
  - `EventProcessor`: Main processor class
  - `process_events()`: Validates and normalizes events
  - `generate_event_id()`: Creates unique event identifiers
  - Date/time normalization to ISO 8601 format
  - TTL calculation (90 days after event date)

**Validation Rules**:
- Required fields: title, date, start_time
- Date format: YYYY-MM-DD
- Time format: HH:MM (24-hour)
- Title max length: 200 characters
- Description max length: 2000 characters

### Module: `storage/`

**Purpose**: Manage all DynamoDB operations

**Key Components**:

- `DynamoDBManager`: Main storage class
  - `get_all_events()`: Retrieves all events from DynamoDB
  - `sync_events()`: Synchronizes new events with existing data
  - `batch_write_events()`: Writes events in batches of 25
  - `batch_delete_events()`: Deletes events in batches of 25

**Sync Algorithm**:
1. Fetch all existing events from DynamoDB
2. Compare with new events from calendar
3. Identify additions (in new, not in existing)
4. Identify updates (in both, but content differs)
5. Identify deletions (in existing, not in new)
6. Execute batch operations with error handling

### Lambda Handler: `lambda_function.py`

**Purpose**: Entry point for Lambda execution, orchestrates the sync process

**Key Functions**:
- `lambda_handler(event, context)`: Main handler
- Initializes logging with JSON formatter
- Coordinates scraper, processor, and storage modules
- Returns execution summary with statistics

## Environment Variables

### Lambda Function Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TABLE_NAME` | DynamoDB table name | - | Yes (set by SAM) |
| `LOG_LEVEL` | Logging verbosity | `INFO` | No |
| `DAYS_AHEAD` | Days to fetch events for | `90` | No |
| `TIMEOUT_SECONDS` | HTTP request timeout | `30` | No |

### Local Development

For local testing, create a `.env` file (not committed to git):

```bash
TABLE_NAME=villages-events-local
LOG_LEVEL=DEBUG
DAYS_AHEAD=90
TIMEOUT_SECONDS=30
AWS_REGION=us-east-1
```

## Local Development Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd aws-lambda-villages-events
```

### 2. Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-cov moto responses
```

### 4. Install AWS SAM CLI

Follow the [official installation guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) for your platform.

**macOS (Homebrew)**:
```bash
brew install aws-sam-cli
```

**Verify installation**:
```bash
sam --version
```

### 5. Configure AWS Credentials

```bash
aws configure
```

Provide:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., `us-east-1`)
- Default output format (e.g., `json`)

## Running Tests

### Unit Tests

Run all unit tests:

```bash
pytest tests/
```

Run with coverage report:

```bash
pytest tests/ --cov=. --cov-report=html
```

View coverage report:

```bash
open htmlcov/index.html
```

### Run Specific Test Files

```bash
# Test calendar scraper
pytest tests/test_villages_calendar.py -v

# Test event processor
pytest tests/test_event_processor.py -v

# Test DynamoDB manager
pytest tests/test_dynamodb_manager.py -v

# Test Lambda handler
pytest tests/test_lambda_function.py -v
```

### Run Tests with Debug Output

```bash
pytest tests/ -v -s
```

### Test Coverage Goals

- Overall coverage: >80%
- Critical modules (processor, storage): >90%
- Focus on core business logic

## Deployment Process

### Step 1: Validate Template

```bash
sam validate
```

This checks the SAM template syntax and structure.

### Step 2: Build Application

```bash
sam build
```

This:
- Installs Python dependencies
- Packages Lambda function code
- Prepares deployment artifacts in `.aws-sam/build/`

### Step 3: Deploy to AWS

**First-time deployment (guided)**:

```bash
sam deploy --guided
```

You'll be prompted for:
- Stack name (e.g., `villages-events-sync-prod`)
- AWS Region (e.g., `us-east-1`)
- Parameter Environment (e.g., `prod`)
- Parameter ScheduleExpression (e.g., `cron(0 6 * * ? *)`)
- Confirm changes before deploy: Y
- Allow SAM CLI IAM role creation: Y
- Save arguments to configuration file: Y

**Subsequent deployments**:

```bash
sam deploy
```

This uses saved configuration from `samconfig.toml`.

### Step 4: Verify Deployment

```bash
# Get stack outputs
aws cloudformation describe-stacks \
  --stack-name villages-events-sync-prod \
  --query 'Stacks[0].Outputs'

# Invoke function manually
aws lambda invoke \
  --function-name <function-name> \
  --log-type Tail \
  output.json

# View output
cat output.json
```

### Using the Deployment Script

```bash
chmod +x deploy.sh
./deploy.sh
```

The script automates:
1. Building the application
2. Validating the template
3. Deploying to AWS
4. Displaying stack outputs

## Manual Testing

### Local Testing with SAM CLI

#### 1. Start Local DynamoDB

Option A: Using Docker (DynamoDB Local):

```bash
docker run -p 8000:8000 amazon/dynamodb-local
```

Option B: Using LocalStack:

```bash
docker run -p 4566:4566 localstack/localstack
```

#### 2. Create Local Table

```bash
aws dynamodb create-table \
  --table-name villages-events-local \
  --attribute-definitions \
    AttributeName=event_id,AttributeType=S \
    AttributeName=event_date,AttributeType=S \
    AttributeName=start_time,AttributeType=S \
  --key-schema AttributeName=event_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --global-secondary-indexes \
    "IndexName=date-index,KeySchema=[{AttributeName=event_date,KeyType=HASH},{AttributeName=start_time,KeyType=RANGE}],Projection={ProjectionType=ALL}" \
  --endpoint-url http://localhost:8000
```

#### 3. Invoke Lambda Locally

```bash
sam local invoke VillagesEventsFunction \
  --event event.json \
  --env-vars '{"TABLE_NAME":"villages-events-local","LOG_LEVEL":"DEBUG"}'
```

Or use the local testing script:

```bash
chmod +x local-test.sh
./local-test.sh
```

### Manual Testing in AWS

#### Invoke Lambda Function

```bash
aws lambda invoke \
  --function-name villages-events-sync-prod-VillagesEventsFunction \
  --log-type Tail \
  --query 'LogResult' \
  --output text \
  output.json | base64 --decode
```

#### View Recent Logs

```bash
aws logs tail /aws/lambda/<function-name> --follow
```

#### Query DynamoDB Table

**Scan all events**:

```bash
aws dynamodb scan \
  --table-name villages-events \
  --max-items 10
```

**Query by date**:

```bash
aws dynamodb query \
  --table-name villages-events \
  --index-name date-index \
  --key-condition-expression "event_date = :date" \
  --expression-attribute-values '{":date":{"S":"2024-12-01"}}'
```

**Get specific event**:

```bash
aws dynamodb get-item \
  --table-name villages-events \
  --key '{"event_id":{"S":"<event-id>"}}'
```

**Count total events**:

```bash
aws dynamodb scan \
  --table-name villages-events \
  --select COUNT
```

## Troubleshooting

### Deployment Issues

#### Issue: SAM build fails with dependency errors

**Solution**:
```bash
# Clean build artifacts
rm -rf .aws-sam/

# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt --upgrade

# Rebuild
sam build
```

#### Issue: CloudFormation stack creation fails

**Solution**:
```bash
# Check stack events for error details
aws cloudformation describe-stack-events \
  --stack-name villages-events-sync-prod \
  --max-items 20

# Delete failed stack
aws cloudformation delete-stack \
  --stack-name villages-events-sync-prod

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name villages-events-sync-prod

# Retry deployment
sam deploy
```

#### Issue: IAM permission errors during deployment

**Solution**:
- Ensure AWS credentials have permissions to create:
  - Lambda functions
  - DynamoDB tables
  - IAM roles
  - EventBridge rules
  - CloudWatch log groups
- Use an admin user or attach `PowerUserAccess` policy

### Runtime Issues

#### Issue: Lambda function times out

**Symptoms**: Function execution exceeds 5-minute timeout

**Debugging**:
```bash
# Check CloudWatch logs
aws logs tail /aws/lambda/<function-name> --since 1h

# Check Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=<function-name> \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum
```

**Solutions**:
- Reduce `DAYS_AHEAD` environment variable
- Increase Lambda timeout in `template.yaml`
- Check for slow network requests in logs

#### Issue: DynamoDB throttling

**Symptoms**: `ProvisionedThroughputExceededException` errors

**Debugging**:
```bash
# Check table metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name UserErrors \
  --dimensions Name=TableName,Value=villages-events \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

**Solutions**:
- Verify table is using on-demand billing mode
- Check for concurrent Lambda executions
- Review batch operation sizes

#### Issue: Calendar scraping fails

**Symptoms**: HTTP errors or parsing failures

**Debugging**:
```bash
# Test scraper locally
python3 -c "
from scraper.villages_calendar import VillagesCalendarScraper
scraper = VillagesCalendarScraper()
events = scraper.fetch_events(days_ahead=7)
print(f'Fetched {len(events)} events')
for event in events[:3]:
    print(event)
"
```

**Solutions**:
- Verify The Villages calendar URL is accessible
- Check if website HTML structure has changed
- Increase `TIMEOUT_SECONDS` environment variable
- Review retry logic in CloudWatch logs

### Testing Issues

#### Issue: Tests fail with import errors

**Solution**:
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Install test dependencies
pip install pytest pytest-cov moto responses

# Run tests from project root
pytest tests/
```

#### Issue: DynamoDB tests fail

**Solution**:
```bash
# Ensure moto is installed
pip install moto[dynamodb]

# Run specific test with verbose output
pytest tests/test_dynamodb_manager.py -v -s
```

### Local Development Issues

#### Issue: AWS credentials not found

**Solution**:
```bash
# Configure AWS CLI
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=<your-key>
export AWS_SECRET_ACCESS_KEY=<your-secret>
export AWS_DEFAULT_REGION=us-east-1
```

#### Issue: SAM local invoke fails

**Solution**:
```bash
# Ensure Docker is running
docker ps

# Check SAM CLI version
sam --version

# Use debug mode
sam local invoke --debug
```

## Code Style and Best Practices

### Python Style Guide

- Follow PEP 8 style guidelines
- Use type hints for function parameters and return values
- Maximum line length: 100 characters
- Use docstrings for all public functions and classes

### Error Handling

- Use specific exception types
- Log errors with context
- Fail gracefully and continue processing when possible
- Return meaningful error messages

### Logging

- Use structured logging (JSON format in Lambda)
- Include relevant context in log messages
- Use appropriate log levels:
  - `DEBUG`: Detailed diagnostic information
  - `INFO`: General informational messages
  - `WARNING`: Warning messages for recoverable issues
  - `ERROR`: Error messages for failures

### Testing

- Write tests for all new features
- Mock external dependencies (HTTP, DynamoDB)
- Test error handling paths
- Aim for >80% code coverage

## Contributing

1. Create a feature branch from `main`
2. Make your changes
3. Run tests and ensure they pass
4. Update documentation if needed
5. Submit a pull request

## Additional Resources

- [AWS Lambda Developer Guide](https://docs.aws.amazon.com/lambda/latest/dg/)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [DynamoDB Developer Guide](https://docs.aws.amazon.com/dynamodb/latest/developerguide/)
- [Python Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [pytest Documentation](https://docs.pytest.org/)

