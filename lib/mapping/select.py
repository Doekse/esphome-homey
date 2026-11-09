"""Map ESPHome SelectInfo onto Homey enum picker capabilities."""

from __future__ import annotations

from typing import cast

from aioesphomeapi import EntityInfo, SelectInfo
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from lib.mapping import (
    DeviceEntityMapper,
    picker_values,
)


class SelectEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        info = cast(SelectInfo, entity)
        if not info.options:
            return

        DeviceEntityMapper.add_suffixed(
            homey_device,
            info.key,
            "esphome_select",
            {
                "values": picker_values((option, option) for option in info.options),
            },
        )
