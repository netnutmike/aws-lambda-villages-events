# Design Document: Villages Events Calendar Sync

## Overview

The Villages Events Calendar Sync application is a serverless Python application that runs daily on AWS Lambda to synchronize event data from The Villages Florida online calendar to DynamoDB. The application leverages the existing python-villages-events repository for calendar scraping logic and provides a data source for an Alexa skill.

### Key Design Decisions

1. **Serverless Architecture**: Using AWS Lambda eliminates server management and provides automatic scaling
2. **DynamoDB for Storage**: NoSQL database optimized for fast key-value lookups needed by Alexa skills
3. **EventBridge Scheduling**: Native AWS service for reliable daily execution
4. **Infrastructure as Code**: Using AWS SAM (Serverless Application Model) for deployment automation
5. **Sync Strategy**: Full sync with comparison logic to identify additions, updates, and deletions

## Architecture

### High-Level Architecture

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

### Component Interaction Flow

1. EventBridge triggers Lambda function daily at configured time
2. Lambda function invokes Calendar Scraper to fetch events from The Villages website
3. Event Processor normalizes and validates event data
4. DynamoDB Manager compares fetched events with existing records
5. DynamoDB Manager performs batch write operations (add/update/delete)
6. Lambda function logs summary and exits

## Components and Interfaces

### 1. Lambda Handler (`lambda_function.py`)

**Responsibility**: Entry point for Lambda execution, orchestrates the sync process

**Interface**:
```python
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Main Lambda handler function.
    
    Args:
        event: EventBridge event payload
        context: Lambda context object
        
    Returns:
        dict: Response with statusCode and summary statistics
    """
```

**Key Functions**:
- Initialize logging
- Invoke calendar scraper
- Coordinate sync process
- Return execution summary

### 2. Calendar Scraper (`scraper/villages_calendar.py`)

**Responsibility**: Fetch and parse event data from The Villages calendar website

**Interface**:
```python
class VillagesCalendarScraper:
    def fetch_events(self, days_ahead: int = 90) -> List[Event]:
        """
        Fetch events from The Villages calendar.
        
        Args:
            days_ahead: Number of days to fetch events for
            
        Returns:
            List of Event objects
        """
```

**Implementation Notes**:
- Adapts logic from python-villages-events repository
- Uses requests library for HTTP calls
- Uses BeautifulSoup4 for HTML parsing
- Implements retry logic with exponential backoff
- Configurable timeout (30 seconds default)

### 3. Event Processor (`processor/event_processor.py`)

**Responsibility**: Normalize, validate, and transform event data

**Interface**:
```python
class EventProcessor:
    def process_events(self, raw_events: List[Event]) -> List[ProcessedEvent]:
        """
        Process and validate raw event data.
        
        Args:
            raw_events: List of raw Event objects from scraper
            
        Returns:
            List of validated ProcessedEvent objects
        """
    
    def generate_event_id(self, event: Event) -> str:
        """
        Generate unique identifier for an event.
        
        Args:
            event: Event object
            
        Returns:
            Unique event ID (hash of title + date + time)
        """
```

**Validation Rules**:
- Required fields: title, date, start_time
- Date format: ISO 8601 (YYYY-MM-DD)
- Time format: 24-hour (HH:MM)
- Maximum title length: 200 characters
- Maximum description length: 2000 characters

### 4. DynamoDB Manager (`storage/dynamodb_manager.py`)

**Responsibility**: Manage all DynamoDB operations

