# Vishal Backend Contract Gap List

This document records Tharun's hardware-control contract against the merged
`vishal-phase1` branch, which includes the current `phase-6` Pi and ESP32
implementation. It describes existing behavior and gaps; it does not approve
new endpoints or change the runtime contract.

## Confirmed ownership and mobile response meaning

- Flutter communicates with the Pi API, not directly with the ESP32.
- `POST /api/v1/robot/move` accepts `direction`
  (`forward`, `backward`, `left`, `right`) and an optional integer
  `speed` from 0 to 255.
- `POST /api/v1/robot/stop` accepts an empty body.
- Robot command routes require a Bearer token stored outside source control.
- HTTP `status: "dispatched"` means the Pi wrote the command to serial. It
  does not confirm ESP32 acceptance or completed movement.
- The API runs inside the Pi robot process and shares its motor controller and
  ESP32 serial connection. Do not start a separate Uvicorn process beside
  `thashu/main.py`.

## Current implementation and remaining gaps

| Item | Current code | Follow-up / owner |
|---|---|---|
| Sensor safety | ESP32 `SafetyManager` remains the final authority for motor safety. Pi `GPIOControl` parses timestamped sensor telemetry and distinguishes `FAR` from missing `NA`. The autonomous follow path uses fresh sensor data (maximum age 750 ms), treats missing/stale values as not clear, treats `FAR` as clear, and uses a 300 mm threshold. The mobile API move path does not run that follow-only sensor pre-check; the ESP32 still checks and can reject movement. | Tharun: verify the firmware safety behavior on the robot. Vishal: change manual pre-check behavior only after the owners agree its contract. |
| ESP32 connection and safety reports | The Pi transport tracks connection state, ACK results, sensor snapshots, and EVENT/FAULT messages. The API status route currently reports connection state but keeps controller readiness `unknown` because it does not track the ESP32 READY event. | Vishal: expose readiness only from observed READY state. Agree any response changes with Niteshvar. |
| ACK handling | `GPIOControl.wait_for_ack()` exists. Voice movement waits up to 750 ms; follow pulses wait 200 ms. The API manager returns after serial dispatch and does not wait for ACK or publish a later command result. | Vishal and Niteshvar: agree how the app will receive ACKED, REJECTED, TIMEOUT, or STOPPED results before changing the API/WebSocket schema. |
| STOP latch and mode | Firmware STOP stops the motors and sets active motion to STOPPED, but the checked-in ESP32 code has no persistent latch that blocks a later movement command. The Pi API reports STOP as dispatched and changes its tracked mode to AUTO; follow remains stopped until explicitly started. | Tharun: confirm/implement the hardware STOP-latch policy. Vishal and Niteshvar: agree selected/paused mode and resume behavior before changing API semantics. |
| Telemetry WebSocket | The API sends raw ESP32 lines from a single-consumer queue. It is not yet a parsed, multi-client event stream for command results and robot state. | Vishal and Niteshvar: agree the event schema, reconnect behavior, and client count before extending telemetry. |
| Network and credentials | The API binds to localhost by default. Devices in different homes cannot reach one another using `127.0.0.1` or the Pi's home-only LAN address. | Tharun: prepare a private encrypted connection and firewall access when the Pi is available. Vishal: provide a fresh test token securely. Only then set `THASHU_API_HOST=0.0.0.0` for access over that private connection. |

## Scope notes

- Do not implement resume, mode, emergency-stop, or command-result routes
  until the mobile-facing contract is agreed with Niteshvar.
- Do not weaken ESP32 safety or treat stale/missing sensor values as clear.
- Physical robot verification belongs to Tharun. Backend software and API
  integration belong to Vishal.
- Update this document and the API contract when the owners resolve a gap.
