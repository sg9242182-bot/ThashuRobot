# THASHU Pi ↔ ESP32 Serial Protocol

**Status:** Current integrated firmware behavior, confirmed by the ESP32 owner  
**Transport:** USB CDC serial at 115200 baud  
**Wire protocol version:** None is carried in command or response frames. Versioning/compatibility policy remains an open Phase 2 decision.

## Source of truth and ownership

This document describes the integrated firmware under `ESP32Firmware/ThashuController` and the Pi transport under `thashu/hardware`. The separate `ESP32Firmware/communicationmanager/communication_manager.cpp` copy is stale in some behavior. The old `command_parser.cpp` is not used by the integrated sketch. Do not use those files to infer the live contract.

The Pi owns high-level behavior and sends semantic commands. The integrated ESP32 firmware owns motor actuation through TA6586 motor drivers, hardware safety checks, sensors, displays, and servo actuation. Flutter communicates with the Pi API, never directly with this serial protocol.

## Framing and parser behavior

Frames are ASCII, terminated by line feed. The ESP32 also accepts CRLF by stripping a trailing carriage return before parsing.

Pi to ESP32 command format:

```text
CMD|sequence|payload...\n
```

The integrated ESP32 accumulates partial serial reads until a newline, using a 128-byte command buffer. An overlong frame is discarded through its next newline. The Pi's serial reader uses newline-delimited reads with a 200 ms read timeout.

A line that is not a valid `CMD` frame, or whose sequence is missing, non-numeric, or negative, is silently ignored; it receives no ACK. Unknown but otherwise well-formed command payloads receive `ACK|sequence|ERROR|INVALID_COMMAND`.

There is no protocol-version field in the wire format. The team must decide whether to add version negotiation or explicitly maintain this unversioned format with a compatibility policy before declaring Phase 2 complete.

## Sequence numbers and command correlation

The Pi allocates positive sequence numbers, starting at 1, and increments for each sent frame. It wraps to 1 after 2,147,483,647. The ESP32 echoes the sequence in ACK and ENCODERS responses. The integrated firmware does not deduplicate commands; repeated frames are processed again.

The Pi must correlate replies by sequence and track ACK timeouts. The current Pi API also assigns a UUID `command_id` to a mobile move/stop request and internally associates it with the serial sequence. A Pi process restart begins the local sequence counter at 1 again; the ESP32 has no duplicate protection across that restart.

## Supported commands

| Payload | Behavior and response |
|---|---|
| `STOP` | Stops the motors when parsed, sets active motion to STOPPED, then replies `ACK|sequence|OK`. |
| `HEARTBEAT` | Updates the ESP32 Pi-frame watchdog and replies `ACK|sequence|ALIVE`. |
| `MOTOR|FORWARD|speed` | Forward motion, speed 0–255. |
| `MOTOR|BACKWARD|speed` | Reverse motion, speed 0–255. |
| `MOTOR|LEFT|speed` | Left turn, speed 0–255. |
| `MOTOR|RIGHT|speed` | Right turn, speed 0–255. |
| `EYES|expression` | Supported expressions: `IDLE`, `HAPPY`, `THINKING`, `LISTENING`, `SPEAKING`, `ALERT`, `SLEEP`. |
| `SERVO|PAN_TILT|pan|tilt` | Sets pan and tilt angles, each 0–180 degrees. |
| `SERVO|MOVE|pan|tilt|duration_ms` | Moves to the requested angles over 50–2000 ms. |
| `ENCODERS` | Returns encoder counts; this command replies with `ENC`, not `ACK`. |

Examples:

```text
CMD|104|MOTOR|FORWARD|180
CMD|105|STOP
CMD|106|EYES|HAPPY
CMD|107|SERVO|PAN_TILT|90|90
CMD|108|HEARTBEAT
CMD|109|ENCODERS
```

Motor, EYES, and SERVO commands normally reply `ACK|sequence|OK` when accepted by the firmware. This ACK confirms firmware handling of the command; it does not confirm that movement has completed.

For `ENCODERS`, the response is:

```text
ENC|sequence|count0|count1|count2|count3
```

## Acknowledgements and errors

ACK frames use:

```text
ACK|sequence|OK
ACK|sequence|ALIVE
ACK|sequence|ERROR|error_code
```

Implemented error codes include:

- `INVALID_COMMAND` — unsupported command payload.
- `INVALID_ARGUMENT` — invalid direction or eye expression.
- `OUT_OF_RANGE` — motor speed, servo angle, or servo duration is outside allowed bounds.
- `OBSTACLE` — ESP32 safety checks reject motion due to an obstacle.
- `SENSOR_NOT_READY` — ESP32 safety checks reject motion because required sensor data is not ready.

The Pi transport tracks ACKs by sequence. The API returns `dispatched` immediately after the Pi writes the command, then reports `acknowledged`, `safety_error`, or `timed_out` through a WebSocket `command_result` event and the command-result lookup route. A timeout means no matching ACK arrived before the configured wait ended; it does not establish whether the ESP32 acted.

## STOP and safety behavior

STOP is not given parser-level priority. It executes when the ESP32 reads it from the serial input stream. Commands are processed in stream order, and there is no duplicate suppression. Do not document STOP as preempting bytes or commands already ahead of it.

ESP32 obstacle checks can stop/reject motion independently. The Pi-side watchdog also stops motors independently according to its runtime policy. The Pi heartbeat runs every 100 ms; the ESP32 communication watchdog is 500 ms and stops the motors if Pi communication expires. These mechanisms are independent. Serial reconnect after missing inbound data is transport recovery, not the Pi motion watchdog. The ESP32 remains the final hardware safety authority.

## Telemetry, events, and faults

The ESP32 emits sensor telemetry every 50 ms:

```text
TEL|0|SENSORS|TOF_L|value|TOF_C|value|TOF_R|value|US_REAR|value
```

Distance values are millimetres. `FAR` represents a fresh out-of-range reading; `NA` represents unavailable, invalid, or stale sensor data. The Pi timestamps telemetry when it receives the line; the serial telemetry frame itself has no timestamp.

Known asynchronous frames include:

```text
EVENT|0|READY
EVENT|0|BLOCKED|OBSTACLE
EVENT|0|STOP|OBSTACLE
FAULT|0|subsystem|detail
INFO|MOTOR_MAP|...
```

The ESP32 emits `EVENT|0|READY` during communication-manager startup. Serial port open alone does not prove readiness. The motor-map INFO line identifies M0–M3 layout and is informational.

## Pi transport timing and reconnect behavior

- Pi heartbeat interval: 100 ms.
- ESP32 Pi-communication watchdog: 500 ms.
- ESP32 sensor telemetry interval: 50 ms.
- Pi serial reconnect retry interval: 1 second while disconnected.
- Pi considers the serial receive stream silent after 2 seconds without inbound data and disconnects/reconnects the transport.

Pi reconnect behavior does not replace the ESP32 watchdog. Do not assume a successful serial write means the ESP32 received, accepted, or completed a command.

## Remaining Phase 2 work

- Agree the protocol-version/compatibility policy; the current wire format has no version field.
- Decide whether restarting the Pi may reuse sequence numbers, or whether Pi sequence allocation must persist/change so IDs remain unique across restarts.
- Shared vectors are in `testdata/pi_esp32_protocol_vectors.csv`; the Pi-side serializer test is `thashu/tests/test_gpio_protocol.py`. It checks the exact outbound frames and sequence wrap.
- The integrated ESP32 has no test harness on this branch to consume the shared fixture. Add/agree firmware-side parser coverage for valid, invalid, partial, overlong, and unknown frames, plus timeout/reconnect behavior.
- Record cross-owner or physical hardware verification with Tharun. Do not infer it from API unit tests.

## Phase boundary

This serial protocol carries motor, eye, servo, encoder, sensor, readiness, event, and fault information only. LLM, voice, camera frames, face recognition, memory, semantic places, and navigation goals remain Pi-side responsibilities.
