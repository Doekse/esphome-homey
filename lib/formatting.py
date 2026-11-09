"""Text formats of uptime, dates, timestamps and event types for Homey."""

from __future__ import annotations

from datetime import datetime


def format_uptime(seconds: float) -> str:
    """Format uptime seconds as ``90d 8h 48m``."""
    total = int(seconds)
    days = total // 86400
    hours = (total % 86400) // 3600
    minutes = (total % 3600) // 60

    parts: list[str] = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def format_date(value: str) -> str:
    """Format an ISO8601 date/timestamp as ``YYYY-MM-DD``."""
    return _parse_iso8601(value).date().isoformat()


def format_timestamp(value: str) -> str:
    """Format an ISO8601 timestamp as ``YYYY-MM-DD HH:MM:SS`` (local time)."""
    dt = _parse_iso8601(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_event_type(event_type: str) -> str:
    """Humanize an ESPHome event_type for Homey titles and Flow tokens."""
    return " ".join(part.capitalize() for part in event_type.split("_"))


def _parse_iso8601(value: str) -> datetime:
    """Parse ESPHome text-sensor ISO8601 (``Z`` normalized for fromisoformat)."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
