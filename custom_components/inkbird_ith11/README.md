Inkbird ITH-11-B Home Assistant custom integration

This custom integration listens for BLE advertisements (works with ESPHome Bluetooth Proxy)
and extracts temperature, humidity and battery values from Inkbird ITH-11-B broadcasts.

Installation
- Copy the `inkbird_ith11` directory into `custom_components/` in your Home Assistant configuration directory.
- Restart Home Assistant.
- Add the integration from Settings -> Devices & Services -> Add Integration and enter the device MAC address.

Notes
- This integration registers a Bluetooth advertisement callback (requires the built-in `bluetooth` integration).
- Parsing is heuristic and may need adjustment for different firmware versions. Contributions welcome.

