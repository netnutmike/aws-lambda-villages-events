"""Unit tests for DynamoDB manager."""
import time
from datetime import datetime, timedelta

import boto3
import pytest
from moto import mock_aws

from processor.models import ProcessedEvent, SyncResult
from storage.dynamodb_manager import DynamoDBManager


@pytest.fixture
def dynamodb_table():
    """Create a mock DynamoDB table for testing."""
    with mock_aws():
        # Create DynamoDB resource
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        # Create table
        table = dynamodb.create_table(
            TableName='test-villages-events',
            KeySchema=[
                {'AttributeName': 'event_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'event_id', 'AttributeType': 'S'},
                {'AttributeName': 'event_date', 'AttributeType': 'S'},
                {'AttributeName': 'start_time', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'date-index',
                    'KeySchema': [
                        {'AttributeName': 'event_date', 'KeyType': 'HASH'},
                        {'AttributeName': 'start_time', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
            ],
            BillingMode='PROVISIONED',
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        
        yield table


@pytest.fixture
def dynamodb_manager(dynamodb_table):
    """Create DynamoDBManager instance with mock table."""
    return DynamoDBManager('test-villages-events')


@pytest.fixture
def sample_event():
    """Create a sample ProcessedEvent for testing."""
    event_date = datetime.now().strftime('%Y-%m-%d')
    ttl = int((datetime.now() + timedelta(days=90)).timestamp())
    
    return ProcessedEvent(
        event_id='test-event-123',
        title='Test Event',
        description='This is a test event',
        event_date=event_date,
        start_time='14:00',
        end_time='16:00',
        location='Test Location',
        category='Test Category',
        url='https://example.com/event',
        last_updated=int(time.time()),
        ttl=ttl
    )


def test_get_all_events_empty_table(dynamodb_manager):
    """Test get_all_events returns empty dict for empty table."""
    events = dynamodb_manager.get_all_events()
    assert events == {}


def test_get_all_events_with_data(dynamodb_manager, sample_event):
    """Test get_all_events retrieves events from table."""
    # Add event to table
    dynamodb_manager.batch_write_events([sample_event])
    
    # Retrieve events
    events = dynamodb_manager.get_all_events()
    
    assert len(events) == 1
    assert sample_event.event_id in events
    retrieved_event = events[sample_event.event_id]
    assert retrieved_event.title == sample_event.title
    assert retrieved_event.event_date == sample_event.event_date


def test_batch_write_events_single(dynamodb_manager, sample_event):
    """Test batch_write_events with single event."""
    count = dynamodb_manager.batch_write_events([sample_event])
    
    assert count == 1
    
    # Verify event was written
    events = dynamodb_manager.get_all_events()
    assert len(events) == 1
    assert sample_event.event_id in events


def test_batch_write_events_multiple(dynamodb_manager):
    """Test batch_write_events with multiple events."""
    events = []
    for i in range(10):
        event_date = datetime.now().strftime('%Y-%m-%d')
        ttl = int((datetime.now() + timedelta(days=90)).timestamp())
        
        event = ProcessedEvent(
            event_id=f'test-event-{i}',
            title=f'Test Event {i}',
            description=f'Description {i}',
            event_date=event_date,
            start_time=f'{10 + i}:00',
            end_time=f'{12 + i}:00',
            location=f'Location {i}',
            category='Test',
            url=None,
            last_updated=int(time.time()),
            ttl=ttl
        )
        events.append(event)
    
    count = dynamodb_manager.batch_write_events(events)
    
    assert count == 10
    
    # Verify all events were written
    retrieved_events = dynamodb_manager.get_all_events()
    assert len(retrieved_events) == 10


def test_batch_write_events_large_batch(dynamodb_manager):
    """Test batch_write_events with more than 25 events (batch limit)."""
    events = []
    for i in range(30):
        event_date = datetime.now().strftime('%Y-%m-%d')
        ttl = int((datetime.now() + timedelta(days=90)).timestamp())
        
        event = ProcessedEvent(
            event_id=f'test-event-{i}',
            title=f'Test Event {i}',
            description=f'Description {i}',
            event_date=event_date,
            start_time='10:00',
            end_time='12:00',
            location='Test Location',
            category='Test',
            url=None,
            last_updated=int(time.time()),
            ttl=ttl
        )
        events.append(event)
    
    count = dynamodb_manager.batch_write_events(events)
    
    assert count == 30
    
    # Verify all events were written
    retrieved_events = dynamodb_manager.get_all_events()
    assert len(retrieved_events) == 30


def test_batch_delete_events(dynamodb_manager, sample_event):
    """Test batch_delete_events removes events from table."""
    # Add event first
    dynamodb_manager.batch_write_events([sample_event])
    
    # Verify event exists
    events = dynamodb_manager.get_all_events()
    assert len(events) == 1
    
    # Delete event
    count = dynamodb_manager.batch_delete_events([sample_event.event_id])
    
    assert count == 1
    
    # Verify event was deleted
    events = dynamodb_manager.get_all_events()
    assert len(events) == 0


def test_batch_delete_events_multiple(dynamodb_manager):
    """Test batch_delete_events with multiple events."""
    # Add multiple events
    events = []
    event_ids = []
    for i in range(10):
        event_date = datetime.now().strftime('%Y-%m-%d')
        ttl = int((datetime.now() + timedelta(days=90)).timestamp())
        
        event = ProcessedEvent(
            event_id=f'test-event-{i}',
            title=f'Test Event {i}',
            description=f'Description {i}',
            event_date=event_date,
            start_time='10:00',
            end_time='12:00',
            location='Test Location',
            category='Test',
            url=None,
            last_updated=int(time.time()),
            ttl=ttl
        )
        events.append(event)
        event_ids.append(event.event_id)
    
    dynamodb_manager.batch_write_events(events)
    
    # Delete all events
    count = dynamodb_manager.batch_delete_events(event_ids)
    
    assert count == 10
    
    # Verify all events were deleted
    retrieved_events = dynamodb_manager.get_all_events()
    assert len(retrieved_events) == 0


def test_sync_events_add_new(dynamodb_manager, sample_event):
    """Test sync_events adds new events."""
    result = dynamodb_manager.sync_events([sample_event])
    
    assert result.added == 1
    assert result.updated == 0
    assert result.deleted == 0
    assert len(result.errors) == 0
    
    # Verify event was added
    events = dynamodb_manager.get_all_events()
    assert len(events) == 1


def test_sync_events_update_existing(dynamodb_manager, sample_event):
    """Test sync_events updates existing events when content differs."""
    # Add initial event
    dynamodb_manager.batch_write_events([sample_event])
    
    # Create updated version
    updated_event = ProcessedEvent(
        event_id=sample_event.event_id,
        title='Updated Title',
        description=sample_event.description,
        event_date=sample_event.event_date,
        start_time=sample_event.start_time,
        end_time=sample_event.end_time,
        location=sample_event.location,
        category=sample_event.category,
        url=sample_event.url,
        last_updated=int(time.time()),
        ttl=sample_event.ttl
    )
    
    result = dynamodb_manager.sync_events([updated_event])
    
    assert result.added == 0
    assert result.updated == 1
    assert result.deleted == 0
    
    # Verify event was updated
    events = dynamodb_manager.get_all_events()
    assert events[sample_event.event_id].title == 'Updated Title'


def test_sync_events_delete_removed(dynamodb_manager, sample_event):
    """Test sync_events deletes events not in new list."""
    # Add initial event
    dynamodb_manager.batch_write_events([sample_event])
    
    # Sync with empty list (event should be deleted)
    result = dynamodb_manager.sync_events([])
    
    assert result.added == 0
    assert result.updated == 0
    assert result.deleted == 1
    
    # Verify event was deleted
    events = dynamodb_manager.get_all_events()
    assert len(events) == 0


def test_sync_events_mixed_operations(dynamodb_manager):
    """Test sync_events with add, update, and delete operations."""
    # Add initial events
    event1 = ProcessedEvent(
        event_id='event-1',
        title='Event 1',
        description='Description 1',
        event_date='2024-01-01',
        start_time='10:00',
        end_time='12:00',
        location='Location 1',
        category='Category 1',
        url=None,
        last_updated=int(time.time()),
        ttl=int((datetime.now() + timedelta(days=90)).timestamp())
    )
    
    event2 = ProcessedEvent(
        event_id='event-2',
        title='Event 2',
        description='Description 2',
        event_date='2024-01-02',
        start_time='14:00',
        end_time='16:00',
        location='Location 2',
        category='Category 2',
        url=None,
        last_updated=int(time.time()),
        ttl=int((datetime.now() + timedelta(days=90)).timestamp())
    )
    
    dynamodb_manager.batch_write_events([event1, event2])
    
    # Create new event list:
    # - event1 with updated title (update)
    # - event3 (new, add)
    # - event2 not included (delete)
    
    event1_updated = ProcessedEvent(
        event_id='event-1',
        title='Event 1 Updated',
        description='Description 1',
        event_date='2024-01-01',
        start_time='10:00',
        end_time='12:00',
        location='Location 1',
        category='Category 1',
        url=None,
        last_updated=int(time.time()),
        ttl=int((datetime.now() + timedelta(days=90)).timestamp())
    )
    
    event3 = ProcessedEvent(
        event_id='event-3',
        title='Event 3',
        description='Description 3',
        event_date='2024-01-03',
        start_time='18:00',
        end_time='20:00',
        location='Location 3',
        category='Category 3',
        url=None,
        last_updated=int(time.time()),
        ttl=int((datetime.now() + timedelta(days=90)).timestamp())
    )
    
    result = dynamodb_manager.sync_events([event1_updated, event3])
    
    assert result.added == 1
    assert result.updated == 1
    assert result.deleted == 1
    
    # Verify final state
    events = dynamodb_manager.get_all_events()
    assert len(events) == 2
    assert 'event-1' in events
    assert 'event-3' in events
    assert 'event-2' not in events
    assert events['event-1'].title == 'Event 1 Updated'


def test_sync_events_no_changes(dynamodb_manager, sample_event):
    """Test sync_events when no changes are needed."""
    # Add initial event
    dynamodb_manager.batch_write_events([sample_event])
    
    # Sync with same event (no changes)
    result = dynamodb_manager.sync_events([sample_event])
    
    assert result.added == 0
    assert result.updated == 0
    assert result.deleted == 0
