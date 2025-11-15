"""AWS Lambda handler for Villages Events Calendar Sync."""
import json
import logging
import os
import time
from typing import Dict, Any

from scraper.villages_calendar import VillagesCalendarScraper
from processor.event_processor import EventProcessor
from storage.dynamodb_manager import DynamoDBManager


# Configure JSON logging
class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'message': record.getMessage(),
            'logger': record.name
        }
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def setup_logging(log_level: str = 'INFO') -> None:
    """
    Configure logging with JSON formatter.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    root_logger = logging.getLogger()
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create new handler with JSON formatter
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)
    
    # Set log level
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler function for Villages Events Calendar Sync.
    
    Args:
        event: EventBridge event payload
        context: Lambda context object
        
    Returns:
        Response dict with statusCode and summary statistics
    """
    # Read configuration from environment variables
    table_name = os.environ.get('TABLE_NAME', 'villages-events')
    log_level = os.environ.get('LOG_LEVEL', 'INFO')
    days_ahead = int(os.environ.get('DAYS_AHEAD', '90'))
    timeout_seconds = int(os.environ.get('TIMEOUT_SECONDS', '30'))
    
    # Initialize logging
    setup_logging(log_level)
    logger = logging.getLogger(__name__)
    
    # Log Lambda execution start
    start_time = time.time()
    logger.info(
        f"Lambda execution started",
        extra={
            'table_name': table_name,
            'days_ahead': days_ahead,
            'timeout_seconds': timeout_seconds
        }
    )
    
    try:
        # Instantiate components
        scraper = VillagesCalendarScraper(timeout=timeout_seconds)
        processor = EventProcessor()
        dynamodb_manager = DynamoDBManager(table_name=table_name)
        
        # Fetch events from calendar with error handling
        try:
            logger.info("Fetching events from calendar")
            raw_events = scraper.fetch_events(days_ahead=days_ahead)
            logger.info(f"Fetched {len(raw_events)} raw events from calendar")
        except Exception as e:
            # Log network/fetch errors and exit with error status
            logger.error(
                f"Failed to fetch events from calendar after retries: {str(e)}",
                extra={'error_type': type(e).__name__},
                exc_info=True
            )
            duration = time.time() - start_time
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'message': 'Failed to fetch calendar events',
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'duration_seconds': round(duration, 2)
                })
            }
        
        # Process and validate events
        logger.info("Processing and validating events")
        processed_events = processor.process_events(raw_events)
        logger.info(f"Processed {len(processed_events)} valid events")
        
        # Synchronize with DynamoDB with error handling
        try:
            logger.info("Synchronizing events with DynamoDB")
            sync_result = dynamodb_manager.sync_events(processed_events)
        except Exception as e:
            # Log DynamoDB errors but don't delete existing events
            logger.error(
                f"Error during DynamoDB sync operation: {str(e)}",
                extra={'error_type': type(e).__name__},
                exc_info=True
            )
            duration = time.time() - start_time
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'message': 'Failed to sync events with DynamoDB',
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'note': 'Previous events remain in DynamoDB',
                    'duration_seconds': round(duration, 2)
                })
            }
        
        # Calculate execution duration
        duration = time.time() - start_time
        
        # Log execution summary
        logger.info(
            f"Lambda execution completed successfully",
            extra={
                'duration_seconds': round(duration, 2),
                'events_added': sync_result.added,
                'events_updated': sync_result.updated,
                'events_deleted': sync_result.deleted,
                'errors': sync_result.errors
            }
        )
        
        # Return success response
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Sync completed successfully',
                'statistics': {
                    'raw_events_fetched': len(raw_events),
                    'valid_events_processed': len(processed_events),
                    'events_added': sync_result.added,
                    'events_updated': sync_result.updated,
                    'events_deleted': sync_result.deleted,
                    'duration_seconds': round(duration, 2)
                },
                'errors': sync_result.errors
            })
        }
        
    except Exception as e:
        # Calculate execution duration
        duration = time.time() - start_time
        
        # Log error
        logger.error(
            f"Lambda execution failed: {str(e)}",
            extra={
                'duration_seconds': round(duration, 2),
                'error_type': type(e).__name__
            },
            exc_info=True
        )
        
        # Return error response
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Sync failed',
                'error': str(e),
                'error_type': type(e).__name__,
                'duration_seconds': round(duration, 2)
            })
        }
