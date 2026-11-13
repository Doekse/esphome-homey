"""Map ESPHome SensorInfo onto Homey measure and meter capabilities."""

from __future__ import annotations

from typing import cast

from aioesphomeapi import EntityInfo, SensorInfo
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from app.lib.mapping import (
    DeviceEntityMapper,
    ObjectIdAlias,
    lookup_device_class,
    match_object_id_alias,
)

CAPABILITY_MAP: dict[str, str] = {
    "absolute_humidity": "measure_absolute_humidity",
    "apparent_power": "measure_apparent_power",
    "aqi": "measure_aqi",
    "area": "measure_area",
    "atmospheric_pressure": "measure_pressure",
    "battery": "measure_battery",
    "blood_glucose_concentration": "measure_blood_glucose",
    "carbon_dioxide": "measure_co2",
    "carbon_monoxide": "measure_co",
    "conductivity": "measure_conductivity",
    "current": "measure_current",
    "data_rate": "measure_data_rate",
    "data_size": "measure_data_size",
    "distance": "measure_distance",
    "duration": "measure_duration",
    "energy": "meter_power",
    "energy_distance": "measure_energy_distance",
    "energy_storage": "meter_power",
    "frequency": "measure_frequency",
    "gas": "meter_gas",
    "humidity": "measure_humidity",
    "illuminance": "measure_luminance",
    "irradiance": "measure_irradiance",
    "moisture": "measure_moisture",
    "monetary": "measure_monetary",
    "nitrogen_dioxide": "measure_nox",
    "nitrogen_monoxide": "measure_nox",
    "nitrous_oxide": "measure_nox",
    "ozone": "measure_o3",
    "ph": "measure_ph",
    "pm1": "measure_pm1",
    "pm10": "measure_pm10",
    "pm25": "measure_pm25",
    "pm4": "measure_pm4",
    "power": "measure_power",
    "power_factor": "measure_power_factor",
    "precipitation": "measure_rain",
    "precipitation_intensity": "measure_rain_intensity",
    "pressure": "measure_pressure",
    "radon": "measure_radon",
    "reactive_energy": "meter_reactive_energy",
    "reactive_power": "measure_reactive_power",
    "signal_strength": "measure_signal_strength",
    "sound_pressure": "measure_noise",
    "speed": "measure_speed",
    "sulphur_dioxide": "measure_so2",
    "temperature": "measure_temperature",
    "temperature_delta": "measure_temperature",
    "volatile_organic_compounds": "measure_tvoc",
    "volatile_organic_compounds_parts": "measure_tvoc",
    "voltage": "measure_voltage",
    "volume": "measure_content_volume",
    "volume_storage": "measure_content_volume",
    "volume_flow_rate": "measure_water",
    "water": "meter_water",
    "weight": "measure_weight",
    "wind_direction": "measure_wind_angle",
    "wind_speed": "measure_wind_strength",
}

