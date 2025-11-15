"""DynamoDB manager for event storage operations."""
import logging
from typing import Dict, List

import boto3
from botocore.exceptions import ClientError

from processor.models import ProcessedEvent, SyncResult

logger = logging.getLogger(__name__)


class DynamoDBManager:
    """Manager for DynamoDB operations."""
    
    BATCH_SIZE = 25  # DynamoDB batch operation limit
    
    def __init__(self, table_name: str):
        """
        Initialize DynamoDB client and table reference.
        
        Args:
            table_name: Name of the DynamoDB table
        """
        self.table_name = table_name
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        logger.info(f"Initialized DynamoDBManager for table: {table_name}")
    
    def get_all_events(self) -> Dict[str, ProcessedEvent]:
        """
        Retrieve all events from DynamoDB using Scan operation.
        
        Returns:
            Dictionary mapping event_id to ProcessedEvent objects
        """
        logger.info("Scanning DynamoDB table for all events")
        events = {}
        
        try:
            # Scan the table (paginated automatically by boto3)
            response = self.table.scan()
            items = response.get('Items', [])
            
            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = self.table.scan(
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                items.extend(response.get('Items', []))
            
            # Convert DynamoDB items to ProcessedEvent objects
            for item in items:
                event = self._item_to_processed_event(item)
                if event:
                    events[event.event_id] = event
            
            logger.info(f"Retrieved {len(events)} events from DynamoDB")
            return events
            
        except ClientError as e:
            logger.error(f"Error scanning DynamoDB table: {e}")
            raise
    
    def sync_events(self, new_events: List[ProcessedEvent]) -> SyncResult:
        """
        Synchronize events with DynamoDB.
        
        Compares new events from calendar with existing events in DynamoDB,
        then performs additions, updates, and deletions as needed.
        
        Args:
            new_events: List of current events from calendar
            
        Returns:
            SyncResult with counts of added, updated, deleted events
        """
        logger.info(f"Starting sync process with {len(new_events)} new events")
        errors = []
        
        try:
            # Get existing events from DynamoDB
            existing_events = self.get_all_events()
            
            # Create lookup dictionaries
            new_events_dict = {event.event_id: event for event in new_events}
            
            # Identify events to add (in new, not in existing)
            events_to_add = [
                event for event_id, event in new_events_dict.items()
                if event_id not in existing_events
            ]
            
            # Identify events to update (in both, but content differs)
            events_to_update = [
                event for event_id, event in new_events_dict.items()
                if event_id in existing_events and 
                self._events_differ(event, existing_events[event_id])
            ]
            
            # Identify events to delete (in existing, not in new)
            event_ids_to_delete = [
                event_id for event_id in existing_events.keys()
                if event_id not in new_events_dict
            ]
            
            logger.info(
                f"Sync plan: {len(events_to_add)} to add, "
                f"{len(events_to_update)} to update, "
                f"{len(event_ids_to_delete)} to delete"
            )
            
            # Perform batch operations
            added_count = 0
            updated_count = 0
            deleted_count = 0
            
            if events_to_add or events_to_update:
                write_count = self.batch_write_events(
                    events_to_add + events_to_update
                )
                added_count = min(write_count, len(events_to_add))
                updated_count = write_count - added_count
            
            if event_ids_to_delete:
                deleted_count = self.batch_delete_events(event_ids_to_delete)
            
            logger.info(
                f"Sync complete: {added_count} added, {updated_count} updated, "
                f"{deleted_count} deleted"
            )
            
            return SyncResult(
                added=added_count,
                updated=updated_count,
                deleted=deleted_count,
                errors=errors
            )
            
        except Exception as e:
            error_msg = f"Error during sync operation: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            return SyncResult(added=0, updated=0, deleted=0, errors=errors)
    
    def batch_write_events(self, events: List[ProcessedEvent]) -> int:
        """
        Write events to DynamoDB in batches of 25 items.
        
        Args:
            events: List of ProcessedEvent objects to write
            
        Returns:
            Count of successfully written events
        """
        if not events:
            return 0
        
        logger.info(f"Writing {len(events)} events to DynamoDB")
        success_count = 0
        
        # Process in batches of 25 (DynamoDB limit)
        for i in range(0, len(events), self.BATCH_SIZE):
            batch = events[i:i + self.BATCH_SIZE]
            
            try:
                with self.table.batch_writer() as writer:
                    for event in batch:
                        item = self._processed_event_to_item(event)
                        writer.put_item(Item=item)
                        success_count += 1
                        
            except ClientError as e:
                logger.error(
                    f"Error writing batch {i // self.BATCH_SIZE + 1}: {e}"
                )
                # Continue processing remaining batches
                continue
        
        logger.info(f"Successfully wrote {success_count} events")
        return success_count
    
    def batch_delete_events(self, event_ids: List[str]) -> int:
        """
        Delete events from DynamoDB in batches of 25 items.
        
        Args:
            event_ids: List of event IDs to delete
            
        Returns:
            Count of successfully deleted events
        """
        if not event_ids:
            return 0
        
        logger.info(f"Deleting {len(event_ids)} events from DynamoDB")
        success_count = 0
        
        # Process in batches of 25 (DynamoDB limit)
        for i in range(0, len(event_ids), self.BATCH_SIZE):
            batch = event_ids[i:i + self.BATCH_SIZE]
            
            try:
                with self.table.batch_writer() as writer:
                    for event_id in batch:
                        writer.delete_item(Key={'event_id': event_id})
                        success_count += 1
                        
            except ClientError as e:
                logger.error(
                    f"Error deleting batch {i // self.BATCH_SIZE + 1}: {e}"
                )
                # Continue processing remaining batches
                continue
        
        logger.info(f"Successfully deleted {success_count} events")
        return success_count
    
    def _item_to_processed_event(self, item: dict) -> ProcessedEvent:
        """
        Convert DynamoDB item to ProcessedEvent object.
        
        Args:
            item: DynamoDB item dictionary
            
        Returns:
            ProcessedEvent object or None if conversion fails
        """
        try:
            return ProcessedEvent(
                event_id=item['event_id'],
                title=item['title'],
                description=item['description'],
                event_date=item['event_date'],
                start_time=item['start_time'],
                end_time=item.get('end_time'),
                location=item['location'],
                category=item['category'],
                url=item.get('url'),
                last_updated=int(item['last_updated']),
                ttl=int(item['ttl'])
            )
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to convert item to ProcessedEvent: {e}")
            return None
    
    def _processed_event_to_item(self, event: ProcessedEvent) -> dict:
        """
        Convert ProcessedEvent object to DynamoDB item.
        
        Args:
            event: ProcessedEvent object
            
        Returns:
            DynamoDB item dictionary
        """
        item = {
            'event_id': event.event_id,
            'title': event.title,
            'description': event.description,
            'event_date': event.event_date,
            'start_time': event.start_time,
            'location': event.location,
            'category': event.category,
            'last_updated': event.last_updated,
            'ttl': event.ttl
        }
        
        # Add optional fields if present
        if event.end_time:
            item['end_time'] = event.end_time
        if event.url:
            item['url'] = event.url
        
        return item
    
    def _events_differ(self, event1: ProcessedEvent, event2: ProcessedEvent) -> bool:
        """
        Compare two ProcessedEvent objects to determine if they differ.
        
        Compares all fields except last_updated timestamp.
        
        Args:
            event1: First ProcessedEvent
            event2: Second ProcessedEvent
            
        Returns:
            True if events differ, False otherwise
        """
        return (
            event1.title != event2.title or
            event1.description != event2.description or
            event1.event_date != event2.event_date or
            event1.start_time != event2.start_time or
            event1.end_time != event2.end_time or
            event1.location != event2.location or
            event1.category != event2.category or
            event1.url != event2.url or
            event1.ttl != event2.ttl
        )
