"""Homey Flow card listeners and sub-capability / event triggers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from lib.formatting import option_title

if TYPE_CHECKING:
    from homey_esphomedriver.esphome_driver import EspHomeDriver  # noqa: F401

_TRIGGER_CARD_IDS = (
    "esphome_number_changed",
    "esphome_select_changed",
    "esphome_string_changed",
    "esphome_boolean_true",
    "esphome_boolean_false",
    "event_generic_received",
    "event_button_received",
    "alarm_doorbell_received",
)

_SUBCAPABILITY_TOKENS = {
    "esphome_number": ("esphome_number_changed", "esphome_number", float),
    "esphome_select": ("esphome_select_changed", "esphome_select", str),
    "esphome_string": ("esphome_string_changed", "esphome_string", str),
}

_EVENT_TOKENS = {
    "alarm_doorbell": ("alarm_doorbell_received", None),
    "event_button": ("event_button_received", "event_button"),
    "event_generic": ("event_generic_received", "event_generic"),
}


def _capability_title(device: Any, capability_id: str) -> str:
    return option_title(
        device.get_capability_options(capability_id).get("title"),
        capability_id,
    )


class DriverFlowHandler:
    """Owns Flow card wiring and the triggers state/event handlers fire."""

    def __init__(self, driver: EspHomeDriver) -> None:
        self._driver = driver
        self._triggers: dict[str, Any] = {}

    def register(self) -> None:
        """Wire condition/action cards; custom esphome_* triggers fire from handlers.

        Homey auto-fires ``alarm_plugged_in_true`` / ``_false`` on capability
        writes. Sub-capabilities like ``esphome_number.<id>`` need explicit
        base-card triggers because those ids are not known at compose time.
        """
        flow = self._driver.homey.flow
        self._triggers = {
            card_id: flow.get_device_trigger_card(card_id)
            for card_id in _TRIGGER_CARD_IDS
        }

        self._action_press("restart", "restart")
        self._action_press("identify", "identify")
        self._action_press("open", "open")
        self._action_set("aircleaner_mode_set", "aircleaner_mode", "aircleaner_mode")

        self._wire_option("light_effect")
        self._wire_option("thermostat_preset")

        self._wire_card(
            flow.get_action_card("esphome_number_set"),
            self._esphome_number_set,
            name=self._autocomplete_sub("esphome_number", setable_only=True),
        )
        self._wire_card(
            flow.get_action_card("esphome_select_set"),
            self._esphome_select_set,
            name=self._autocomplete_sub("esphome_select"),
            esphome_select=self._select_value_autocomplete,
        )
        self._wire_card(
            flow.get_action_card("esphome_button_press"),
            self._esphome_button_press,
            name=self._autocomplete_sub("button"),
        )

        self._condition_on("alarm_plugged_in_is", "alarm_plugged_in")
        self._condition_on("alarm_triggered_is", "alarm_triggered")
        self._condition_value(
            "aircleaner_mode_is", "aircleaner_mode", "aircleaner_mode"
        )
        self._wire_card(
            flow.get_condition_card("esphome_boolean_is"),
            self._esphome_boolean_is,
            name=self._autocomplete_sub("esphome_boolean"),
        )
        self._wire_card(
            flow.get_condition_card("esphome_string_is"),
            self._esphome_string_is,
            name=self._autocomplete_sub("esphome_string"),
        )
        self._wire_card(
            flow.get_condition_card("esphome_select_is"),
            self._esphome_select_is,
            name=self._autocomplete_sub("esphome_select"),
            esphome_select=self._select_value_autocomplete,
        )

    async def trigger_subcapability(
        self,
        device: Any,
        capability_id: str,
        value: Any,
    ) -> None:
        """Fire the base Flow card for an ``esphome_*`` sub-capability change."""
        base, sep, _ = capability_id.partition(".")
        if not sep:
            return
        name = _capability_title(device, capability_id)
        if base == "esphome_boolean":
            card_id = "esphome_boolean_true" if value else "esphome_boolean_false"
            await self._triggers[card_id].trigger(device, {"name": name})
            return
        spec = _SUBCAPABILITY_TOKENS.get(base)
        if spec is None:
            return
        card_id, token, conv = spec
        await self._triggers[card_id].trigger(
            device, {token: conv(value), "name": name}
        )

    async def trigger_event(
        self,
        device: Any,
        capability_id: str,
        value: Any = None,
    ) -> None:
        """Fire the Flow card for an event or doorbell capability."""
        base, sep, _ = capability_id.partition(".")
        if not sep:
            return
        spec = _EVENT_TOKENS.get(base)
        if spec is None:
            return
        card_id, token = spec
        tokens: dict[str, Any] = {"name": _capability_title(device, capability_id)}
        if token is not None:
            tokens[token] = value
        await self._triggers[card_id].trigger(device, tokens)

    def _wire_option(self, capability_id: str) -> None:
        """Wire set / is / changed cards that pick an enum option by id."""
        flow = self._driver.homey.flow
        autocomplete = self._autocomplete_enum(capability_id)

        async def set_option(args: dict[str, Any], **_kwargs: Any) -> Any:
            return await args["device"].trigger_capability_listener(
                capability_id, args[capability_id]["id"]
            )

        async def option_is(args: dict[str, Any], **_kwargs: Any) -> Any:
            return self._flow_value_is(
                args["device"], capability_id, args[capability_id]["id"]
            )

        listeners = {capability_id: autocomplete}
        self._wire_card(
            flow.get_action_card(f"{capability_id}_set"), set_option, **listeners
        )
        self._wire_card(
            flow.get_condition_card(f"{capability_id}_is"), option_is, **listeners
        )
        self._wire_card(
            flow.get_device_trigger_card(f"{capability_id}_changed"),
            option_is,
            **listeners,
        )

    def _action_press(
        self,
        card_id: str,
        capability_id: str,
        value: Any = True,
    ) -> None:
        async def run(args: dict[str, Any], **_kwargs: Any) -> Any:
            return await args["device"].trigger_capability_listener(
                capability_id, value
            )

        self._driver.homey.flow.get_action_card(card_id).register_run_listener(run)

    def _action_set(self, card_id: str, capability_id: str, arg_key: str) -> None:
        async def run(args: dict[str, Any], **_kwargs: Any) -> Any:
            return await args["device"].trigger_capability_listener(
                capability_id, args[arg_key]
            )

        self._driver.homey.flow.get_action_card(card_id).register_run_listener(run)

    @staticmethod
    def _flow_value_is(device: Any, capability_id: str, value: Any) -> bool:
        """Compare a Flow argument to the live capability; empty args never match."""
        if not value:
            return False
        return value == device.get_capability_value(capability_id)

    def _condition_on(self, card_id: str, capability_id: str) -> None:
        async def run(args: dict[str, Any], **_kwargs: Any) -> Any:
            return args["device"].get_capability_value(capability_id)

        self._driver.homey.flow.get_condition_card(card_id).register_run_listener(run)

    def _condition_value(self, card_id: str, capability_id: str, arg_key: str) -> None:
        async def run(args: dict[str, Any], **_kwargs: Any) -> Any:
            return self._flow_value_is(args["device"], capability_id, args[arg_key])

        self._driver.homey.flow.get_condition_card(card_id).register_run_listener(run)

    def _wire_card(
        self,
        card: Any,
        run: Callable[..., Any],
        **autocomplete: Callable[..., Any],
    ) -> None:
        for arg_name, listener in autocomplete.items():
            card.register_argument_autocomplete_listener(arg_name, listener)
        card.register_run_listener(run)

    async def _esphome_number_set(self, args: dict[str, Any], **_kwargs: Any) -> Any:
        return await args["device"].trigger_capability_listener(
            args["name"]["id"],
            args["esphome_number"],
        )

    async def _esphome_select_set(self, args: dict[str, Any], **_kwargs: Any) -> Any:
        return await args["device"].trigger_capability_listener(
            args["name"]["id"],
            args["esphome_select"]["id"],
        )

    async def _esphome_button_press(self, args: dict[str, Any], **_kwargs: Any) -> Any:
        return await args["device"].trigger_capability_listener(
            args["name"]["id"],
            True,
        )

    async def _esphome_boolean_is(self, args: dict[str, Any], **_kwargs: Any) -> Any:
        return args["device"].get_capability_value(args["name"]["id"])

    async def _esphome_string_is(self, args: dict[str, Any], **_kwargs: Any) -> Any:
        return self._flow_value_is(
            args["device"], args["name"]["id"], args["esphome_string"]
        )

    async def _esphome_select_is(self, args: dict[str, Any], **_kwargs: Any) -> Any:
        return self._flow_value_is(
            args["device"], args["name"]["id"], args["esphome_select"]["id"]
        )

    def _autocomplete_enum(self, capability_id: str) -> Callable[..., Any]:
        async def listener(query: str, **args: Any) -> list[dict[str, str]]:
            return self._enum_values_autocomplete(query, capability_id, args["device"])

        return listener

    def _autocomplete_sub(
        self, base: str, *, setable_only: bool = False
    ) -> Callable[..., Any]:
        async def listener(query: str, **args: Any) -> list[dict[str, str]]:
            return self._subcapability_autocomplete(
                args["device"], base, query, setable_only=setable_only
            )

        return listener

    async def _select_value_autocomplete(
        self,
        query: str,
        **args: Any,
    ) -> list[dict[str, str]]:
        selected = args.get("name")
        if not selected:
            return []
        return self._enum_values_autocomplete(query, selected["id"], args["device"])

    def _enum_values_autocomplete(
        self,
        query: str,
        capability_id: str,
        device: Any,
    ) -> list[dict[str, str]]:
        values = device.get_capability_options(capability_id).get("values", [])
        query_lower = query.lower()
        results: list[dict[str, str]] = []
        for value in values:
            option_id = str(value["id"])
            name = option_title(value.get("title"), option_id)
            if query_lower in name.lower() or query_lower in option_id.lower():
                results.append({"id": option_id, "name": name})
        return results

    def _subcapability_autocomplete(
        self,
        device: Any,
        base: str,
        query: str,
        *,
        setable_only: bool = False,
    ) -> list[dict[str, str]]:
        query_lower = query.lower()
        results: list[dict[str, str]] = []
        for capability_id in device.get_capabilities():
            if not capability_id.startswith(f"{base}."):
                continue
            options = device.get_capability_options(capability_id)
            # button.refresh has no entity key and must not be a press target.
            if options.get("key") is None:
                continue
            if setable_only and not options.get("setable", False):
                continue
            name = option_title(options.get("title"), capability_id)
            if query_lower in name.lower() or query_lower in capability_id.lower():
                results.append({"id": capability_id, "name": name})
        return results
