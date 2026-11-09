"""Timeline notifications when a firmware sync adds or removes entities."""

from __future__ import annotations

from typing import Any


async def create_timeline_notification(homey: Any, excerpt: str) -> None:
    """Post one Homey timeline notification. ``**double asterisks**`` render bold."""
    await homey.notifications.create_notification(excerpt)


async def notify_entities_changed(
    *,
    homey: Any,
    device_name: str,
    added: list[str],
    removed: list[str],
    enabled: bool = True,
) -> None:
    """Post a timeline notification for entities a firmware sync added or removed."""
    if not enabled or not (added or removed):
        return
    # A removal can break Flows, so that notification asks the user to check them.
    # A zero count is left out; "added 0" is not something to say.
    if removed and added:
        key = "notifications.entities_changed_removed"
    elif removed:
        key = "notifications.entities_removed"
    else:
        key = "notifications.entities_changed"
    # Timeline excerpts render **double asterisks** as bold.
    excerpt = homey.translate(
        key,
        device=f"**{device_name}**",
        added=str(len(added)),
        removed=str(len(removed)),
    )
    if not excerpt:
        return
    await create_timeline_notification(homey, excerpt)
