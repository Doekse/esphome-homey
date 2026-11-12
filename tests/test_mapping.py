"""Pair-time mapping helper tests.

Pins object-id alias matching (exact / suffix / unit / ``unless_device_class``),
device-class lookup, picker option shape, ESPHome temperature-unit conversion,
and the hidden bare ids ``add_suffixed`` adds so Homey Flow ``$filter`` can match.
"""

from __future__ import annotations

import pytest
from aioesphomeapi import (
    BinarySensorInfo,
    ButtonInfo,
    CoverInfo,
    EntityCategory,
    EntityInfo,
    FanInfo,
    MediaPlayerEntityFeature,
    MediaPlayerInfo,
    SwitchInfo,
    TemperatureUnit,
)
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption
from homey_esphomedriver.system import SETTABLE, capability_base

from app.lib.mapping import (
    REFRESH_CAPABILITY,
    DeviceEntityMapper,
    ObjectIdAlias,
    celsius_step,
    lookup_device_class,
    match_object_id_alias,
    picker_values,
    refresh_options,
)


def aliases() -> tuple[ObjectIdAlias, ...]:
    return (
        ObjectIdAlias("measure_uptime", exact=("uptime",)),
        ObjectIdAlias(
            "measure_dew_point",
            exact=("dew_point",),
            suffixes=("_dew_point",),
        ),
        ObjectIdAlias(
            "measure_wind_strength",
            units=("m/s", "km/h"),
            unless_device_class=("precipitation",),
        ),
    )


def mapped_device(*entities: EntityInfo) -> HomeyEspHomeDeviceOption:
    homey_device = DeviceEntityMapper.empty_option()
    DeviceEntityMapper.map(list(entities), homey_device)
    return homey_device


def test_empty_option_shape() -> None:
    option = DeviceEntityMapper.empty_option()
    assert option == {
        "name": "",
        "data": {},
        "store": {},
        "settings": {},
        "capabilities": [],
        "capabilitiesOptions": {},
    }
    seeded = DeviceEntityMapper.empty_option(["onoff"])
    assert seeded["capabilities"] == ["onoff"]
    assert seeded["capabilitiesOptions"] == {}


def test_match_object_id_alias_exact_is_case_insensitive() -> None:
    match = match_object_id_alias("Uptime", None, "", aliases())
    assert match is not None
    assert match.capability == "measure_uptime"


def test_match_object_id_alias_suffix() -> None:
    match = match_object_id_alias("outdoor_dew_point", None, "", aliases())
    assert match is not None
    assert match.capability == "measure_dew_point"


def test_match_object_id_alias_unit() -> None:
    match = match_object_id_alias("anemometer", "km/h", "", aliases())
    assert match is not None
    assert match.capability == "measure_wind_strength"


def test_match_object_id_alias_skips_unless_device_class() -> None:
    match = match_object_id_alias("anemometer", "km/h", "precipitation", aliases())
    assert match is None


def test_match_object_id_alias_first_match_wins() -> None:
    table = (
        ObjectIdAlias("first", exact=("speed",)),
        ObjectIdAlias("second", exact=("speed",)),
    )
    match = match_object_id_alias("speed", None, "", table)
    assert match is not None
    assert match.capability == "first"


def test_match_object_id_alias_returns_none_when_unmatched() -> None:
    assert match_object_id_alias("relay", None, "", aliases()) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Temperature", "measure_temperature"),
        (None, None),
        ("", None),
        ("unknown", None),
    ],
)
def test_lookup_device_class(value: str | None, expected: str | None) -> None:
    mapping = {"temperature": "measure_temperature"}
    assert lookup_device_class(value, mapping) == expected


def test_picker_values_shape() -> None:
    assert picker_values([("heat", "Heat"), ("cool", "Cool")]) == [
        {"id": "heat", "title": {"en": "Heat"}},
        {"id": "cool", "title": {"en": "Cool"}},
    ]


def test_celsius_step_scales_fahrenheit_only() -> None:
    """Kelvin and Celsius steps are already Homey °C; Fahrenheit is not."""
    assert celsius_step(TemperatureUnit.FAHRENHEIT, 1.8) == pytest.approx(1.0)
    assert celsius_step(TemperatureUnit.KELVIN, 0.5) == 0.5
    assert celsius_step(None, 0.5) == 0.5


