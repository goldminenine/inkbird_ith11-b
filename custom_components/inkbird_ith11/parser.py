"""Parser for Inkbird ITH-11-B BLE advertisements.

This module implements heuristic parsing of BLE advertisement/service/manufacturer
bytes to extract temperature (°C), humidity (%), and battery (%).

The ITH-11-B advertising format varies by firmware; this parser scans
manufacturer_data and service_data byte payloads for plausible numeric
patterns (int16 temperature with scale 0.01 or 0.1, humidity as 0-100,
battery as 0-100). It returns a dict with available keys: 'temperature',
'humidity', 'battery'.
"""
from __future__ import annotations

from typing import Optional, Tuple


def _as_bytes(value) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    # Some HA objects might expose memoryview
    try:
        return bytes(value)
    except Exception:
        return b""


def _find_temperature(payload: bytes) -> Tuple[Optional[float], Optional[int]]:
    """Search payload for a plausible temperature value and return (temp, index).

    Tries signed/unsigned 16-bit values interpreted as x/100 or x/10.
    Returns (temperature in °C, index) if found in realistic range (-40..85).
    """
    if not payload:
        return None, None

    for i in range(len(payload) - 1):
        # try combinations of endian/signed/scale
        for byteorder in ("little", "big"):
            for signed in (True, False):
                raw = int.from_bytes(payload[i:i+2], byteorder=byteorder, signed=signed)
                for scale in (100.0, 10.0):
                    temp = raw / scale
                    if -40.0 <= temp <= 85.0:
                        return round(temp, 2), i
    return None, None


def _find_humidity(payload: bytes, temp_index: Optional[int] = None) -> Tuple[Optional[int], Optional[int]]:
    """Search payload for a plausible humidity byte (0..100).

    Prefer bytes after the temperature index if provided, avoid tiny noise values (<3).
    Returns (humidity, index).
    """
    if not payload:
        return None, None

    candidates = [(idx, b) for idx, b in enumerate(payload) if 0 <= b <= 100 and b > 3]
    if not candidates:
        return None, None

    if temp_index is not None:
        after = [c for c in candidates if c[0] > temp_index]
        if after:
            # choose the closest one after temp_index
            chosen = min(after, key=lambda t: t[0])
            return int(chosen[1]), int(chosen[0])

    # fallback: prefer candidates in the middle/end region
    mid = len(payload) // 2
    chosen = min(candidates, key=lambda t: abs(t[0] - mid))
    return int(chosen[1]), int(chosen[0])


def _find_battery(payload: bytes, temp_index: Optional[int] = None, hum_index: Optional[int] = None) -> Tuple[Optional[int], Optional[int]]:
    """Search payload for a plausible battery percentage (0..100).

    Scan from the end for a reasonable battery (>=10%). Returns (battery, index).
    """
    if not payload:
        return None, None

    for idx in range(len(payload) - 1, -1, -1):
        b = payload[idx]
        if 10 <= b <= 100:
            return int(b), idx

    # last-resort: any 0..100 value
    for idx, b in enumerate(payload):
        if 0 <= b <= 100:
            return int(b), idx

    return None, None


def parse(service_info) -> dict:
    """Parse a BluetoothServiceInfo-like object and extract sensor values.

    This parser is strict: it decodes only Inkbird ITH-11-B manufacturer_data
    under company id 9545 using the documented offsets. If that key is not
    present or the payload is too short, the function returns an empty dict.
    """
    result = {}

    try:
        mfg = getattr(service_info, "manufacturer_data", None)
        if isinstance(mfg, dict) and 9545 in mfg:
            payload = _as_bytes(mfg.get(9545))
            # Need at least 9 bytes for indexes up to x[8]
            if payload and len(payload) > 8:
                # user-provided formulas:
                # humidity = (x[7] << 8) + x[6]
                # temperature = (x[5] << 8) + x[4]
                # battery = x[8]
                try:
                    raw_hum = (payload[7] << 8) + payload[6]
                    raw_temp = (payload[5] << 8) + payload[4]
                    batt = payload[8]

                    # Scale: device uses 0.1 units (e.g., 161 -> 16.1°C, 999 -> 99.9%)
                    hum = round(raw_hum / 10.0, 1)
                    temp = round(raw_temp / 10.0, 1)

                    result["temperature"] = temp
                    result["humidity"] = hum
                    result["battery"] = int(batt)
                    return result
                except Exception:
                    # If decoding fails, return empty rather than guessing
                    return {}
    except Exception:
        return {}

    return {}
