import asyncio
import logging
import time
from abc import ABC
from datetime import timedelta

import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.binary_sensor import PLATFORM_SCHEMA
from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .base import LaresBase
from .const import OUTPUT_ON, OUTPUT_CONTROL, OUTPUT_ON_VALUE, OUTPUT_OFF_VALUE

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT, default='80'): cv.string,
    vol.Optional(CONF_USERNAME, default='admin'): cv.string,
    vol.Optional(CONF_PASSWORD, default='lares'): cv.string,
})

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    client = LaresBase(config_entry.data)
    device_info = await client.device_info()
    basis_info = await client.basis_info()
    descriptions = await client.outputs_descriptions(device_info)

    async def async_update_data():
        async with async_timeout.timeout(DEFAULT_TIMEOUT):
            return await client.outputs_status(device_info)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="lares_outputs",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )
    await coordinator.async_refresh()

    async_add_entities(
        LaresOutput(client, coordinator, basis_info['PINToUse'], descriptions[output], str(output))
        for output in descriptions
    )


class LaresOutput(CoordinatorEntity, LightEntity, ABC):

    def __init__(self, client: LaresBase, coordinator: DataUpdateCoordinator, pin: str, name: str, idx: str):
        super().__init__(coordinator, context=idx)
        self._client = client
        self._coordinator = coordinator
        self._pin = pin
        self._name = name
        self._idx = idx

    @property
    def unique_id(self) -> str:
        return self._idx

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_on(self) -> bool:
        return self._coordinator.data[int(self._idx)]["status"] == OUTPUT_ON

    @property
    def available(self) -> bool:
        return self._coordinator.data[int(self._idx)]["remoteControl"] == OUTPUT_CONTROL

    async def async_turn_on(self) -> None:
        _LOGGER.debug('Output %s on sent', self._idx)
        await self._client.command_output(self._pin, self._idx, OUTPUT_ON_VALUE)
        i = 0
        while not self.is_on and i < 5:
            i += 1
            await asyncio.sleep(200 / 1000)
            await self.coordinator.async_request_refresh()
        _LOGGER.debug('Output %s on', self._idx)

    async def async_turn_off(self) -> None:
        _LOGGER.debug('Output %s off sent', self._idx)
        await self._client.command_output(self._pin, self._idx, OUTPUT_OFF_VALUE)
        i = 0
        while self.is_on and i < 5:
            i += 1
            await asyncio.sleep(200 / 1000)
            await self.coordinator.async_request_refresh()
        _LOGGER.debug('Output %s on', self._idx)
