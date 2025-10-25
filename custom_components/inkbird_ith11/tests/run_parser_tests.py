import sys
import os

# Add custom_components to path so we can import the integration package
ROOT = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(ROOT, "custom_components"))

from inkbird_ith11 import parser

class DummyServiceInfo:
    def __init__(self, manufacturer_data=None, service_data=None, advertisement=None, address=None):
        self.manufacturer_data = manufacturer_data or {}
        self.service_data = service_data or {}
        self.advertisement = advertisement
        self.address = address or "aa:bb:cc:dd:ee:ff"


def run():
    print("Running parser smoke tests...")

    # Test 1: temp 23.45 (2345 little-endian), humidity 56, battery 95
    temp_le = (2345).to_bytes(2, byteorder='little', signed=True)
    payload = temp_le + bytes([56, 95])
    svc = DummyServiceInfo(manufacturer_data={1: payload})
    res = parser.parse(svc)
    print("Test 1 payload:", payload.hex())
    print("Parsed:", res)
    ok1 = (abs(res.get('temperature', 0) - 23.45) < 0.01) and res.get('humidity') == 56 and res.get('battery') == 95
    print("Test 1 OK?", ok1)

    # Test 2: big-endian 230 -> 23.0 if /10, battery 80
    raw = (230).to_bytes(2, byteorder='big', signed=True)
    payload2 = raw + bytes([80])
    svc2 = DummyServiceInfo(service_data={"abc": payload2})
    res2 = parser.parse(svc2)
    print("Test 2 payload:", payload2.hex())
    print("Parsed:", res2)
    ok2 = (abs(res2.get('temperature', 0) - 23.0) < 0.01) and res2.get('battery') == 80
    print("Test 2 OK?", ok2)

    # Test 3: empty payload
    svc3 = DummyServiceInfo(manufacturer_data={1: b''})
    res3 = parser.parse(svc3)
    print("Test 3 Parsed:", res3)
    ok3 = res3 == {}
    print("Test 3 OK?", ok3)

    # Test 4: user-provided advertisement_data payload
    # Original repr: b'\x02(\x07\\\xa1\x00\xe7\x03F\x00D\x08\x00\x00\x00\x00'
    # Interpreted bytes: 02 28 07 5C A1 00 E7 03 46 00 44 08 00 00 00 00
    payload4 = bytes([0x02, 0x28, 0x07, 0x5C, 0xA1, 0x00, 0xE7, 0x03, 0x46, 0x00, 0x44, 0x08, 0x00, 0x00, 0x00, 0x00])
    svc4 = DummyServiceInfo(manufacturer_data={9545: payload4})
    res4 = parser.parse(svc4)
    print("Test 4 payload:", payload4.hex())
    print("Parsed:", res4)
    # According to the user's formula:
    # humidity = (x[7] << 8) + x[6] -> (0x03 << 8) + 0xE7 = 999 -> 99.9%
    # temperature = (x[5] << 8) + x[4] -> (0x00 << 8) + 0xA1 = 161 -> 16.1°C
    # battery = x[8] -> 0x46 = 70
    exp_temp = 16.1
    exp_hum = 99.9
    exp_batt = 70
    ok4 = (
        (abs(res4.get('temperature', 0) - exp_temp) < 0.05)
        and abs(res4.get('humidity', 0) - exp_hum) < 0.05
        and res4.get('battery') == exp_batt
    )
    print("Test 4 OK? (matches expected temp/hum/batt)", ok4)

    # Test 5: second user-provided advertisement_data payload (user's new sample)
    # Original repr: b'\x02(\x07\\\x9f\x00\xe7\x03V\x00D\x08\x00\x00\x00\x00'
    # Interpreted bytes: 02 28 07 5C 9F 00 E7 03 56 00 44 08 00 00 00 00
    payload5 = bytes([0x02, 0x28, 0x07, 0x5C, 0x9F, 0x00, 0xE7, 0x03, 0x56, 0x00, 0x44, 0x08, 0x00, 0x00, 0x00, 0x00])
    svc5 = DummyServiceInfo(manufacturer_data={9545: payload5})
    res5 = parser.parse(svc5)
    print("Test 5 payload:", payload5.hex())
    print("Parsed:", res5)
    # According to formula:
    # humidity -> same (999 -> 99.9%), temperature -> 0x009F = 159 -> 15.9°C, battery = 0x56 = 86
    ok5 = (
        (abs(res5.get('temperature', 0) - 15.9) < 0.05)
        and abs(res5.get('humidity', 0) - 99.9) < 0.05
        and res5.get('battery') == 86
    )
    print("Test 5 OK? (matches expected temp/hum/batt)", ok5)

    all_ok = ok1 and ok2 and ok3 and ok4 and ok5
    print("ALL OK?", all_ok)
    if not all_ok:
        sys.exit(2)

if __name__ == '__main__':
    run()
