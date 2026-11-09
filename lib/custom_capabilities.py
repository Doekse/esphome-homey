"""Parsers for this app's own capabilities, on top of the system capabilities.

homey-esphomedriver knows Homey's system capabilities. The generic app also
shows entities as ``esphome_*`` capabilities, a few extra Homey-style ones
(``thermostat_preset``, ``light_effect``, ``open`` …) and event
capabilities. Their parsers live here and are passed to
``register_capability``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from aioesphomeapi import AlarmControlPanelState, ClimatePreset, LockCommand
from homey_esphomedriver.system import (
    BoundEntity,
    ReportParser,
    SetParser,
    capability_base,
    lookup,
)

from lib.formatting import (
    format_date,
    format_event_type,
    format_timestamp,
    format_uptime,
)
from lib.tasks import spawn

if TYPE_CHECKING:
    from homey.device import Device

    from lib.flow import DriverFlowHandler

_BUTTON_IDLE_DELAY_MS = 1000
_DOORBELL_IDLE_DELAY_MS = 5000
_IDLE = "idle"

EVENT_CAPABILITIES = ("alarm_doorbell", "event_button", "event_generic")
"""Event capabilities: set when the event fires, back to idle shortly after."""

_SUBCAPABILITIES = (
    "esphome_number",
    "esphome_select",
    "esphome_string",
    "esphome_boolean",
)
"""Suffixed capabilities whose base Flow card fires on a change."""

_PRESET = {
    ClimatePreset.NONE: "none",
    ClimatePreset.HOME: "home",
    ClimatePreset.AWAY: "away",
    ClimatePreset.BOOST: "boost",
    ClimatePreset.COMFORT: "comfort",
    ClimatePreset.ECO: "eco",
    ClimatePreset.SLEEP: "sleep",
    ClimatePreset.ACTIVITY: "activity",
}


def _report_preset(state: Any, entity: BoundEntity) -> str | None:
    del entity
    if state.custom_preset:
        return str(state.custom_preset)
    if state.preset is None:
        return None
    return _PRESET.get(state.preset, "none")


def _set_preset(
    value: Any, opts: Mapping[str, Any], entity: BoundEntity
) -> dict[str, Any]:
    del opts, entity
    preset = ClimatePreset.__members__.get(str(value).upper())
    if preset is not None and str(value) == preset.name.lower():
        return {"preset": preset}
    return {"custom_preset": str(value)}


def _report_effect(state: Any, entity: BoundEntity) -> str:
    del entity
    return str(state.effect)


def _set_effect(
    value: Any, opts: Mapping[str, Any], entity: BoundEntity
) -> dict[str, Any]:
    del opts, entity
    return {"state": True, "effect": str(value)}


def _report_triggered(state: Any, entity: BoundEntity) -> bool:
    del entity
    return bool(state.state == AlarmControlPanelState.TRIGGERED)


def _set_open(
    value: Any, opts: Mapping[str, Any], entity: BoundEntity
) -> dict[str, Any]:
    del value, opts, entity
    return {"command": LockCommand.OPEN}


def _report_uptime(state: Any, entity: BoundEntity) -> str:
    del entity
    return format_uptime(float(state.state))


def _report_date(state: Any, entity: BoundEntity) -> str:
    del entity
    return format_date(str(state.state))


def _report_timestamp(state: Any, entity: BoundEntity) -> str:
    del entity
    return format_timestamp(str(state.state))


def _report_text(state: Any, entity: BoundEntity) -> str:
    """The state as text; a sensor without a unit is shown as text too."""
    del entity
    return str(state.state)


_PARSERS: dict[str, tuple[ReportParser | None, SetParser | None]] = {
    "thermostat_preset": (_report_preset, _set_preset),
    "light_effect": (_report_effect, _set_effect),
    "alarm_triggered": (_report_triggered, None),
    "open": (None, _set_open),
    "measure_uptime": (_report_uptime, None),
    "measure_date": (_report_date, None),
    "measure_timestamp": (_report_timestamp, None),
    "esphome_string": (_report_text, None),
}
"""This app's parsers by capability base; ``None`` keeps the system parser."""


class CustomCapabilities:
    """This app's parsers for one device, and the timers its events need."""

    def __init__(self, device: Device, flow: DriverFlowHandler) -> None:
        """
        Args:
            device: The Homey device.
            flow: Fires the Flow cards of sub-capability changes and events.
        """
        self._device = device
        self._flow = flow
        self._idle_timeouts: dict[str, Any] = {}

    def parsers(self, capability_id: str, domain: str) -> dict[str, Any]:
        """Keyword arguments for ``register_capability`` of ``capability_id``."""
        base = capability_base(capability_id)
        if base == "aircleaner_mode":
            system = lookup("fan_mode", domain)
            if system is not None:
                return {
                    "report_parser": system.report_parser,
                    "set_parser": system.set_parser,
                }
        if base in EVENT_CAPABILITIES:
            return {"report_parser": self._event_parser(capability_id)}
        report, setter = _PARSERS.get(base, (None, None))
        if base in _SUBCAPABILITIES:
            if report is None:
                system = lookup(capability_id, domain)
                report = system.report_parser if system else None
            if report is not None:
                report = self._triggering(capability_id, report)
        kwargs: dict[str, Any] = {}
        if report is not None:
            kwargs["report_parser"] = report
        if setter is not None:
            kwargs["set_parser"] = setter
        return kwargs

    def uninit(self) -> None:
        """Cancel idle timers of events that just fired."""
        for timeout_id in self._idle_timeouts.values():
            self._device.homey.clear_timeout(timeout_id)
        self._idle_timeouts.clear()

    def _triggering(self, capability_id: str, report: ReportParser) -> ReportParser:
        """Fire the base Flow card when the value of a sub-capability changes.

        Homey only fires ``<full_id>_changed`` itself, which compose cannot
        declare for ids made from object ids.
        """

        def parse(state: Any, entity: BoundEntity) -> Any:
            value = report(state, entity)
            previous = self._device.get_capability_value(capability_id)
            if value is not None and value != previous:
                spawn(
                    self._device,
                    self._flow.trigger_subcapability(
                        self._device, capability_id, value
                    ),
                )
            return value

        return parse

    def _event_parser(self, capability_id: str) -> ReportParser:
        doorbell = capability_base(capability_id) == "alarm_doorbell"

        def parse(state: Any, entity: BoundEntity) -> Any:
            del entity
            self._cancel_idle(capability_id)
            event_type = str(state.event_type)
            value: Any = True if doorbell else event_type
            token = None if doorbell else format_event_type(event_type)
            idle: Any = False if doorbell else _IDLE
            delay = _DOORBELL_IDLE_DELAY_MS if doorbell else _BUTTON_IDLE_DELAY_MS
            spawn(
                self._device,
                self._trigger_then_idle(capability_id, token, idle, delay),
            )
            return value

        return parse

    async def _trigger_then_idle(
        self, capability_id: str, token: Any, idle: Any, delay_ms: int
    ) -> None:
        await self._flow.trigger_event(self._device, capability_id, token)

        def on_idle() -> None:
            self._idle_timeouts.pop(capability_id, None)
            spawn(self._device, self._device.set_capability_value(capability_id, idle))

        self._idle_timeouts[capability_id] = self._device.homey.set_timeout(
            on_idle, delay_ms
        )

    def _cancel_idle(self, capability_id: str) -> None:
        timeout_id = self._idle_timeouts.pop(capability_id, None)
        if timeout_id is not None:
            self._device.homey.clear_timeout(timeout_id)
