"""Config flow for Inkbird ITH-11-B integration."""
from __future__ import annotations

import re
from typing import Any
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_MAC, CONF_NAME, DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)

MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")


class InkbirdConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Inkbird ITH-11-B."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:  # type: ignore[override]
        """Handle the initial step."""
        errors = {}
        try:
            if user_input is not None:
                mac = user_input.get(CONF_MAC, "").strip()
                name = user_input.get(CONF_NAME) or DEFAULT_NAME
                if not MAC_RE.match(mac):
                    errors["base"] = "invalid_mac"
                else:
                    # Use MAC as unique ID
                    await self.async_set_unique_id(mac.lower())
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=name, data={CONF_MAC: mac.lower(), CONF_NAME: name})

            data_schema = vol.Schema({
                vol.Required(CONF_MAC): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            })

            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
                errors=errors,
            )
        except Exception:  # pragma: no cover - log and re-raise so HA surfaces the error
            _LOGGER.exception("Unexpected error in Inkbird config flow")
            raise

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow for this config entry."""
        return InkbirdOptionsFlow(config_entry)


class InkbirdOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Inkbird ITH-11-B."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):  # type: ignore[override]
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema({
            vol.Optional(CONF_NAME, default=self.config_entry.data.get(CONF_NAME)): str,
        })
        return self.async_show_form(step_id="init", data_schema=data_schema)
