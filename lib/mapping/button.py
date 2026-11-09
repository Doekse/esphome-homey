"""Map ESPHome ButtonInfo onto pressable Homey button capabilities."""

from __future__ import annotations

from typing import cast

from aioesphomeapi import ButtonInfo, EntityInfo
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from lib.mapping import (
    DeviceEntityMapper,
)


class ButtonEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        info = cast(ButtonInfo, entity)
        device_class = (info.device_class or "").lower()
        if device_class in ("restart", "identify"):
            DeviceEntityMapper.add_indexed(homey_device, info.key, device_class)
            return
        DeviceEntityMapper.add_suffixed(homey_device, info.key, "button")
