"""DriverFlowHandler trigger and helper tests."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.lib.flow import DriverFlowHandler


class _Device:
    def __init__(
        self,
        *,
        capabilities: list[str] | None = None,
        options: dict[str, dict[str, Any]] | None = None,
        values: dict[str, Any] | None = None,
    ) -> None:
        self._capabilities = list(capabilities or [])
        self._options = options or {}
        self._values = values or {}

    def get_capabilities(self) -> list[str]:
        return list(self._capabilities)

    def get_capability_options(self, capability_id: str) -> dict[str, Any]:
        return self._options.get(capability_id, {})

    def get_capability_value(self, capability_id: str) -> Any:
        return self._values.get(capability_id)


def _handler_with_cards() -> tuple[DriverFlowHandler, dict[str, AsyncMock]]:
    handler = DriverFlowHandler(MagicMock())
    cards = {
        "esphome_number_changed": AsyncMock(),
        "esphome_select_changed": AsyncMock(),
        "esphome_string_changed": AsyncMock(),
        "esphome_boolean_true": AsyncMock(),
        "esphome_boolean_false": AsyncMock(),
        "event_generic_received": AsyncMock(),
        "event_button_received": AsyncMock(),
        "alarm_doorbell_received": AsyncMock(),
    }
    handler._triggers = cards
    return handler, cards


@pytest.mark.parametrize(
    ("capability_id", "value", "card_id", "tokens"),
    [
        (
            "esphome_number.volume",
            42,
            "esphome_number_changed",
            {"esphome_number": 42.0, "name": "Volume"},
        ),
        (
            "esphome_select.mode",
            "auto",
            "esphome_select_changed",
            {"esphome_select": "auto", "name": "Mode"},
        ),
        (
            "esphome_string.label",
            "hi",
            "esphome_string_changed",
            {"esphome_string": "hi", "name": "Label"},
        ),
        (
            "esphome_boolean.flag",
            True,
            "esphome_boolean_true",
            {"name": "Flag"},
        ),
        (
            "esphome_boolean.flag",
            False,
            "esphome_boolean_false",
            {"name": "Flag"},
        ),
    ],
)
def test_trigger_subcapability_dispatches(
    capability_id: str,
    value: Any,
    card_id: str,
    tokens: dict[str, Any],
) -> None:
    """Sub-capability triggers hit the matching base Flow card with title tokens."""
    handler, cards = _handler_with_cards()
    device = _Device(options={capability_id: {"title": tokens["name"]}})

    asyncio.run(handler.trigger_subcapability(device, capability_id, value))

    cards[card_id].trigger.assert_awaited_once_with(device, tokens)
    for name, card in cards.items():
        if name != card_id:
            card.trigger.assert_not_called()


@pytest.mark.parametrize(
    ("capability_id", "value", "card_id", "tokens"),
    [
        (
            "event_generic.custom",
            "pressed",
            "event_generic_received",
            {"event_generic": "pressed", "name": "Custom"},
        ),
        (
            "event_button.doorbell_btn",
            "single_click",
            "event_button_received",
            {"event_button": "single_click", "name": "Doorbell Btn"},
        ),
        (
            "alarm_doorbell.front",
            None,
            "alarm_doorbell_received",
            {"name": "Front"},
        ),
    ],
)
def test_trigger_event_dispatches(
    capability_id: str,
    value: Any,
    card_id: str,
    tokens: dict[str, Any],
) -> None:
    """Event triggers hit the matching Flow card for the capability prefix."""
    handler, cards = _handler_with_cards()
    device = _Device(options={capability_id: {"title": tokens["name"]}})

    asyncio.run(handler.trigger_event(device, capability_id, value))

    cards[card_id].trigger.assert_awaited_once_with(device, tokens)
    for name, card in cards.items():
        if name != card_id:
            card.trigger.assert_not_called()


def test_flow_value_is_rejects_empty_args() -> None:
    """Empty Flow arguments never match a live capability value."""
    device = _Device(values={"light_effect": "rainbow"})
    assert DriverFlowHandler._flow_value_is(device, "light_effect", "") is False
    assert DriverFlowHandler._flow_value_is(device, "light_effect", None) is False
    assert DriverFlowHandler._flow_value_is(device, "light_effect", "rainbow") is True


def test_subcapability_autocomplete_filters_setable_and_key() -> None:
    """Autocomplete skips missing keys and unsettable numbers when requested."""
    handler = DriverFlowHandler(MagicMock())
    device = _Device(
        capabilities=[
            "esphome_number.ro",
            "esphome_number.rw",
            "button.refresh",
            "button.press_me",
        ],
        options={
            "esphome_number.ro": {"key": 1, "setable": False, "title": "RO"},
            "esphome_number.rw": {"key": 2, "setable": True, "title": "RW"},
            "button.refresh": {"title": "Refresh"},
            "button.press_me": {"key": 3, "title": "Press Me"},
        },
    )

    numbers = handler._subcapability_autocomplete(
        device, "esphome_number", "", setable_only=True
    )
    assert numbers == [{"id": "esphome_number.rw", "name": "RW"}]

    buttons = handler._subcapability_autocomplete(device, "button", "")
    assert buttons == [{"id": "button.press_me", "name": "Press Me"}]
