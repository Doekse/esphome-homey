"""Map ESPHome LightInfo onto Homey light capabilities.

Homey's color UI only binds bare ``light_*`` IDs, so a Homey device maps one light.
"""

from __future__ import annotations

from typing import cast

from aioesphomeapi import ColorMode, EntityInfo, LightColorCapability, LightInfo
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption
from homey_esphomedriver.units import mireds_to_kelvin

from lib.mapping import (
    DeviceEntityMapper,
    picker_values,
)


class LightEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        if DeviceEntityMapper.has_entity_type(homey_device, "light"):
            return

        info = cast(LightInfo, entity)
        DeviceEntityMapper.set_device_class(homey_device, "light")

        modes = info.supported_color_modes or []
        light_supports_brightness = _modes_support(
            modes, LightColorCapability.BRIGHTNESS
        )
        light_supports_color_changing = _modes_support(modes, LightColorCapability.RGB)
        light_supports_color_temp = _modes_support(
            modes,
            LightColorCapability.COLOR_TEMPERATURE,
        )

        DeviceEntityMapper.add_indexed(homey_device, info.key, "onoff")

        if (
            light_supports_brightness
            or light_supports_color_temp
            or light_supports_color_changing
        ):
            DeviceEntityMapper.add_capability(homey_device, info.key, "dim")

        if light_supports_color_temp:
            DeviceEntityMapper.add_capability(
                homey_device,
                info.key,
                "light_temperature",
                {
                    "min_color_temp_kelvin": (
                        int(round(mireds_to_kelvin(info.max_mireds)))
                        if info.max_mireds
                        else 2000
                    ),
                    "max_color_temp_kelvin": (
                        int(round(mireds_to_kelvin(info.min_mireds)))
                        if info.min_mireds
                        else 6500
                    ),
                },
            )

        if light_supports_color_changing:
            DeviceEntityMapper.add_capability(homey_device, info.key, "light_hue")
            DeviceEntityMapper.add_capability(
                homey_device, info.key, "light_saturation"
            )

        if light_supports_color_temp and light_supports_color_changing:
            DeviceEntityMapper.add_capability(homey_device, info.key, "light_mode")

        if info.effects:
            DeviceEntityMapper.add_capability(
                homey_device,
                info.key,
                "light_effect",
                {
                    "values": picker_values(
                        (effect, effect) for effect in info.effects
                    ),
                },
            )


def _modes_support(modes: list[ColorMode], flag: LightColorCapability) -> bool:
    """Return whether any advertised color mode includes the capability flag bit."""
    return any(int(mode) & int(flag) == int(flag) for mode in modes)
