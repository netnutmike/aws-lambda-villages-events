"""Event processor for validating and normalizing event data."""
import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import List

from processor.models import Event, ProcessedEvent

logger = logging.getLogger(__name__)


class EventProcessor:
    """Processor for validating and normalizing event data."""
    
    MAX_TITLE_LENGTH = 200
    MAX_DESCRIPTION_LENGTH = 2000
    TTL_DAYS = 90
    
    def process_events(self, raw_events: List[Event]) -> List[ProcessedEvent]:
        """
        Process and validate raw event data.
        
        Args:
            raw_events: List of raw Event objects from scraper
            
        Returns:
            List of validated ProcessedEvent objects
        """
        processed_events = []
        
        for event in raw_events:
            try:
                processed_event = self._process_single_event(event)
                if processed_event:
                    processed_events.append(processed_event)
            except Exception as e:
                logger.warning(
                    f"Failed to process event '{event.title}': {e}"
                )
                continue
        
        logger.info(
            f"Processed {len(processed_events)} valid events out of "
            f"{len(raw_events)} total events"
        )
        return processed_events
    
    def _process_single_event(self, event: Event) -> ProcessedEvent:
        """
        Process a single event.
        
        Args:
            event: Raw Event object
            
        Returns:
            ProcessedEvent object or None if validation fails
        """
        # Validate required fields
        if not self._validate_required_fields(event):
            return None
        
        # Normalize date to ISO 8601 format
        normalized_date = self._normalize_date(event.date)
        if not normalized_date:
            logger.warning(
                f"Invalid date format for event '{event.title}': {event.date}"
            )
            return None
        
        # Normalize times to 24-hour format
        normalized_start_time = self._normalize_time(event.start_time)
        if not normalized_start_time:
            logger.warning(
                f"Invalid start time format for event '{event.title}': "
                f"{event.start_time}"
            )
            return None
        
        normalized_end_time = None
        if event.end_time:
            normalized_end_time = self._normalize_time(event.end_time)
        
        # Truncate fields to maximum length
        title = event.title[:self.MAX_TITLE_LENGTH]
        description = event.description[:self.MAX_DESCRIPTION_LENGTH]
        
        # Generate event ID
        event_id = self.generate_event_id(
            title=title,
            date=normalized_date,
            time=normalized_start_time
        )
        
        # Calculate TTL (90 days after event date)
        ttl = self._calculate_ttl(normalized_date)
        
        # Get current timestamp
        last_updated = int(time.time())
        
        return ProcessedEvent(
            event_id=event_id,
            title=title,
            description=description,
            event_date=normalized_date,
            start_time=normalized_start_time,
            end_time=normalized_end_time,
            location=event.location,
            category=event.category,
            url=event.url,
            last_updated=last_updated,
            ttl=ttl
        )
    
    def _validate_required_fields(self, event: Event) -> bool:
        """
        Validate that required fields are present and non-empty.
        
        Args:
            event: Event object to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not event.title or not event.title.strip():
            logger.warning("Event missing required field: title")
            return False
        
        if not event.date or not event.date.strip():
            logger.warning(f"Event '{event.title}' missing required field: date")
            return False
        
        if not event.start_time or not event.start_time.strip():
            logger.warning(
                f"Event '{event.title}' missing required field: start_time"
            )
            return False
        
        return True
    
    def _normalize_date(self, date_str: str) -> str:
        """
        Normalize date to ISO 8601 format (YYYY-MM-DD).
        
        Args:
            date_str: Date string in various formats
            
        Returns:
            ISO 8601 formatted date string or None if parsing fails
        """
        # Try common date formats
        date_formats = [
            '%Y-%m-%d',      # ISO 8601
            '%m/%d/%Y',      # US format
            '%m-%d-%Y',      # US format with dashes
            '%B %d, %Y',     # Full month name
            '%b %d, %Y',     # Abbreviated month name
            '%d/%m/%Y',      # European format
            '%Y/%m/%d',      # Alternative ISO format
        ]
        
        for fmt in date_formats:
            try:
                date_obj = datetime.strptime(date_str.strip(), fmt)
                return date_obj.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        return None
    
    def _normalize_time(self, time_str: str) -> str:
        """
        Normalize time to 24-hour format (HH:MM).
        
        Args:
            time_str: Time string in various formats
            
        Returns:
            24-hour formatted time string or None if parsing fails
        """
        # Try common time formats
        time_formats = [
            '%H:%M',         # 24-hour format
            '%I:%M %p',      # 12-hour format with AM/PM
            '%I:%M%p',       # 12-hour format without space
            '%H:%M:%S',      # 24-hour with seconds
            '%I:%M:%S %p',   # 12-hour with seconds and AM/PM
        ]
        
        time_str = time_str.strip()
        
        for fmt in time_formats:
            try:
                time_obj = datetime.strptime(time_str, fmt)
                return time_obj.strftime('%H:%M')
            except ValueError:
                continue
        
        return None
    
    def _calculate_ttl(self, event_date: str) -> int:
        """
        Calculate TTL as 90 days after event date.
        
        Args:
            event_date: ISO 8601 formatted date string (YYYY-MM-DD)
            
        Returns:
            Unix timestamp for TTL
        """
        date_obj = datetime.strptime(event_date, '%Y-%m-%d')
        ttl_date = date_obj + timedelta(days=self.TTL_DAYS)
        return int(ttl_date.timestamp())
    
    def generate_event_id(self, title: str, date: str, time: str) -> str:
        """
        Generate unique identifier for an event using hash of title + date + time.
        
        Args:
            title: Event title
            date: Event date (ISO 8601 format)
            time: Event start time (24-hour format)
            
        Returns:
            Unique event ID (SHA256 hash)
        """
        # Create composite string
        composite = f"{title}|{date}|{time}"
        
        # Generate SHA256 hash
        hash_obj = hashlib.sha256(composite.encode('utf-8'))
        event_id = hash_obj.hexdigest()
        
        return event_id
