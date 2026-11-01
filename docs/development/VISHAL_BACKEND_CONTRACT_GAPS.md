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
| Sensor safety and Pi pre-check | ESP32 `SafetyManager` checks front ToF and rear ultrasonic data and uses a 300 mm obstacle threshold. ToF readings are fresh for up to 150 ms; rear ultrasonic readings for up to 200 ms. The ESP32 emits front `FAR` values, but rear telemetry is `NA` when no valid range is available. The Pi API does not parse sensor telemetry or run a matching pre-check; `GPIOControl` queues raw lines. The checked-in `thashu/vision/follow_logic.py` is face-follow logic, not the ToF gate. | Tharun: confirm whether the “current Pi follow check” exists outside this branch and reconcile rear `FAR` and turn-safety behavior with the checked-in firmware. Vishal: integrate Pi-side checks only after locating/agreeing the Pi sensor-state source. |
| STOP latch and mode | ESP32 handles STOP by stopping motors and setting active motion to STOPPED, but the checked-in firmware has no persistent STOP-latch flag that blocks a later movement command. The Pi manager changes its tracked mode to `AUTO` on STOP and has no paused state or explicit resume route. | Tharun: confirm/implement the hardware STOP latch policy. Vishal and Niteshvar: agree how selected mode, paused state, and explicit resume are represented to the app before changing the API. |
| ESP32 ACK tracking | ESP32 `CommunicationManager` emits sequence-correlated ACKs for accepted and rejected commands. On the Pi, `GPIOControl.send()` returns a sequence after serial write and `read_line()` queues raw inbound lines; the checked-in Pi code has no sequence-correlated ACK waiter or 750 ms timeout. | Tharun: identify the Pi file/commit containing the ACK tracker and follow-pulse timeout he referred to, if it exists outside this branch. Vishal: align the checked-in Pi implementation with the frozen protocol and agreed timeouts. |
| Async app result | The API returns only `dispatched`. The existing WebSocket wraps raw lines; it does not publish parsed command outcomes. | Vishal and Niteshvar: choose the agreed status/event shape and delivery path before adding or changing endpoints. |
| Network and credentials | The Pi target is Bookworm/Python 3.11.2, but it is not yet available for app access. | Tharun: prepare the private connection. Vishal: provide a fresh test token securely when the server can be reached. |

## Scope notes

- Do not implement new resume, mode, emergency-stop, or command-result routes until the mobile-facing contract is agreed with Niteshvar.
- Do not weaken the ESP32 safety authority or treat stale/missing sensor values as clear.
- Physical robot verification belongs to Tharun. Backend software behavior and API integration belong to Vishal.
- Resolve gaps with the listed owners, then update this document and the API contract before implementation.
