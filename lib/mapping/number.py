"""Map ESPHome NumberInfo onto settable Homey slider capabilities."""

from __future__ import annotations

from typing import cast

from aioesphomeapi import EntityInfo, NumberInfo
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from lib.mapping import (
    DeviceEntityMapper,
)


class NumberEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        info = cast(NumberInfo, entity)
        capability_options: dict[str, object] = {
            "setable": True,
            "uiComponent": "slider",
            "min": info.min_value,
            "max": info.max_value,
            "step": info.step,
        }
        if info.unit_of_measurement:
            capability_options["units"] = info.unit_of_measurement

        DeviceEntityMapper.add_suffixed(
            homey_device,
            info.key,
            "esphome_number",
            capability_options,
        )