# Object ids and units with no ESPHome device class, or that must beat one.
OBJECT_ID_ALIASES: tuple[ObjectIdAlias, ...] = (
    ObjectIdAlias(
        "measure_uptime",
        exact=("uptime",),
    ),
    ObjectIdAlias(
        "measure_battery_voltage",
        exact=("battery_voltage",),
        claim_class=False,
    ),
    ObjectIdAlias(
        "measure_dew_point",
        exact=("dew_point",),
        suffixes=("_dew_point",),
    ),
    ObjectIdAlias(
        "measure_gust_angle",
        exact=(
            "gust_angle",
            "gust_direction",
            "wind_gust_angle",
            "wind_gust_direction",
        ),
        suffixes=(
            "_gust_angle",
            "_gust_direction",
            "_wind_gust_angle",
            "_wind_gust_direction",
        ),
    ),
    ObjectIdAlias(
        "measure_gust_strength",
        exact=(
            "gust",
            "gust_speed",
            "gust_strength",
            "wind_gust",
            "wind_gust_speed",
            "wind_gust_strength",
        ),
        suffixes=(
            "_gust",
            "_gust_speed",
            "_gust_strength",
            "_wind_gust",
            "_wind_gust_speed",
            "_wind_gust_strength",
        ),
    ),
    ObjectIdAlias(
        "measure_rotation",
        exact=("angle", "rotation"),
        suffixes=("_angle", "_rotation"),
        unless_device_class=("wind_direction",),
    ),
    ObjectIdAlias(
        "measure_ultraviolet",
        units=("uvi", "uv index"),
    ),
    ObjectIdAlias(
        "measure_ch2o",
        exact=("formaldehyde", "hcho", "ch2o"),
        suffixes=("_formaldehyde", "_hcho", "_ch2o"),
    ),
    ObjectIdAlias(
        "measure_tvoc_index",
        exact=("voc_index", "voc"),
        suffixes=("_voc_index",),
        unless_device_class=(
            "volatile_organic_compounds",
            "volatile_organic_compounds_parts",
        ),
    ),
    ObjectIdAlias(
        "measure_nox_index",
        exact=("nox_index", "nox"),
        suffixes=("_nox_index",),
        unless_device_class=(
            "nitrogen_dioxide",
            "nitrogen_monoxide",
            "nitrous_oxide",
        ),
    ),
    ObjectIdAlias(
        "measure_hepa_filter",
        exact=(
            "hepa_filter",
            "hepa_filter_life",
            "hepa_filter_remaining",
        ),
        suffixes=(
            "_hepa_filter",
            "_hepa_filter_life",
            "_hepa_filter_remaining",
        ),
    ),
    ObjectIdAlias(
        "measure_carbon_filter",
        exact=(
            "carbon_filter",
            "carbon_filter_life",
            "carbon_filter_remaining",
            "charcoal_filter",
            "active_carbon_filter",
        ),
        suffixes=(
            "_carbon_filter",
            "_carbon_filter_life",
            "_carbon_filter_remaining",
            "_charcoal_filter",
            "_active_carbon_filter",
        ),
    ),
    ObjectIdAlias(
        "measure_hepa_filter",
        exact=(
            "filter_life",
            "filter_remaining",
            "filter_lifetime",
            "filter_life_level",
        ),
        suffixes=(
            "_filter_life",
            "_filter_remaining",
            "_filter_lifetime",
            "_filter_life_level",
        ),
    ),
)


class SensorEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        info = cast(SensorInfo, entity)
        device_class = (info.device_class or "").lower()
        unit = info.unit_of_measurement or None
        alias = match_object_id_alias(
            info.object_id or "",
            unit,
            device_class,
            OBJECT_ID_ALIASES,
        )
        if alias is not None:
            capability_id = alias.capability
            claim_class = alias.claim_class
        else:
            capability_id = lookup_device_class(device_class, CAPABILITY_MAP)
            claim_class = True

        if claim_class:
            DeviceEntityMapper.set_device_class(homey_device, "sensor")

        capability_options: dict[str, object] = {}
        if unit and capability_id is not None:
            unit_lower = unit.lower().strip()
            if capability_id == "measure_noise" and unit != "dB":
                capability_options["units"] = unit
            elif capability_id == "measure_monetary":
                capability_options["units"] = unit
            elif device_class == "volatile_organic_compounds_parts":
                capability_options["units"] = unit
            elif capability_id == "measure_ch2o" and unit_lower in ("ppb", "ppm"):
                capability_options["units"] = unit

        if capability_id is not None:
            DeviceEntityMapper.add_indexed(
                homey_device,
                info.key,
                capability_id,
                capability_options,
            )
            return

        if unit:
            capability_options["units"] = unit
            DeviceEntityMapper.add_suffixed(
                homey_device,
                info.key,
                "esphome_number",
                capability_options,
            )
            return

        DeviceEntityMapper.add_suffixed(
            homey_device,
            info.key,
            "esphome_string",
            capability_options,
        )
