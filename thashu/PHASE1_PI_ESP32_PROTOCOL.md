# THASHU Pi ↔ ESP32 Serial Protocol

**Protocol version:** 1  
**Status:** Version 1 command/reply format confirmed by the ESP32 owner  
**Transport:** USB CDC serial at 115200 baud

## Source of truth and ownership

This document describes the integrated firmware under `ESP32Firmware/ThashuController` and the Pi transport under `thashu/hardware`. The separate `ESP32Firmware/communicationmanager/communication_manager.cpp` copy is stale in some behavior. The old `command_parser.cpp` is not used by the integrated sketch. Do not infer the live contract from those files.

The Pi owns high-level behavior and sends semantic commands. The integrated ESP32 firmware owns motor actuation through TA6586 motor drivers, hardware safety checks, sensors, displays, and servo actuation. Flutter communicates with the Pi API, never directly with this serial protocol.

## Version 1 frame formats

All protocol frames are ASCII and newline terminated. The version field follows the message class. Debug-only `DBG` lines are console diagnostics, not protocol frames.

Pi to ESP32 commands:

```text
CMD|1|<session_id>|<sequence>|<payload...>
```

ESP32 replies correlated to a command:

```text
ACK|1|<session_id>|<sequence>|<result...>
ENC|1|<session_id>|<sequence>|<count0>|<count1>|<count2>|<count3>
```

The Pi generates a new 32-character lowercase hexadecimal UUID session ID at process startup. Sequence numbers begin at 1 and increment for every command through 2,147,483,647. The Pi does not wrap within a session; it refuses further sends at exhaustion. Restarting the Pi creates a new session ID and starts the sequence at 1. The unique command identity is the pair `(session_id, sequence)`. The ESP32 echoes both values in `ACK` and `ENC` responses. It does not deduplicate commands.

Unsolicited telemetry, event, and fault frames carry version 1 and reserved sequence 0. INFO frames carry the version but no sequence:

```text
TEL|1|0|SENSORS|TOF_L|value|TOF_C|value|TOF_R|value|US_REAR|value
EVENT|1|0|READY
FAULT|1|0|subsystem|detail
INFO|1|MOTOR_MAP|...
```

Legacy unversioned command frames are not accepted by the integrated parser. A command with a well-formed session and sequence but unsupported version receives `ACK|1|<session_id>|<sequence>|ERROR|UNSUPPORTED_VERSION`. A line that cannot be safely correlated (bad class, missing fields, malformed version/session/sequence) is ignored without an ACK.

## Framing and parser behavior

The ESP32 accumulates partial serial reads until a newline in a 128-byte command buffer. CRLF is accepted by stripping the trailing carriage return. An overlong frame is discarded through its next newline. The Pi's serial reader uses newline-delimited reads with a 200 ms timeout.

The Pi accepts an `ACK` for command tracking only when the frame version is 1 and the session ID matches its current process session. A delayed ACK from an earlier Pi session cannot complete a new command with the same sequence number. Heartbeat `ALIVE` replies are not exposed as ordinary command results.

## Supported command payloads

| Payload after the version/session/sequence fields | Behavior and response |
|---|---|
| `STOP` | Stops motors when parsed, sets active motion to STOPPED, and replies `ACK|1|session|sequence|OK`. |
| `HEARTBEAT` | Refreshes the ESP32 communication watchdog and replies `ACK|1|session|sequence|ALIVE`. |
| `MOTOR|FORWARD|speed` | Forward motion; speed 0–255. |
| `MOTOR|BACKWARD|speed` | Reverse motion; speed 0–255. |
| `MOTOR|LEFT|speed` | Left turn; speed 0–255. |
| `MOTOR|RIGHT|speed` | Right turn; speed 0–255. |
| `EYES|expression` | `IDLE`, `HAPPY`, `THINKING`, `LISTENING`, `SPEAKING`, `ALERT`, `SLEEP`. |
| `SERVO|PAN_TILT|pan|tilt` | Pan and tilt each 0–180 degrees. |
| `SERVO|MOVE|pan|tilt|duration_ms` | Pan and tilt 0–180 degrees; duration 50–2000 ms. |
| `ENCODERS` | Returns encoder counts with `ENC`, not `ACK`. |

Examples:

```text
CMD|1|0123456789abcdef0123456789abcdef|1|STOP
CMD|1|0123456789abcdef0123456789abcdef|2|MOTOR|FORWARD|180
CMD|1|0123456789abcdef0123456789abcdef|3|EYES|HAPPY
CMD|1|0123456789abcdef0123456789abcdef|4|SERVO|PAN_TILT|90|90
CMD|1|0123456789abcdef0123456789abcdef|5|HEARTBEAT
CMD|1|0123456789abcdef0123456789abcdef|6|ENCODERS
```

Normal accepted commands reply `ACK|1|session_id|sequence|OK`; safety or validation rejections reply with `ERROR|error_code`. ACK means the firmware handled or rejected the command, not that movement completed.

Implemented error codes include `INVALID_COMMAND`, `INVALID_ARGUMENT`, `OUT_OF_RANGE`, `OBSTACLE`, `SENSOR_NOT_READY`, and `UNSUPPORTED_VERSION`.

## STOP and safety behavior

STOP has no parser-level priority. It executes when parsed from the serial input stream. Commands are processed in stream order, and there is no duplicate suppression. ESP32 obstacle checks can stop/reject motion independently. The Pi-side watchdog also stops motors independently according to its runtime policy.

The Pi heartbeat runs every 100 ms. The ESP32 communication watchdog is 500 ms and stops motors if Pi communication expires. These mechanisms are independent. Serial reconnect is transport recovery, not the Pi motion watchdog. The ESP32 remains the final hardware safety authority.

## Telemetry, events, and reconnect behavior

Sensor telemetry is emitted every 50 ms. Distances are millimetres; `FAR` means fresh/out-of-range and `NA` means unavailable, invalid, or stale. The serial telemetry frame has no timestamp; the Pi timestamps it on receipt.

Known unsolicited version-1 frames include `EVENT|1|0|BOOT`, `EVENT|1|0|READY`, `EVENT|1|0|BLOCKED|OBSTACLE`, `EVENT|1|0|STOP|OBSTACLE`, and `FAULT|1|0|subsystem|detail`. Startup also emits a versioned `INFO|1|MOTOR_MAP|...` line.

The Pi retries serial connection every 1 second while disconnected. It disconnects/reconnects after 2 seconds without inbound serial data. The ESP32 watchdog remains active independently.

## Test vectors and remaining validation

Shared command/reply vectors are in `testdata/pi_esp32_protocol_vectors.csv`. The Pi framing and session-correlation tests are in `thashu/tests/test_gpio_protocol.py`; run them from the repository root with:

```powershell
python -m unittest thashu.tests.test_gpio_protocol
```

The fixture is language-neutral. The integrated ESP32 has no test harness on this branch to consume it yet. Firmware-side parser coverage for partial, overlong, malformed, and unsupported-version frames, plus physical verification, remains with the ESP32 owner.

## Phase boundary

The serial protocol carries motor, eye, servo, encoder, sensor, readiness, event, and fault information only. LLM, voice, camera frames, face recognition, memory, semantic places, and navigation goals remain Pi-side responsibilities.
