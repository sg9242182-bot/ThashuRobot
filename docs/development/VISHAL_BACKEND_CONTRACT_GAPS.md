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
| ACK handling | Voice movement waits up to 750 ms; follow pulses wait 200 ms. API move/stop returns `dispatched` immediately, tracks the matching ACK asynchronously for up to 750 ms, publishes `acknowledged`, `safety_error`, or `timed_out` as a WebSocket `command_result`, and exposes the current result at `GET /api/v1/robot/commands/{command_id}`. Results are retained in process memory for 24 hours (maximum 1,000), so a process restart clears them. | Vishal and Niteshvar: integrate Flutter with these agreed field names and statuses. |
| STOP latch and mode | Firmware STOP stops the motors and sets active motion to STOPPED, but the checked-in ESP32 code has no persistent latch that blocks a later movement command. The Pi API reports STOP as dispatched and changes its tracked mode to AUTO; follow remains stopped until explicitly started. | Tharun: confirm/implement the hardware STOP-latch policy. Vishal and Niteshvar: agree selected/paused mode and resume behavior before changing API semantics. |
| Telemetry WebSocket | The API sends raw ESP32 lines and broadcasts `command_result` events to connected WebSocket clients. Raw serial telemetry remains a single-consumer queue. | Vishal and Niteshvar: integrate the event schema and reconnect behavior in Flutter. |
| Network and credentials | The API binds to localhost by default. Devices in different homes cannot reach one another using `127.0.0.1` or the Pi's home-only LAN address. | Tharun: prepare a private encrypted connection and firewall access when the Pi is available. Vishal: provide a fresh test token securely. Only then set `THASHU_API_HOST=0.0.0.0` for access over that private connection. |

## Phase 2 protocol contract (deployed protocol v0)

This documents the working protocol reported by Tharun and observed from the
integrated ESP32 output (TEL|0|SENSORS...). The Pi client, shared vectors,
tests, and integrated firmware on this branch use this format.

- Transport: USB CDC serial at 115200 baud, newline-delimited ASCII.
- Commands: CMD|sequence|payload...\n.
- Acknowledgements: ACK|sequence|result...\n. Results include OK, ALIVE, and
  ERROR|reason.
- Encoder reply: ENC|sequence|count0|count1|count2|count3\n.
- Sensor telemetry:
  TEL|0|SENSORS|TOF_L|value|TOF_C|value|TOF_R|value|US_REAR|value\n.
  Distances are millimetres; fresh out-of-range readings are FAR, and
  unavailable/stale readings are NA.
- Startup/fault/event frames use the deployed v0 forms, including
  EVENT|0|READY, EVENT|0|STOP|OBSTACLE, EVENT|0|BLOCKED|OBSTACLE, and
  FAULT|0|subsystem|detail.
- Supported command payloads:
  - STOP → ACK|sequence|OK
  - HEARTBEAT → ACK|sequence|ALIVE
  - MOTOR|FORWARD/BACKWARD/LEFT/RIGHT|0..255 → OK, a safety error,
    or a validation error
  - EYES|IDLE/HAPPY/THINKING/LISTENING/SPEAKING/ALERT/SLEEP
  - SERVO|PAN_TILT|pan|tilt
  - SERVO|MOVE|pan|tilt|duration_ms
  - ENCODERS → an ENC frame, not an ACK
- The Pi allocates positive sequence numbers from 1 through 2,147,483,647 and
  stops instead of wrapping. The ESP32 parser accepts nonnegative sequence
  numbers. The command and ACK frames carry no protocol-version field and no
  session ID; ACK matching is by sequence only. A Pi restart resets the
  sequence, so a delayed ACK from before restart cannot be distinguished from
  a new ACK with a reused sequence.
- This protocol has no unsupported-version response or duplicate-command
  suppression. Do not send the incompatible v1 envelope
  CMD|version|session_id|sequence|payload; the v0 parser expects the
  sequence in field 2.
- The integrated motor driver is TA6586. EYES and SERVO are supported;
  legacy EXPRESSION and EAR commands must not be sent.
- The Pi heartbeat is sent every 100 ms and the ESP32 watchdog is 500 ms.
  STOP, ESP32 obstacle checks, and the watchdog retain their existing behavior.
- The separate ESP32Firmware/communicationmanager/ copy and
  command_parser.cpp are legacy/stale; the integrated sketch uses
  ESP32Firmware/ThashuController/communication_manager.cpp.

## Remaining Phase 2 decisions

- The deployed v0 command/reply and telemetry frames are implemented in the
  integrated sketch, Pi serial transport, shared protocol vectors, and this
  document.
- Session-aware ACK correlation and explicit command-version negotiation are
  not provided by v0. Reintroducing either requires an agreed protocol change
  coordinated across Pi, ESP32, and backend tests.
- The user-reported test of the running v0 ESP32 parser passed 9 applicable
  checks: valid HEARTBEAT/STOP/EYES, invalid and unknown commands, partial
  frames, oversized-frame discard, and recovery after an oversized frame.
  Unsupported-version testing was not applicable to v0. The branch-aligned
  source still requires compile/upload and Pi integration verification.
- STOP latch and selected/paused mode behavior still need the owners' decision
  before changing API semantics.

## Scope notes

- Do not implement resume, mode, or emergency-stop routes until their
  mobile-facing contract is agreed with Niteshvar.
- Do not weaken ESP32 safety or treat stale/missing sensor values as clear.
- Physical robot verification belongs to Tharun. Backend software and API
  integration belong to Vishal.
- Update this document and the API contract when the owners resolve a gap.