**Interface**:
```python
class DynamoDBManager:
    def __init__(self, table_name: str):
        """Initialize DynamoDB client and table reference."""
        
    def get_all_events(self) -> Dict[str, ProcessedEvent]:
        """
        Retrieve all events from DynamoDB.
        
        Returns:
            Dictionary mapping event_id to ProcessedEvent
        """
    
    def sync_events(self, new_events: List[ProcessedEvent]) -> SyncResult:
        """
        Synchronize events with DynamoDB.
        
        Args:
            new_events: List of current events from calendar
            
        Returns:
            SyncResult with counts of added, updated, deleted events
        """
    
    def batch_write_events(self, events: List[ProcessedEvent]) -> int:
        """Write events in batches of 25 (DynamoDB limit)."""
    
    def batch_delete_events(self, event_ids: List[str]) -> int:
        """Delete events in batches of 25 (DynamoDB limit)."""
```

**Sync Logic**:
1. Fetch all existing events from DynamoDB
2. Compare with new events from calendar
3. Identify additions (in new, not in existing)
4. Identify updates (in both, but content differs)
5. Identify deletions (in existing, not in new)
6. Execute batch operations with error handling

## Data Models

### Event Data Model

**DynamoDB Table Schema**:
```
Table Name: villages-events
Partition Key: event_id (String)
Sort Key: None (single-item access pattern)
Billing Mode: On-Demand

Attributes:
- event_id: String (PK) - Unique identifier
- title: String - Event name
- description: String - Event details
- event_date: String - ISO 8601 date (YYYY-MM-DD)
- start_time: String - 24-hour time (HH:MM)
- end_time: String - 24-hour time (HH:MM) [optional]
- location: String - Venue name
- category: String - Event category/type
- url: String - Link to event details [optional]
- last_updated: Number - Unix timestamp
- ttl: Number - Time-to-live for automatic cleanup (90 days after event_date)
```

**GSI (Global Secondary Index)**:
```
Index Name: date-index
Partition Key: event_date (String)
Sort Key: start_time (String)
Projection: ALL

Purpose: Enable efficient queries by date for Alexa skill
```

### Python Data Classes

```python
@dataclass
class Event:
    """Raw event from calendar scraper."""
    title: str
    date: str
    start_time: str
    end_time: Optional[str]
    location: str
    description: str
    category: str
    url: Optional[str]

@dataclass
class ProcessedEvent:
    """Validated and normalized event."""
    event_id: str
    title: str
    description: str
    event_date: str
    start_time: str
    end_time: Optional[str]
    location: str
    category: str
    url: Optional[str]
    last_updated: int
    ttl: int

@dataclass
class SyncResult:
    """Result of sync operation."""
    added: int
    updated: int
    deleted: int
    errors: List[str]
```

## Error Handling

### Error Categories and Strategies

1. **Network Errors** (Calendar fetch failures)
   - Strategy: Retry with exponential backoff (3 attempts)
   - Logging: Log error details and retry attempts
   - Outcome: If all retries fail, exit Lambda with error status

2. **Parsing Errors** (Invalid HTML structure)
   - Strategy: Skip malformed events, continue processing
   - Logging: Log skipped events with reason
   - Outcome: Process remaining valid events

3. **DynamoDB Errors** (Throttling, service errors)
   - Strategy: Use boto3 automatic retries with exponential backoff
   - Logging: Log failed operations
   - Outcome: Continue processing, report failures in summary

4. **Validation Errors** (Invalid event data)
   - Strategy: Skip invalid events, log validation failures
   - Logging: Log event details and validation failure reason
   - Outcome: Process remaining valid events

### Logging Strategy

- Use Python logging module with JSON formatter
- Log Level: INFO for normal operations, ERROR for failures
- CloudWatch Logs retention: 30 days
- Key log events:
  - Lambda start/end with execution time
  - Calendar fetch start/complete with event count
  - Sync operation summary (added/updated/deleted counts)
  - Individual errors with context

### Monitoring and Alerts

- CloudWatch Metric: Lambda errors (built-in)
- CloudWatch Metric: Lambda duration (built-in)
- Custom Metric: Events synced count
- Alarm: Lambda function errors > 0 in 24 hours

## Deployment Architecture

### Infrastructure as Code (AWS SAM)

**template.yaml** structure:
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Parameters:
  - Environment (dev/prod)
  - ScheduleExpression (cron expression)

