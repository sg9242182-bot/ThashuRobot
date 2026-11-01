# Vishal Backend Contract Gap List

This document records Tharun's hardware-control contract and compares it with the current Pi backend on `vishal-phase1`. It does not add routes or change runtime behavior.

## Confirmed ownership and mobile response meaning

- Flutter communicates with the Pi API, not directly with the ESP32.
- `POST /api/v1/robot/move` accepts `direction` (`forward`, `backward`, `left`, `right`) and an optional integer `speed` from 0 to 255.
- `POST /api/v1/robot/stop` currently accepts an empty body.
- Robot command routes require a Bearer token stored outside source control.
- An HTTP response with `status: "dispatched"` means only that the Pi wrote the command to serial. It must never be shown as proof that the ESP32 accepted or completed movement.
- The core move/stop endpoint details were shared with Niteshvar, who acknowledged them and is waiting for a Pi address and test token.

## Tharun's hardware contract

- Missing, `NA`, or stale sensor data is not clear. `FAR` means a working sensor sees no obstacle within range and may count as clear.
- Forward moves require fresh, clear front ToF readings. Reverse moves require a fresh, clear rear reading. The stated follow clearance threshold is 300 mm.
- Before dispatch, the Pi must require a connected ESP32 and no STOP latch or higher-priority safety event. The ESP32 remains the final safety authority and may reject a command.
- STOP sends the dedicated ESP32 STOP command and latches motion stopped. It must not automatically restart movement. If Auto was selected, it remains selected but paused; resuming requires an explicit resume/Auto action and fresh safety checks. STOP must not turn a manual session into active Auto.
- The Pi tracks the command sequence and waits for `ACK|sequence|OK`, a safety rejection, or timeout. Ordinary commands wait up to 750 ms; follow pulses use a shorter wait. On rejection or timeout, report failure and ensure STOP is sent.
- The app may receive `dispatched` immediately and a later result (`ACKED`, `REJECTED`, `TIMEOUT`, or `STOPPED`) through a status endpoint or event stream. The exact mobile event/status contract remains to be agreed with Niteshvar.

## Verified implementation gaps on `vishal-phase1`

| Item | What the current repository code does | Required follow-up / owner |
|---|---|---|
| Safety pre-check | The API/manager validate direction and speed but do not read fresh ToF data, enforce the 300 mm threshold, or check a Pi-side STOP latch/safety event. The checked-in `thashu/vision/follow_logic.py` is face-follow logic and does not contain that ToF gate. | Tharun: point to the current Pi follow/sensor-safety implementation if it lives elsewhere; confirm the sensor data source and the definition of “fresh.” Vishal: integrate the agreed pre-check only after locating the authoritative source. |
| STOP and mode | `RobotCommandManager.dispatch("stop")` currently changes the tracked mode to `AUTO`. There is no paused/stopped run state or explicit resume route. | Vishal and Niteshvar: agree how paused vs selected mode is represented to the app. Tharun: confirm how the Pi should enforce the STOP latch and explicit resume. |
| ESP32 ACK tracking | `GPIOControl.send()` returns a sequence after serial write. `read_line()` queues raw inbound lines; the checked-in code has no sequence-correlated ACK/rejection waiter or 750 ms command timeout. | Vishal: implement the tracker in the Pi transport after confirming exact reply/rejection forms. Tharun: specify the shorter follow-pulse timeout and safety-rejection event format. |
| Async app result | The API returns only `dispatched`. The existing WebSocket wraps raw lines; it does not publish parsed command outcomes. | Vishal and Niteshvar: choose the agreed status/event shape and delivery path before adding or changing endpoints. |
| Network and credentials | The Pi target is Bookworm/Python 3.11.2, but it is not yet available for app access. | Tharun: prepare the private connection. Vishal: provide a fresh test token securely when the server can be reached. |

## Scope notes

- Do not implement new resume, mode, emergency-stop, or command-result routes until the mobile-facing contract is agreed with Niteshvar.
- Do not weaken the ESP32 safety authority or treat stale/missing sensor values as clear.
- Physical robot verification belongs to Tharun. Backend software behavior and API integration belong to Vishal.
- Resolve gaps with the listed owners, then update this document and the API contract before implementation.
