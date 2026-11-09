"""Refresh-capability planning tests.

``plan_capability_refresh`` diffs by ``(entity key, capability base)`` so
remapping cannot reshuffle Flow cards bound to bare Homey ids. Caps without a
``key`` match on Homey id.
"""

from __future__ import annotations

import asyncio
from types import MappingProxyType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aioesphomeapi import (
    BinarySensorInfo,
    DeviceInfo,
    EntityCategory,
    EntityInfo,
    SensorInfo,
    SwitchInfo,
)

from lib.capabilities import DeviceCapabilityHandler
from lib.mapping import DeviceEntityMapper
from lib.refresh import (
    capability_base,
    plan_appeared_and_gone,
    plan_capability_refresh,
)


def test_capability_base() -> None:
    assert capability_base("onoff") == "onoff"
    assert capability_base("measure_temperature.1") == "measure_temperature"
    assert capability_base("esphome_number.pump") == "esphome_number"


def test_scope_keeps_entity_when_capability_base_changes() -> None:
    """An entity that is still present keeps its Homey id when the base changes."""
    current = {"onoff": {"key": 1, "title": "Relay"}}
    plan = (
        ["onoff"],
        [("measure_temperature", {"key": 1, "title": "Relay"})],
        [],
    )
    assert plan_appeared_and_gone(current, {1}, plan) == ([], [], [])


def test_scope_removes_vanished_key() -> None:
    current = {"onoff": {"key": 1}, "measure_temperature": {"key": 2}}
    plan = (["onoff"], [], [])
    assert plan_appeared_and_gone(current, {2}, plan) == (["onoff"], [], [])


def test_scope_adds_new_key() -> None:
    current = {"onoff": {"key": 1}}
    plan = ([], [("measure_temperature", {"key": 2})], [])
    assert plan_appeared_and_gone(current, {1, 2}, plan) == (
        [],
        [("measure_temperature", {"key": 2})],
        [],
    )


def test_scope_ignores_keyless_capabilities() -> None:
    current = {"onoff": {"key": 1}, "button.refresh": {}}
    plan = (
        ["button.refresh"],
        [("esphome_button", {"uiComponent": None})],
        [],
    )
    assert plan_appeared_and_gone(current, {1}, plan) == ([], [], [])


def test_scope_passes_updates_through() -> None:
    current = {"onoff": {"key": 1, "title": "Old"}}
    update = [("onoff", {"key": 1, "title": "New"})]
    plan = ([], [], update)
    assert plan_appeared_and_gone(current, {1}, plan) == ([], [], update)


def test_plan_keeps_current_id_when_identity_matches() -> None:
    """Matched (key, base) pairs keep the current Homey id, not the scratch id."""
    current = {"onoff": {"key": 1, "title": "Relay"}}
    desired = {"onoff.relay": {"key": 1, "title": "Relay"}}
    to_remove, to_add, to_update = plan_capability_refresh(current, desired)
    assert to_remove == []
    assert to_add == []
    assert to_update == []


def test_plan_updates_when_options_change() -> None:
    current = {"onoff": {"key": 1, "title": "Old"}}
    desired = {"onoff": {"key": 1, "title": "New"}}
    to_remove, to_add, to_update = plan_capability_refresh(current, desired)
    assert to_remove == []
    assert to_add == []
    assert to_update == [("onoff", {"key": 1, "title": "New"})]


def test_plan_removes_gone_entities_and_adds_new_ones() -> None:
    current = {"onoff": {"key": 1}, "measure_temperature": {"key": 2}}
    desired = {"measure_temperature": {"key": 2}, "onoff.pump": {"key": 3}}
    to_remove, to_add, to_update = plan_capability_refresh(current, desired)
    assert to_remove == ["onoff"]
    assert to_update == []
    assert to_add == [("onoff.pump", {"key": 3})]


def test_plan_indexes_scratch_when_bare_id_already_taken() -> None:
    """A new entity whose scratch id is already taken gets ``base.key``."""
    current = {"onoff": {"key": 1}}
    desired: dict[str, dict[str, Any]] = {
        "onoff": {"key": 2},
        "onoff.relay": {"key": 1},
    }
    to_remove, to_add, to_update = plan_capability_refresh(current, desired)
    assert to_remove == []
    assert to_update == []
    assert to_add == [("onoff.2", {"key": 2})]


