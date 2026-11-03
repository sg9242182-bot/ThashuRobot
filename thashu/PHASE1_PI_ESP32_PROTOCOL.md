# THASHU Pi ↔ ESP32 Serial Protocol

**Contract label:** deployed protocol v0
**Status:** Confirmed by the ESP32 owner; command and ACK frames have no explicit version field
**Transport:** USB CDC serial at 115200 baud

## Ownership and source of truth

The integrated firmware under `ESP32Firmware/ThashuController` and the Pi
transport under `thashu/hardware` define this contract. The separate
`ESP32Firmware/communicationmanager/communication_manager.cpp` copy and old
`command_parser.cpp` are stale and are not the integrated implementation.

The Pi owns high-level behavior and sends semantic commands. The ESP32 owns
motor actuation through TA6586 drivers, sensors, hardware safety, eyes, and
servo actuation. Flutter communicates with the Pi API, never directly with
this serial protocol.

## Frame formats

Frames are ASCII and newline terminated. Commands, ACKs, and encoder replies
use these forms:

```text
CMD|<sequence>|<payload...>
ACK|<sequence>|<result...>
ENC|<sequence>|<count0>|<count1>|<count2>|<count3>
```

Unsolicited frames use the deployed forms below. `TEL`, `EVENT`, and `FAULT`
include the literal `0`; `INFO` does not:

```text
TEL|0|SENSORS|TOF_L|value|TOF_C|value|TOF_R|value|US_REAR|value
EVENT|0|READY
EVENT|0|BLOCKED|OBSTACLE
EVENT|0|STOP|OBSTACLE
FAULT|0|subsystem|detail
INFO|MOTOR_MAP|...
```

The protocol is called v0 for documentation, but **CMD and ACK frames do not
carry a protocol-version field or Pi session ID**. Do not send the incompatible
v1 form `CMD|version|session_id|sequence|payload`.

The Pi starts sequence numbers at 1 and increments them through
2,147,483,647. It refuses to send more commands instead of wrapping. After a
Pi restart, numbering starts at 1 again. ACK matching uses only the sequence
number. Therefore a delayed ACK from before a restart can be mistaken for a
new ACK with the same sequence, and the ESP32 does not deduplicate commands.
This is a known limitation of v0, not a guarantee of session-safe correlation.

## Framing and parsing

The ESP32 accumulates partial serial reads until newline in a 128-byte command
buffer. It accepts CRLF by removing the trailing carriage return and discards
an overlong frame through its next newline. It rejects malformed command
sequences and unknown or invalid command payloads according to the responses
below. Unsupported-version negotiation does not apply because command frames
have no version field.

The Pi also accumulates serial chunks until newline; a serial read timeout does
not end a frame. It accepts at most 128 bytes before newline, removes a
trailing carriage return, and discards oversized frames through the next
newline. A partial frame is cleared when the serial connection changes so
bytes from separate connections are never combined. Its serial read timeout
is 200 ms.

The Pi tracks ACKs by sequence number. It accepts results `OK` and
`ERROR|reason`; `ALIVE` is the heartbeat response and is not treated as an
ordinary command result. The ESP32 parser accepts sequence zero, but the Pi
allocates only positive sequence numbers.

## Supported command payloads

| Payload after the sequence field | Behavior and response |
|---|---|
| `STOP` | Stops motors when parsed, sets active motion to STOPPED, and returns `ACK|sequence|OK`. |
| `HEARTBEAT` | Refreshes the ESP32 watchdog and returns `ACK|sequence|ALIVE`. |
| `MOTOR|FORWARD|speed` | Forward motion; speed 0–255. |
| `MOTOR|BACKWARD|speed` | Reverse motion; speed 0–255. |
| `MOTOR|LEFT|speed` | Left turn; speed 0–255. |
| `MOTOR|RIGHT|speed` | Right turn; speed 0–255. |
| `EYES|expression` | `IDLE`, `HAPPY`, `THINKING`, `LISTENING`, `SPEAKING`, `ALERT`, `SLEEP`. |
| `SERVO|PAN_TILT|pan|tilt` | Pan and tilt each 0–180 degrees. |
| `SERVO|MOVE|pan|tilt|duration_ms` | Pan and tilt 0–180 degrees; duration 50–2000 ms. |
| `ENCODERS` | Returns counts in an `ENC` frame, not an ACK. |

Examples:

```text
CMD|1|STOP
CMD|2|MOTOR|FORWARD|180
CMD|3|EYES|HAPPY
CMD|4|SERVO|PAN_TILT|90|90
CMD|5|HEARTBEAT
CMD|6|ENCODERS
```

Accepted commands return `ACK|sequence|OK`; heartbeat returns `ALIVE`.
Validation and safety rejections use `ERROR|reason`, including
`INVALID_COMMAND`, `INVALID_ARGUMENT`, `OUT_OF_RANGE`, `OBSTACLE`, and
`SENSOR_NOT_READY`.

## Stop, safety, heartbeat, and reconnect

STOP executes when parsed from the serial input stream. It has no parser-level
priority; commands are processed in stream order. ESP32 obstacle checks and
the Pi watchdog independently stop motors. The ESP32 remains the final
hardware safety authority.

The Pi sends a heartbeat every 100 ms. The ESP32 communication watchdog is
500 ms and stops motors if Pi communication expires. Sensor telemetry is
emitted every 50 ms; distances are millimetres, `FAR` means fresh and
out-of-range, and `NA` means unavailable, invalid, or stale. The Pi timestamps
telemetry when received because the wire frame has no timestamp.

The Pi retries serial connection every second while disconnected. It closes
and reconnects after two seconds without inbound serial data. Reconnection
does not add session identity to v0 commands or ACKs.

## Tests and validation status

Shared command/reply vectors are in `testdata/pi_esp32_protocol_vectors.csv`.
Pi framing, ACK, receive-buffer, and reconnect tests are in
`thashu/tests/test_gpio_protocol.py`; run from the repository root:

```powershell
python -m unittest thashu.tests.test_gpio_protocol
```

Tharun reports parser checks passed for HEARTBEAT, STOP, EYES, an invalid EYES
argument, an unknown command, partial frames, and oversized-frame discard and
recovery. Unsupported-version testing does not apply to v0. There is no
standalone ESP32 parser-test harness in the branch; compiling/uploading the
branch-aligned firmware and verifying Pi integration remain open.

## Phase boundary

The serial protocol carries motor, eye, servo, encoder, sensor, readiness,
event, and fault information only. LLM, voice, camera frames, face
recognition, memory, semantic places, and navigation goals remain Pi-side
responsibilities.
