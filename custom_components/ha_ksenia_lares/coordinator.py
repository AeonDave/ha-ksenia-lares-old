"""Shared poller for Lares digital outputs."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .base import LaresBase
from .outputs import OutputStatus

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)
DEFAULT_TIMEOUT = 10


class LaresOutputsCoordinator(DataUpdateCoordinator[list[OutputStatus]]):
    """Poll output status XML on a fixed interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: LaresBase,
        device_info: dict[str, str],
        config_entry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="lares_outputs",
            update_interval=SCAN_INTERVAL,
        )
        self._client = client
        self._device_info = device_info

    async def _async_update_data(self) -> list[OutputStatus]:
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                data = await self._client.outputs_status(self._device_info)
        except TimeoutError as err:
            raise UpdateFailed("Timeout during connection to Lares") from err
        if not data:
            raise UpdateFailed("No output status received from Lares")
        return data
