"""Map ESPHome ClimateInfo onto Homey climate capabilities.

Homey's thermostat UI binds bare capability IDs, so one climate maps per device.
"""

from __future__ import annotations

from typing import cast

from aioesphomeapi import (
    ClimateFanMode,
    ClimateInfo,
    ClimateMode,
    ClimatePreset,
    ClimateSwingMode,
    EntityInfo,
    TemperatureUnit,
)
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption
from homey_esphomedriver.units import convert_temperature, temperature_unit_label

from lib.mapping import DeviceEntityMapper, celsius_step, picker_values


class ClimateEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        if DeviceEntityMapper.has_entity_type(homey_device, "climate"):
            return

        info = cast(ClimateInfo, entity)
        modes = info.supported_modes
        cooling = {
            ClimateMode.COOL,
            ClimateMode.HEAT_COOL,
            ClimateMode.DRY,
            ClimateMode.FAN_ONLY,
        }
        DeviceEntityMapper.set_device_class(
            homey_device,
            "thermostat"
            if ClimateMode.HEAT in modes and not cooling.intersection(modes)
            else "airconditioning",
        )

        unit = info.temperature_unit or TemperatureUnit.CELSIUS
        unit_label = temperature_unit_label(unit)

        DeviceEntityMapper.add_capability(
            homey_device,
            info.key,
            "thermostat_mode",
            {"values": _thermostat_values(modes)},
        )
        DeviceEntityMapper.add_indexed(homey_device, info.key, "onoff")

        temp_options: dict[str, object] = {
            "min": convert_temperature(unit_label, info.visual_min_temperature),
            "max": convert_temperature(unit_label, info.visual_max_temperature),
            "step": celsius_step(unit, info.visual_target_temperature_step),
        }
        if info.supports_two_point_target_temperature:
            for base in ("target_temperature_min", "target_temperature_max"):
                DeviceEntityMapper.add_capability(
                    homey_device,
                    info.key,
                    base,
                    temp_options,
                )
        else:
            DeviceEntityMapper.add_capability(
                homey_device,
                info.key,
                "target_temperature",
                temp_options,
            )

        if info.supports_target_humidity:
            DeviceEntityMapper.add_capability(
                homey_device,
                info.key,
                "target_humidity",
                {
                    "min": info.visual_min_humidity,
                    "max": info.visual_max_humidity,
                },
            )

        fan_values = _climate_fan_values(
            info.supported_fan_modes,
            info.supported_custom_fan_modes,
        )
        if fan_values:
            DeviceEntityMapper.add_capability(
                homey_device,
                info.key,
                "fan_mode",
                {"values": fan_values},
            )

        swing_values = _swing_values(info.supported_swing_modes)
        if swing_values:
            DeviceEntityMapper.add_capability(
                homey_device,
                info.key,
                "swing_mode",
                {"values": swing_values},
            )

        preset_values = _climate_preset_values(
            info.supported_presets,
            info.supported_custom_presets,
        )
        if preset_values:
            DeviceEntityMapper.add_capability(
                homey_device,
                info.key,
                "thermostat_preset",
                {"values": preset_values},
            )

        if info.supports_current_temperature:
            DeviceEntityMapper.add_capability(
                homey_device, info.key, "measure_temperature"
            )

        if info.supports_current_humidity:
            DeviceEntityMapper.add_capability(
                homey_device,
                info.key,
                "measure_humidity",
            )


def _thermostat_values(modes: list[ClimateMode]) -> list[dict[str, object]]:
    titles = {
        ClimateMode.HEAT_COOL: ("auto", "Automatic"),
        ClimateMode.AUTO: ("auto", "Automatic"),
        ClimateMode.HEAT: ("heat", "Heat"),
        ClimateMode.COOL: ("cool", "Cool"),
        ClimateMode.DRY: ("dry", "Dry"),
        ClimateMode.FAN_ONLY: ("fan_only", "Fan"),
        ClimateMode.OFF: ("off", "Off"),
    }
    by_id: dict[str, tuple[str, str]] = {}
    for mode in modes:
        mapped = titles.get(mode)
        if mapped is not None:
            by_id[mapped[0]] = mapped
    return picker_values(
        by_id[mode_id]
        for mode_id in ("auto", "heat", "cool", "dry", "fan_only", "off")
        if mode_id in by_id
    )


