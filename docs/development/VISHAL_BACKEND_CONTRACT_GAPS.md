# Vishal Backend Contract Gap List

This document tracks confirmed behavior and unresolved interface decisions for Vishal's Raspberry Pi backend work. It does not approve new routes or change robot behavior.

## Confirmed backend contract

- Flutter communicates with the Pi API; it does not communicate directly with the ESP32.
- `POST /api/v1/robot/move` accepts `direction` (`forward`, `backward`, `left`, `right`) and an optional integer `speed` from 0 to 255.
- `POST /api/v1/robot/stop` accepts an empty body.
- Robot command routes require a Bearer token. The token is configured outside source control.
- A successful response with `status: "dispatched"` means the Pi wrote a command to its serial transport. It does not prove ESP32 acknowledgement or physical movement.
- A dispatched move sets the Pi's tracked control mode to `MANUAL`; a dispatched stop sets the tracked mode to `AUTO`. The current backend tracks these labels; it does not implement an automatic motor controller.
- The core move/stop endpoint details were shared with Niteshvar, who acknowledged them and is waiting for a Pi address and test token. Current response/error examples are documented in `api/README.md`; share any updates with him before client integration.

## Open decisions and owners

| Item | Current state | Owner / next action |
|---|---|---|
| Safety check before manual movement | The API validates direction and speed, but does not currently evaluate a live robot safety state before dispatch. | Vishal and Tharun: define how the Pi learns whether movement is safe and what response it should return when it is not. |
| Switching from Manual back to Auto | Stop changes the tracked mode to `AUTO`; an automatic motor controller is not integrated in this backend. | Tharun owns robot behavior; agree what “back to Auto” physically means before describing it as resumed autonomous control. |
| ESP32 acknowledgement and timeout | The app response intentionally reports Pi dispatch only. The API does not wait for or correlate ESP32 acknowledgements. | Vishal and Tharun: confirm whether the Pi should track ACK, rejection, or timeout internally under the frozen serial protocol. |
| Telemetry WebSocket | The endpoint currently wraps raw ESP32 lines as `{"type":"esp32_line","line":"..."}`. | Vishal and Niteshvar: confirm whether Flutter needs this feed and agree stale-data, reconnect, and event behavior before expanding it. |
| Pi network access and test credentials | Pi target is Raspberry Pi OS Bookworm with Python 3.11.2, but the Pi is not yet available for app connection. | Tharun prepares the Pi/private connection; Vishal provides a fresh test token through a secure channel when ready. |

## Scope notes

- Do not add mode, emergency-stop, reset, mock, or other API routes until their contracts are approved by the relevant owners.
- Physical robot verification belongs to Tharun. Backend software behavior and API contract documentation belong to Vishal.
- Update this list when an owner resolves an item; do not treat an assumption as an approval.
