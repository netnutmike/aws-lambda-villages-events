"""Integration tests for Lambda handler."""
import json
import os
from unittest.mock import Mock, patch, MagicMock
import pytest

from lambda_function import lambda_handler, setup_logging
from processor.models import Event, ProcessedEvent, SyncResult


@pytest.fixture
def mock_env():
    """Set up environment variables for testing."""
    env_vars = {
        'TABLE_NAME': 'test-villages-events',
        'LOG_LEVEL': 'INFO',
        'DAYS_AHEAD': '90',
        'TIMEOUT_SECONDS': '30'
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def mock_context():
    """Create a mock Lambda context."""
    context = Mock()
    context.function_name = 'test-function'
    context.memory_limit_in_mb = 512
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-function'
    context.aws_request_id = 'test-request-id'
    return context


@pytest.fixture
def sample_raw_events():
    """Create sample raw events."""
    return [
        Event(
            title='Test Event 1',
            date='2024-01-15',
            start_time='10:00 AM',
            end_time='12:00 PM',
            location='Test Location 1',
            description='Test Description 1',
            category='Entertainment',
            url='https://example.com/event1'
        ),
        Event(
            title='Test Event 2',
            date='2024-01-16',
            start_time='2:00 PM',
            end_time='4:00 PM',
            location='Test Location 2',
            description='Test Description 2',
            category='Sports',
            url='https://example.com/event2'
        )
    ]


@pytest.fixture
def sample_processed_events():
    """Create sample processed events."""
    return [
        ProcessedEvent(
            event_id='event1_id',
            title='Test Event 1',
            description='Test Description 1',
            event_date='2024-01-15',
            start_time='10:00',
            end_time='12:00',
            location='Test Location 1',
            category='Entertainment',
            url='https://example.com/event1',
            last_updated=1234567890,
            ttl=1234567890
        ),
        ProcessedEvent(
            event_id='event2_id',
            title='Test Event 2',
            description='Test Description 2',
            event_date='2024-01-16',
            start_time='14:00',
            end_time='16:00',
            location='Test Location 2',
            category='Sports',
            url='https://example.com/event2',
            last_updated=1234567890,
            ttl=1234567890
        )
    ]


class TestLambdaHandler:
    """Test cases for Lambda handler."""
    
    @patch('lambda_function.DynamoDBManager')
    @patch('lambda_function.EventProcessor')
    @patch('lambda_function.VillagesCalendarScraper')
    def test_successful_sync(
        self,
        mock_scraper_class,
        mock_processor_class,
        mock_dynamodb_class,
        mock_env,
        mock_context,
        sample_raw_events,
        sample_processed_events
    ):
        """Test successful end-to-end sync process."""
        # Setup mocks
        mock_scraper = Mock()
        mock_scraper.fetch_events.return_value = sample_raw_events
        mock_scraper_class.return_value = mock_scraper
        
        mock_processor = Mock()
        mock_processor.process_events.return_value = sample_processed_events
        mock_processor_class.return_value = mock_processor
        
        mock_dynamodb = Mock()
        mock_dynamodb.sync_events.return_value = SyncResult(
            added=2,
            updated=0,
            deleted=0,
            errors=[]
        )
        mock_dynamodb_class.return_value = mock_dynamodb
        
        # Execute Lambda handler
        event = {}
        response = lambda_handler(event, mock_context)
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['message'] == 'Sync completed successfully'
        assert body['statistics']['raw_events_fetched'] == 2
        assert body['statistics']['valid_events_processed'] == 2
        assert body['statistics']['events_added'] == 2
        assert body['statistics']['events_updated'] == 0
        assert body['statistics']['events_deleted'] == 0
        assert 'duration_seconds' in body['statistics']
        
        # Verify component interactions
        mock_scraper.fetch_events.assert_called_once_with(days_ahead=90)
        mock_processor.process_events.assert_called_once_with(sample_raw_events)
        mock_dynamodb.sync_events.assert_called_once_with(sample_processed_events)
    
    @patch('lambda_function.DynamoDBManager')
    @patch('lambda_function.EventProcessor')
    @patch('lambda_function.VillagesCalendarScraper')
    def test_calendar_fetch_failure(
        self,
        mock_scraper_class,
        mock_processor_class,
        mock_dynamodb_class,
        mock_env,
        mock_context
    ):
        """Test error handling for calendar fetch failures."""
        # Setup mock to raise exception
        mock_scraper = Mock()
        mock_scraper.fetch_events.side_effect = Exception('Network error')
        mock_scraper_class.return_value = mock_scraper
        
        # Execute Lambda handler
        event = {}
        response = lambda_handler(event, mock_context)
        
        # Verify error response
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['message'] == 'Failed to fetch calendar events'
        assert 'Network error' in body['error']
        assert body['error_type'] == 'Exception'
        assert 'duration_seconds' in body
        
        # Verify processor was instantiated but not used, and DynamoDB sync was not called
        mock_processor_class.assert_called_once()
        mock_dynamodb_class.assert_called_once()
        # The sync_events method should not be called
        assert not mock_dynamodb_class.return_value.sync_events.called
    
    @patch('lambda_function.DynamoDBManager')
    @patch('lambda_function.EventProcessor')
    @patch('lambda_function.VillagesCalendarScraper')
    def test_dynamodb_sync_failure(
        self,
        mock_scraper_class,
        mock_processor_class,
        mock_dynamodb_class,
        mock_env,
        mock_context,
        sample_raw_events,
        sample_processed_events
    ):
        """Test error handling for DynamoDB sync failures."""
        # Setup mocks
        mock_scraper = Mock()
        mock_scraper.fetch_events.return_value = sample_raw_events
        mock_scraper_class.return_value = mock_scraper
        
        mock_processor = Mock()
        mock_processor.process_events.return_value = sample_processed_events
        mock_processor_class.return_value = mock_processor
        
        mock_dynamodb = Mock()
        mock_dynamodb.sync_events.side_effect = Exception('DynamoDB error')
        mock_dynamodb_class.return_value = mock_dynamodb
        
        # Execute Lambda handler
        event = {}
        response = lambda_handler(event, mock_context)
        
        # Verify error response
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['message'] == 'Failed to sync events with DynamoDB'
        assert 'DynamoDB error' in body['error']
        assert body['error_type'] == 'Exception'
        assert body['note'] == 'Previous events remain in DynamoDB'
        assert 'duration_seconds' in body
        
        # Verify scraper and processor were called
        mock_scraper.fetch_events.assert_called_once()
        mock_processor.process_events.assert_called_once()
    
    @patch('lambda_function.DynamoDBManager')
    @patch('lambda_function.EventProcessor')
    @patch('lambda_function.VillagesCalendarScraper')
    def test_sync_with_updates_and_deletions(
        self,
        mock_scraper_class,
        mock_processor_class,
        mock_dynamodb_class,
        mock_env,
        mock_context,
        sample_raw_events,
        sample_processed_events
    ):
        """Test sync process with additions, updates, and deletions."""
        # Setup mocks
        mock_scraper = Mock()
        mock_scraper.fetch_events.return_value = sample_raw_events
        mock_scraper_class.return_value = mock_scraper
        
        mock_processor = Mock()
        mock_processor.process_events.return_value = sample_processed_events
        mock_processor_class.return_value = mock_processor
        
        mock_dynamodb = Mock()
        mock_dynamodb.sync_events.return_value = SyncResult(
            added=1,
            updated=1,
            deleted=2,
            errors=[]
        )
        mock_dynamodb_class.return_value = mock_dynamodb
        
        # Execute Lambda handler
        event = {}
        response = lambda_handler(event, mock_context)
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['statistics']['events_added'] == 1
        assert body['statistics']['events_updated'] == 1
        assert body['statistics']['events_deleted'] == 2
    
    @patch('lambda_function.DynamoDBManager')
    @patch('lambda_function.EventProcessor')
    @patch('lambda_function.VillagesCalendarScraper')
    @patch('lambda_function.setup_logging')
    def test_logging_output(
        self,
        mock_setup_logging,
        mock_scraper_class,
        mock_processor_class,
        mock_dynamodb_class,
        mock_env,
        mock_context,
        sample_raw_events,
        sample_processed_events,
        caplog
    ):
        """Test that logging output is generated correctly."""
        # Setup logging to use standard formatter for testing
        import logging
        logger = logging.getLogger('lambda_function')
        logger.setLevel(logging.INFO)
        
        # Setup mocks
        mock_scraper = Mock()
        mock_scraper.fetch_events.return_value = sample_raw_events
        mock_scraper_class.return_value = mock_scraper
        
        mock_processor = Mock()
        mock_processor.process_events.return_value = sample_processed_events
        mock_processor_class.return_value = mock_processor
        
        mock_dynamodb = Mock()
        mock_dynamodb.sync_events.return_value = SyncResult(
            added=2,
            updated=0,
            deleted=0,
            errors=[]
        )
        mock_dynamodb_class.return_value = mock_dynamodb
        
        # Execute Lambda handler
        event = {}
        with caplog.at_level(logging.INFO, logger='lambda_function'):
            response = lambda_handler(event, mock_context)
        
        # Verify logging output
        assert response['statusCode'] == 200
        log_messages = [record.message for record in caplog.records]
        assert any('Lambda execution started' in msg for msg in log_messages)
        assert any('Fetching events from calendar' in msg for msg in log_messages)
        assert any('Processing and validating events' in msg for msg in log_messages)
        assert any('Synchronizing events with DynamoDB' in msg for msg in log_messages)
        assert any('Lambda execution completed successfully' in msg for msg in log_messages)


class TestSetupLogging:
    """Test cases for logging setup."""
    
    def test_setup_logging_default_level(self):
        """Test logging setup with default INFO level."""
        setup_logging()
        logger = __import__('logging').getLogger()
        assert logger.level == __import__('logging').INFO
    
    def test_setup_logging_debug_level(self):
        """Test logging setup with DEBUG level."""
        setup_logging('DEBUG')
        logger = __import__('logging').getLogger()
        assert logger.level == __import__('logging').DEBUG
    
    def test_setup_logging_error_level(self):
        """Test logging setup with ERROR level."""
        setup_logging('ERROR')
        logger = __import__('logging').getLogger()
        assert logger.level == __import__('logging').ERROR
