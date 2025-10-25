"""Inkbird ITH-11-B Home Assistant integration.

This integration listens for BLE advertisements (works with ESPHome BLE proxy)
and exposes temperature, humidity and battery sensors.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import logging

from .const import DOMAIN, CONF_MAC, DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Inkbird ITH-11-B from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "entry": entry,
        "state": {},
    }

    _LOGGER.debug("Setting up Inkbird entry %s for MAC %s", entry.entry_id, entry.data.get(CONF_MAC))

    # Forward to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _LOGGER.debug("Unloaded Inkbird entry %s", entry.entry_id)
    return unload_ok
