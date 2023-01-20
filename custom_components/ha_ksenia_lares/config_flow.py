import logging

import voluptuous as vol
from homeassistant import exceptions
from homeassistant.config_entries import ConfigFlow

from .base import LaresBase
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({"host": str, "port": int, "username": str, "password": str})


async def validate_input(data):
    client = LaresBase(data)
    info = await client.general_info()
    if info is None:
        raise InvalidAuth
    return {"title": info["name"], "id": info["id"]}


class KseniaConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

        errors = {}

        try:
            info = await validate_input(user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception(f"Unexpected exception {ex}")
            errors["base"] = "unknown"
        else:
            # Abort in case the host was already configured before.
            await self.async_set_unique_id(str(info["id"]))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