def _swing_values(modes: list[ClimateSwingMode]) -> list[dict[str, object]]:
    if not modes or modes == [ClimateSwingMode.OFF]:
        return []
    present = set(modes)
    present.add(ClimateSwingMode.OFF)
    titles = {
        ClimateSwingMode.OFF: ("off", "Off"),
        ClimateSwingMode.VERTICAL: ("vertical", "Vertical"),
        ClimateSwingMode.HORIZONTAL: ("horizontal", "Horizontal"),
        ClimateSwingMode.BOTH: ("both", "Both"),
    }
    return picker_values(
        titles[mode]
        for mode in (
            ClimateSwingMode.OFF,
            ClimateSwingMode.VERTICAL,
            ClimateSwingMode.HORIZONTAL,
            ClimateSwingMode.BOTH,
        )
        if mode in present
    )


def _climate_fan_values(
    modes: list[ClimateFanMode],
    custom_modes: list[str],
) -> list[dict[str, object]]:
    if (not modes or modes == [ClimateFanMode.OFF]) and not custom_modes:
        return []
    present = set(modes)
    titles = {
        ClimateFanMode.AUTO: "Auto",
        ClimateFanMode.ON: "On",
        ClimateFanMode.LOW: "Low",
        ClimateFanMode.MEDIUM: "Medium",
        ClimateFanMode.MIDDLE: "Middle",
        ClimateFanMode.HIGH: "High",
        ClimateFanMode.FOCUS: "Focus",
        ClimateFanMode.DIFFUSE: "Diffuse",
        ClimateFanMode.QUIET: "Quiet",
        ClimateFanMode.OFF: "Off",
    }
    entries = [
        (mode.name.lower(), titles[mode])
        for mode in (
            ClimateFanMode.AUTO,
            ClimateFanMode.ON,
            ClimateFanMode.LOW,
            ClimateFanMode.MEDIUM,
            ClimateFanMode.MIDDLE,
            ClimateFanMode.HIGH,
            ClimateFanMode.FOCUS,
            ClimateFanMode.DIFFUSE,
            ClimateFanMode.QUIET,
            ClimateFanMode.OFF,
        )
        if mode in present
    ]
    used = {item_id for item_id, _title in entries}
    entries.extend(
        (mode, mode)
        for mode in custom_modes
        if mode and mode not in used and mode.lower() not in used
    )
    return picker_values(entries)


def _climate_preset_values(
    presets: list[ClimatePreset],
    custom_presets: list[str],
) -> list[dict[str, object]]:
    if (not presets or presets == [ClimatePreset.NONE]) and not custom_presets:
        return []
    present = set(presets)
    titles = {
        ClimatePreset.NONE: "None",
        ClimatePreset.HOME: "Home",
        ClimatePreset.AWAY: "Away",
        ClimatePreset.BOOST: "Boost",
        ClimatePreset.COMFORT: "Comfort",
        ClimatePreset.ECO: "Eco",
        ClimatePreset.SLEEP: "Sleep",
        ClimatePreset.ACTIVITY: "Activity",
    }
    entries = [
        (preset.name.lower(), titles[preset])
        for preset in (
            ClimatePreset.NONE,
            ClimatePreset.HOME,
            ClimatePreset.AWAY,
            ClimatePreset.BOOST,
            ClimatePreset.COMFORT,
            ClimatePreset.ECO,
            ClimatePreset.SLEEP,
            ClimatePreset.ACTIVITY,
        )
        if preset in present
    ]
    used = {item_id for item_id, _title in entries}
    entries.extend(
        (preset, preset)
        for preset in custom_presets
        if preset and preset not in used and preset.lower() not in used
    )
    return picker_values(entries)
