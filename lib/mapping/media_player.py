"""Map ESPHome MediaPlayerInfo onto Homey speaker and volume capabilities.

Homey's media UI only binds bare ``speaker_*`` IDs, so a Homey device maps one player.
"""

from __future__ import annotations

from typing import cast

from aioesphomeapi import (
    EntityInfo,
    MediaPlayerEntityFeature,
    MediaPlayerInfo,
)
from homey_esphomedriver.esphome_types import HomeyEspHomeDeviceOption

from lib.mapping import (
    DeviceEntityMapper,
)


class MediaPlayerEntityMapper:
    def map(
        self,
        entity: EntityInfo,
        homey_device: HomeyEspHomeDeviceOption,
    ) -> None:
        if DeviceEntityMapper.has_entity_type(homey_device, "media_player"):
            return

        info = cast(MediaPlayerInfo, entity)
        DeviceEntityMapper.set_device_class(homey_device, "mediaplayer")

        flags = info.feature_flags
        if not flags:
            flags = (
                MediaPlayerEntityFeature.STOP
                | MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_MUTE
            )
            if info.supports_pause:
                flags |= MediaPlayerEntityFeature.PAUSE | MediaPlayerEntityFeature.PLAY
        DeviceEntityMapper.add_capability(
            homey_device,
            info.key,
            "speaker_playing",
            {"supports_pause": bool(flags & MediaPlayerEntityFeature.PAUSE)},
        )

        for feature, capabilities in (
            (MediaPlayerEntityFeature.VOLUME_SET, ("volume_set",)),
            (MediaPlayerEntityFeature.VOLUME_MUTE, ("volume_mute",)),
            (MediaPlayerEntityFeature.VOLUME_STEP, ("volume_up", "volume_down")),
            (MediaPlayerEntityFeature.STOP, ("speaker_stop",)),
        ):
            if not flags & feature:
                continue
            for capability in capabilities:
                DeviceEntityMapper.add_capability(homey_device, info.key, capability)
