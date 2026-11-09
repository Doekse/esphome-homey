"""Pair-time mapping of ESPHome entities onto one Homey device.

The generic ESPHome app gives a device a capability for every entity it can
show. Each capability's options record the entity it is bound to (``key``,
``entity_type``, ``name``, ``device_id``), so the device can call
``register_capability`` for it on every start.

Per-entity mappers live in this package. Homey system UIs (light, cover,
climate, and similar) bind bare capability IDs, so those domains map one
entity per Homey device. Custom ``esphome_*`` capabilities are always suffixed.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from aioesphomeapi import (
    AlarmControlPanelInfo,
    BinarySensorInfo,
    ButtonInfo,
    ClimateInfo,
    CoverInfo,
    EntityCategory,
    EntityInfo,
    EventInfo,
    FanInfo,
    LightInfo,
    LockInfo,
    MediaPlayerInfo,
    NumberInfo,
    SelectInfo,
    SensorInfo,
    SirenInfo,
    SwitchInfo,
    TemperatureUnit,
    TextSensorInfo,
    ValveInfo,
    WaterHeaterInfo,
)
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption
from homey_esphomedriver.system import domain_of

REFRESH_CAPABILITY = "button.refresh"


def refresh_options(manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    """The Refresh button's options as the driver manifest declares them."""
    options = (manifest or {}).get("capabilitiesOptions", {})
    return dict(options.get(REFRESH_CAPABILITY, {"maintenanceAction": True}))


_current_entity: EntityInfo | None = None

# First non-sensor class wins. Light does not replace sensor. Only doorbell
# events set a Homey class.
_ENTITY_PRIORITY: dict[type[EntityInfo], int] = {
    AlarmControlPanelInfo: 0,
    WaterHeaterInfo: 1,
    ClimateInfo: 2,
    CoverInfo: 3,
    LockInfo: 4,
    ValveInfo: 5,
    MediaPlayerInfo: 6,
    FanInfo: 7,
    SirenInfo: 8,
    EventInfo: 9,
    BinarySensorInfo: 10,
    SensorInfo: 11,
    LightInfo: 12,
    SwitchInfo: 13,
    ButtonInfo: 14,
    NumberInfo: 15,
    SelectInfo: 16,
    TextSensorInfo: 17,
}

# wifi_info / version text sensors duplicate Device Information settings.
_DEVICE_INFO_TEXT_SENSOR_IDS = frozenset(
    {
        "ip_address",
        "mac_address",
        "dns_address",
        "esphome_version",
        "version",
    }
)


@dataclass(frozen=True, slots=True)
class ObjectIdAlias:
    """Maps an ESPHome object id or unit onto a Homey capability id."""

    capability: str
    """Homey capability id to assign."""

    exact: tuple[str, ...] = ()
    """Object ids that match exactly."""

    suffixes: tuple[str, ...] = ()
    """Object id suffixes that match."""

    units: tuple[str, ...] = ()
    """Units of measurement that match."""

    unless_device_class: tuple[str, ...] = ()
    """Skip this alias when the entity has one of these device classes."""

    claim_class: bool = True
    """Whether matching this alias should set the Homey device class."""


def match_object_id_alias(
    object_id: str,
    unit: str | None,
    device_class: str,
    aliases: Sequence[ObjectIdAlias],
) -> ObjectIdAlias | None:
    """Return the first alias matching object id, suffix, or unit.

    Args:
        object_id: ESPHome entity object id.
        unit: Unit of measurement, if any.
        device_class: ESPHome device class used to skip aliases via
            :attr:`ObjectIdAlias.unless_device_class`.
        aliases: Ordered alias table; first match wins.
    """
    object_id = object_id.lower()
    unit_lower = (unit or "").lower().strip()
    device_class = device_class.lower()
    for alias in aliases:
        if alias.unless_device_class and device_class in alias.unless_device_class:
            continue
        if object_id in alias.exact:
            return alias
        if alias.suffixes and object_id.endswith(alias.suffixes):
            return alias
        if alias.units and unit_lower in alias.units:
            return alias
    return None


def lookup_device_class(
    value: str | None,
    mapping: Mapping[str, str],
) -> str | None:
    """Look up a lowered ESPHome device class in a Homey capability/class map."""
    if not value:
        return None
    return mapping.get(value.lower())


def picker_values(entries: Iterable[tuple[str, str]]) -> list[dict[str, object]]:
    """Homey enum picker options ``[{id, title: {en}}]``."""
    return [{"id": item_id, "title": {"en": title}} for item_id, title in entries]


