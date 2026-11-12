"""This app's own capabilities, bound with register_capability.

The library knows Homey's system capabilities; the generic app adds the
``esphome_*`` and extra capabilities it maps entities to, and the Flow cards
and idle timers that go with them.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aioesphomeapi import (
    ClimateInfo,
    ClimatePreset,
    ClimateState,
    EntityInfo,
    Event,
    EventInfo,
    FanInfo,
    FanState,
    LightInfo,
    LightState,
    LockCommand,
    LockInfo,
    NumberInfo,
    NumberState,
    SensorInfo,
    SensorState,
)
from homey_esphomedriver.system import BoundEntity, domain_of

from app.lib.custom_capabilities import CustomCapabilities


class _Device:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.timeouts: list[Any] = []
        self.error = MagicMock()
        self.homey = SimpleNamespace(
            set_timeout=lambda callback, ms: (
                self.timeouts.append((callback, ms)) or len(self.timeouts)
            ),
            clear_timeout=MagicMock(),
        )

    def get_capability_value(self, capability_id: str) -> Any:
        return self.values.get(capability_id)

    async def set_capability_value(self, capability_id: str, value: Any) -> None:
        self.values[capability_id] = value


def _custom() -> tuple[CustomCapabilities, _Device, SimpleNamespace]:
    device = _Device()
    flow = SimpleNamespace(trigger_subcapability=AsyncMock(), trigger_event=AsyncMock())
    return CustomCapabilities(device, flow), device, flow  # type: ignore[arg-type]


def _entity(device: _Device, info: EntityInfo) -> BoundEntity:
    domain = domain_of(info)
    assert domain is not None
    return BoundEntity(device=device, info=info, domain=domain)  # type: ignore[arg-type]


def test_climate_preset_reads_and_sets_named_and_custom_presets() -> None:
    custom, device, _flow = _custom()
    parsers = custom.parsers("thermostat_preset", "climate")
    entity = _entity(device, ClimateInfo())
    report, setter = parsers["report_parser"], parsers["set_parser"]
    assert report(ClimateState(preset=ClimatePreset.ECO), entity) == "eco"
    assert report(ClimateState(custom_preset="Night"), entity) == "Night"
    assert setter("boost", {}, entity) == {"preset": ClimatePreset.BOOST}
    assert setter("Night", {}, entity) == {"custom_preset": "Night"}


def test_light_effect_and_lock_open() -> None:
    custom, device, _flow = _custom()
    light = _entity(device, LightInfo())
    effect = custom.parsers("light_effect", "light")
    assert effect["report_parser"](LightState(effect="Rainbow"), light) == "Rainbow"
    assert effect["set_parser"]("Rainbow", {}, light) == {
        "state": True,
        "effect": "Rainbow",
    }
    lock = _entity(device, LockInfo())
    assert custom.parsers("open", "lock")["set_parser"](True, {}, lock) == {
        "command": LockCommand.OPEN
    }


def test_air_cleaner_mode_uses_the_fan_mode_parsers() -> None:
    custom, device, _flow = _custom()
    fan = _entity(device, FanInfo())
    parsers = custom.parsers("aircleaner_mode", "fan")
    assert parsers["report_parser"](FanState(preset_mode="Silent"), fan) == "silent"
    assert parsers["set_parser"]("silent", {}, fan) == {"preset_mode": "Silent"}


def test_uptime_is_formatted() -> None:
    custom, device, _flow = _custom()
    sensor = _entity(device, SensorInfo(unit_of_measurement="s"))
    report = custom.parsers("measure_uptime", "sensor")["report_parser"]
    assert report(SensorState(state=90061.0), sensor) == "1d 1h 1m"


def test_system_capabilities_keep_the_library_parsers() -> None:
    custom, _device, _flow = _custom()
    assert custom.parsers("measure_temperature", "sensor") == {}
    assert custom.parsers("button.reset", "button") == {}


def test_sub_capability_change_fires_its_flow_card() -> None:
    async def run() -> None:
        custom, device, flow = _custom()
        number = _entity(device, NumberInfo())
        report = custom.parsers("esphome_number.level", "number")["report_parser"]

        assert report(NumberState(state=3.0), number) == 3.0
        await asyncio.sleep(0)
        flow.trigger_subcapability.assert_awaited_once_with(
            device, "esphome_number.level", 3.0
        )

        device.values["esphome_number.level"] = 3.0
        report(NumberState(state=3.0), number)
        await asyncio.sleep(0)
        assert flow.trigger_subcapability.await_count == 1

    asyncio.run(run())


def test_event_fires_its_flow_card_then_goes_idle() -> None:
    async def run() -> None:
        custom, device, flow = _custom()
        event = _entity(device, EventInfo())
        report = custom.parsers("event_button.remote", "event")["report_parser"]

        assert report(Event(event_type="double_press"), event) == "double_press"
        for _ in range(3):
            await asyncio.sleep(0)
        flow.trigger_event.assert_awaited_once_with(
            device, "event_button.remote", "Double Press"
        )
        (on_idle, delay) = device.timeouts[0]
        assert delay == 1000
        on_idle()
        await asyncio.sleep(0)
        assert device.values["event_button.remote"] == "idle"

    asyncio.run(run())


def test_doorbell_rings_for_five_seconds() -> None:
    async def run() -> None:
        custom, device, flow = _custom()
        event = _entity(device, EventInfo())
        report = custom.parsers("alarm_doorbell.front", "event")["report_parser"]

        assert report(Event(event_type="ring"), event) is True
        for _ in range(3):
            await asyncio.sleep(0)
        flow.trigger_event.assert_awaited_once_with(
            device, "alarm_doorbell.front", None
        )
        assert device.timeouts[0][1] == 5000

    asyncio.run(run())