def test_plan_adds_missing_flow_filter_marker() -> None:
    current = {
        "button.refresh": {},
        "button.play": {"key": 1},
    }
    desired = {
        "button.refresh": {},
        "esphome_button": {"uiComponent": None},
        "button.play": {"key": 1},
    }
    to_remove, to_add, to_update = plan_capability_refresh(current, desired)
    assert to_remove == []
    assert to_update == []
    assert to_add == [("esphome_button", {"uiComponent": None})]


def test_plan_removes_obsolete_flow_filter_marker() -> None:
    current = {
        "button.refresh": {},
        "esphome_boolean": {"uiComponent": None},
        "onoff": {"key": 1},
    }
    desired = {
        "button.refresh": {},
        "onoff": {"key": 1},
    }
    to_remove, to_add, to_update = plan_capability_refresh(current, desired)
    assert to_remove == ["esphome_boolean"]
    assert to_add == []
    assert to_update == []


def test_plan_survives_capability_options_stored_as_null() -> None:
    """A stored ``None`` is removed when the desired set does not name it."""
    current: dict[str, Any] = {
        "onoff": {"key": 1},
        "esphome_string.old_slot": None,
        "esphome_boolean": {"uiComponent": None},
    }
    desired: dict[str, Any] = {
        "onoff": {"key": 1},
        "esphome_boolean": {"uiComponent": None},
    }

    to_remove, to_add, to_update = plan_capability_refresh(current, desired)

    assert to_remove == ["esphome_string.old_slot"]
    assert to_add == []
    assert to_update == []


def test_plan_keeps_a_null_options_capability_the_node_still_has() -> None:
    """A null entry the desired set still names is filled in, not removed."""
    current: dict[str, Any] = {"esphome_boolean": None}
    desired: dict[str, Any] = {"esphome_boolean": {"uiComponent": None}}

    to_remove, to_add, to_update = plan_capability_refresh(current, desired)

    assert to_remove == []
    assert to_update == [("esphome_boolean", {"uiComponent": None})]