def celsius_step(unit: TemperatureUnit | None, step: float) -> float:
    """ESPHome temperature step as Homey °C."""
    if unit == TemperatureUnit.FAHRENHEIT:
        return step * 5 / 9
    return step


class _EntityMapper(Protocol):
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None: ...


_MAPPERS: dict[type[EntityInfo], _EntityMapper] | None = None


class DeviceEntityMapper:
    """Maps ESPHome entities onto a Homey pair-time payload."""

    @staticmethod
    def empty_option(
        capabilities: list[str] | None = None,
    ) -> HomeyEspHomeDeviceOption:
        """Empty pair-time payload the mapper mutates in place."""
        return {
            "name": "",
            "data": {},
            "store": {},
            "settings": {},
            "capabilities": capabilities if capabilities is not None else [],
            "capabilitiesOptions": {},
        }

    @classmethod
    def map(
        cls,
        entities: list[EntityInfo],
        homey_device: HomeyEspHomeDeviceOption,
        *,
        category_only: EntityCategory | None = None,
    ) -> None:
        """Map supported entity types onto ``homey_device``.

        Args:
            entities: Native API entity infos from the node.
            homey_device: Pair-time device payload to mutate.
            category_only: When set, only map entities in that category
                (used when the user enables diagnostic or configuration caps).
        """
        global _current_entity
        mappers = _get_mappers()
        for entity in sorted(
            entities,
            key=lambda item: _ENTITY_PRIORITY.get(type(item), 100),
        ):
            if cls._should_skip(entity, category_only=category_only):
                continue

            mapper = mappers.get(type(entity))
            if mapper is None:
                continue
            _current_entity = entity
            try:
                mapper.map(entity, homey_device)
            finally:
                _current_entity = None

    @classmethod
    def map_device(
        cls,
        entities: list[EntityInfo],
        homey_device: HomeyEspHomeDeviceOption,
        *,
        diagnostics: bool = False,
        configuration: bool = False,
        refresh: Mapping[str, Any] | None = None,
    ) -> None:
        """Fill a pair-time payload, including ``button.refresh``.

        Args:
            refresh: Options of the Refresh button, from :func:`refresh_options`.
        """
        cls.map(entities, homey_device)
        if diagnostics:
            cls.map(entities, homey_device, category_only=EntityCategory.DIAGNOSTIC)
        if configuration:
            cls.map(entities, homey_device, category_only=EntityCategory.CONFIG)
        homey_device["capabilities"].append(REFRESH_CAPABILITY)
        homey_device["capabilitiesOptions"][REFRESH_CAPABILITY] = dict(
            refresh or {"maintenanceAction": True}
        )

    @staticmethod
    def _should_skip(
        entity: EntityInfo,
        *,
        category_only: EntityCategory | None = None,
    ) -> bool:
        """Skip entities that should not appear on the Homey device."""
        if (
            isinstance(entity, TextSensorInfo)
            and entity.object_id in _DEVICE_INFO_TEXT_SENSOR_IDS
        ):
            return True
        if entity.disabled_by_default:
            return True
        if category_only is not None:
            return entity.entity_category != category_only
        return entity.entity_category in (
            EntityCategory.DIAGNOSTIC,
            EntityCategory.CONFIG,
        )

    @staticmethod
    def has_entity_type(
        homey_device: HomeyEspHomeDeviceOption,
        entity_type: str,
    ) -> bool:
        """Return whether a capability is already bound to this entity domain."""
        return any(
            options.get("entity_type") == entity_type
            for options in homey_device["capabilitiesOptions"].values()
        )

    @classmethod
    def add_indexed(
        cls,
        homey_device: HomeyEspHomeDeviceOption,
        key: int,
        base: str,
        capability_options: dict[str, Any] | None = None,
    ) -> None:
        """Add ``base``, or ``base.<object_id>`` when ``base`` is already used."""
        suffix = _current_entity.object_id if _current_entity is not None else base
        capability = cls.next_capability_id(homey_device, base, suffix)
        cls.add_capability(homey_device, key, capability, capability_options)

    @classmethod
    def add_suffixed(
        cls,
        homey_device: HomeyEspHomeDeviceOption,
        key: int,
        base: str,
        capability_options: dict[str, Any] | None = None,
    ) -> None:
        """Add ``base.<object_id>`` and a hidden bare id for Flow ``$filter``.

        ``button`` uses ``esphome_button`` so Homey does not emit a system Press
        card for a dummy bare ``button``.
        """
        marker = "esphome_button" if base == "button" else base
        if marker not in homey_device["capabilities"]:
            homey_device["capabilities"].append(marker)
            homey_device["capabilitiesOptions"][marker] = {"uiComponent": None}
        suffix = _current_entity.object_id if _current_entity is not None else base
        cls.add_capability(homey_device, key, f"{base}.{suffix}", capability_options)

    @staticmethod
    def add_capability(
        homey_device: HomeyEspHomeDeviceOption,
        key: int,
        capability: str,
        capability_options: dict[str, Any] | None = None,
    ) -> None:
        """Push a capability and record the ESPHome entity it is bound to."""
        homey_device["capabilities"].append(capability)
        options = homey_device["capabilitiesOptions"].setdefault(capability, {})
        options["key"] = key
        if _current_entity is not None:
            options["name"] = _current_entity.name
            options["device_id"] = _current_entity.device_id
        if capability_options:
            options.update(capability_options)
        if "entity_type" not in options and _current_entity is not None:
            domain = domain_of(_current_entity)
            if domain is not None:
                options["entity_type"] = domain
        if "." in capability and "title" not in options and _current_entity is not None:
            title = _current_entity.name or _current_entity.object_id
            if title:
                options["title"] = title

    @staticmethod
    def next_capability_id(
        homey_device: HomeyEspHomeDeviceOption,
        base_capability: str,
        suffix: str,
    ) -> str:
        """Return ``base`` or ``base.<suffix>`` when the native cap is already used."""
        existing = [
            capability
            for capability in homey_device["capabilities"]
            if capability == base_capability
            or capability.startswith(f"{base_capability}.")
        ]
        if not existing:
            return base_capability
        return f"{base_capability}.{suffix}"

    @staticmethod
    def set_device_class(
        homey_device: HomeyEspHomeDeviceOption,
        device_class: str,
    ) -> None:
        """Keep the first non-sensor class. Light does not replace sensor."""
        current = homey_device.get("class")
        if current == "sensor" and device_class == "light":
            return
        if current and current != "sensor":
            return
        homey_device["class"] = device_class


