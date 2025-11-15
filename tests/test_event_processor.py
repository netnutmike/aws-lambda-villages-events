"""Unit tests for EventProcessor."""
import pytest
from datetime import datetime, timedelta
from processor.event_processor import EventProcessor
from processor.models import Event


class TestEventProcessor:
    """Test cases for EventProcessor class."""
    
    def test_process_events_valid_event(self):
        """Test processing a valid event."""
        processor = EventProcessor()
        
        raw_events = [
            Event(
                title="Live Music Night",
                date="2024-01-15",
                start_time="19:00",
                end_time="21:00",
                location="Spanish Springs",
                description="Enjoy live entertainment",
                category="Entertainment",
                url="https://example.com/event/123"
            )
        ]
        
        processed = processor.process_events(raw_events)
        
        assert len(processed) == 1
        event = processed[0]
        
        assert event.title == "Live Music Night"
        assert event.event_date == "2024-01-15"
        assert event.start_time == "19:00"
        assert event.end_time == "21:00"
        assert event.location == "Spanish Springs"
        assert event.description == "Enjoy live entertainment"
        assert event.category == "Entertainment"
        assert event.url == "https://example.com/event/123"
        assert event.event_id is not None
        assert event.last_updated > 0
        assert event.ttl > 0
    
    def test_process_events_missing_required_fields(self):
        """Test that events with missing required fields are skipped."""
        processor = EventProcessor()
        
        raw_events = [
            Event(
                title="",  # Missing title
                date="2024-01-15",
                start_time="19:00",
                end_time=None,
                location="Location",
                description="Description",
                category="Category",
                url=None
            ),
            Event(
                title="Valid Event",
                date="",  # Missing date
                start_time="19:00",
                end_time=None,
                location="Location",
                description="Description",
                category="Category",
                url=None
            ),
            Event(
                title="Another Valid Event",
                date="2024-01-15",
                start_time="",  # Missing start_time
                end_time=None,
                location="Location",
                description="Description",
                category="Category",
                url=None
            )
        ]
        
        processed = processor.process_events(raw_events)
        
        # All events should be skipped due to missing required fields
        assert len(processed) == 0
    
    def test_generate_event_id_consistency(self):
        """Test that event_id generation is consistent for same inputs."""
        processor = EventProcessor()
        
        event_id_1 = processor.generate_event_id(
            title="Test Event",
            date="2024-01-15",
            time="19:00"
        )
        
        event_id_2 = processor.generate_event_id(
            title="Test Event",
            date="2024-01-15",
            time="19:00"
        )
        
        # Same inputs should produce same event_id
        assert event_id_1 == event_id_2
        assert len(event_id_1) == 64  # SHA256 produces 64 character hex string
    
    def test_generate_event_id_uniqueness(self):
        """Test that different events produce different event_ids."""
        processor = EventProcessor()
        
        event_id_1 = processor.generate_event_id(
            title="Event A",
            date="2024-01-15",
            time="19:00"
        )
        
        event_id_2 = processor.generate_event_id(
            title="Event B",
            date="2024-01-15",
            time="19:00"
        )
        
        event_id_3 = processor.generate_event_id(
            title="Event A",
            date="2024-01-16",
            time="19:00"
        )
        
        # Different inputs should produce different event_ids
        assert event_id_1 != event_id_2
        assert event_id_1 != event_id_3
        assert event_id_2 != event_id_3
    
    def test_normalize_date_iso_format(self):
        """Test date normalization with ISO 8601 format."""
        processor = EventProcessor()
        
        normalized = processor._normalize_date("2024-01-15")
        assert normalized == "2024-01-15"
    
    def test_normalize_date_us_format(self):
        """Test date normalization with US format."""
        processor = EventProcessor()
        
        normalized = processor._normalize_date("01/15/2024")
        assert normalized == "2024-01-15"
    
    def test_normalize_date_full_month_name(self):
        """Test date normalization with full month name."""
        processor = EventProcessor()
        
        normalized = processor._normalize_date("January 15, 2024")
        assert normalized == "2024-01-15"
    
    def test_normalize_date_invalid_format(self):
        """Test that invalid date format returns None."""
        processor = EventProcessor()
        
        normalized = processor._normalize_date("invalid-date")
        assert normalized is None
    
    def test_normalize_time_24_hour_format(self):
        """Test time normalization with 24-hour format."""
        processor = EventProcessor()
        
        normalized = processor._normalize_time("19:00")
        assert normalized == "19:00"
    
    def test_normalize_time_12_hour_format_pm(self):
        """Test time normalization with 12-hour PM format."""
        processor = EventProcessor()
        
        normalized = processor._normalize_time("7:00 PM")
        assert normalized == "19:00"
    
    def test_normalize_time_12_hour_format_am(self):
        """Test time normalization with 12-hour AM format."""
        processor = EventProcessor()
        
        normalized = processor._normalize_time("9:30 AM")
        assert normalized == "09:30"
    
    def test_normalize_time_no_space(self):
        """Test time normalization with 12-hour format without space."""
        processor = EventProcessor()
        
        normalized = processor._normalize_time("7:00PM")
        assert normalized == "19:00"
    
    def test_normalize_time_invalid_format(self):
        """Test that invalid time format returns None."""
        processor = EventProcessor()
        
        normalized = processor._normalize_time("invalid-time")
        assert normalized is None
    
    def test_calculate_ttl(self):
        """Test TTL calculation (90 days after event date)."""
        processor = EventProcessor()
        
        event_date = "2024-01-15"
        ttl = processor._calculate_ttl(event_date)
        
        # Calculate expected TTL
        date_obj = datetime.strptime(event_date, '%Y-%m-%d')
        expected_ttl_date = date_obj + timedelta(days=90)
        expected_ttl = int(expected_ttl_date.timestamp())
        
        assert ttl == expected_ttl
    
    def test_process_events_truncates_long_fields(self):
        """Test that long title and description are truncated."""
        processor = EventProcessor()
        
        long_title = "A" * 300  # Exceeds MAX_TITLE_LENGTH (200)
        long_description = "B" * 3000  # Exceeds MAX_DESCRIPTION_LENGTH (2000)
        
        raw_events = [
            Event(
                title=long_title,
                date="2024-01-15",
                start_time="19:00",
                end_time=None,
                location="Location",
                description=long_description,
                category="Category",
                url=None
            )
        ]
        
        processed = processor.process_events(raw_events)
        
        assert len(processed) == 1
        assert len(processed[0].title) == 200
        assert len(processed[0].description) == 2000
    
    def test_process_events_handles_optional_end_time(self):
        """Test processing event without end time."""
        processor = EventProcessor()
        
        raw_events = [
            Event(
                title="Event Without End Time",
                date="2024-01-15",
                start_time="19:00",
                end_time=None,
                location="Location",
                description="Description",
                category="Category",
                url=None
            )
        ]
        
        processed = processor.process_events(raw_events)
        
        assert len(processed) == 1
        assert processed[0].end_time is None
    
    def test_process_events_skips_invalid_dates(self):
        """Test that events with invalid dates are skipped."""
        processor = EventProcessor()
        
        raw_events = [
            Event(
                title="Invalid Date Event",
                date="not-a-date",
                start_time="19:00",
                end_time=None,
                location="Location",
                description="Description",
                category="Category",
                url=None
            )
        ]
        
        processed = processor.process_events(raw_events)
        
        assert len(processed) == 0
    
    def test_process_events_skips_invalid_times(self):
        """Test that events with invalid times are skipped."""
        processor = EventProcessor()
        
        raw_events = [
            Event(
                title="Invalid Time Event",
                date="2024-01-15",
                start_time="not-a-time",
                end_time=None,
                location="Location",
                description="Description",
                category="Category",
                url=None
            )
        ]
        
        processed = processor.process_events(raw_events)
        
        assert len(processed) == 0
    
    def test_process_events_multiple_valid_and_invalid(self):
        """Test processing mix of valid and invalid events."""
        processor = EventProcessor()
        
        raw_events = [
            Event(
                title="Valid Event 1",
                date="2024-01-15",
                start_time="19:00",
                end_time=None,
                location="Location 1",
                description="Description 1",
                category="Category 1",
                url=None
            ),
            Event(
                title="",  # Invalid - missing title
                date="2024-01-16",
                start_time="20:00",
                end_time=None,
                location="Location 2",
                description="Description 2",
                category="Category 2",
                url=None
            ),
            Event(
                title="Valid Event 2",
                date="2024-01-17",
                start_time="21:00",
                end_time=None,
                location="Location 3",
                description="Description 3",
                category="Category 3",
                url=None
            )
        ]
        
        processed = processor.process_events(raw_events)
        
        # Only valid events should be processed
        assert len(processed) == 2
        assert processed[0].title == "Valid Event 1"
        assert processed[1].title == "Valid Event 2"
