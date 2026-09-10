"""Ksenia Lares < v4.0 Home Assistant integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries, core
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .base import LaresBase
from .const import DOMAIN
from .coordinator import LaresOutputsCoordinator

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
PLATFORMS = [Platform.LIGHT, Platform.COVER]


@dataclass
class LaresRuntimeData:
    client: LaresBase
    coordinator: LaresOutputsCoordinator
    device_info: dict[str, Any]
    descriptions: dict[int, str]
    pin: str


async def async_setup_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    session = async_get_clientsession(hass)
    client = LaresBase(entry.data, session)

    device_info = await client.device_info()
    if device_info is None:
        raise ConfigEntryNotReady("Impossible to get Lares device info")
    basis_info = await client.basis_info()
    if basis_info is None or "PINToUse" not in basis_info:
        raise ConfigEntryNotReady("Impossible to get Lares basis info")
    descriptions = await client.outputs_descriptions(device_info)
    if not descriptions:
        raise ConfigEntryNotReady("Impossible to get Lares outputs descriptions")

    if entry.unique_id:
        device_info["identifiers"] = {(DOMAIN, entry.unique_id)}

    coordinator = LaresOutputsCoordinator(hass, client, device_info, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = LaresRuntimeData(
        client=client,
        coordinator=coordinator,
        device_info=device_info,
        descriptions=descriptions,
        pin=basis_info["PINToUse"],
    )
    entry.async_on_unload(entry.add_update_listener(options_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info(
        "Lares setup complete: %s outputs, coordinator items=%s",
        len(descriptions),
        len(coordinator.data or []),
    )
    return True


async def options_update_listener(hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry):
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True
