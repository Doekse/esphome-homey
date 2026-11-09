"""Map ESPHome AlarmControlPanelInfo onto Homey homealarm capabilities."""

from __future__ import annotations

from typing import cast

from aioesphomeapi import (
    AlarmControlPanelCommand,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelInfo,
    EntityInfo,
)
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from lib.mapping import (
    DeviceEntityMapper,
)


class AlarmControlPanelEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        if DeviceEntityMapper.has_entity_type(homey_device, "alarm_control_panel"):
            return

        info = cast(AlarmControlPanelInfo, entity)
        DeviceEntityMapper.set_device_class(homey_device, "homealarm")

        flags = info.supported_features
        values: list[dict[str, object]] = [
            {"id": "disarmed", "title": {"en": "Disarmed"}},
        ]
        options: dict[str, object] = {"values": values}

        armed_command = _preferred_command(
            flags,
            (
                (
                    AlarmControlPanelEntityFeature.ARM_AWAY,
                    AlarmControlPanelCommand.ARM_AWAY,
                ),
                (
                    AlarmControlPanelEntityFeature.ARM_VACATION,
                    AlarmControlPanelCommand.ARM_VACATION,
                ),
            ),
        )
        if armed_command is not None:
            values.append({"id": "armed", "title": {"en": "Armed"}})
            options["alarm_armed_command"] = int(armed_command)

        partial_command = _preferred_command(
            flags,
            (
                (
                    AlarmControlPanelEntityFeature.ARM_HOME,
                    AlarmControlPanelCommand.ARM_HOME,
                ),
                (
                    AlarmControlPanelEntityFeature.ARM_NIGHT,
                    AlarmControlPanelCommand.ARM_NIGHT,
                ),
                (
                    AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS,
                    AlarmControlPanelCommand.ARM_CUSTOM_BYPASS,
                ),
            ),
        )
        if partial_command is not None:
            values.append({"id": "partially_armed", "title": {"en": "Partially armed"}})
            options["alarm_partial_command"] = int(partial_command)

        DeviceEntityMapper.add_capability(
            homey_device,
            info.key,
            "homealarm_state",
            options,
        )

        if flags & AlarmControlPanelEntityFeature.TRIGGER:
            DeviceEntityMapper.add_capability(homey_device, info.key, "alarm_triggered")


def _preferred_command(
    flags: int,
    candidates: tuple[
        tuple[AlarmControlPanelEntityFeature, AlarmControlPanelCommand], ...
    ],
) -> AlarmControlPanelCommand | None:
    for feature, command in candidates:
        if flags & feature:
            return command
    return None
