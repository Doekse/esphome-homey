"""Map ESPHome BinarySensorInfo onto Homey alarm and contact capabilities."""

from __future__ import annotations

from typing import cast

from aioesphomeapi import BinarySensorInfo, EntityInfo
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from app.lib.mapping import (
    DeviceEntityMapper,
    lookup_device_class,
)

CAPABILITY_MAP: dict[str, str] = {
    "battery": "alarm_battery",
    "battery_charging": "battery_charging_state",
    "carbon_monoxide": "alarm_co",
    "cold": "alarm_cold",
    "connectivity": "alarm_connectivity",
    "door": "alarm_contact",
    "garage_door": "alarm_contact",
    "gas": "alarm_gas",
    "heat": "alarm_heat",
    "light": "alarm_light",
    "moisture": "alarm_moisture",
    "motion": "alarm_motion",
    "moving": "alarm_generic",
    "occupancy": "alarm_occupancy",
    "opening": "alarm_open",
    "plug": "alarm_plugged_in",
    "power": "alarm_power",
    "presence": "alarm_presence",
    "problem": "alarm_problem",
    "running": "alarm_running",
    "safety": "alarm_safety",
    "smoke": "alarm_smoke",
    "sound": "alarm_noise",
    "tamper": "alarm_tamper",
    "vibration": "alarm_vibration",
    "window": "alarm_contact",
}


class BinarySensorEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        info = cast(BinarySensorInfo, entity)
        device_class = (info.device_class or "").lower()
        if device_class == "smoke":
            DeviceEntityMapper.set_device_class(homey_device, "smokealarm")
        else:
            DeviceEntityMapper.set_device_class(homey_device, "sensor")

        if device_class == "update":
            return

        capability_id = lookup_device_class(device_class, CAPABILITY_MAP)
        if capability_id is not None:
            DeviceEntityMapper.add_indexed(homey_device, info.key, capability_id)
            return

        DeviceEntityMapper.add_suffixed(homey_device, info.key, "esphome_boolean")
