"""Map ESPHome WaterHeaterInfo onto Homey waterheater capabilities.

Homey's ``heater_operation_mode`` values match ESPHome ``WaterHeaterMode`` names.
"""

from __future__ import annotations

from typing import cast

from aioesphomeapi import (
    EntityInfo,
    WaterHeaterFeature,
    WaterHeaterInfo,
    WaterHeaterMode,
)
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption
from homey_esphomedriver.units import convert_temperature, temperature_unit_label

from lib.mapping import DeviceEntityMapper, celsius_step, picker_values


class WaterHeaterEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        if DeviceEntityMapper.has_entity_type(homey_device, "water_heater"):
            return

        info = cast(WaterHeaterInfo, entity)
        DeviceEntityMapper.set_device_class(homey_device, "waterheater")

        flags = info.supported_features
        unit = info.temperature_unit
        unit_label = temperature_unit_label(unit)

        if flags & WaterHeaterFeature.SUPPORTS_ON_OFF:
            DeviceEntityMapper.add_indexed(homey_device, info.key, "onoff")

        if flags & WaterHeaterFeature.SUPPORTS_OPERATION_MODE:
            titles = {
                WaterHeaterMode.OFF: "Off",
                WaterHeaterMode.ECO: "Eco",
                WaterHeaterMode.ELECTRIC: "Electric",
                WaterHeaterMode.PERFORMANCE: "Performance",
                WaterHeaterMode.HIGH_DEMAND: "High Demand",
                WaterHeaterMode.HEAT_PUMP: "Heat Pump",
                WaterHeaterMode.GAS: "Gas",
            }
            values = picker_values(
                (mode.name.lower(), titles[mode])
                for mode in info.supported_modes
                if mode in titles
            )
            DeviceEntityMapper.add_capability(
                homey_device,
                info.key,
                "heater_operation_mode",
                {"values": values} if values else {},
            )

        temp_options: dict[str, object] = {
            "min": convert_temperature(unit_label, info.min_temperature),
            "max": convert_temperature(unit_label, info.max_temperature),
            "step": celsius_step(unit, info.target_temperature_step),
        }
        if flags & WaterHeaterFeature.SUPPORTS_TWO_POINT_TARGET_TEMPERATURE:
            for base in ("target_temperature_min", "target_temperature_max"):
                DeviceEntityMapper.add_capability(
                    homey_device,
                    info.key,
                    base,
                    temp_options,
                )
        elif flags & WaterHeaterFeature.SUPPORTS_TARGET_TEMPERATURE:
            DeviceEntityMapper.add_capability(
                homey_device,
                info.key,
                "target_temperature",
                temp_options,
            )

        if flags & WaterHeaterFeature.SUPPORTS_CURRENT_TEMPERATURE:
            DeviceEntityMapper.add_capability(
                homey_device, info.key, "measure_temperature"
            )
