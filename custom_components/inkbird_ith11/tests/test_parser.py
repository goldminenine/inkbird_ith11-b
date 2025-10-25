from __future__ import annotations

from inkbird_ith11 import parser


class DummyServiceInfo:
    def __init__(self, manufacturer_data=None, service_data=None, advertisement=None):
        self.manufacturer_data = manufacturer_data or {}
        self.service_data = service_data or {}
        self.advertisement = advertisement


def test_parse_temp_hum_batt_le():
    # temperature 23.45°C encoded as int16 little-endian = 2345 -> 0x29 0x09
    temp_le = (2345).to_bytes(2, byteorder='little', signed=True)
    # humidity 56, battery 95
    payload = temp_le + bytes([56, 95])
    svc = DummyServiceInfo(manufacturer_data={1: payload})
    res = parser.parse(svc)
    assert res.get('temperature') == 23.45 or res.get('temperature') == 23.45
    assert res.get('humidity') == 56
    assert res.get('battery') == 95


def test_parse_temp_be_scaling():
    # big-endian 230 -> 23.0 if /10
    raw = (230).to_bytes(2, byteorder='big', signed=True)
    payload = raw + bytes([80])
    svc = DummyServiceInfo(service_data={"abc": payload})
    res = parser.parse(svc)
    assert res.get('temperature') == 23.0
    assert res.get('battery') == 80


def test_no_values():
    svc = DummyServiceInfo(manufacturer_data={1: b''}, service_data={})
    res = parser.parse(svc)
    assert res == {}

