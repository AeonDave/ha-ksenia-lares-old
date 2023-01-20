"""Ksenia Lares < v4.0 Component."""
import asyncio
import logging

import voluptuous as vol
from homeassistant import config_entries, core
from homeassistant.const import Platform

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener
    hass.data[DOMAIN][entry.entry_id] = hass_data
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    return True


async def options_update_listener(hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry):
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    unload_ok = all(
        await asyncio.gather(
            *(hass.config_entries.async_forward_entry_unload(entry, component)
              for component in PLATFORMS)
        )
    )
    hass.data[DOMAIN][entry.entry_id]["unsub_options_update_listener"]()
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True