def test_category_split_survives_null_capability_options() -> None:
    """Category split skips null options instead of AttributeError on ``.get``."""
    handler = DeviceCapabilityHandler.__new__(DeviceCapabilityHandler)
    handler._device = SimpleNamespace(
        _capabilities_options={
            "measure_temperature": {"key": 1},
            "esphome_string.broken": None,
            "onoff": {"key": 2},
        }
    )
    entities = [
        BinarySensorInfo(
            object_id="status",
            key=1,
            name="Status",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        BinarySensorInfo(
            object_id="relay",
            key=2,
            name="Relay",
            entity_category=EntityCategory.CONFIG,
        ),
    ]

    diagnostic, configuration = handler._capabilities_by_category(entities)

    assert diagnostic == ["measure_temperature"]
    assert configuration == ["onoff"]


def _mapped(*entities: EntityInfo) -> tuple[list[str], dict[str, dict[str, Any]]]:
    scratch = DeviceEntityMapper.empty_option()
    DeviceEntityMapper.map_device(list(entities), scratch)
    return list(scratch["capabilities"]), dict(scratch["capabilitiesOptions"])


def _handler(
    entities: list[EntityInfo],
    *,
    capabilities: list[str],
    options: dict[str, Any],
    store: dict[str, Any] | None = None,
    compilation_time: str = "live",
    list_error: Exception | None = None,
) -> tuple[
    DeviceCapabilityHandler,
    SimpleNamespace,
    dict[str, Any],
    list[tuple[str, Any]],
]:
    saved = {} if store is None else dict(store)
    writes: list[tuple[str, Any]] = []

    async def set_store_value(key: str, value: Any) -> None:
        saved[key] = value
        writes.append((key, value))

    async def list_entities() -> tuple[list[EntityInfo], list[object]]:
        if list_error is not None:
            raise list_error
        return entities, []

    client = SimpleNamespace(
        device_info=DeviceInfo(compilation_time=compilation_time),
        list_entities_services=list_entities,
    )
    device = SimpleNamespace(
        _capabilities=list(capabilities),
        _capabilities_options=dict(options),
        _state={},
        _client_emit=AsyncMock(),
        bind_capability=MagicMock(),
        unregister_capability=MagicMock(),
        driver=SimpleNamespace(manifest={}),
        get_setting=lambda key: {"device_class": "auto"}.get(key),
        get_store=lambda: MappingProxyType(dict(saved)),
        set_store_value=set_store_value,
        set_capability_options=AsyncMock(),
        set_class=AsyncMock(),
        _require_client=lambda: client,
    )
    return DeviceCapabilityHandler(device), device, saved, writes


def test_sync_entities_keeps_base_change_and_records_build() -> None:
    """A firmware sync does not re-add an entity whose capability base changed."""
    relay = SwitchInfo(object_id="relay", key=1, name="Relay")
    capabilities, options = _mapped(relay)
    sensor = SensorInfo(
        object_id="temp",
        key=1,
        name="Temp",
        device_class="temperature",
    )
    handler, device, saved, writes = _handler(
        [sensor],
        capabilities=capabilities,
        options=options,
        store={"entities_build": "old"},
    )

    result = asyncio.run(handler.sync_entities("new"))

    assert result.added == []
    assert result.removed == []
    assert result.removed_titles == []
    assert "onoff" in device._capabilities
    assert not any(
        capability.startswith("measure_temperature")
        for capability in device._capabilities
    )
    device.set_class.assert_not_awaited()
    assert saved["entities_build"] == "new"
    assert writes[-1] == ("entities_build", "new")


def test_sync_entities_captures_removed_titles_before_removal() -> None:
    """Titles are read before removal deletes the capability options."""
    options = {
        "onoff.relay": {"key": 1, "title": "Relay"},
        "measure_temperature": {"key": 2},
        "sensor.localized": {
            "key": 3,
            "title": {"en": "Localized", "nl": "Gelokaliseerd"},
        },
        "onoff.nl_only": {"key": 4, "title": {"nl": "Alleen"}},
        "onoff.blank": {"key": 5, "title": ""},
    }
    handler, device, _saved, _writes = _handler(
        [],
        capabilities=list(options),
        options=options,
        store={"entities_build": "old"},
    )

    result = asyncio.run(handler.sync_entities("new"))

    assert result.removed == list(options)
    assert result.removed_titles == [
        "Relay",
        "measure_temperature",
        "Localized",
        "onoff.nl_only",
        "onoff.blank",
    ]
    assert device._capabilities_options == {}


def test_sync_entities_leaves_build_when_listing_fails() -> None:
    relay = SwitchInfo(object_id="relay", key=1, name="Relay")
    capabilities, options = _mapped(relay)
    handler, _device, saved, writes = _handler(
        [],
        capabilities=capabilities,
        options=options,
        store={"entities_build": "old"},
        list_error=RuntimeError("list failed"),
    )

    with pytest.raises(RuntimeError, match="list failed"):
        asyncio.run(handler.sync_entities("new"))

    assert saved["entities_build"] == "old"
    assert writes == []


def test_refresh_records_live_build() -> None:
    relay = SwitchInfo(object_id="relay", key=1, name="Relay")
    capabilities, options = _mapped(relay)
    handler, device, saved, writes = _handler(
        [relay],
        capabilities=capabilities,
        options=options,
        store={"entities_build": "old"},
        compilation_time="live",
    )

    asyncio.run(handler.refresh())

    device.set_class.assert_awaited_once_with("socket")
    assert saved["entities_build"] == "live"
    assert writes[-1] == ("entities_build", "live")


def test_sync_binds_added_and_unbinds_removed_capabilities() -> None:
    relay = SwitchInfo(object_id="relay", key=1, name="Relay")
    pump = SwitchInfo(object_id="pump", key=2, name="Pump")
    capabilities, options = _mapped(relay)
    handler, device, _saved, _writes = _handler(
        [pump],
        capabilities=capabilities,
        options=options,
        store={"entities_build": "old"},
    )

    result = asyncio.run(handler.sync_entities("new"))

    assert result.removed == ["onoff"]
    device.unregister_capability.assert_called_once_with("onoff")
    added = result.added
    assert added and all(cap in device._capabilities for cap in added)
    device.bind_capability.assert_any_call(added[0])
    assert device._capabilities_options[added[0]]["name"] == "Pump"
