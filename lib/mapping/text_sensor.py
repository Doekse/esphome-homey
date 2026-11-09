"""Map ESPHome TextSensorInfo onto Homey string capabilities.

ESPHome ``text_sensor`` only supports ``date`` / ``timestamp`` device classes
(ISO8601 strings); everything else uses ``esphome_string.<object_id>``.
"""

from __future__ import annotations

from typing import cast

from aioesphomeapi import EntityInfo, TextSensorInfo
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from lib.mapping import (
    DeviceEntityMapper,
    lookup_device_class,
)

CAPABILITY_MAP: dict[str, str] = {
    "date": "measure_date",
    "timestamp": "measure_timestamp",
}


class TextSensorEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        info = cast(TextSensorInfo, entity)
        DeviceEntityMapper.set_device_class(homey_device, "sensor")

        capability_id = lookup_device_class(info.device_class, CAPABILITY_MAP)
        if capability_id is not None:
            DeviceEntityMapper.add_indexed(homey_device, info.key, capability_id)
            return

        DeviceEntityMapper.add_suffixed(homey_device, info.key, "esphome_string")
