"""The generic ESPHome device: binds the capabilities mapped at pairing.

Every capability's options record the entity it was mapped from, so the device
binds them all with ``register_capability`` on every start. On top of the
library it keeps the capabilities in step with the firmware (Refresh, firmware
rebuilds, the diagnostics / configuration toggles) and owns the Homey class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from aioesphomeapi import EntityCategory
from homey_esphomedriver import EspHomeClient, EspHomeDevice
from homey_esphomedriver.system import SETTABLE, capability_base, reports_only

from lib.capabilities import DeviceCapabilityHandler
from lib.custom_capabilities import EVENT_CAPABILITIES, CustomCapabilities
from lib.notifications import notify_entities_changed
from lib.tasks import spawn

if TYPE_CHECKING:
    from lib.driver import GenericEspHomeDriver


class GenericEspHomeDevice(EspHomeDevice):
    """A node paired through the generic app, with a capability per entity."""

    _capability_handler: DeviceCapabilityHandler
    _custom: CustomCapabilities
    _unbound: set[str]

    async def on_esphome_init(self, client: EspHomeClient | None) -> None:
        """Bind every capability that pairing mapped to an entity."""
        del client
        # Homey initializes the driver, and with it the Flow cards, first.
        flow = cast("GenericEspHomeDriver", self.driver).flow
        self._custom = CustomCapabilities(self, flow)
        self._capability_handler = DeviceCapabilityHandler(self)
        self._unbound = set()

        device_class = self.get_setting("device_class")
        if device_class not in (None, "auto"):
            await self._apply_device_class_setting(str(device_class))

        await self._seed_event_capabilities()
        await self._capability_handler.ensure_refresh()
        for capability_id in self.get_capabilities():
            self.bind_capability(capability_id)

    async def on_esphome_ready(self, client: EspHomeClient) -> None:
        """Finish binding devices paired before 0.6, then follow new firmware."""
        if self._unbound:
            await self._bind_by_key(client)
        if self._has_outdated_capabilities():
            try:
                await self._capability_handler.refresh()
            except Exception as error:  # noqa: BLE001
                self.error("Could not remap outdated capabilities:", error)
        device_info = client.device_info
        if device_info is None:
            return
        build = device_info.compilation_time
        entities_build = await self._ensure_entities_build(build)
        if (
            build
            and build != entities_build
            and self.brand_profile.accepts_project(device_info.project_name)
        ):
            await self._sync_entities(build)

    async def on_esphome_uninit(self) -> None:
        self._custom.uninit()

    async def on_settings(
        self,
        old_settings: dict[str, bool | float | str | None],
        new_settings: dict[str, bool | float | str | None],
        changed_keys: tuple[str, ...],
    ) -> str | None:
        """Apply the device-class override and the category toggles."""
        message = await super().on_settings(old_settings, new_settings, changed_keys)
        if "device_class" in changed_keys:
            await self._apply_device_class_setting(str(new_settings["device_class"]))
        if "show_diagnostics" in changed_keys:
            await self._capability_handler.apply_category(
                bool(new_settings.get("show_diagnostics")),
                EntityCategory.DIAGNOSTIC,
                "diagnostic_capabilities",
            )
        if "show_configuration" in changed_keys:
            await self._capability_handler.apply_category(
                bool(new_settings.get("show_configuration")),
                EntityCategory.CONFIG,
                "configuration_capabilities",
            )
        return message

    def bind_capability(self, capability_id: str) -> None:
        """Bind a mapped capability to the entity its options record."""
        # WORKAROUND: Homey may persist options as null (Athom will return {}).
        options = self._capabilities_options.get(capability_id) or {}
        domain = options.get("entity_type")
        if domain is None or options.get("key") is None:
            return
        name = options.get("name")
        if name is None:
            # Paired before 0.6, which bound by key: look the name up once.
            self._unbound.add(capability_id)
            return
        try:
            self.register_capability(
                capability_id,
                str(domain),
                str(name),
                device_id=int(options.get("device_id") or 0),
                **self._custom.parsers(capability_id, str(domain)),
            )
        except ValueError as error:
            self.error(f"Could not bind {capability_id}:", error)

    def _has_outdated_capabilities(self) -> bool:
        """Whether the device has capabilities that pairing no longer maps.

        Refresh swaps them for the current ones. Devices paired before 0.6
        have garage door and lock binary sensors as ``garagedoor_closed`` and
        ``locked`` toggles, which the library does not bind to an entity that
        only reports.
        """
        for capability_id, options in self._capabilities_options.items():
            base = capability_base(capability_id)
            domain = (options or {}).get("entity_type")
            if domain is not None and reports_only(str(domain)) and base in SETTABLE:
                return True
        return False

    async def _bind_by_key(self, client: EspHomeClient) -> None:
        """Record the entity name of capabilities stored with only a key."""
        entities, _services = await client.list_entities_services()
        by_key = {entity.key: entity for entity in entities}
        unbound, self._unbound = self._unbound, set()
        for capability_id in unbound:
            options = dict(self._capabilities_options.get(capability_id) or {})
            entity = by_key.get(int(options["key"]))
            if entity is None:
                self.error(f"No entity with key {options['key']} for {capability_id}")
                continue
            options.update(name=entity.name, device_id=entity.device_id)
            await self.set_capability_options(capability_id, options)
            self.bind_capability(capability_id)

    async def _sync_entities(self, build: str) -> None:
        result = await self._capability_handler.sync_entities(build)
        self.log(
            f"Synced capabilities for firmware {build}: "
            f"added {result.added}, removed {result.removed}"
        )
        spawn(
            self,
            notify_entities_changed(
                homey=self.homey,
                device_name=self.get_name(),
                added=result.added,
                removed=result.removed_titles,
                enabled=self.get_setting("notify_entities_changed") is not False,
            ),
        )

    async def _ensure_entities_build(self, build: str) -> str:
        """Return the stored build, seeding a missing key from the old setting.

        This login overwrote the compilation_time setting already, so a
        missing key is seeded from the build itself: not a firmware change.
        """
        store = self.get_store()
        if "entities_build" in store:
            return str(store.get("entities_build") or "")
        await self.set_store_value("entities_build", build)
        return build

    async def _apply_device_class_setting(self, value: str) -> None:
        """Set Homey class from the device_class setting (auto restores mapped)."""
        target = self.get_store().get("auto_class") if value == "auto" else value
        if target:
            await self.set_class(str(target))

    async def _seed_event_capabilities(self) -> None:
        """Homey shows event capabilities as null until a value is written."""
        for capability_id in self.get_capabilities():
            base = capability_base(capability_id)
            if (
                base in EVENT_CAPABILITIES
                and "." in capability_id
                and self.get_capability_value(capability_id) is None
            ):
                await self.set_capability_value(
                    capability_id, False if base == "alarm_doorbell" else "idle"
                )
