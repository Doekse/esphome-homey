"""Map ESPHome CoverInfo onto Homey windowcovering capabilities."""

from __future__ import annotations

from typing import cast

from aioesphomeapi import CoverInfo, EntityInfo
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from app.lib.mapping import (
    DeviceEntityMapper,
    lookup_device_class,
)

CLASS_MAP: dict[str, str] = {
    "awning": "sunshade",
    "blind": "blinds",
    "curtain": "curtain",
    "damper": "windowcoverings",
    "door": "garagedoor",
    "garage": "garagedoor",
    "gate": "garagedoor",
    "shade": "sunshade",
    "shutter": "shutterblinds",
    "window": "windowcoverings",
}


class CoverEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        if DeviceEntityMapper.has_entity_type(homey_device, "cover"):
            return

        info = cast(CoverInfo, entity)
        covering_type = lookup_device_class(info.device_class, CLASS_MAP) or (
            "windowcoverings"
        )

        DeviceEntityMapper.set_device_class(homey_device, covering_type)
        DeviceEntityMapper.add_capability(
            homey_device, info.key, "windowcoverings_state"
        )

        if info.supports_position:
            DeviceEntityMapper.add_capability(
                homey_device, info.key, "windowcoverings_set"
            )

        if info.supports_tilt:
            for base in (
                "windowcoverings_tilt_up",
                "windowcoverings_tilt_down",
                "windowcoverings_tilt_set",
            ):
                DeviceEntityMapper.add_capability(homey_device, info.key, base)

        if covering_type == "garagedoor":
            DeviceEntityMapper.add_capability(
                homey_device, info.key, "garagedoor_closed"
            )
        elif not info.supports_position:
            # Without a position slider, this shows whether it is open.
            DeviceEntityMapper.add_capability(
                homey_device, info.key, "windowcoverings_closed"
            )
