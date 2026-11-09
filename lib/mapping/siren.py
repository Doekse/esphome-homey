"""Map ESPHome SirenInfo onto Homey siren capabilities.

Homey has no siren-specific system capability; a siren uses ``onoff`` and
``volume_set``.
"""

from __future__ import annotations

from typing import cast

from aioesphomeapi import EntityInfo, SirenInfo
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from lib.mapping import (
    DeviceEntityMapper,
)


class SirenEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        if DeviceEntityMapper.has_entity_type(homey_device, "siren"):
            return

        info = cast(SirenInfo, entity)
        DeviceEntityMapper.set_device_class(homey_device, "siren")
        DeviceEntityMapper.add_indexed(homey_device, info.key, "onoff")

        if info.supports_volume:
            DeviceEntityMapper.add_capability(homey_device, info.key, "volume_set")
