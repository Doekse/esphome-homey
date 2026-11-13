"""Map ESPHome LockInfo onto Homey lock capabilities."""

from __future__ import annotations

from typing import cast

from aioesphomeapi import EntityInfo, LockInfo
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from app.lib.mapping import (
    DeviceEntityMapper,
)


class LockEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        if DeviceEntityMapper.has_entity_type(homey_device, "lock"):
            return

        info = cast(LockInfo, entity)
        DeviceEntityMapper.set_device_class(homey_device, "lock")
        DeviceEntityMapper.add_capability(homey_device, info.key, "locked")
        DeviceEntityMapper.add_capability(homey_device, info.key, "alarm_door_fault")
        if info.supports_open:
            DeviceEntityMapper.add_capability(homey_device, info.key, "open")