def _get_mappers() -> dict[type[EntityInfo], _EntityMapper]:
    """Build the type-to-mapper registry once.

    Late imports avoid circular dependencies with per-entity mapper modules.
    """
    global _MAPPERS
    if _MAPPERS is not None:
        return _MAPPERS

    from lib.mapping.alarm_control_panel import (
        AlarmControlPanelEntityMapper,
    )
    from lib.mapping.binary_sensor import (
        BinarySensorEntityMapper,
    )
    from lib.mapping.button import (
        ButtonEntityMapper,
    )
    from lib.mapping.climate import (
        ClimateEntityMapper,
    )
    from lib.mapping.cover import (
        CoverEntityMapper,
    )
    from lib.mapping.event import (
        EventEntityMapper,
    )
    from lib.mapping.fan import (
        FanEntityMapper,
    )
    from lib.mapping.light import (
        LightEntityMapper,
    )
    from lib.mapping.lock import (
        LockEntityMapper,
    )
    from lib.mapping.media_player import (
        MediaPlayerEntityMapper,
    )
    from lib.mapping.number import (
        NumberEntityMapper,
    )
    from lib.mapping.select import (
        SelectEntityMapper,
    )
    from lib.mapping.sensor import (
        SensorEntityMapper,
    )
    from lib.mapping.siren import (
        SirenEntityMapper,
    )
    from lib.mapping.switch import (
        SwitchEntityMapper,
    )
    from lib.mapping.text_sensor import (
        TextSensorEntityMapper,
    )
    from lib.mapping.valve import (
        ValveEntityMapper,
    )
    from lib.mapping.water_heater import (
        WaterHeaterEntityMapper,
    )

    _MAPPERS = {
        AlarmControlPanelInfo: AlarmControlPanelEntityMapper(),
        BinarySensorInfo: BinarySensorEntityMapper(),
        ButtonInfo: ButtonEntityMapper(),
        ClimateInfo: ClimateEntityMapper(),
        CoverInfo: CoverEntityMapper(),
        EventInfo: EventEntityMapper(),
        FanInfo: FanEntityMapper(),
        LightInfo: LightEntityMapper(),
        LockInfo: LockEntityMapper(),
        MediaPlayerInfo: MediaPlayerEntityMapper(),
        NumberInfo: NumberEntityMapper(),
        SelectInfo: SelectEntityMapper(),
        SensorInfo: SensorEntityMapper(),
        SirenInfo: SirenEntityMapper(),
        SwitchInfo: SwitchEntityMapper(),
        TextSensorInfo: TextSensorEntityMapper(),
        ValveInfo: ValveEntityMapper(),
        WaterHeaterInfo: WaterHeaterEntityMapper(),
    }
    return _MAPPERS
