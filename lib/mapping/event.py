"""Map ESPHome EventInfo onto Homey event capabilities."""

from __future__ import annotations

from typing import cast

from aioesphomeapi import EntityInfo, EventInfo
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from lib.formatting import format_event_type
from lib.mapping import (
    DeviceEntityMapper,
    picker_values,
)


class EventEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        info = cast(EventInfo, entity)
        if not info.event_types:
            return

        device_class = (info.device_class or "").lower()
        if device_class == "doorbell":
            DeviceEntityMapper.set_device_class(homey_device, "doorbell")
            DeviceEntityMapper.add_suffixed(homey_device, info.key, "alarm_doorbell")
            return

        base = "event_button" if device_class == "button" else "event_generic"
        DeviceEntityMapper.add_suffixed(
            homey_device,
            info.key,
            base,
            {
                "values": picker_values(
                    [
                        ("idle", "Idle"),
                        *[
                            (event_type, format_event_type(event_type))
                            for event_type in info.event_types
                        ],
                    ]
                ),
            },
        )
