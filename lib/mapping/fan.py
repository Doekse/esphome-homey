"""Map ESPHome FanInfo onto Homey fan capabilities."""

from __future__ import annotations

from typing import cast

from aioesphomeapi import EntityInfo, FanInfo
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from lib.mapping import (
    DeviceEntityMapper,
    picker_values,
)


class FanEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        if DeviceEntityMapper.has_entity_type(homey_device, "fan"):
            return

        info = cast(FanInfo, entity)
        DeviceEntityMapper.set_device_class(homey_device, "fan")
        DeviceEntityMapper.add_indexed(homey_device, info.key, "onoff")

        if info.supports_speed:
            speed_count = info.supported_speed_count or 1
            DeviceEntityMapper.add_capability(
                homey_device,
                info.key,
                "fan_speed",
                {"min": 0, "max": 1, "step": 1 / speed_count},
            )

        if info.supports_oscillation:
            DeviceEntityMapper.add_capability(homey_device, info.key, "fan_oscillate")

        presets = [mode for mode in info.supported_preset_modes if mode]
        if not presets:
            return

        lowered = [mode.lower() for mode in presets]
        capability = (
            "aircleaner_mode"
            if all(mode in {"fan", "auto", "silent", "favorite"} for mode in lowered)
            else "fan_mode"
        )
        DeviceEntityMapper.add_capability(
            homey_device,
            info.key,
            capability,
            {
                "values": picker_values((mode.lower(), mode) for mode in presets),
            },
        )
