"""Keep a device's capabilities in step with the node's entities.

The generic app maps every entity it can show to a capability. Refresh, a
firmware rebuild and the diagnostics / configuration toggles add and remove
capabilities on a live device; each added one is bound with
``register_capability`` and each removed one unbound.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from aioesphomeapi import EntityCategory, EntityInfo

from lib.mapping import REFRESH_CAPABILITY, DeviceEntityMapper, refresh_options
from lib.refresh import plan_appeared_and_gone, plan_capability_refresh

if TYPE_CHECKING:
    from lib.device import GenericEspHomeDevice


@dataclass(frozen=True, slots=True)
class EntitySyncResult:
    """Capability ids added and removed, plus titles captured before removal."""

    added: list[str]
    removed: list[str]
    removed_titles: list[str]


class DeviceCapabilityHandler:
    """Add, remove, and refresh Homey capabilities on a live device."""

    def __init__(self, device: GenericEspHomeDevice) -> None:
        self._device = device
        self._lock = asyncio.Lock()

    async def ensure_refresh(self) -> None:
        """Add the Refresh button on older pairings and listen to it."""
        device = self._device
        if not device.has_capability(REFRESH_CAPABILITY):
            await self._add_capabilities(
                [REFRESH_CAPABILITY],
                {REFRESH_CAPABILITY: refresh_options(device.driver.manifest)},
            )
        device.register_capability_listener(REFRESH_CAPABILITY, self.refresh)

    async def refresh(self, _value: Any = True, **_kwargs: Any) -> None:
        """Add/remove capabilities from a live remap; keep unchanged Homey ids."""
        # No timeline notification: the user pressed Refresh themselves.
        async with self._lock:
            device = self._device
            entities, scratch = await self._list_mapped_entities()
            to_remove, to_add, to_update = plan_capability_refresh(
                device._capabilities_options, scratch["capabilitiesOptions"]
            )
            await self._apply_capability_refresh(entities, to_remove, to_add, to_update)
            mapped_class = scratch.get("class")
            if mapped_class and device.get_setting("device_class") == "auto":
                await device.set_store_value("auto_class", mapped_class)
                await device.set_class(mapped_class)
            device_info = device._require_client().device_info
            if device_info is not None:
                await self._store_entities_build(device_info.compilation_time)

    async def sync_entities(self, build: str) -> EntitySyncResult:
        """Add and remove capabilities for entities that appeared or vanished."""
        async with self._lock:
            device = self._device
            entities, scratch = await self._list_mapped_entities()
            current = device._capabilities_options
            plan = plan_capability_refresh(current, scratch["capabilitiesOptions"])
            to_remove, to_add, to_update = plan_appeared_and_gone(
                current, {entity.key for entity in entities}, plan
            )
            # Removal deletes the options, and the title with them.
            removed_titles = [
                _removed_title(current.get(capability_id), capability_id)
                for capability_id in to_remove
            ]
            await self._apply_capability_refresh(entities, to_remove, to_add, to_update)
            await self._store_entities_build(build)
            return EntitySyncResult(
                added=[capability_id for capability_id, _options in to_add],
                removed=list(to_remove),
                removed_titles=removed_titles,
            )

    async def apply_category(
        self,
        enabled: bool,
        category: EntityCategory,
        store_key: str,
    ) -> None:
        """Add or remove capabilities for one entity category from the live device."""
        async with self._lock:
            device = self._device
            if not enabled:
                # Batch — per-cap removeCapability reinitializes and times out
                # on entity-heavy nodes inside on_settings ACK.
                removed = device.get_store().get(store_key) or []
                await self._remove_capabilities(removed)
                await device.set_store_value(store_key, [])
                return

            (
                entities,
                _services,
            ) = await device._require_client().list_entities_services()
            existing = device.get_capabilities()
            scratch = DeviceEntityMapper.empty_option(list(existing))
            DeviceEntityMapper.map(entities, scratch, category_only=category)
            present = set(existing)
            added = [
                capability_id
                for capability_id in scratch["capabilities"]
                if capability_id not in present
            ]
            await self._add_capabilities(
                added,
                {
                    capability_id: scratch["capabilitiesOptions"][capability_id]
                    for capability_id in added
                },
            )
            await device.set_store_value(store_key, added)

    async def _add_capabilities(
        self,
        capability_ids: list[str],
        options: dict[str, dict[str, Any]],
    ) -> None:
        """Batch-add capabilities and bind each one to its entity."""
        if not capability_ids:
            return
        device = self._device
        await device._client_emit(
            "addCapabilities",
            data={"capabilityIds": capability_ids, "capabilitiesOptions": options},
        )
        device._capabilities.extend(capability_ids)
        device._capabilities_options.update(options)
        for capability_id in capability_ids:
            device.bind_capability(capability_id)

    async def _remove_capabilities(self, capability_ids: Sequence[str]) -> None:
        """Unbind, then batch-remove capabilities and drop their local state."""
        if not capability_ids:
            return
        device = self._device
        for capability_id in capability_ids:
            device.unregister_capability(capability_id)
        await device._client_emit(
            "removeCapabilities",
            data={"capabilityIds": capability_ids},
        )
        removed = set(capability_ids)
        device._capabilities = [
            capability_id
            for capability_id in device._capabilities
            if capability_id not in removed
        ]
        for capability_id in capability_ids:
            device._capabilities_options.pop(capability_id, None)
            device._state.pop(capability_id, None)

    def _capabilities_by_category(
        self, entities: list[EntityInfo]
    ) -> tuple[list[str], list[str]]:
        """Split current caps into diagnostic vs configuration by entity key."""
        diagnostic_keys: set[int] = set()
        configuration_keys: set[int] = set()
        for entity in entities:
            if entity.entity_category == EntityCategory.DIAGNOSTIC:
                diagnostic_keys.add(entity.key)
            elif entity.entity_category == EntityCategory.CONFIG:
                configuration_keys.add(entity.key)

        diagnostic: list[str] = []
        configuration: list[str] = []
        for capability_id, stored in self._device._capabilities_options.items():
            # WORKAROUND: Homey may persist options as null (Athom will return {}).
            key = (stored or {}).get("key")
            if key is None:
                continue
            key = int(key)
            if key in diagnostic_keys:
                diagnostic.append(capability_id)
            elif key in configuration_keys:
                configuration.append(capability_id)
        return diagnostic, configuration

    async def _list_mapped_entities(
        self,
    ) -> tuple[list[EntityInfo], dict[str, Any]]:
        """List entities and map them with the device's category settings."""
        device = self._device
        entities, _services = await device._require_client().list_entities_services()
        scratch = DeviceEntityMapper.empty_option()
        DeviceEntityMapper.map_device(
            entities,
            scratch,
            diagnostics=bool(device.get_setting("show_diagnostics")),
            configuration=bool(device.get_setting("show_configuration")),
            refresh=refresh_options(device.driver.manifest),
        )
        return entities, dict(scratch)

    async def _apply_capability_refresh(
        self,
        entities: list[EntityInfo],
        to_remove: list[str],
        to_add: list[tuple[str, dict[str, Any]]],
        to_update: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """Apply a capability plan and rewrite the category indexes."""
        device = self._device
        added = dict(to_add)
        await self._remove_capabilities(to_remove)
        await self._add_capabilities(list(added), added)
        for capability_id, options in to_update:
            await device.set_capability_options(capability_id, options)
            # The entity's key, name or sub-device may have changed.
            device.bind_capability(capability_id)

        diagnostic, configuration = self._capabilities_by_category(entities)
        await device.set_store_value("diagnostic_capabilities", diagnostic)
        await device.set_store_value("configuration_capabilities", configuration)

    async def _store_entities_build(self, build: str) -> None:
        """Record the build the current capabilities were mapped from."""
        device = self._device
        if device.get_store().get("entities_build") != build:
            await device.set_store_value("entities_build", build)


def _removed_title(stored: Any, capability_id: str) -> str:
    """Return the stored title, or the capability id when it has none."""
    title = stored.get("title") if isinstance(stored, dict) else None
    if isinstance(title, str) and title:
        return title
    if isinstance(title, dict):
        english = title.get("en")
        if isinstance(english, str) and english:
            return english
    return capability_id
