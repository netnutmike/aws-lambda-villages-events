"""Calendar scraper for The Villages Florida events."""
import logging
import time
from datetime import datetime, timedelta
from typing import List
from bs4 import BeautifulSoup
import requests

from processor.models import Event

logger = logging.getLogger(__name__)


class VillagesCalendarScraper:
    """Scraper for The Villages Florida online calendar."""
    
    BASE_URL = "https://www.thevillages.com/calendar"
    
    def __init__(self, timeout: int = 30):
        """
        Initialize the calendar scraper.
        
        Args:
            timeout: HTTP request timeout in seconds (default: 30)
        """
        self.timeout = timeout
    
    def fetch_events(self, days_ahead: int = 90) -> List[Event]:
        """
        Fetch events from The Villages calendar.
        
        Args:
            days_ahead: Number of days to fetch events for (default: 90)
            
        Returns:
            List of Event objects
        """
        logger.info(f"Fetching events for {days_ahead} days ahead")
        
        # Calculate date range
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=days_ahead)
        
        # Fetch calendar HTML
        html_content = self._fetch_calendar_html(start_date, end_date)
        
        # Parse events from HTML
        events = self._parse_events(html_content)
        
        logger.info(f"Successfully fetched {len(events)} events")
        return events
    
    def _fetch_calendar_html(self, start_date, end_date) -> str:
        """
        Fetch calendar HTML from The Villages website with retry logic.
        
        Args:
            start_date: Start date for event range
            end_date: End date for event range
            
        Returns:
            HTML content as string
            
        Raises:
            requests.RequestException: If all retry attempts fail
        """
        params = {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        }
        
        max_retries = 3
        base_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching calendar HTML (attempt {attempt + 1}/{max_retries})")
                response = requests.get(
                    self.BASE_URL,
                    params=params,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.text
                
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    # Calculate exponential backoff delay
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay} seconds..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"All {max_retries} retry attempts failed. Last error: {e}"
                    )
                    raise
    
    def _parse_events(self, html_content: str) -> List[Event]:
        """
        Parse events from calendar HTML.
        
        Args:
            html_content: HTML content from calendar page
            
        Returns:
            List of Event objects
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        events = []
        
        # Find all event elements
        # Note: This is a placeholder implementation that needs to be adapted
        # based on the actual HTML structure of The Villages calendar
        event_elements = soup.find_all('div', class_='event-item')
        
        for element in event_elements:
            try:
                event = self._parse_event_element(element)
                if event:
                    events.append(event)
            except Exception as e:
                logger.warning(f"Failed to parse event element: {e}")
                continue
        
        return events
    
    def _parse_event_element(self, element) -> Event:
        """
        Parse a single event element.
        
        Args:
            element: BeautifulSoup element containing event data
            
        Returns:
            Event object or None if parsing fails
        """
        # Extract event data from HTML element
        # Note: This is a placeholder implementation that needs to be adapted
        # based on the actual HTML structure of The Villages calendar
        
        title_elem = element.find('h3', class_='event-title')
        date_elem = element.find('span', class_='event-date')
        time_elem = element.find('span', class_='event-time')
        location_elem = element.find('span', class_='event-location')
        description_elem = element.find('div', class_='event-description')
        category_elem = element.find('span', class_='event-category')
        url_elem = element.find('a', class_='event-link')
        
        if not all([title_elem, date_elem, time_elem]):
            return None
        
        # Parse time range
        time_text = time_elem.get_text(strip=True)
        start_time, end_time = self._parse_time_range(time_text)
        
        return Event(
            title=title_elem.get_text(strip=True),
            date=date_elem.get_text(strip=True),
            start_time=start_time,
            end_time=end_time,
            location=location_elem.get_text(strip=True) if location_elem else '',
            description=description_elem.get_text(strip=True) if description_elem else '',
            category=category_elem.get_text(strip=True) if category_elem else '',
            url=url_elem.get('href') if url_elem else None
        )
    
    def _parse_time_range(self, time_text: str) -> tuple[str, str]:
        """
        Parse time range from text.
        
        Args:
            time_text: Time text (e.g., "10:00 AM - 2:00 PM")
            
        Returns:
            Tuple of (start_time, end_time)
        """
        if '-' in time_text:
            parts = time_text.split('-')
            start_time = parts[0].strip()
            end_time = parts[1].strip() if len(parts) > 1 else None
        else:
            start_time = time_text.strip()
            end_time = None
        
        return start_time, end_time
