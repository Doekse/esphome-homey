"""The generic ESPHome driver: pairs any node with a capability per entity."""

from __future__ import annotations

from collections.abc import Sequence

from aioesphomeapi import DeviceInfo, EntityInfo
from homey_esphomedriver import EspHomeDriver
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from app.lib.flow import DriverFlowHandler
from app.lib.mapping import DeviceEntityMapper, refresh_options


class GenericEspHomeDriver(EspHomeDriver):
    """Maps every entity of a node to a capability when it is paired."""

    flow: DriverFlowHandler

    async def on_esphome_init(self) -> None:
        """Wire the app's Flow cards."""
        self.flow = DriverFlowHandler(self)
        self.flow.register()

    async def on_pair_device(
        self,
        device: HomeyEspHomeDeviceOption,
        device_info: DeviceInfo,
        entities: Sequence[EntityInfo],
    ) -> HomeyEspHomeDeviceOption:
        """Give the new device a capability for every entity it can show."""
        scratch = DeviceEntityMapper.empty_option()
        DeviceEntityMapper.map_device(
            list(entities), scratch, refresh=refresh_options(self.manifest)
        )
        # Homey requires a class; mapping leaves it unset when no entity claims one.
        device_class = scratch.get("class") or "other"
        device["capabilities"] = scratch["capabilities"]
        device["capabilitiesOptions"] = scratch["capabilitiesOptions"]
        device["class"] = device_class
        device["settings"].update(
            {
                "device_class": "auto",
                "show_diagnostics": False,
                "show_configuration": False,
            }
        )
        device["store"].update(
            {"auto_class": device_class, "entities_build": device_info.compilation_time}
        )
        self.debug(
            f"Mapped {device['name']} to {len(device['capabilities'])} "
            f"capabilities, class={device_class}"
        )
        return device
