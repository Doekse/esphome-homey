"""Map ESPHome SwitchInfo onto Homey onoff capabilities."""

from __future__ import annotations

from typing import cast

from aioesphomeapi import EntityInfo, SwitchInfo
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from lib.mapping import (
    DeviceEntityMapper,
)


class SwitchEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        info = cast(SwitchInfo, entity)
        DeviceEntityMapper.set_device_class(homey_device, "socket")
        DeviceEntityMapper.add_indexed(homey_device, info.key, "onoff")
