"""Map ESPHome ValveInfo onto Homey valve capabilities."""

from __future__ import annotations

from typing import cast

from aioesphomeapi import EntityInfo, ValveInfo
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from lib.mapping import (
    DeviceEntityMapper,
)


class ValveEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        if DeviceEntityMapper.has_entity_type(homey_device, "valve"):
            return

        info = cast(ValveInfo, entity)
        if (info.device_class or "").lower() == "water":
            DeviceEntityMapper.set_device_class(homey_device, "watervalve")

        if info.supports_position:
            DeviceEntityMapper.add_capability(homey_device, info.key, "valve_position")
        else:
            DeviceEntityMapper.add_indexed(homey_device, info.key, "onoff")
