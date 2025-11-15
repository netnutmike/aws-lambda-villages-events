"""Data models for event processing."""
from dataclasses import dataclass
from typing import Optional


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
    errors: list[str]
