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

## Phase 2 protocol contract (version 1)

This section records the confirmed behavior of the integrated firmware. The
integrated firmware is the source of truth; the separate
`ESP32Firmware/communicationmanager/communication_manager.cpp` copy is stale
in some behavior, and the old `command_parser.cpp` is not used by the
integrated sketch.

- Transport is USB CDC serial at 115200 baud. Commands use
  `CMD|1|session_id|sequence|payload...\n`. ACKs use
  `ACK|1|session_id|sequence|result...\n`; ENCODERS replies include
  version, session, sequence, and four counts.
- Supported payloads:
  - `STOP` → `ACK|1|session_id|sequence|OK`
  - `HEARTBEAT` → `ACK|1|session_id|sequence|ALIVE`
  - `MOTOR|FORWARD/BACKWARD/LEFT/RIGHT|0..255` → `ACK|1|session_id|sequence|OK`
    or a safety/error ACK
  - `EYES|IDLE/HAPPY/THINKING/LISTENING/SPEAKING/ALERT/SLEEP`
  - `SERVO|PAN_TILT|pan|tilt`
  - `SERVO|MOVE|pan|tilt|duration_ms`
  - `ENCODERS` → `ENC|1|session_id|sequence|count0|count1|count2|count3` (this
    command responds with `ENC`, not an ACK)
- Pi sequence numbers start at 1 and stop at 2,147,483,647; the Pi refuses
  further sends rather than reusing an identity. A Pi process restart creates
  a new session ID and resets the sequence. The command identity is
  `(session_id, sequence)`; the ESP32 echoes both in correlated replies and
  does not deduplicate commands.
- All serial frames now carry version 1. STOP executes when parsed from the
  serial input stream. It has no special parser-level priority or duplicate
  suppression. ESP32 obstacle checks and the Pi watchdog independently stop
  the motors.
- The integrated motor driver is TA6586. `EYES` and `SERVO` are the
  supported commands; `EXPRESSION` and `EAR` are legacy documentation and
  must not be sent.
- The Pi heartbeat is sent every 100 ms and the ESP32 watchdog is 500 ms.
  The Pi's serial reconnect behavior is separate from that hardware watchdog.
- Sensor telemetry is sent every 50 ms as
  `TEL|1|0|SENSORS|TOF_L|value|TOF_C|value|TOF_R|value|US_REAR|value`;
  distance values are millimetres, with `FAR` for fresh out-of-range and
  `NA` for unavailable/stale readings.
- Asynchronous frames include `EVENT|1|0|READY`,
  `EVENT|1|0|BLOCKED|OBSTACLE`, `EVENT|1|0|STOP|OBSTACLE`, and
  `FAULT|1|0|subsystem|detail`.

## Remaining Phase 2 decisions

- The protocol document now reflects version 1 of the integrated command/
  reply framing. Legacy `EXPRESSION` and `EAR` commands remain unsupported.
- The API reports Pi dispatch immediately and forwards final ACK/error/
  timeout results using the agreed `command_result` schema. Lookup is
  available by command ID. Flutter integration remains for Vishal and
  Niteshvar to coordinate.
- Versioned Pi command framing and session-aware ACK matching are implemented
  on the Pi side. The integrated ESP32 parser has been updated in the same
  versioned protocol commit; the framing/session tests must pass after pulling
  before the change is accepted.
- The version-1 wire format has no legacy command compatibility: old
  unversioned Pi frames are ignored.
- STOP latch and selected/paused mode behavior still need the owners' decision
  before changing API semantics.

## Scope notes

- Do not implement resume, mode, or emergency-stop routes until their
  mobile-facing contract is agreed with Niteshvar.
- Do not weaken ESP32 safety or treat stale/missing sensor values as clear.
- Physical robot verification belongs to Tharun. Backend software and API
  integration belong to Vishal.
- Update this document and the API contract when the owners resolve a gap.
