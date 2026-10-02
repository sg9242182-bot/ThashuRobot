# THASHU ESP32 HARDWARE PIN ALLOCATION

**Project:** Thashu — Intelligent Self-Reliant Robot  
**Phase:** Phase 1 — Hardware Abstraction & ESP32 Migration  
**Status:** PROPOSED ENCODER MAP — hardware validation required before checklist sign-off
**MCU:** ESP32-WROOM-32, 38-pin NodeMCU  
**Expansion:** Purple ESP32 38-pin expansion board

## Current hardware

- 4 DC motors
- 2 × Robocraze DRV8833 2-channel motor-driver modules (SKU TIFMC0199; see [product listing](https://robocraze.com/products/drv8833-2-channel-dc-motor-driver))
- 4 × HC-89 interrupt sensors, one per motor (see [product listing](https://robocraze.com/products/hc-89-interrupt-sensor))
- 3 × VL53LDK ToF sensors: front-left, front-center, front-right
- 2 × 0.96-inch OLED displays
- 1 × HC-SR04 rear ultrasonic sensor
- 2 × MG90S servos: camera pan and camera tilt
- Ear servos are NOT part of the current design.

## Baseline and proposed GPIO allocation (proposal pending hardware validation)

| GPIO | Function | Direction | Hardware |
|---:|---|---|---|
| 2 | HC-SR04 TRIG | OUT | HC-SR04 |
| 4 | Front-left ToF X | OUT | VL53LDK |
| 5 | Camera PAN servo signal | OUT | MG90S |
| 13 | DRV8833 #1 IN1 | OUT | Motor driver |
| 14 | DRV8833 #1 IN2 | OUT | Motor driver |
| 15 | Camera TILT servo signal | OUT | MG90S |
| 16 | Front-center ToF X | OUT | VL53LDK |
| 17 | Front-right ToF X | OUT | VL53LDK |
| 18 | DRV8833 #2 IN4 | OUT | Motor driver |
| 19 | DRV8833 #2 IN3 | OUT | Motor driver |
| 21 | I2C SDA | I/O | 3 ToF + 2 OLED |
| 22 | I2C SCL | I/O | 3 ToF + 2 OLED |
| 23 | DRV8833 #2 IN2 | OUT | Motor driver |
| 25 | DRV8833 #2 IN1 | OUT | Motor driver |
| 26 | DRV8833 #1 IN4 | OUT | Motor driver |
| 27 | DRV8833 #1 IN3 | OUT | Motor driver |
| 12 | HC-SR04 ECHO (proposed; retain existing voltage divider) | IN | HC-SR04 |
| 33 | Encoder 1 DO (proposed) | IN/interrupt | HC-89 on motor 1 |
| 35 | Encoder 2 DO (proposed) | IN/interrupt | HC-89 on motor 2 |
| 36 | Encoder 3 DO (proposed) | IN/interrupt | HC-89 on motor 3 |
| 39 | Encoder 4 DO (proposed) | IN/interrupt | HC-89 on motor 4 |
| 32 | Shared driver EEP/nSLEEP (proposed) | OUT | Both DRV8833 modules |
| 34 | Shared driver ULT/nFAULT (proposed) | IN | Both DRV8833 modules; 3.3 V pull-up required |

## I2C bus

GPIO21 and GPIO22 are shared by all five I2C devices:

- Left OLED
- Right OLED
- Left ToF
- Center ToF
- Right ToF

The three ToF X lines provide independent startup/address-management control because the sensors initially use the same default I2C address.

## Encoder and shared-driver-pin review — 2026-10-02

The four HC-89 sensors provide one digital `DO` pulse signal each. Each signal needs its own ESP32 input; `AO` is not used for pulse counting. These are single-channel pulse sensors, so they count rotation but do not independently report direction. Power each HC-89 from 3.3 V for ESP32 logic compatibility, as allowed by the product listing.

The proposed driver-pin sharing and encoder assignment require bench validation before wiring is treated as final:

- Both driver `EEP` / `nSLEEP` inputs can share one ESP32 output if the installed modules expose those pins as logic inputs. The proposed shared output is GPIO32, which would release GPIO33.
- Both `ULT` / `nFAULT` pins can share one ESP32 input only if the installed modules expose the DRV8833 active-low, open-drain fault outputs directly. The combined signal requires a pull-up to 3.3 V and loses per-driver fault identification. The proposed input is GPIO34, which would release GPIO35.
- Robocraze's accessible listing identifies the DRV8833 module but does not document the board-level `EEP` / `ULT` circuitry or pull-up voltage. Confirm these module connections before tying the signals together.

The proposed complete map is:

- Tie both `EEP` / `nSLEEP` module inputs to GPIO32. Keep GPIO33 for encoder 1.
- Tie both `ULT` / `nFAULT` module outputs to GPIO34 only after verifying the module pull-up is absent or to 3.3 V. Add one external pull-up to 3.3 V if needed. Keep GPIO35 for encoder 2.
- Encoder DO signals: motor 1 → GPIO33, motor 2 → GPIO35, motor 3 → GPIO36, motor 4 → GPIO39. Power the HC-89 boards at 3.3 V and connect grounds together.
- Move HC-SR04 ECHO from GPIO36 to GPIO12, retaining the existing 5 V-to-3.3 V divider. The HC-SR04 ECHO signal must be low while the ESP32 samples boot straps; verify cold boots with the sensor connected before accepting this assignment. GPIO12 defaults to a strap-selected supply-voltage function at reset, so a high ECHO during reset can prevent normal boot.

HC-89 sensors provide one pulse output each. They count rotation but do not report direction, and the listing gives no pulses-per-revolution value. Determine effective counts per wheel revolution experimentally before using encoder counts for distance or closed-loop control.

## Freeze rule

The baseline assignments for existing functions remain unchanged except the proposed HC-SR04 ECHO move to GPIO12. The map above is the proposed wiring plan; do not connect shared fault outputs until the board pull-up voltage is checked. Do not close the mapping checklist item until the pulse-count, fault, sleep, and repeated cold-boot checks below pass. Firmware pin definitions must be updated to this map before the physical rewiring is used for powered motor operation.

## DRV8833 driver 1

- IN1 → GPIO13
- IN2 → GPIO14
- IN3 → GPIO27
- IN4 → GPIO26
- ULT → GPIO34 (shared proposed input; bench validation pending)
- EEP → GPIO32 (shared proposed output; bench validation pending)
- OUT1/OUT2 → motor channel 1
- OUT3/OUT4 → motor channel 2

## DRV8833 driver 2

- IN1 → GPIO25
- IN2 → GPIO23
- IN3 → GPIO19
- IN4 → GPIO18
- ULT → GPIO34 (shared proposed input; bench validation pending)
- EEP → GPIO32 (shared proposed output; bench validation pending)
- OUT1/OUT2 → motor channel 1
- OUT3/OUT4 → motor channel 2

## Camera pan/tilt

- GPIO5 → PAN MG90S signal
- GPIO15 → TILT MG90S signal

Servo power is separate from ESP32 GPIO power, with a common ground.

Servo control will use ESP32 hardware PWM with software rate/position limiting for smooth movement.

## HC-SR04

- GPIO2 → TRIG
- GPIO12 → ECHO (proposed reassignment; existing voltage divider remains)
- Existing voltage divider remains on ECHO before the ESP32 input.

## Encoder and driver-sharing bench acceptance

- [ ] Open the USB serial monitor at 115200 baud with the Pi disconnected. Send `CMD|1|ENCODERS` followed by a newline; expect `ENC|1|0|0|0|0` after boot. Rotate only wheel 1 by hand and repeat with sequence 2; only the first count should increase. Repeat for wheels 2–4. Counts use rising edges, so calibrate counts per wheel revolution and do not infer direction.
- [ ] With motor power disconnected, confirm each HC-89 DO switches between valid ESP32 logic-low and logic-high as the encoder wheel slots pass; verify the signal never exceeds 3.3 V when powered at 3.3 V.
- [ ] Connect one sensor at a time to its proposed GPIO and verify one counter increments for that wheel only. Rotate slowly by hand and compare counts per full wheel revolution; repeat in both directions (counts should increase in both directions because these are single-channel sensors).
- [ ] With motor power disconnected, measure each module ULT/nFAULT pin and its pull-up rail. Confirm both are open-drain-compatible and no pin is pulled above 3.3 V before combining them on GPIO34.
- [ ] Verify each EEP/nSLEEP input is a logic input and both modules enter sleep when GPIO32 is low and wake when it is high.
- [ ] With motors disconnected and HC-SR04 ECHO moved to GPIO12 through the existing divider, perform at least 10 power-cycle/cold-boot trials; every boot must start normally. Confirm GPIO12 is low at reset and ECHO measurements still work after startup.
- [ ] Run each wheel separately at low duty, confirm the matching encoder counter changes, test STOP, and confirm all motors remain stopped after STOP and on a ToF safety stop.
- [ ] Repeat a short all-wheel low-speed run; check for missed counts, false counts from motor noise, driver faults, and ESP32 resets.

## Pin safety

The allocation avoids GPIO6–11 (flash-connected) and GPIO1/3 (primary serial/programming). GPIO34/35 are used only as inputs.

GPIO5 is used for PAN after successful functional and cold-boot validation. GPIO15 is used for TILT. GPIO2 is used for HC-SR04 TRIG. GPIO34/35/36/39 are input-only and suitable for encoder/fault/echo use. GPIO12 is a strap pin and is proposed for ECHO only because ECHO should remain low until triggered; repeated cold-boot validation is mandatory.

## Servo validation record

### PAN — GPIO5
- [x] Movement test passed on GPIO5
- [x] Slow movement passed
- [x] Fixed-position test stable
- [x] No fixed-position jitter observed
- [x] Cold-boot test passed on GPIO5

GPIO2 was the previous PAN signal and failed; it is now reassigned to HC-SR04 TRIG.

### TILT — GPIO15
- [x] Functional test passed
- [x] Fixed-position test passed
- [x] Movement test passed
- [x] Repeated cold-boot test passed