def test_suffixed_custom_cap_adds_hidden_flow_filter_marker() -> None:
    """Bare ``esphome_boolean`` exists only so Homey ``$filter`` can match."""
    homey_device = mapped_device(
        BinarySensorInfo(object_id="screen_button", key=1, name="Screen"),
        BinarySensorInfo(object_id="flag", key=2, name="Flag"),
    )
    assert homey_device["capabilities"] == [
        "esphome_boolean",
        "esphome_boolean.screen_button",
        "esphome_boolean.flag",
    ]
    marker = homey_device["capabilitiesOptions"]["esphome_boolean"]
    assert marker == {"uiComponent": None}


def test_button_entity_adds_custom_flow_filter_marker() -> None:
    """Bare ``esphome_button`` exists only so Homey ``$filter`` matches ``button.*``."""
    homey_device = mapped_device(
        ButtonInfo(object_id="press_me", key=1, name="Press"),
        ButtonInfo(object_id="reset", key=2, name="Reset"),
    )
    assert homey_device["capabilities"] == [
        "esphome_button",
        "button.press_me",
        "button.reset",
    ]
    marker = homey_device["capabilitiesOptions"]["esphome_button"]
    assert marker == {"uiComponent": None}


def test_map_device_attaches_refresh_with_the_manifest_options() -> None:
    manifest = {
        "capabilitiesOptions": {
            REFRESH_CAPABILITY: {"maintenanceAction": True, "title": {"en": "R"}}
        }
    }
    homey_device = mapped_device()
    DeviceEntityMapper.map_device([], homey_device, refresh=refresh_options(manifest))
    assert homey_device["capabilities"] == [REFRESH_CAPABILITY]
    assert homey_device["capabilitiesOptions"][REFRESH_CAPABILITY] == {
        "maintenanceAction": True,
        "title": {"en": "R"},
    }


def test_capabilities_record_the_entity_they_are_bound_to() -> None:
    homey_device = mapped_device(
        SwitchInfo(object_id="relay", key=7, name="Relay", device_id=3)
    )
    options = homey_device["capabilitiesOptions"]["onoff"]
    assert options["key"] == 7
    assert options["entity_type"] == "switch"
    assert options["name"] == "Relay"
    assert options["device_id"] == 3


def test_map_device_includes_diagnostic_entities() -> None:
    entity = BinarySensorInfo(
        object_id="status",
        key=1,
        name="Status",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    assert mapped_device(entity)["capabilities"] == []

    homey_device = mapped_device()
    DeviceEntityMapper.map_device([entity], homey_device, diagnostics=True)
    assert homey_device["capabilities"] == [
        "esphome_boolean",
        "esphome_boolean.status",
        REFRESH_CAPABILITY,
    ]


@pytest.mark.parametrize(
    ("device_class", "expected"),
    [("garage_door", "alarm_contact"), ("lock", "esphome_boolean.lock")],
)
def test_binary_sensor_never_maps_to_a_settable_capability(
    device_class: str, expected: str
) -> None:
    entity = BinarySensorInfo(
        object_id="lock", key=1, name="Lock", device_class=device_class
    )
    capabilities = mapped_device(entity)["capabilities"]
    assert expected in capabilities
    assert not {capability_base(c) for c in capabilities} & SETTABLE


@pytest.mark.parametrize(
    ("device_class", "supports_position", "closed"),
    [
        ("shutter", False, "windowcoverings_closed"),
        ("shutter", True, None),
        ("garage", False, "garagedoor_closed"),
    ],
)
def test_cover_shows_closed_without_a_position(
    device_class: str, supports_position: bool, closed: str | None
) -> None:
    entity = CoverInfo(
        object_id="cover",
        key=1,
        name="Cover",
        device_class=device_class,
        supports_position=supports_position,
    )
    capabilities = mapped_device(entity)["capabilities"]
    found = [c for c in capabilities if c.endswith("_closed")]
    assert found == ([closed] if closed else [])


@pytest.mark.parametrize(
    ("flags", "has_onoff"),
    [
        (MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF, True),
        (MediaPlayerEntityFeature.PAUSE, False),
    ],
)
def test_media_player_turns_on_and_off_when_it_can(
    flags: MediaPlayerEntityFeature, has_onoff: bool
) -> None:
    entity = MediaPlayerInfo(
        object_id="speaker", key=1, name="Speaker", feature_flags=flags
    )
    assert ("onoff" in mapped_device(entity)["capabilities"]) is has_onoff


def test_fan_oscillation_is_homeys_oscillating() -> None:
    entity = FanInfo(object_id="fan", key=1, name="Fan", supports_oscillation=True)
    assert "oscillating" in mapped_device(entity)["capabilities"]
