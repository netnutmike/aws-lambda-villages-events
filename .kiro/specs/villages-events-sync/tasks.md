# Implementation Plan

- [x] 1. Set up project structure and configuration files
  - Create directory structure for Lambda function (scraper/, processor/, storage/, tests/)
  - Create requirements.txt with core dependencies (boto3, requests, beautifulsoup4)
  - Create .gitignore file excluding Python cache, virtual environments, and AWS artifacts
  - Create Renovate configuration file (renovate.json) for automated dependency updates
  - _Requirements: 4.1, 4.2, 7.5_

- [x] 2. Implement calendar scraper module
  - [x] 2.1 Create VillagesCalendarScraper class in scraper/villages_calendar.py
    - Adapt logic from python-villages-events repository to fetch calendar HTML
    - Implement fetch_events() method with configurable days_ahead parameter
    - Parse HTML using BeautifulSoup4 to extract event data (title, date, time, location, description, category)
    - Return list of Event dataclass objects
    - _Requirements: 1.1_
  
  - [x] 2.2 Add retry logic with exponential backoff for HTTP requests
    - Implement 3 retry attempts with exponential backoff for network failures
    - Configure 30-second timeout for HTTP requests
    - Log retry attempts and final failures
    - _Requirements: 6.1_
  
  - [x] 2.3 Write unit tests for calendar scraper
    - Mock HTTP responses using responses library
    - Test successful event parsing
    - Test retry logic on network failures
    - Test timeout handling
    - _Requirements: 1.1, 6.1_

- [x] 3. Implement event processor module
  - [x] 3.1 Create Event and ProcessedEvent dataclasses in processor/models.py
    - Define Event dataclass with raw calendar fields
    - Define ProcessedEvent dataclass with normalized fields including event_id, ttl
    - Define SyncResult dataclass for sync operation results
    - _Requirements: 1.2, 2.5_
  
  - [x] 3.2 Create EventProcessor class in processor/event_processor.py
    - Implement process_events() method to validate and normalize event data
    - Implement generate_event_id() method using hash of title + date + time
    - Validate required fields (title, date, start_time)
    - Normalize date to ISO 8601 format (YYYY-MM-DD)
    - Normalize time to 24-hour format (HH:MM)
    - Calculate TTL as 90 days after event_date
    - Add last_updated timestamp
    - Skip invalid events and log validation errors
    - _Requirements: 1.2, 2.5, 6.4_
  
  - [x] 3.3 Write unit tests for event processor
    - Test event validation logic for required fields
    - Test event_id generation consistency
    - Test date/time normalization
    - Test TTL calculation
    - Test handling of invalid events
    - _Requirements: 1.2, 2.5_

- [x] 4. Implement DynamoDB manager module
  - [x] 4.1 Create DynamoDBManager class in storage/dynamodb_manager.py
    - Initialize boto3 DynamoDB client and table reference in __init__()
    - Implement get_all_events() method using Scan operation
    - Return dictionary mapping event_id to ProcessedEvent objects
    - _Requirements: 2.1, 2.5_
  
  - [x] 4.2 Implement sync logic in sync_events() method
    - Compare new events from calendar with existing events from DynamoDB
    - Identify events to add (in new, not in existing)
    - Identify events to update (in both, but content differs)
    - Identify events to delete (in existing, not in new)
    - Call batch_write_events() for additions and updates
    - Call batch_delete_events() for deletions
    - Return SyncResult with counts and any errors
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  
  - [x] 4.3 Implement batch operations for DynamoDB
    - Implement batch_write_events() to write in batches of 25 items
    - Implement batch_delete_events() to delete in batches of 25 items
    - Handle DynamoDB throttling with boto3 automatic retries
    - Log failed operations and continue processing
    - Return count of successful operations
    - _Requirements: 2.2, 2.3, 2.4, 6.2_
  
  - [x] 4.4 Write unit tests for DynamoDB manager
    - Mock boto3 DynamoDB client using moto library
    - Test get_all_events() retrieval
    - Test sync logic for additions, updates, deletions
    - Test batch operations
    - Test error handling for DynamoDB failures
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 6.2_

- [x] 5. Implement Lambda handler
  - [x] 5.1 Create lambda_function.py with lambda_handler entry point
    - Initialize Python logging with JSON formatter
    - Read configuration from environment variables (TABLE_NAME, LOG_LEVEL, DAYS_AHEAD, TIMEOUT_SECONDS)
    - Log Lambda execution start with timestamp
    - Instantiate VillagesCalendarScraper, EventProcessor, and DynamoDBManager
    - Call scraper.fetch_events() to retrieve calendar data
    - Call processor.process_events() to validate and normalize events
    - Call dynamodb_manager.sync_events() to synchronize with DynamoDB
    - Log execution summary with counts of added, updated, deleted events
    - Log Lambda execution end with duration
    - Return response dict with statusCode 200 and summary statistics
    - _Requirements: 1.1, 1.2, 1.5, 6.3, 6.4, 7.1_
  
  - [x] 5.2 Implement error handling in Lambda handler
    - Wrap calendar fetch in try-except to catch and log network errors
    - Exit with error status if calendar fetch fails after retries
    - Wrap DynamoDB operations in try-except to log errors
    - Ensure previous events remain in DynamoDB if sync fails
    - Return response dict with statusCode 500 and error details on failure
    - _Requirements: 6.1, 6.2, 6.5_
  
  - [x] 5.3 Write integration tests for Lambda handler
    - Test end-to-end sync process with mocked calendar and DynamoDB
    - Test error handling for calendar fetch failures
    - Test error handling for DynamoDB failures
    - Verify logging output
    - _Requirements: 1.1, 1.2, 6.1, 6.2_

