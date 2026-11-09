"""The generic device binds what pairing mapped, and the driver maps it."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aioesphomeapi import ButtonInfo, DeviceInfo, LightInfo, SwitchInfo

from lib.custom_capabilities import CustomCapabilities
from lib.device import GenericEspHomeDevice
from lib.driver import GenericEspHomeDriver


def _device(options: dict[str, Any]) -> GenericEspHomeDevice:
    device = GenericEspHomeDevice.__new__(GenericEspHomeDevice)
    device._capabilities = list(options)
    device._capabilities_options = dict(options)
    device._custom = CustomCapabilities(device, AsyncMock())
    device._unbound = []
    device.register_capability = MagicMock()  # type: ignore[method-assign]
    device.error = MagicMock()

    async def set_capability_options(capability_id: str, values: Any) -> None:
        device._capabilities_options[capability_id] = dict(values)

    device.set_capability_options = set_capability_options  # type: ignore[method-assign]
    return device


def test_capabilities_bind_to_the_entity_their_options_record() -> None:
    device = _device(
        {
            "onoff": {"key": 1, "entity_type": "switch", "name": "Relay"},
            "dim.led": {
                "key": 2,
                "entity_type": "light",
                "name": "LED",
                "device_id": 3,
            },
            "esphome_button": {"uiComponent": None},
            "button.refresh": None,
        }
    )
    for capability_id in list(device._capabilities_options):
        device.bind_capability(capability_id)

    calls = [
        call.args + (call.kwargs.get("device_id"),)
        for call in device.register_capability.call_args_list
    ]  # noqa: E501
    assert calls == [("onoff", "switch", "Relay", 0), ("dim.led", "light", "LED", 3)]


def test_a_capability_the_library_cannot_bind_is_logged() -> None:
    device = _device({"brand": {"key": 1, "entity_type": "light", "name": "LED"}})
    device.register_capability.side_effect = ValueError("no parser")  # type: ignore[attr-defined]
    device.bind_capability("brand")
    device.error.assert_called_once()


def test_capabilities_paired_by_key_get_their_name_on_connect() -> None:
    """Devices paired before 0.6 stored only the entity key."""
    device = _device({"onoff": {"key": 1, "entity_type": "switch"}})
    device.bind_capability("onoff")
    device.register_capability.assert_not_called()  # type: ignore[attr-defined]
    assert device._unbound == ["onoff"]

    relay = SwitchInfo(object_id="relay", key=1, name="Relay")
    client = SimpleNamespace(
        list_entities_services=AsyncMock(return_value=([relay], []))
    )
    asyncio.run(device._bind_by_key(client))  # type: ignore[arg-type]

    assert device._capabilities_options["onoff"]["name"] == "Relay"
    device.register_capability.assert_called_once()  # type: ignore[attr-defined]
    assert device._unbound == []


def test_pairing_maps_every_entity() -> None:
    driver = GenericEspHomeDriver.__new__(GenericEspHomeDriver)
    driver.manifest = {}  # type: ignore[misc]
    driver.debug = MagicMock()  # type: ignore[method-assign]
    payload: dict[str, Any] = {
        "name": "node",
        "data": {"id": "aabbccddeeff"},
        "store": {"address": "192.0.2.1"},
        "settings": {"host": "192.0.2.1"},
    }
    entities = [
        LightInfo(object_id="led", key=1, name="LED"),
        ButtonInfo(object_id="reset", key=2, name="Reset"),
    ]

    result = asyncio.run(
        driver.on_pair_device(payload, DeviceInfo(compilation_time="b1"), entities)  # type: ignore[arg-type]
    )

    assert "onoff" in result["capabilities"]
    assert "button.reset" in result["capabilities"]
    assert "button.refresh" in result["capabilities"]
    assert result["capabilitiesOptions"]["onoff"]["name"] == "LED"
    assert result["class"] == "light"
    assert result["settings"]["device_class"] == "auto"
    assert result["store"] == {
        "address": "192.0.2.1",
        "auto_class": "light",
        "entities_build": "b1",
    }


def test_sensors_shown_as_controls_are_refreshed_on_connect() -> None:
    """Before 0.6, garage door and lock binary sensors became toggles."""
    device = _device(
        {
            "garagedoor_closed": {
                "key": 1,
                "entity_type": "binary_sensor",
                "name": "Garage",
            },
            "onoff": {"key": 2, "entity_type": "switch", "name": "Relay"},
        }
    )
    device._capability_handler = SimpleNamespace(refresh=AsyncMock())  # type: ignore[assignment]
    client = SimpleNamespace(device_info=None)
    asyncio.run(device.on_esphome_ready(client))  # type: ignore[arg-type]
    device._capability_handler.refresh.assert_awaited_once()


def test_capabilities_that_only_show_a_value_are_left_alone() -> None:
    device = _device(
        {
            "alarm_contact": {"key": 1, "entity_type": "binary_sensor", "name": "Door"},
            "onoff": {"key": 2, "entity_type": "switch", "name": "Relay"},
            "button.refresh": None,
        }
    )
    assert device._has_outdated_capabilities() is False
