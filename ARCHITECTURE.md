# Architecture Documentation

## Table of Contents

- [High-Level Architecture](#high-level-architecture)
- [Component Architecture](#component-architecture)
- [Data Flow](#data-flow)
- [DynamoDB Schema Design](#dynamodb-schema-design)
- [Sync Algorithm](#sync-algorithm)
- [Error Handling Strategy](#error-handling-strategy)
- [Monitoring and Alerting](#monitoring-and-alerting)
- [Security Architecture](#security-architecture)
- [Performance Considerations](#performance-considerations)

## High-Level Architecture

The Villages Events Calendar Sync is a serverless application built on AWS Lambda that runs on a scheduled basis to synchronize event data from The Villages Florida online calendar to DynamoDB.

### Architecture Diagram

```
                                    ┌─────────────────────────────────┐
                                    │     The Villages Calendar       │
                                    │         (Web Source)            │
                                    └────────────┬────────────────────┘
                                                 │ HTTPS
                                                 │
┌──────────────────────┐                        │
│  Amazon EventBridge  │                        │
│   (Scheduled Rule)   │                        │
│                      │                        │
│  Cron: 0 6 * * ? *   │                        │
│  (Daily at 6 AM UTC) │                        │
└──────────┬───────────┘                        │
           │ Trigger                            │
           │                                    │
           ▼                                    │
┌──────────────────────────────────────────────┼────────┐
│         AWS Lambda Function                  │        │
│         (Python 3.11, ARM64)                 │        │
│                                              │        │
│  ┌────────────────────────────────────────┐ │        │
│  │  Lambda Handler (lambda_function.py)   │ │        │
│  │  - Initialize logging                  │ │        │
│  │  - Coordinate modules                  │ │        │
│  │  - Return execution summary            │ │        │
│  └────────────┬───────────────────────────┘ │        │
│               │                              │        │
│               ▼                              │        │
│  ┌────────────────────────────────────────┐ │        │
│  │  Calendar Scraper Module               │ │        │
│  │  (scraper/villages_calendar.py)        │◄┼────────┘
│  │  - Fetch HTML from calendar            │ │
│  │  - Parse events with BeautifulSoup     │ │
│  │  - Retry logic with backoff            │ │
│  └────────────┬───────────────────────────┘ │
│               │                              │
│               ▼                              │
│  ┌────────────────────────────────────────┐ │
│  │  Event Processor Module                │ │
│  │  (processor/event_processor.py)        │ │
│  │  - Validate event data                 │ │
│  │  - Normalize dates/times               │ │
│  │  - Generate event IDs                  │ │
│  │  - Calculate TTL                       │ │
│  └────────────┬───────────────────────────┘ │
│               │                              │
│               ▼                              │
│  ┌────────────────────────────────────────┐ │
│  │  DynamoDB Manager Module               │ │
│  │  (storage/dynamodb_manager.py)         │ │
│  │  - Compare new vs existing events      │ │
│  │  - Identify adds/updates/deletes       │ │
│  │  - Execute batch operations            │ │
│  └────────────┬───────────────────────────┘ │
│               │                              │
└───────────────┼──────────────────────────────┘
                │ Boto3 SDK
                │
                ▼
┌─────────────────────────────────────────────┐
│         Amazon DynamoDB                     │
│                                             │
│  Table: villages-events                    │
│  - Partition Key: event_id                 │
│  - GSI: date-index (event_date, start_time)│
│  - TTL: ttl (90 days after event)          │
│  - Billing: On-Demand                      │
└─────────────────────────────────────────────┘
                │
                │ Query/Scan
                ▼
┌─────────────────────────────────────────────┐
│         Consumer Applications               │
│         (e.g., Alexa Skill)                 │
└─────────────────────────────────────────────┘
```

### Key Architectural Decisions

1. **Serverless Architecture**: AWS Lambda eliminates server management, provides automatic scaling, and reduces operational overhead
2. **Event-Driven Scheduling**: EventBridge provides reliable, managed scheduling without maintaining cron servers
3. **NoSQL Database**: DynamoDB offers fast key-value lookups optimized for Alexa skill queries
4. **Modular Design**: Separation of concerns (scraping, processing, storage) enables independent testing and maintenance
5. **Infrastructure as Code**: AWS SAM template ensures reproducible deployments and version control of infrastructure

## Component Architecture

### 1. Lambda Handler (`lambda_function.py`)

**Responsibilities**:
- Entry point for Lambda execution
- Initialize structured logging (JSON format)
- Read configuration from environment variables
- Orchestrate module execution flow
- Handle top-level exceptions
- Return execution summary

**Dependencies**:
- `scraper.villages_calendar.VillagesCalendarScraper`
- `processor.event_processor.EventProcessor`
- `storage.dynamodb_manager.DynamoDBManager`

**Configuration**:
- Runtime: Python 3.11
- Memory: 512 MB
- Timeout: 5 minutes (300 seconds)
- Architecture: ARM64 (Graviton2)

### 2. Calendar Scraper Module

**File**: `scraper/villages_calendar.py`

**Class**: `VillagesCalendarScraper`

**Responsibilities**:
- Fetch HTML content from The Villages calendar website
- Parse HTML using BeautifulSoup4
- Extract event information (title, date, time, location, description, category)
- Implement retry logic for network failures
- Handle HTTP timeouts

**Key Methods**:
```python
def fetch_events(self, days_ahead: int = 90) -> List[Event]:
    """
    Fetch events from The Villages calendar.
    
    Args:
        days_ahead: Number of days to fetch events for
        
    Returns:
        List of Event objects
        
    Raises:
        requests.RequestException: If all retry attempts fail
    """
```

**Retry Strategy**:
- Maximum attempts: 3
- Backoff: Exponential (1s, 2s, 4s)
- Timeout: 30 seconds per request
- Retryable errors: Network errors, timeouts, 5xx responses

**Dependencies**:
- `requests`: HTTP client library
- `beautifulsoup4`: HTML parsing library
- `processor.models.Event`: Data class for raw events

### 3. Event Processor Module

**File**: `processor/event_processor.py`

**Class**: `EventProcessor`

**Responsibilities**:
- Validate event data (required fields, formats)
- Normalize dates to ISO 8601 format (YYYY-MM-DD)
- Normalize times to 24-hour format (HH:MM)
- Generate unique event identifiers
- Calculate TTL (90 days after event date)
- Add metadata (last_updated timestamp)
- Filter out invalid events

**Key Methods**:
```python
def process_events(self, raw_events: List[Event]) -> List[ProcessedEvent]:
    """Process and validate raw event data."""

def generate_event_id(self, event: Event) -> str:
    """Generate unique identifier using hash of title + date + time."""
```

**Validation Rules**:
- Required fields: `title`, `date`, `start_time`
- Title: 1-200 characters
- Description: 0-2000 characters
- Date format: Must be parseable to YYYY-MM-DD
- Time format: Must be parseable to HH:MM

**Data Models** (`processor/models.py`):
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

### 4. DynamoDB Manager Module

**File**: `storage/dynamodb_manager.py`

**Class**: `DynamoDBManager`

**Responsibilities**:
- Initialize boto3 DynamoDB client
- Retrieve all existing events from DynamoDB
- Compare new events with existing events
- Identify additions, updates, and deletions
- Execute batch write operations
- Execute batch delete operations
- Handle DynamoDB errors and throttling

**Key Methods**:
```python
def get_all_events(self) -> Dict[str, ProcessedEvent]:
    """Retrieve all events from DynamoDB using Scan operation."""

def sync_events(self, new_events: List[ProcessedEvent]) -> SyncResult:
    """Synchronize events with DynamoDB."""

def batch_write_events(self, events: List[ProcessedEvent]) -> int:
    """Write events in batches of 25 (DynamoDB limit)."""

def batch_delete_events(self, event_ids: List[str]) -> int:
    """Delete events in batches of 25 (DynamoDB limit)."""
```

**Batch Operations**:
- DynamoDB batch limit: 25 items per request
- Automatic batching for large datasets
- Error handling for partial failures
- Retry logic via boto3 automatic retries

## Data Flow

### End-to-End Data Flow

```
1. EventBridge Trigger
   └─> Lambda invoked with scheduled event

2. Lambda Handler Initialization
   ├─> Read environment variables
   ├─> Initialize logging
   └─> Create module instances

3. Calendar Scraping Phase
   ├─> HTTP GET request to The Villages calendar
   ├─> Parse HTML with BeautifulSoup
   ├─> Extract event data
   └─> Return List[Event]

4. Event Processing Phase
   ├─> Validate each event
   ├─> Normalize dates and times
   ├─> Generate event_id (hash)
   ├─> Calculate TTL
   ├─> Filter invalid events
   └─> Return List[ProcessedEvent]

5. Synchronization Phase
   ├─> Scan DynamoDB for existing events
   ├─> Compare new vs existing
   ├─> Identify changes:
   │   ├─> Additions (in new, not in existing)
   │   ├─> Updates (in both, content differs)
   │   └─> Deletions (in existing, not in new)
   ├─> Batch write additions and updates
   ├─> Batch delete removed events
   └─> Return SyncResult

6. Response Generation
   ├─> Log execution summary
   ├─> Return HTTP 200 with statistics
   └─> Lambda execution completes
```

### Data Transformation Pipeline

```
Raw HTML
   │
   ▼ (BeautifulSoup parsing)
Event {
  title: "Live Music at Spanish Springs"
  date: "12/15/2024"
  start_time: "7:00 PM"
  ...
}
   │
   ▼ (Validation & Normalization)
ProcessedEvent {
  event_id: "a3f5b2c1..."
  title: "Live Music at Spanish Springs"
  event_date: "2024-12-15"
  start_time: "19:00"
  ttl: 1739577600
  last_updated: 1702656000
  ...
}
   │
   ▼ (DynamoDB write)
DynamoDB Item {
  "event_id": {"S": "a3f5b2c1..."},
  "title": {"S": "Live Music at Spanish Springs"},
  "event_date": {"S": "2024-12-15"},
  "start_time": {"S": "19:00"},
  "ttl": {"N": "1739577600"},
  ...
}
```

## DynamoDB Schema Design

### Table Configuration

**Table Name**: `villages-events`

**Billing Mode**: On-Demand (PAY_PER_REQUEST)
- Automatically scales with traffic
- No capacity planning required
- Cost-effective for variable workloads

**Primary Key**:
- Partition Key: `event_id` (String)
- No Sort Key (single-item access pattern)

**Attributes**:
```
event_id         String    (PK) Unique identifier (hash of title+date+time)
title            String         Event name
description      String         Event details
event_date       String         ISO 8601 date (YYYY-MM-DD)
start_time       String         24-hour time (HH:MM)
end_time         String         24-hour time (HH:MM) [optional]
location         String         Venue name
category         String         Event category/type
url              String         Link to event details [optional]
last_updated     Number         Unix timestamp of last sync
ttl              Number         Time-to-live for automatic cleanup
```

### Global Secondary Index (GSI)

**Index Name**: `date-index`

**Purpose**: Enable efficient queries by date for Alexa skill

**Key Schema**:
- Partition Key: `event_date` (String)
- Sort Key: `start_time` (String)

**Projection**: ALL (all attributes projected)

**Query Pattern**:
```python
# Get all events on a specific date
response = dynamodb.query(
    TableName='villages-events',
    IndexName='date-index',
    KeyConditionExpression='event_date = :date',
    ExpressionAttributeValues={':date': '2024-12-15'}
)

# Get events on a date within a time range
response = dynamodb.query(
    TableName='villages-events',
    IndexName='date-index',
    KeyConditionExpression='event_date = :date AND start_time BETWEEN :start AND :end',
    ExpressionAttributeValues={
        ':date': '2024-12-15',
        ':start': '18:00',
        ':end': '22:00'
    }
)
```

### Time-to-Live (TTL)

**Attribute**: `ttl`

**Purpose**: Automatically delete events 90 days after they occur

**Calculation**:
```python
event_datetime = datetime.strptime(event_date, '%Y-%m-%d')
ttl_datetime = event_datetime + timedelta(days=90)
ttl = int(ttl_datetime.timestamp())
```

**Benefits**:
- Automatic cleanup without manual intervention
- No cost for TTL deletions
- Keeps table size manageable
- Removes stale data

### Access Patterns

1. **Get event by ID** (Primary Key):
   ```python
   get_item(Key={'event_id': 'abc123'})
   ```

2. **Get all events on a date** (GSI):
   ```python
   query(IndexName='date-index', KeyConditionExpression='event_date = :date')
   ```

3. **Get all events** (Scan - used by sync process):
   ```python
   scan(TableName='villages-events')
   ```

4. **Batch write events**:
   ```python
   batch_write_item(RequestItems={'villages-events': [...]})
   ```

5. **Batch delete events**:
   ```python
   batch_write_item(RequestItems={'villages-events': [DeleteRequest...]})
   ```

## Sync Algorithm

### Overview

The sync algorithm compares new events from the calendar with existing events in DynamoDB to identify additions, updates, and deletions.

### Algorithm Steps

```python
def sync_events(new_events: List[ProcessedEvent]) -> SyncResult:
    # Step 1: Retrieve all existing events from DynamoDB
    existing_events = get_all_events()  # Returns Dict[event_id, ProcessedEvent]
    
    # Step 2: Create lookup sets
    new_event_ids = {event.event_id for event in new_events}
    existing_event_ids = set(existing_events.keys())
    
    # Step 3: Identify additions (in new, not in existing)
    additions = [
        event for event in new_events 
        if event.event_id not in existing_event_ids
    ]
    
    # Step 4: Identify potential updates (in both)
    potential_updates = [
        event for event in new_events 
        if event.event_id in existing_event_ids
    ]
    
    # Step 5: Filter to actual updates (content differs)
    updates = [
        event for event in potential_updates
        if event != existing_events[event.event_id]
    ]
    
    # Step 6: Identify deletions (in existing, not in new)
    deletions = [
        event_id for event_id in existing_event_ids
        if event_id not in new_event_ids
    ]
    
    # Step 7: Execute batch operations
    added_count = batch_write_events(additions)
    updated_count = batch_write_events(updates)
    deleted_count = batch_delete_events(deletions)
    
    # Step 8: Return results
    return SyncResult(
        added=added_count,
        updated=updated_count,
        deleted=deleted_count,
        errors=[]
    )
```

### Comparison Logic

**Event Equality**:
Events are considered equal if all fields match (excluding `last_updated`):
- `event_id`
- `title`
- `description`
- `event_date`
- `start_time`
- `end_time`
- `location`
- `category`
- `url`

**Update Detection**:
An update is detected when:
- `event_id` exists in both new and existing
- Any field (except `last_updated`) differs

### Edge Cases

1. **No changes**: If all events are identical, no operations are performed
2. **All new events**: If DynamoDB is empty, all events are additions
3. **All deleted**: If calendar returns no events, all existing events are deleted
4. **Partial failures**: Failed operations are logged but don't stop processing

## Error Handling Strategy

### Error Categories

#### 1. Network Errors (Calendar Fetch)

**Types**:
- Connection timeouts
- DNS resolution failures
- HTTP 5xx errors
- Network unreachable

**Strategy**:
- Retry with exponential backoff (3 attempts)
- Log each retry attempt
- If all retries fail, exit Lambda with error status
- Preserve existing DynamoDB data

**Implementation**:
```python
for attempt in range(1, 4):
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        if attempt < 3:
            wait_time = 2 ** attempt
            logger.warning(f"Retry {attempt}/3 after {wait_time}s")
            time.sleep(wait_time)
        else:
            logger.error("All retries failed")
            raise
```

#### 2. Parsing Errors (HTML Structure Changes)

**Types**:
- Missing HTML elements
- Unexpected HTML structure
- Invalid data formats

**Strategy**:
- Skip malformed events
- Log parsing errors with context
- Continue processing remaining events
- Return partial results

**Implementation**:
```python
valid_events = []
for raw_event in raw_events:
    try:
        event = parse_event(raw_event)
        valid_events.append(event)
    except ParsingError as e:
        logger.warning(f"Skipped event: {e}")
        continue
return valid_events
```

#### 3. Validation Errors (Invalid Event Data)

**Types**:
- Missing required fields
- Invalid date/time formats
- Data exceeds length limits

**Strategy**:
- Skip invalid events
- Log validation failures with details
- Continue processing valid events
- Track skipped count in summary

**Implementation**:
```python
def process_events(raw_events):
    processed = []
    for event in raw_events:
        if not validate_event(event):
            logger.warning(f"Invalid event: {event.title}")
            continue
        processed.append(normalize_event(event))
    return processed
```

#### 4. DynamoDB Errors

**Types**:
- Throttling (ProvisionedThroughputExceededException)
- Service errors (InternalServerError)
- Item size exceeded
- Conditional check failures

**Strategy**:
- Use boto3 automatic retries with exponential backoff
- Log failed operations
- Continue processing remaining items
- Report failures in sync summary

**Implementation**:
```python
# Boto3 automatic retry configuration
config = Config(
    retries={
        'max_attempts': 3,
        'mode': 'adaptive'
    }
)
dynamodb = boto3.client('dynamodb', config=config)
```

### Logging Strategy

**Log Levels**:
- `DEBUG`: Detailed diagnostic information (disabled in production)
- `INFO`: General informational messages (default)
- `WARNING`: Recoverable issues (skipped events, retries)
- `ERROR`: Failures that prevent completion

**Key Log Events**:
```python
# Lambda start
logger.info("Lambda execution started", extra={
    "request_id": context.request_id,
    "function_name": context.function_name
})

# Calendar fetch
logger.info("Fetching events from calendar", extra={
    "days_ahead": days_ahead
})

# Sync summary
logger.info("Sync completed", extra={
    "added": result.added,
    "updated": result.updated,
    "deleted": result.deleted,
    "duration_ms": duration
})

# Errors
logger.error("Calendar fetch failed", extra={
    "error": str(e),
    "attempts": 3
})
```

### Failure Modes and Recovery

| Failure Mode | Impact | Recovery |
|--------------|--------|----------|
| Calendar unavailable | No sync occurs | Existing data preserved, retry next day |
| Partial parsing failure | Some events skipped | Valid events synced, errors logged |
| DynamoDB throttling | Some operations fail | Boto3 retries, partial sync possible |
| Lambda timeout | Incomplete sync | Existing data preserved, retry next day |
| Invalid credentials | No DynamoDB access | Lambda fails, CloudWatch alarm triggered |

## Monitoring and Alerting

### CloudWatch Metrics

**Built-in Lambda Metrics**:
- `Invocations`: Number of times function is invoked
- `Errors`: Number of invocations that result in errors
- `Duration`: Execution time in milliseconds
- `Throttles`: Number of throttled invocations
- `ConcurrentExecutions`: Number of concurrent executions

**Custom Metrics** (optional):
```python
cloudwatch = boto3.client('cloudwatch')
cloudwatch.put_metric_data(
    Namespace='VillagesEventsSync',
    MetricData=[
        {
            'MetricName': 'EventsSynced',
            'Value': result.added + result.updated,
            'Unit': 'Count'
        },
        {
            'MetricName': 'EventsDeleted',
            'Value': result.deleted,
            'Unit': 'Count'
        }
    ]
)
```

### CloudWatch Logs

**Log Group**: `/aws/lambda/<function-name>`

**Retention**: 30 days (configurable in SAM template)

**Log Insights Queries**:

```sql
# Find all errors in last 24 hours
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc

# Calculate average sync duration
fields @duration
| stats avg(@duration) as avg_duration_ms

# Count events synced per execution
fields @timestamp, added, updated, deleted
| parse @message /added=(?<added>\d+).*updated=(?<updated>\d+).*deleted=(?<deleted>\d+)/
| stats sum(added) as total_added, sum(updated) as total_updated, sum(deleted) as total_deleted
```

### Recommended Alarms

1. **Lambda Errors**:
   ```yaml
   Metric: Errors
   Threshold: > 0
   Period: 1 day
   Action: SNS notification
   ```

2. **Lambda Duration**:
   ```yaml
   Metric: Duration
   Threshold: > 240000 ms (4 minutes)
   Period: 1 invocation
   Action: SNS notification
   ```

3. **DynamoDB Throttling**:
   ```yaml
   Metric: UserErrors (DynamoDB)
   Threshold: > 10
   Period: 5 minutes
   Action: SNS notification
   ```

### Monitoring Dashboard

Create a CloudWatch dashboard with:
- Lambda invocation count (last 7 days)
- Lambda error rate (last 7 days)
- Lambda duration trend (last 7 days)
- DynamoDB item count (current)
- DynamoDB read/write capacity (last 24 hours)

## Security Architecture

### IAM Permissions (Least Privilege)

**Lambda Execution Role**:
```yaml
Policies:
  - PolicyName: DynamoDBAccess
    PolicyDocument:
      Statement:
        - Effect: Allow
          Action:
            - dynamodb:PutItem
            - dynamodb:GetItem
            - dynamodb:Scan
            - dynamodb:DeleteItem
            - dynamodb:BatchWriteItem
          Resource:
            - !GetAtt VillagesEventsTable.Arn
  
  - PolicyName: CloudWatchLogs
    PolicyDocument:
      Statement:
        - Effect: Allow
          Action:
            - logs:CreateLogGroup
            - logs:CreateLogStream
            - logs:PutLogEvents
          Resource:
            - !Sub "arn:aws:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/*"
```

**Key Security Principles**:
- No wildcard permissions
- Scoped to specific table ARN
- No cross-account access
- No VPC access (not required)

### Data Security

**Encryption at Rest**:
- DynamoDB: AWS-managed encryption keys (default)
- CloudWatch Logs: Encrypted by default

**Encryption in Transit**:
- HTTPS for calendar website
- AWS SDK uses TLS for all API calls

**Sensitive Data**:
- No PII or sensitive data in events
- No API keys or secrets required
- No credentials stored in code

### Network Security

**Lambda Network**:
- Runs in AWS-managed VPC
- No custom VPC required
- Outbound internet access for calendar fetch

**DynamoDB Access**:
- Private AWS network (no internet exposure)
- IAM-based authentication
- No public endpoints

## Performance Considerations

### Lambda Performance

**Cold Start Optimization**:
- Deployment package size: < 10 MB
- Minimal dependencies
- ARM64 architecture (faster cold starts)
- No heavy initialization in global scope

**Memory Allocation**:
- Configured: 512 MB
- Typical usage: 200-300 MB
- Provides headroom for large event sets

**Execution Time**:
- Typical: 30-60 seconds
- Maximum: 300 seconds (5 minutes)
- Factors: Network latency, event count, DynamoDB operations

### DynamoDB Performance

**Read Performance**:
- On-demand mode: Automatically scales
- Scan operation: Efficient for small tables (< 10,000 items)
- GSI queries: Sub-millisecond latency

**Write Performance**:
- Batch writes: 25 items per request
- On-demand mode: No throttling under normal load
- Typical sync: 100-500 events in 5-10 seconds

**Optimization Strategies**:
- Use batch operations (25 items per batch)
- Parallel batch requests (if needed)
- Efficient comparison logic (hash-based)

### Scalability

**Current Scale**:
- Events per sync: 100-1,000
- Sync frequency: Once per day
- DynamoDB items: 500-2,000

**Future Scale Considerations**:
- If events > 10,000: Consider pagination for Scan
- If sync frequency increases: Monitor Lambda concurrency
- If query load increases: Monitor GSI performance

### Cost Optimization

**Lambda Costs**:
- ARM64 architecture: 20% cheaper than x86
- Right-sized memory: 512 MB balances performance and cost
- Minimal execution time: Efficient code reduces duration

**DynamoDB Costs**:
- On-demand billing: Pay only for actual usage
- TTL deletions: Free (no write capacity consumed)
- Efficient batch operations: Minimize request count

**Estimated Monthly Costs** (typical usage):
- Lambda: $0.50 - $1.00
- DynamoDB: $1.00 - $3.00
- CloudWatch Logs: $0.50
- **Total: $2.00 - $5.00 per month**

## Conclusion

This architecture provides a robust, scalable, and cost-effective solution for synchronizing event data from The Villages calendar to DynamoDB. The serverless design eliminates operational overhead while maintaining high reliability and performance.

Key architectural strengths:
- Fully managed services (no servers to maintain)
- Automatic scaling and high availability
- Comprehensive error handling and logging
- Security best practices (least privilege, encryption)
- Cost-optimized design (< $5/month)
- Modular and testable codebase

For implementation details, see [DEVELOPER.md](DEVELOPER.md).
