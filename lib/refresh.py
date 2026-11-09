"""Sticky Homey ids when remapping a live device onto a new pair-time payload."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from homey_esphomedriver.system import capability_base

CapabilityPlan = tuple[
    list[str],
    list[tuple[str, dict[str, Any]]],
    list[tuple[str, dict[str, Any]]],
]


def plan_capability_refresh(
    current_options: dict[str, dict[str, Any]],
    desired_options: dict[str, dict[str, Any]],
) -> CapabilityPlan:
    """Diff current vs the pair-time payload, keeping sticky Homey ids.

    Entity-backed caps keep the current Homey id when ``(key, capability
    base)`` matches. Caps without a ``key``, including stored ``None``, match
    on Homey id.
    """
    desired_keyed = {
        (int(options["key"]), capability_base(capability_id)): (
            capability_id,
            options,
        )
        for capability_id, options in desired_options.items()
        if options and options.get("key") is not None
    }

    to_remove: list[str] = []
    to_add: list[tuple[str, dict[str, Any]]] = []
    to_update: list[tuple[str, dict[str, Any]]] = []
    matched: set[tuple[int, str]] = set()
    taken: set[str] = set()

    for capability_id, stored in current_options.items():
        # WORKAROUND: Homey may persist options as null (Athom will return {}).
        options = stored or {}
        key = options.get("key")
        if key is None:
            desired = desired_options.get(capability_id)
            if desired is None:
                to_remove.append(capability_id)
                continue
            taken.add(capability_id)
            merged = {**options, **desired}
            if merged != options:
                to_update.append((capability_id, merged))
            continue

        identity = (int(key), capability_base(capability_id))
        match = desired_keyed.get(identity)
        if match is None:
            to_remove.append(capability_id)
            continue
        taken.add(capability_id)
        matched.add(identity)
        merged = {**options, **match[1]}
        if merged != options:
            to_update.append((capability_id, merged))

    for capability_id, options in desired_options.items():
        key = options.get("key")
        if key is None:
            if capability_id not in current_options:
                to_add.append((capability_id, options))
                taken.add(capability_id)
            continue
        identity = (int(key), capability_base(capability_id))
        if identity in matched:
            continue
        new_id = (
            capability_id
            if capability_id not in taken
            else f"{capability_base(capability_id)}.{int(key)}"
        )
        taken.add(new_id)
        to_add.append((new_id, options))

    return to_remove, to_add, to_update


def plan_appeared_and_gone(
    current_options: dict[str, dict[str, Any]],
    entity_keys: Collection[int],
    plan: CapabilityPlan,
) -> CapabilityPlan:
    """Keep adds and removes for entities that appeared or disappeared.

    A new capability base for an entity that is still present is left in
    place, so Flow cards bound to the current Homey id keep working.
    Capabilities without a key are never added or removed.
    """
    to_remove, to_add, to_update = plan
    present = {int(key) for key in entity_keys}
    owned: set[int] = set()
    for stored in current_options.values():
        key = (stored or {}).get("key")
        if key is not None:
            owned.add(int(key))

    kept_remove: list[str] = []
    for capability_id in to_remove:
        key = (current_options.get(capability_id) or {}).get("key")
        if key is not None and int(key) not in present:
            kept_remove.append(capability_id)

    kept_add: list[tuple[str, dict[str, Any]]] = []
    for capability_id, options in to_add:
        key = (options or {}).get("key")
        if key is not None and int(key) not in owned:
            kept_add.append((capability_id, options))
    return kept_remove, kept_add, to_update
