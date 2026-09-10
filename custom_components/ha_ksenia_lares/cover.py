"""Shutter covers built from TAPP SU / TAPP GIU pulse output pairs.

Open/close follow this house's physical wiring (and the old Lovelace
Apri/Chiudi cards), not the panel SU/GIU labels. See outputs.pair_shutters.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.cover import CoverDeviceClass, CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import OUTPUT_CONTROL, OUTPUT_OFF_VALUE, OUTPUT_ON, OUTPUT_ON_VALUE
from .coordinator import LaresOutputsCoordinator
from .outputs import OutputStatus, ShutterPair, pair_shutters

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = config_entry.runtime_data
    pairs = pair_shutters(runtime.descriptions)
    entities = [
        LaresShutter(
            coordinator=runtime.coordinator,
            client=runtime.client,
            pin=runtime.pin,
            pair=pair,
            device_info=runtime.device_info,
        )
        for pair in pairs
    ]
    _LOGGER.info("Setting up %s Lares shutter covers", len(entities))
    async_add_entities(entities)


class LaresShutter(CoordinatorEntity[LaresOutputsCoordinator], CoverEntity):
    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: LaresOutputsCoordinator,
        client,
        pin: str,
        pair: ShutterPair,
        device_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, context=pair.unique_id)
        self._client = client
        self._pin = pin
        self._pair = pair
        self._attr_name = pair.name.title()
        self._attr_unique_id = pair.unique_id
        self._attr_icon = "mdi:window-shutter"
        self._attr_device_info = DeviceInfo(
            identifiers=device_info["identifiers"],
            name=device_info["name"],
            manufacturer=device_info.get("manufacturer"),
            model=device_info.get("model"),
            sw_version=device_info.get("sw_version"),
        )

    def _row(self, output_id: int) -> OutputStatus | None:
        try:
            return self.coordinator.data[output_id]
        except (TypeError, IndexError, KeyError):
            return None

    def _both_remote(self) -> bool:
        up = self._row(self._pair.up_id)
        down = self._row(self._pair.down_id)
        return bool(
            up
            and down
            and up.remote_control == OUTPUT_CONTROL
            and down.remote_control == OUTPUT_CONTROL
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._both_remote()

    @property
    def is_closed(self) -> bool | None:
        # The panel does not report shutter position.
        return None

    @property
    def is_opening(self) -> bool:
        row = self._row(self._pair.up_id)
        return bool(row and row.status == OUTPUT_ON)

    @property
    def is_closing(self) -> bool:
        row = self._row(self._pair.down_id)
        return bool(row and row.status == OUTPUT_ON)

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._client.command_output(self._pin, str(self._pair.up_id), OUTPUT_ON_VALUE)
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._client.command_output(self._pin, str(self._pair.down_id), OUTPUT_ON_VALUE)
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._client.command_output(self._pin, str(self._pair.up_id), OUTPUT_OFF_VALUE)
        await self._client.command_output(self._pin, str(self._pair.down_id), OUTPUT_OFF_VALUE)
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()
