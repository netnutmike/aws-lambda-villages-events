"""Unit tests for VillagesCalendarScraper."""
import pytest
import responses
from requests.exceptions import RequestException, Timeout
from scraper.villages_calendar import VillagesCalendarScraper


class TestVillagesCalendarScraper:
    """Test cases for VillagesCalendarScraper class."""
    
    @responses.activate
    def test_fetch_events_success(self):
        """Test successful event fetching and parsing."""
        # Mock HTML response with sample event data
        mock_html = """
        <html>
            <body>
                <div class="event-item">
                    <h3 class="event-title">Live Music at Spanish Springs</h3>
                    <span class="event-date">2024-01-15</span>
                    <span class="event-time">7:00 PM - 9:00 PM</span>
                    <span class="event-location">Spanish Springs Town Square</span>
                    <div class="event-description">Enjoy live entertainment</div>
                    <span class="event-category">Entertainment</span>
                    <a class="event-link" href="/event/123">Details</a>
                </div>
                <div class="event-item">
                    <h3 class="event-title">Golf Tournament</h3>
                    <span class="event-date">2024-01-16</span>
                    <span class="event-time">8:00 AM</span>
                    <span class="event-location">Championship Golf Course</span>
                </div>
            </body>
        </html>
        """
        
        responses.add(
            responses.GET,
            "https://www.thevillages.com/calendar",
            body=mock_html,
            status=200
        )
        
        scraper = VillagesCalendarScraper(timeout=30)
        events = scraper.fetch_events(days_ahead=30)
        
        assert len(events) == 2
        
        # Verify first event
        assert events[0].title == "Live Music at Spanish Springs"
        assert events[0].date == "2024-01-15"
        assert events[0].start_time == "7:00 PM"
        assert events[0].end_time == "9:00 PM"
        assert events[0].location == "Spanish Springs Town Square"
        assert events[0].description == "Enjoy live entertainment"
        assert events[0].category == "Entertainment"
        assert events[0].url == "/event/123"
        
        # Verify second event
        assert events[1].title == "Golf Tournament"
        assert events[1].date == "2024-01-16"
        assert events[1].start_time == "8:00 AM"
        assert events[1].end_time is None
    
    @responses.activate
    def test_fetch_events_with_retry_success(self):
        """Test retry logic succeeds after initial failures."""
        mock_html = """
        <html>
            <body>
                <div class="event-item">
                    <h3 class="event-title">Test Event</h3>
                    <span class="event-date">2024-01-15</span>
                    <span class="event-time">10:00 AM</span>
                </div>
            </body>
        </html>
        """
        
        # First two attempts fail, third succeeds
        responses.add(
            responses.GET,
            "https://www.thevillages.com/calendar",
            body="Server Error",
            status=500
        )
        responses.add(
            responses.GET,
            "https://www.thevillages.com/calendar",
            body="Server Error",
            status=500
        )
        responses.add(
            responses.GET,
            "https://www.thevillages.com/calendar",
            body=mock_html,
            status=200
        )
        
        scraper = VillagesCalendarScraper(timeout=30)
        events = scraper.fetch_events(days_ahead=30)
        
        assert len(events) == 1
        assert events[0].title == "Test Event"
        assert len(responses.calls) == 3
    
    @responses.activate
    def test_fetch_events_all_retries_fail(self):
        """Test that exception is raised when all retries fail."""
        # All three attempts fail
        for _ in range(3):
            responses.add(
                responses.GET,
                "https://www.thevillages.com/calendar",
                body="Server Error",
                status=500
            )
        
        scraper = VillagesCalendarScraper(timeout=30)
        
        with pytest.raises(RequestException):
            scraper.fetch_events(days_ahead=30)
        
        assert len(responses.calls) == 3
    
    @responses.activate
    def test_fetch_events_timeout(self):
        """Test timeout handling."""
        responses.add(
            responses.GET,
            "https://www.thevillages.com/calendar",
            body=Timeout("Request timed out")
        )
        responses.add(
            responses.GET,
            "https://www.thevillages.com/calendar",
            body=Timeout("Request timed out")
        )
        responses.add(
            responses.GET,
            "https://www.thevillages.com/calendar",
            body=Timeout("Request timed out")
        )
        
        scraper = VillagesCalendarScraper(timeout=30)
        
        with pytest.raises(Timeout):
            scraper.fetch_events(days_ahead=30)
        
        assert len(responses.calls) == 3
    
    @responses.activate
    def test_parse_events_skips_invalid_elements(self):
        """Test that invalid event elements are skipped."""
        mock_html = """
        <html>
            <body>
                <div class="event-item">
                    <h3 class="event-title">Valid Event</h3>
                    <span class="event-date">2024-01-15</span>
                    <span class="event-time">10:00 AM</span>
                </div>
                <div class="event-item">
                    <h3 class="event-title">Invalid Event - Missing Date</h3>
                    <span class="event-time">10:00 AM</span>
                </div>
                <div class="event-item">
                    <h3 class="event-title">Another Valid Event</h3>
                    <span class="event-date">2024-01-16</span>
                    <span class="event-time">2:00 PM</span>
                </div>
            </body>
        </html>
        """
        
        responses.add(
            responses.GET,
            "https://www.thevillages.com/calendar",
            body=mock_html,
            status=200
        )
        
        scraper = VillagesCalendarScraper(timeout=30)
        events = scraper.fetch_events(days_ahead=30)
        
        # Only valid events should be returned
        assert len(events) == 2
        assert events[0].title == "Valid Event"
        assert events[1].title == "Another Valid Event"
    
    def test_parse_time_range_with_end_time(self):
        """Test parsing time range with start and end times."""
        scraper = VillagesCalendarScraper()
        start_time, end_time = scraper._parse_time_range("10:00 AM - 2:00 PM")
        
        assert start_time == "10:00 AM"
        assert end_time == "2:00 PM"
    
    def test_parse_time_range_without_end_time(self):
        """Test parsing time range with only start time."""
        scraper = VillagesCalendarScraper()
        start_time, end_time = scraper._parse_time_range("10:00 AM")
        
        assert start_time == "10:00 AM"
        assert end_time is None