- [x] 6. Create AWS SAM infrastructure template
  - [x] 6.1 Create template.yaml with SAM resources
    - Define Parameters for Environment and ScheduleExpression
    - Define VillagesEventsFunction Lambda resource with Python 3.11 runtime
    - Configure Lambda with 512 MB memory, 5 minute timeout, arm64 architecture
    - Define environment variables (TABLE_NAME, LOG_LEVEL, DAYS_AHEAD, TIMEOUT_SECONDS)
    - Define VillagesEventsTable DynamoDB resource with on-demand billing
    - Configure table with event_id as partition key
    - Define GSI (date-index) with event_date as partition key and start_time as sort key
    - Configure TTL attribute on ttl field
    - Define VillagesEventsFunctionRole IAM role with least privilege permissions
    - Grant DynamoDB permissions (PutItem, GetItem, Scan, DeleteItem) on villages-events table only
    - Grant CloudWatch Logs permissions (CreateLogGroup, CreateLogStream, PutLogEvents)
    - Define DailyScheduleRule EventBridge rule with cron expression
    - Define DailySchedulePermission to allow EventBridge to invoke Lambda
    - Define Outputs for FunctionArn, TableName, and ScheduleExpression
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 7.1, 7.2, 7.3_
  
  - [x] 6.2 Create samconfig.toml for deployment configuration
    - Configure default deployment parameters (region, stack name, capabilities)
    - Set confirm_changeset to true for safety
    - Configure S3 bucket for deployment artifacts
    - _Requirements: 3.1, 3.5_

- [x] 7. Create deployment automation scripts
  - [x] 7.1 Create deploy.sh script for building and deploying
    - Install Python dependencies to .aws-sam/build directory
    - Run sam build to package Lambda function
    - Run sam validate to check template syntax
    - Run sam deploy with guided or configured parameters
    - Output deployment results and stack outputs
    - _Requirements: 3.5_
  
  - [x] 7.2 Create local-test.sh script for local testing
    - Start DynamoDB Local or use LocalStack
    - Run sam local invoke with test event payload
    - Display Lambda output and logs
    - _Requirements: 3.5_

- [x] 8. Create comprehensive documentation
  - [x] 8.1 Create README.md with project overview
    - Describe application purpose and architecture
    - List key features and AWS services used
    - Include architecture diagram
    - Provide quick start deployment instructions
    - Link to detailed developer documentation
    - Include troubleshooting section for common issues
    - _Requirements: 5.1, 5.5_
  
  - [x] 8.2 Create DEVELOPER.md with detailed developer documentation
    - Document project structure and key components
    - Explain code organization (scraper, processor, storage modules)
    - Document all environment variables and configuration options
    - Provide local development setup instructions (Python virtual environment, dependencies)
    - Document how to run unit tests and integration tests
    - Document deployment process step-by-step
    - Include troubleshooting guide for deployment issues
    - Document how to manually trigger Lambda function for testing
    - Document how to query DynamoDB table for verification
    - _Requirements: 5.2, 5.3, 5.4, 5.5_
  
  - [x] 8.3 Create ARCHITECTURE.md with technical architecture details
    - Document high-level architecture with component diagrams
    - Explain data flow from calendar to DynamoDB
    - Document DynamoDB table schema and GSI design
    - Explain sync algorithm and logic
    - Document error handling strategies
    - Document monitoring and alerting approach
    - _Requirements: 5.1, 5.2_

- [x] 9. Configure Renovate for dependency management
  - [x] 9.1 Create renovate.json configuration file
    - Enable Renovate bot for the repository
    - Configure weekly schedule for dependency checks
    - Group Python dependencies together
    - Configure auto-merge for minor and patch updates
    - Set up PR creation for major updates requiring review
    - Configure commit message format
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 10. Create example configuration and helper files
  - [x] 10.1 Create .env.example file with sample environment variables
    - Document all required environment variables
    - Provide example values for local development
    - Include comments explaining each variable
    - _Requirements: 5.4, 7.1_
  
  - [x] 10.2 Create event.json with sample EventBridge event payload
    - Create test event for local Lambda invocation
    - Include realistic event structure
    - _Requirements: 3.5_
