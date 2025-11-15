# Villages Events Calendar Sync

A serverless AWS Lambda application that automatically synchronizes event data from The Villages Florida online calendar to DynamoDB, providing a reliable data source for Alexa skills and other applications.

## Overview

This application runs daily on AWS Lambda to fetch, process, and store event information from The Villages calendar. It maintains an up-to-date DynamoDB table by automatically adding new events, updating modified events, and removing outdated ones.

## Architecture

```
┌─────────────────────┐
│  EventBridge Rule   │
│  (Daily Trigger)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Lambda Function   │
│  (Python 3.11)      │
│                     │
│  ┌───────────────┐  │
│  │ Calendar      │  │
│  │ Scraper       │  │
│  └───────┬───────┘  │
│          │          │
│  ┌───────▼───────┐  │
│  │ Event         │  │
│  │ Processor     │  │
│  └───────┬───────┘  │
│          │          │
│  ┌───────▼───────┐  │
│  │ DynamoDB      │  │
│  │ Manager       │  │
│  └───────────────┘  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   DynamoDB Table    │
│  villages-events    │
└─────────────────────┘
```

## Key Features

- **Automated Daily Sync**: Runs automatically on a configurable schedule using AWS EventBridge
- **Smart Synchronization**: Identifies and processes additions, updates, and deletions efficiently
- **Robust Error Handling**: Implements retry logic with exponential backoff for network failures
- **Automatic Cleanup**: Uses DynamoDB TTL to automatically remove events 90 days after they occur
- **Cost-Optimized**: Uses on-demand DynamoDB billing and ARM64 Lambda architecture
- **Comprehensive Logging**: Detailed CloudWatch logs for monitoring and troubleshooting
- **Infrastructure as Code**: Complete AWS SAM template for reproducible deployments

## AWS Services Used

- **AWS Lambda**: Serverless compute for running the sync process
- **Amazon DynamoDB**: NoSQL database for storing event data
- **Amazon EventBridge**: Scheduled trigger for daily execution
- **AWS CloudWatch**: Logging and monitoring
- **AWS SAM**: Infrastructure as code and deployment automation
- **AWS IAM**: Least-privilege security permissions

## Quick Start

### Prerequisites

- AWS CLI configured with appropriate credentials
- AWS SAM CLI installed ([installation guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html))
- Python 3.11 or later
- An AWS account with permissions to create Lambda functions, DynamoDB tables, and IAM roles

### Deployment

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd aws-lambda-villages-events
   ```

2. **Build the application**:
   ```bash
   sam build
   ```

3. **Deploy to AWS**:
   ```bash
   sam deploy --guided
   ```

   Follow the prompts to configure:
   - Stack name (e.g., `villages-events-sync`)
   - AWS Region (e.g., `us-east-1`)
   - Environment (e.g., `prod`)
   - Schedule expression (e.g., `cron(0 6 * * ? *)` for 6 AM UTC daily)

4. **Verify deployment**:
   ```bash
   aws lambda invoke --function-name <function-name> --log-type Tail output.json
   cat output.json
   ```

### Alternative: Using the deployment script

```bash
chmod +x deploy.sh
./deploy.sh
```

## Configuration

The Lambda function uses the following environment variables:

- `TABLE_NAME`: DynamoDB table name (automatically set by SAM template)
- `LOG_LEVEL`: Logging verbosity (`INFO` or `DEBUG`)
- `DAYS_AHEAD`: Number of days to fetch events for (default: 90)
- `TIMEOUT_SECONDS`: HTTP request timeout in seconds (default: 30)

## Project Structure

```
.
├── lambda_function.py          # Lambda handler entry point
├── scraper/
│   └── villages_calendar.py    # Calendar scraping logic
├── processor/
│   ├── models.py               # Data models
│   └── event_processor.py      # Event validation and normalization
├── storage/
│   └── dynamodb_manager.py     # DynamoDB operations
├── tests/                      # Unit and integration tests
├── template.yaml               # AWS SAM infrastructure template
├── samconfig.toml             # SAM deployment configuration
├── requirements.txt           # Python dependencies
└── deploy.sh                  # Deployment automation script
```

## Documentation

- [DEVELOPER.md](DEVELOPER.md) - Detailed developer documentation, local setup, and testing
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture and design decisions

## Monitoring

After deployment, monitor the application using:

- **CloudWatch Logs**: View execution logs at `/aws/lambda/<function-name>`
- **CloudWatch Metrics**: Monitor Lambda invocations, errors, and duration
- **DynamoDB Console**: Verify event data in the `villages-events` table

## Troubleshooting

### Lambda function times out

**Symptom**: Function execution exceeds the 5-minute timeout

**Solutions**:
- Check CloudWatch logs for slow network requests
- Reduce `DAYS_AHEAD` environment variable to fetch fewer events
- Increase Lambda timeout in `template.yaml` (max 15 minutes)

### No events appearing in DynamoDB

**Symptom**: Lambda executes successfully but table is empty

**Solutions**:
- Check CloudWatch logs for parsing errors
- Verify The Villages calendar website is accessible
- Test calendar scraper locally using `local-test.sh`
- Check IAM permissions for DynamoDB write access

### Calendar scraping fails

**Symptom**: HTTP errors or parsing failures in logs

**Solutions**:
- Verify The Villages calendar URL is still valid
- Check if website HTML structure has changed
- Review retry logic in CloudWatch logs
- Test with increased `TIMEOUT_SECONDS` value

### DynamoDB throttling errors

**Symptom**: `ProvisionedThroughputExceededException` in logs

**Solutions**:
- Verify table is using on-demand billing mode
- Check for concurrent Lambda executions (should be only one daily)
- Review batch operation sizes in code

### Events not being deleted

**Symptom**: Old events remain in DynamoDB after they're removed from calendar

**Solutions**:
- Verify sync logic is identifying deletions correctly
- Check CloudWatch logs for deletion operation counts
- Ensure TTL is configured on the DynamoDB table
- Manually verify event_id generation is consistent

## Contributing

For development guidelines and contribution instructions, see [DEVELOPER.md](DEVELOPER.md).

## License

[Add your license information here]

## Support

For issues and questions:
- Check the [troubleshooting section](#troubleshooting) above
- Review [DEVELOPER.md](DEVELOPER.md) for detailed documentation
- Check CloudWatch logs for error details
- Review [ARCHITECTURE.md](ARCHITECTURE.md) for system design

