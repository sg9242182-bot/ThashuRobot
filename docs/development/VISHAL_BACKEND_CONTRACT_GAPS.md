# Vishal Backend Contract Gap List

This document records Tharun's hardware-control contract against the merged
`vishal-phase1` branch, which includes the current `phase-6` Pi and ESP32
implementation. It describes existing behavior and gaps; it does not approve
new endpoints or change the runtime contract.

## Confirmed ownership and mobile response meaning

- Flutter communicates with the Pi API, not directly with the ESP32.
- `POST /api/v1/robot/move` accepts `direction`
  (`forward`, `backward`, `left`, `right`) and an optional integer
  `speed` from 0 to 255, plus a required UUID `request_id`.
- `POST /api/v1/robot/stop` accepts a required UUID `request_id`.
- Robot command routes require a Bearer token stored outside source control.
- HTTP `status: "dispatched"` means the Pi wrote the command to serial. It
  does not confirm ESP32 acceptance or completed movement.
- The API runs inside the Pi robot process and shares its motor controller and
  ESP32 serial connection. Do not start a separate Uvicorn process beside
  `thashu/main.py`.

## Current implementation and remaining gaps

| Item | Current code | Follow-up / owner |
|---|---|---|
| Sensor safety | ESP32 `SafetyManager` remains the final authority for motor safety. Pi `GPIOControl` parses timestamped sensor telemetry and distinguishes `FAR` from missing `NA`. Both autonomous follow and the shared command manager require a snapshot no older than 750 ms, treat missing/stale values as unsafe, treat `FAR` as clear, and require numeric readings above 300 mm. Forward/turning checks all front ToF sensors; backward checks rear. | Tharun: verify the firmware safety behavior on the robot. |
| ESP32 connection and safety reports | The Pi transport tracks connection state, ACK results, sensor snapshots, and EVENT/FAULT messages. The API status route currently reports connection state but keeps controller readiness `unknown` because it does not track the ESP32 READY event. | Vishal: expose readiness only from observed READY state. Agree any response changes with Niteshvar. |
| ACK handling and retry recovery | Voice movement waits up to 750 ms; follow pulses wait 200 ms. API move/stop returns `dispatched` immediately, tracks the matching ACK asynchronously for up to 750 ms, publishes `acknowledged`, `safety_error`, or `timed_out` as a WebSocket `command_result`, and exposes the latest result at `GET /api/v1/robot/commands/{command_id}`. Request IDs, action payloads, command IDs, and latest results are stored in SQLite for 24 hours. A restart changes `dispatching`/`awaiting_ack` records to `unknown` and never resends them. | Vishal implemented persistent idempotency for move and STOP; Niteshvar to integrate UUID request IDs. |
| STOP latch and mode | Pi exposes `POST /api/v1/robot/mode` with `{"mode":"MANUAL"}` or `{"mode":"AUTO"}`. It cancels Pi motion/follow timers, sends STOP, and switches only after `ACK|sequence|OK`. On failure, the previous mode remains selected, motion is inhibited, and a second best-effort STOP is sent. AUTO selection is paused; existing follow starts only through its explicit start action. Normal STOP cancels Pi motion/follow and returns selected mode to AUTO paused. ESP32 STOP itself is not latched against later commands. | Tharun: verify firmware stop behavior. Emergency Stop remains open pending an ESP32 protocol/firmware latch and explicit reset contract. Niteshvar: integrate and review the mode route and response. |
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
- A latched Emergency Stop and reset are not present in the deployed protocol.
  Tharun must propose and verify the ESP32 protocol/firmware change before the
  Pi claims or exposes that feature.

## Scope notes

- The proposed mode route is implemented as `POST /api/v1/robot/mode`; Niteshvar
  must review its request/response contract before integrating the Flutter app.
- Do not expose a latched Emergency Stop route until the ESP32 command/event and
  explicit reset behavior are implemented and verified.
- Do not weaken ESP32 safety or treat stale/missing sensor values as clear.
- Physical robot verification belongs to Tharun. Backend software and API
  integration belong to Vishal.
- Update this document and the API contract when the owners resolve a gap.
