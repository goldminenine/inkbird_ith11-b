"""Sensor platform for Inkbird ITH-11-B integration."""
from __future__ import annotations

import logging
from typing import Any
from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from homeassistant.components.bluetooth import (
    async_register_callback,
    BluetoothCallbackMatcher,
    BluetoothScanningMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.components.sensor import SensorDeviceClass

from .const import DOMAIN, CONF_MAC, SENSOR_TEMPERATURE, SENSOR_HUMIDITY, SENSOR_BATTERY
from .parser import parse

_LOGGER = logging.getLogger(__name__)

UPDATE_SIGNAL = f"{DOMAIN}_update"


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up sensors for a config entry."""
    entry_id = entry.entry_id
    mac = entry.data.get(CONF_MAC)
    name = entry.data.get("name") or mac

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry_id, {})
    hass.data[DOMAIN][entry_id]["state"] = {}

    # Create entities
    sensors = [
        InkbirdSensor(entry_id, SENSOR_TEMPERATURE, name),
        InkbirdSensor(entry_id, SENSOR_HUMIDITY, name),
        InkbirdSensor(entry_id, SENSOR_BATTERY, name),
    ]

    async_add_entities(sensors, True)

    # Register bluetooth callback if available
    try:
        @callback
        def _service_info_callback(service_info, change=None) -> None:
            try:
                # Some BLE proxies change the source address; don't strictly filter by address here.
                # Do not bail out if `address` is None — ESPHome BLE proxy may forward adverts without an address.
                # Log received advertisement for debugging
                try:
                    mfg = getattr(service_info, "manufacturer_data", None)
                    sdata = getattr(service_info, "service_data", None)
                except Exception:
                    mfg = None
                    sdata = None
                _LOGGER.debug("Inkbird received advert from %s, manufacturer_data=%s, service_data=%s", service_info.address, mfg, sdata)

                data = parse(service_info)
                if not data:
                    return

                # Build raw payload hex map for attributes
                raw_mfg = {}
                raw_svc = {}
                try:
                    if isinstance(mfg, dict):
                        for k, v in mfg.items():
                            try:
                                raw_mfg[str(k)] = bytes(v).hex()
                            except Exception:
                                try:
                                    raw_mfg[str(k)] = v.hex()
                                except Exception:
                                    raw_mfg[str(k)] = str(v)
                    if isinstance(sdata, dict):
                        for k, v in sdata.items():
                            try:
                                raw_svc[str(k)] = bytes(v).hex()
                            except Exception:
                                try:
                                    raw_svc[str(k)] = v.hex()
                                except Exception:
                                    raw_svc[str(k)] = str(v)
                except Exception:
                    pass

                # Add last_seen timestamp
                ts = datetime.utcnow().isoformat() + "Z"

                # Update state with parsed values and debug attributes
                hass.data[DOMAIN][entry_id]["state"].update(data)
                hass.data[DOMAIN][entry_id]["state"]["raw_manufacturer"] = raw_mfg
                hass.data[DOMAIN][entry_id]["state"]["raw_service_data"] = raw_svc
                hass.data[DOMAIN][entry_id]["state"]["last_seen"] = ts

                _LOGGER.debug("Inkbird parsed data for %s: %s (raw_mfg=%s, raw_svc=%s)", service_info.address, data, raw_mfg, raw_svc)
                # Send the full state (including raw payloads) to listeners
                full_state = hass.data[DOMAIN][entry_id]["state"].copy()
                async_dispatcher_send(hass, f"{UPDATE_SIGNAL}_{entry_id}", full_state)
            except Exception as exc:  # pragma: no cover - robust handling
                _LOGGER.exception("Error parsing Inkbird service info: %s", exc)

        # Use BluetoothScanningMode as required by modern HA API
        matcher = BluetoothCallbackMatcher(address=mac)
        unregister = async_register_callback(hass, _service_info_callback, matcher, BluetoothScanningMode.ACTIVE)
        unregisters = [unregister]
        _LOGGER.debug("Registered bluetooth callback for address matcher (mac=%s).", mac)

        # Also register fallback matchers to increase chance of receiving adverts
        try:
            mfg_matcher = BluetoothCallbackMatcher(manufacturer_id=9545)
            un2 = async_register_callback(hass, _service_info_callback, mfg_matcher, BluetoothScanningMode.ACTIVE)
            unregisters.append(un2)
            _LOGGER.debug("Registered bluetooth callback for manufacturer_id=9545")
        except Exception:
            _LOGGER.debug("Could not register manufacturer_id matcher")

        try:
            uuid_matcher = BluetoothCallbackMatcher(service_uuid="0000fff0-0000-1000-8000-00805f9b34fb")
            un3 = async_register_callback(hass, _service_info_callback, uuid_matcher, BluetoothScanningMode.ACTIVE)
            unregisters.append(un3)
            _LOGGER.debug("Registered bluetooth callback for service_uuid fff0")
        except Exception:
            _LOGGER.debug("Could not register service_uuid matcher")

        # DEBUG fallback: register a global matcher that receives all adverts so we can
        # verify the callback is fired even if specific matchers fail (remove in prod).
        try:
            global_matcher = BluetoothCallbackMatcher()
            un_global = async_register_callback(hass, _service_info_callback, global_matcher, BluetoothScanningMode.ACTIVE)
            unregisters.append(un_global)
            _LOGGER.debug("Registered global bluetooth callback matcher for debugging")
        except Exception:
            _LOGGER.debug("Could not register global matcher")
        _LOGGER.debug("Total bluetooth callbacks registered: %d", len(unregisters))
    except Exception:  # pragma: no cover - best effort
        _LOGGER.error("Bluetooth integration not available; cannot listen for Inkbird BLE adverts")
        return

    hass.data[DOMAIN][entry_id]["unregister_bluetooth"] = unregisters


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    entry_id = entry.entry_id
    unregister = hass.data[DOMAIN][entry_id].get("unregister_bluetooth")
    if unregister:
        try:
            for un in unregister:
                un()
        except Exception:
            pass
    return True


class InkbirdSensor(SensorEntity):
    """Generic Inkbird sensor entity."""

    _attr_should_poll = False

    def __init__(self, entry_id: str, sensor_type: str, base_name: str) -> None:
        self._entry_id = entry_id
        self._sensor_type = sensor_type
        self._base_name = base_name
        self._unique_id = f"{entry_id}_{sensor_type}"
        self._attr_name = f"{base_name} {sensor_type.capitalize()}"
        self._state = None

        if sensor_type == SENSOR_TEMPERATURE:
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        elif sensor_type == SENSOR_HUMIDITY:
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_device_class = SensorDeviceClass.HUMIDITY
        elif sensor_type == SENSOR_BATTERY:
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_device_class = SensorDeviceClass.BATTERY

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def native_value(self) -> Any:
        return self._state

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes (raw payloads + last seen)."""
        state = self.hass.data[DOMAIN].get(self._entry_id, {}).get("state", {})
        attrs = {}
        if "raw_manufacturer" in state:
            attrs["raw_manufacturer"] = state.get("raw_manufacturer")
        if "raw_service_data" in state:
            attrs["raw_service_data"] = state.get("raw_service_data")
        if "last_seen" in state:
            attrs["last_seen"] = state.get("last_seen")
        return attrs

    @property
    def device_info(self) -> dict:
        """Return device information for the device registry."""
        entry = self.hass.data[DOMAIN].get(self._entry_id, {}).get("entry")
        mac = None
        if entry is not None:
            mac = entry.data.get(CONF_MAC)
        if not mac:
            return {}
        return {
            "identifiers": {(DOMAIN, mac)},
            "name": self._base_name,
            "manufacturer": "Inkbird",
            "model": "ITH-11-B",
        }

    async def async_added_to_hass(self) -> None:
        # Initialize from stored state if available
        state = self.hass.data[DOMAIN][self._entry_id].get("state", {})
        if self._sensor_type in state:
            self._state = state[self._sensor_type]
            # Ensure HA sees the initial value immediately
            self.async_write_ha_state()

        # Subscribe to updates
        self._unsub = async_dispatcher_connect(
            self.hass, f"{UPDATE_SIGNAL}_{self._entry_id}", self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        if hasattr(self, "_unsub") and callable(self._unsub):
            self._unsub()

    @callback
    def _handle_update(self, data: dict) -> None:
        if self._sensor_type in data:
            self._state = data[self._sensor_type]
            self.async_write_ha_state()