Resources:
  - VillagesEventsFunction (Lambda)
  - VillagesEventsTable (DynamoDB)
  - VillagesEventsFunctionRole (IAM Role)
  - DailyScheduleRule (EventBridge)
  - DailySchedulePermission (Lambda Permission)

Outputs:
  - FunctionArn
  - TableName
  - ScheduleExpression
```

### Deployment Process

1. **Build Phase**:
   - Install dependencies to build directory
   - Package Lambda deployment artifact
   - Validate SAM template

2. **Deploy Phase**:
   - Create/update CloudFormation stack
   - Upload Lambda code to S3
   - Deploy infrastructure changes
   - Update function code

3. **Verification Phase**:
   - Invoke Lambda function with test event
   - Verify DynamoDB table created
   - Check CloudWatch logs

### Environment Configuration

**Environment Variables**:
- `TABLE_NAME`: DynamoDB table name (from SAM template)
- `LOG_LEVEL`: Logging level (INFO/DEBUG)
- `DAYS_AHEAD`: Number of days to fetch events (default: 90)
- `TIMEOUT_SECONDS`: HTTP request timeout (default: 30)

**Lambda Configuration**:
- Runtime: Python 3.11
- Memory: 512 MB
- Timeout: 5 minutes
- Architecture: arm64 (Graviton2 for cost savings)

## Testing Strategy

### Unit Tests

**Coverage Areas**:
- Event processor validation logic
- Event ID generation
- Date/time parsing and formatting
- DynamoDB sync logic (with mocked boto3)

**Framework**: pytest with pytest-cov for coverage

**Mocking Strategy**:
- Mock external HTTP calls (responses library)
- Mock boto3 DynamoDB client (moto library)
- Mock environment variables

### Integration Tests

**Coverage Areas**:
- End-to-end sync process with local DynamoDB
- Calendar scraper with recorded HTTP responses
- Error handling scenarios

**Tools**:
- LocalStack or DynamoDB Local for local testing
- VCR.py for recording/replaying HTTP interactions

### Manual Testing

**Pre-Deployment**:
- Test Lambda function locally with SAM CLI
- Verify deployment package size < 50 MB
- Test with sample calendar data

**Post-Deployment**:
- Trigger Lambda manually via AWS Console
- Verify events appear in DynamoDB
- Check CloudWatch logs for errors

## Security Considerations

1. **IAM Permissions**: Lambda execution role limited to:
   - DynamoDB: PutItem, GetItem, Scan, DeleteItem on villages-events table only
   - CloudWatch Logs: CreateLogGroup, CreateLogStream, PutLogEvents

2. **Network Security**: Lambda runs in AWS-managed VPC (no custom VPC needed)

3. **Data Security**: 
   - DynamoDB encryption at rest (AWS managed keys)
   - No sensitive data in event records
   - CloudWatch Logs encrypted

4. **Secrets Management**: No API keys or secrets required (public calendar)

## Performance Considerations

1. **Lambda Cold Start**: Minimize by keeping deployment package small (<10 MB)
2. **DynamoDB Throughput**: On-demand mode handles variable load
3. **Batch Operations**: Use batch write/delete (25 items per batch) to minimize API calls
4. **Memory Allocation**: 512 MB provides good balance of performance and cost
5. **Concurrent Executions**: Single daily execution, no concurrency needed

## Maintenance and Operations

### Dependency Updates

- Renovate configuration for automated PR creation
- Weekly schedule for dependency checks
- Auto-merge for patch updates with passing tests

### Monitoring Checklist

- Daily: Check CloudWatch dashboard for errors
- Weekly: Review sync operation metrics
- Monthly: Review Lambda costs and optimize if needed

### Troubleshooting Guide

Common issues and resolutions documented in developer documentation:
- Calendar website structure changes
- DynamoDB throttling
- Lambda timeout issues
- Missing events in sync
