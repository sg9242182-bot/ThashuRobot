# Thashu Phase 1 — Pi ↔ ESP32 Hardware Protocol

**Version:** 1.0  
**Status:** Frozen for Phase 1 implementation  
**Transport:** USB CDC serial  
**Baud:** 115200

## 1. Ownership

### Raspberry Pi
- High-level movement decisions
- AI, vision, voice, memory and behavior
- Semantic eye/expression requests
- No direct GPIO/pin knowledge

### ESP32
- Motor actuation through 2× DRV8833
- Hardware STOP and watchdog
- ToF/ultrasonic acquisition
- OLED rendering
- Ear-servo control
- Hardware-level validation/fault handling

## 2. Timing

- Pi heartbeat: **100 ms** (10 Hz)
- ESP32 Pi-communication watchdog: **500 ms**
- Sensor telemetry target: **20 Hz**
- Motor control model: **continuous/current-command**

The watchdog is enforced by the ESP32. Pi-side reconnect logic is not a substitute for hardware safety.

## 3. Frame format

All frames are ASCII and newline terminated:

```text
<CLASS>|<SEQUENCE>|<FIELD>|<FIELD>...\n
```

Pi commands use `CMD`.

Examples:

```text
CMD|104|MOTOR|FORWARD|180
CMD|105|STOP
CMD|106|EYES|HAPPY
CMD|107|SERVO|PAN_TILT|90|90
CMD|108|HEARTBEAT
```

## 4. Message classes

### Pi → ESP32

- `CMD` — command

### ESP32 → Pi

- `ACK` — command acknowledgement
- `TEL` — periodic telemetry
- `EVENT` — asynchronous hardware event
- `FAULT` — abnormal hardware condition

## 5. Sequence numbers

- Pi commands receive monotonically increasing sequence numbers.
- Sequence `0` is reserved for non-correlated messages.
- Sequence numbers may restart after a Pi transport restart.
- ESP32 may use the sequence number to detect duplicate commands.

## 6. Motor commands

```text
CMD|N|MOTOR|FORWARD|0-255
CMD|N|MOTOR|BACKWARD|0-255
CMD|N|MOTOR|LEFT|0-255
CMD|N|MOTOR|RIGHT|0-255
CMD|N|STOP
```

The ESP32 owns the actual PWM/GPIO mapping.

`STOP` is safety-critical and has higher processing priority than normal movement or expression commands.

## 7. Heartbeat

Pi sends:

```text
CMD|N|HEARTBEAT
```

ESP32 acknowledges:

```text
ACK|N|ALIVE
```

If the ESP32 does not receive valid Pi communication for 500 ms, it must enter its safe motor state.

## 8. Eye commands

Pi sends semantic expressions:

```text
CMD|N|EYES|IDLE
CMD|N|EYES|HAPPY
CMD|N|EYES|LISTENING
CMD|N|EYES|THINKING
CMD|N|EYES|SPEAKING
CMD|N|EYES|ALERT
CMD|N|EYES|SLEEP
```

The ESP32 owns OLED addresses, drawing and animation.

## 9. Ear commands

Normal runtime behavior should prefer semantic expressions. Direct servo commands are retained for hardware bring-up:

```text
CMD|N|EXPRESSION|HAPPY
CMD|N|EXPRESSION|LISTENING
CMD|N|EXPRESSION|ALERT
CMD|N|EAR|LEFT|ANGLE
CMD|N|EAR|RIGHT|ANGLE
```

The ESP32 clamps servo angles to configured mechanical limits.

## 10. Existing pan/tilt servo

The existing tracking abstraction uses:

```text
CMD|N|SERVO|PAN_TILT|PAN|TILT
```

The ESP32 owns the actual servo PWM output.

## 11. Sensor telemetry

Telemetry is targeted at 20 Hz and uses millimetres for distance values.

The exact field layout may be extended without changing the ownership model. Invalid sensor data must not be represented ambiguously as a valid zero-distance measurement.

Example conceptual message:

```text
TEL|0|SENSORS|TOF_L|420|TOF_C|385|TOF_R|510|US_REAR|730
```

## 12. Faults and events

Examples:

```text
FAULT|0|MOTOR|DRIVER
FAULT|0|SENSOR|TOF_L
FAULT|0|WATCHDOG|PI_TIMEOUT

EVENT|0|BOOT
EVENT|0|READY
EVENT|0|STOPPED
EVENT|0|OBSTACLE
EVENT|0|SENSOR_RECOVERED
```

## 13. Acknowledgements

Successful command execution:

```text
ACK|N|OK
```

Examples of command rejection:

```text
ACK|N|ERROR|INVALID_COMMAND
ACK|N|ERROR|INVALID_ARGUMENT
ACK|N|ERROR|OUT_OF_RANGE
ACK|N|ERROR|HARDWARE_FAULT
```

A successful USB write is **not** equivalent to successful hardware execution.

## 14. Startup

ESP32 startup sequence:

1. Initialize hardware.
2. Force motors to STOP.
3. Initialize sensors.
4. Initialize OLEDs.
5. Initialize servos.
6. Start watchdog.
7. Publish `EVENT|0|READY`.

Pi should use the READY event to determine hardware readiness rather than assuming that opening the serial device means the controller is ready.

## 15. Shutdown and failure

Normal shutdown:

```text
Pi → STOP → ESP32 motor stop → Pi closes transport → OS shutdown
```

Pi crash/disconnect:

```text
Pi disappears → ESP32 watchdog expires → motors STOP
```

These are independent safety mechanisms.

## 16. Priority

The ESP32 behavioral priority is:

1. Safety / STOP / watchdog / hardware fault
2. Motor commands
3. Sensor processing/telemetry
4. OLED/ear expression

## 17. Phase 1 boundary

This protocol does **not** carry LLM, voice, face-recognition, memory, place-recognition, navigation-goal or camera-frame data. Those remain Pi-side responsibilities.
