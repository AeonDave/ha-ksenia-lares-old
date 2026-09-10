"""On/off lights for Lares digital outputs, including shutter pulse channels."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import OUTPUT_CONTROL, OUTPUT_OFF_VALUE, OUTPUT_ON, OUTPUT_ON_VALUE
from .coordinator import LaresOutputsCoordinator
from .outputs import OutputStatus, is_shutter_output_name

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = config_entry.runtime_data
    entities = [
        LaresOutput(
            coordinator=runtime.coordinator,
            client=runtime.client,
            pin=runtime.pin,
            name=name,
            idx=str(index),
            device_info=runtime.device_info,
        )
        for index, name in runtime.descriptions.items()
    ]
    _LOGGER.info("Setting up %s Lares light entities", len(entities))
    async_add_entities(entities)


class LaresOutput(CoordinatorEntity[LaresOutputsCoordinator], LightEntity):
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: LaresOutputsCoordinator,
        client,
        pin: str,
        name: str,
        idx: str,
        device_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, context=idx)
        self._client = client
        self._pin = pin
        self._idx = idx
        self._attr_name = name
        self._attr_unique_id = idx
        self._attr_device_info = DeviceInfo(
            identifiers=device_info["identifiers"],
            name=device_info["name"],
            manufacturer=device_info.get("manufacturer"),
            model=device_info.get("model"),
            sw_version=device_info.get("sw_version"),
        )
        self._attr_icon = (
            "mdi:window-shutter" if is_shutter_output_name(name) else "mdi:lightbulb"
        )

    def _row(self) -> OutputStatus | None:
        try:
            return self.coordinator.data[int(self._idx)]
        except (TypeError, IndexError, KeyError, ValueError):
            return None

    @property
    def is_on(self) -> bool:
        row = self._row()
        return bool(row and row.status == OUTPUT_ON)

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        row = self._row()
        return bool(row and row.remote_control == OUTPUT_CONTROL)

    async def async_turn_on(self) -> None:
        await self._client.command_output(self._pin, self._idx, OUTPUT_ON_VALUE)
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        await self._client.command_output(self._pin, self._idx, OUTPUT_OFF_VALUE)
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()
