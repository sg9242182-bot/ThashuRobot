# THASHU ESP32 HARDWARE PIN ALLOCATION

**Project:** Thashu — Intelligent Self-Reliant Robot  
**Phase:** Phase 1 — Hardware Abstraction & ESP32 Migration  
**Status:** TA6586 board header identified from the user's photo; GPIO12 tilt-servo reset test and four-encoder map validation remain. New motor-driver GPIO mapping is documented but firmware adaptation and physical tests remain pending.
**MCU:** ESP32-WROOM-32, 38-pin NodeMCU  
**Expansion:** Purple ESP32 38-pin expansion board

## Current hardware

- 4 DC motors
- 2 × Makerbazar TA6586 dual-channel motor-driver modules; each drives two motors independently (see [product listing](https://makerbazar.in/products/1-3v-14v-5a-dual-dc-motor-drive-module)). User-provided board photo shows header labels GND, 3V3, D0–D3, VT.
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
| 13 | TA6586 module 1 D0 (motor channel A input 1) | OUT | Motor driver |
| 14 | TA6586 module 1 D1 (motor channel A input 2) | OUT | Motor driver |
| 15 | Encoder 1 DO (proposed; boot-log strap only) | IN/interrupt | HC-89 on motor 4 |
| 16 | Front-center ToF X | OUT | VL53LDK |
| 17 | Front-right ToF X | OUT | VL53LDK |
| 18 | TA6586 module 2 D3 (motor channel B input 2) | OUT | Motor driver |
| 19 | TA6586 module 2 D2 (motor channel B input 1) | OUT | Motor driver |
| 21 | I2C SDA | I/O | 3 ToF + 2 OLED |
| 22 | I2C SCL | I/O | 3 ToF + 2 OLED |
| 23 | TA6586 module 2 D1 (motor channel A input 2) | OUT | Motor driver |
| 25 | TA6586 module 2 D0 (motor channel A input 1) | OUT | Motor driver |
| 26 | TA6586 module 1 D3 (motor channel B input 2) | OUT | Motor driver |
| 27 | TA6586 module 1 D2 (motor channel B input 1) | OUT | Motor driver |
| 12 | Camera TILT servo signal (provisional; cold-boot validation required) | OUT after startup | MG90S |
| 33 | Encoder 4 DO (provisional) | IN/interrupt | HC-89 on motor 1 |
| 35 | Encoder 2 DO (proposed) | IN/interrupt | HC-89 on motor 2 |
| 36 | HC-SR04 ECHO (restored baseline; retain divider) | IN | HC-SR04 |
| 39 | Encoder 3 DO (proposed) | IN/interrupt | HC-89 on motor 3 |
| 32 | Unassigned by revised TA6586 wiring map | — | Available GPIO |
| 34 | Unassigned by revised TA6586 wiring map | — | Available GPIO |

## I2C bus

GPIO21 and GPIO22 are shared by all five I2C devices:

- Left OLED
- Right OLED
- Left ToF
- Center ToF
- Right ToF

The three ToF X lines provide independent startup/address-management control because the sensors initially use the same default I2C address.

## TA6586 board interface and motor GPIO mapping — 2026-10-22

The user's board photo shows the seven-pin header in this order: GND, 3V3, D0, D1, D2, D3, VT. The listing describes a dual H-bridge for two independently controlled motors. The TA6586 datasheet specifies two logic inputs per motor bridge, a 3.0–14 V operating range, and a 2.2 V minimum high input at the chip. That supports 3.3 V ESP32 logic at chip level; the board implementation still needs bench validation. The vendor's “5 A per channel” figure is not a verified continuous-current/thermal rating.

Proposed channel pairing and assignments (motor direction polarity is to be confirmed by a brief low-speed test):

Direction calibration (2026-10-23): User reports isolated positive-drive testing showed M0 moves in the intended chassis-forward direction, while M1, M2, and M3 run in reverse under the same positive command. MotorManager now reverses control polarity for M1–M3 in software; recheck all four wheel directions after uploading before floor testing.

Encoder speed matching (2026-10-23): MotorManager now samples encoder pulse rates every 250 ms and applies bounded PID corrections (up to ±35% of requested PWM) to simultaneously driven motors, using their group's measured mean pulse rate as the shared target. M0–M3 map to encoder IDs 4, 2, 3, 1 respectively; this preserves the existing encoder wiring. The requested speed remains a base PWM command, and a single motor by itself has no peer reference, so it remains open-loop. HC-89 pulses per wheel revolution and PID gains are not calibrated; this is relative speed matching, not verified RPM regulation. Compile and test with all wheels raised before floor driving.

| Module/channel | Header input 1 | Header input 2 | Motor |
|---|---|---|---|
| Module 1, A | D0 → GPIO13 | D1 → GPIO14 | Motor 1 |
| Module 1, B | D2 → GPIO27 | D3 → GPIO26 | Motor 2 |
| Module 2, A | D0 → GPIO25 | D1 → GPIO23 | Motor 3 |
| Module 2, B | D2 → GPIO19 | D3 → GPIO18 | Motor 4 |

Use the module's printed motor-supply polarity and motor-output terminals. The photo does not make terminal polarity text legible, so do not infer screw-terminal polarity from terminal color or position. Keep the board's 3V3 and VT pins unconnected for this ESP32 setup; power the ESP32 independently and connect ESP32 GND to both driver-board GND pins. Power the motors from a regulated rail within the motors' 3–6 V rating; do not connect the 3S battery directly to these motors. Although the listing claims 5 A/channel, thermal/current capability of these specific assembled boards has not been verified.

The TA6586 truth table supports PWM on one input with the paired input low for one direction, and the opposite input for reverse. Both inputs low leave the outputs open/coasting; both high invoke braking. Verify actual motor direction at low speed before fixing wheel orientation.

These TA6586 boards do not expose the DRV8833 EEP/nSLEEP and ULT/nFAULT pins assumed by the old allocation. GPIO32 and GPIO34 are therefore not connected to these boards. The existing firmware still contains DRV8833-era sleep/fault assumptions; adapt and compile that code before the integrated motor subsystem is considered ready. The TA6586 chip includes internal thermal/overcurrent protection, but this module provides no documented fault-status output to the ESP32.

The proposed GPIO pairing is based on the user-provided board photo and the TA6586 datasheet, but remains subject to wiring, low-speed direction, STOP, safety-stop, and cold-boot tests. Do not call it physically validated yet.

The integrated firmware maps encoder IDs 1–4 to GPIO15, GPIO35, GPIO39, and GPIO33 respectively; these sensors are mounted on motors 4, 2, 3, and 1. GPIO36 remains reserved for HC-SR04 ECHO. GPIO15 is a boot strap that controls ROM boot-message output when low; verify the HC-89 output does not prevent application boot. Power HC-89 boards at 3.3 V and connect grounds together. The tilt-servo signal is provisionally moved from GPIO15 to GPIO12 to free GPIO15. GPIO12 is a flash-voltage strap: its use is conditional on confirming it remains low during reset with the servo attached and passing repeated cold boots.

Bench result (2026-10-03): HC-SR04 ECHO on GPIO12 allowed operation only when connected after boot; with ECHO connected during power-on, boot produced serial garbage/repeated output and did not start normally. This is consistent with GPIO12 being sampled high and selecting 1.8 V flash power on this 3.3 V-flash ESP32-WROOM board. Withdraw GPIO12 as an ECHO candidate. Restore HC-SR04 ECHO to GPIO36 through its existing divider for the standalone ultrasonic test. GPIO36's encoder conflict is resolved by moving encoder 3 to GPIO39; encoder 4 is assigned to GPIO15. The GPIO12 tilt-servo reassignment remains provisional pending reset-level and repeated cold-boot tests.

HC-89 sensors provide one pulse output each. They count rotation but do not report direction, and the listing gives no pulses-per-revolution value. Determine effective counts per wheel revolution experimentally before using encoder counts for distance or closed-loop control.

## Freeze rule

Restore the baseline HC-SR04 ECHO assignment at GPIO36. The GPIO12 ECHO proposal is withdrawn after the cold-boot failure. GPIO36 is reserved for HC-SR04 ECHO; the encoder-ID map uses GPIO15/35/39/33 (IDs 1–4, mounted on motors 4/2/3/1). Do not connect any encoder to GPIO36. The candidate four-encoder map is assigned in firmware, but it is not approved as final until encoder pulses, GPIO15 startup behavior, GPIO12 tilt-servo reset behavior, motor-channel directions, STOP/ToF-stop checks, and cold-boot checks pass.

## TA6586 module 1

- D0 → GPIO13; D1 → GPIO14 → Motor 1 channel A input pair
- D2 → GPIO27; D3 → GPIO26 → Motor 2 channel B input pair
- Motor supply → regulated motor rail within the motors' 3–6 V rating, observing printed polarity
- GND → common ESP32/battery ground
- 3V3 and VT → leave unconnected
- Motor output pair A → Motor 1; motor output pair B → Motor 2

## TA6586 module 2

- D0 → GPIO25; D1 → GPIO23 → Motor 3 channel A input pair
- D2 → GPIO19; D3 → GPIO18 → Motor 4 channel B input pair
- Motor supply → same regulated motor rail, observing printed polarity
- GND → common ESP32/battery ground
- 3V3 and VT → leave unconnected
- Motor output pair A → Motor 3; motor output pair B → Motor 4

D0/D1 and D2/D3 are the two input pairs; the direction associated with each motor wire polarity must be confirmed experimentally. Do not wire GPIO32 or GPIO34 to these TA6586 boards.

## Camera pan/tilt

- GPIO5 → PAN MG90S signal
- GPIO12 → TILT MG90S signal (provisional; cold-boot validation required)

Servo power is separate from ESP32 GPIO power, with a common ground.

Servo control will use ESP32 hardware PWM with software rate/position limiting for smooth movement.

## HC-SR04

- GPIO2 → TRIG
- GPIO36 → ECHO (restored baseline; existing voltage divider remains)
- Existing voltage divider remains on ECHO before the ESP32 input.

## Encoder and TA6586 bench acceptance

- [ ] Open the USB serial monitor at 115200 baud with the Pi disconnected. Send CMD|1|ENCODERS followed by a newline; expect ENC|1|0|0|0|0 after boot. Rotate the wheel on motor 4 by hand and repeat with sequence 2; only encoder count 1 should increase. Then rotate motors 2, 3, and 1 in turn; only counts 2, 3, and 4 should increase respectively. Counts use rising edges, so calibrate counts per wheel revolution and do not infer direction.
- [ ] With motor power disconnected, confirm each HC-89 DO switches between valid ESP32 logic-low and logic-high as the encoder wheel slots pass; verify the signal never exceeds 3.3 V when powered at 3.3 V.
- [ ] Connect one sensor at a time to its proposed GPIO and verify one counter increments for that wheel only. Rotate slowly by hand and compare counts per full wheel revolution; repeat in both directions (counts should increase in both directions because these are single-channel sensors).
- [ ] Before connecting motor outputs, verify board GND continuity, motor-supply polarity against printed markings, and regulated motor voltage within the motors' 3–6 V rating. Leave 3V3 and VT unconnected.
- [ ] With wheels raised and at low PWM, test each TA6586 channel independently: verify D0/D1 control module 1 channel A, D2/D3 module 1 channel B, and the corresponding pairs on module 2. Confirm direction and encoder association; swap motor leads or update mapping only after recording the result.
- [ ] Verify STOP makes both inputs in each motor pair low and stops all four motors; verify hardware safety STOP also stops them. Confirm the board does not overheat or reset during brief low-speed tests. The board's advertised 5 A/channel rating is not a continuous thermal validation.
- [ ] With HC-SR04 ECHO on GPIO36 through the existing divider, perform at least 10 cold boots and verify ultrasonic readings. Keep all encoder outputs off GPIO36; GPIO12 must remain disconnected from ECHO.
- [ ] With the tilt servo signal moved to GPIO12, verify GPIO12 stays low during reset and pass at least 10 cold boots with the servo attached; then verify tilt movement. Confirm GPIO15 encoder output levels do not prevent normal application boot (ROM boot text may be suppressed when GPIO15 is low).
- [ ] Repeat a short all-wheel low-speed run; check for missed counts, false counts from motor noise, driver fault symptoms, and ESP32 resets.

## Pin safety

The allocation avoids GPIO6–11 (flash-connected) and GPIO1/3 (primary serial/programming). GPIO34/35/36/39 are input-only; GPIO32 and GPIO34 are unassigned by the TA6586 wiring proposal.

GPIO5 is used for PAN after successful functional and cold-boot validation. GPIO12 is provisionally assigned to TILT only after reset-level and repeated cold-boot validation; do not use it for HC-SR04 ECHO. GPIO15 is provisionally assigned to encoder 1 (on motor 4); GPIO33 is assigned to encoder 4 (on motor 1). A low level on GPIO15 may suppress ROM boot text, so confirm normal application boot. GPIO2 is used for HC-SR04 TRIG. GPIO34/35/36/39 are input-only.

## Servo validation record

### PAN — GPIO5
- [x] Movement test passed on GPIO5
- [x] Slow movement passed
- [x] Fixed-position test stable
- [x] No fixed-position jitter observed
- [x] Cold-boot test passed on GPIO5

GPIO2 was the previous PAN signal and failed; it is now reassigned to HC-SR04 TRIG.

### TILT — previous GPIO15; candidate GPIO12
The following tests passed on GPIO15 before reassignment and do not validate GPIO12:
- [x] Functional test passed on GPIO15
- [x] Fixed-position test passed on GPIO15
- [x] Movement test passed on GPIO15
- [x] Repeated cold-boot test passed on GPIO15

User report (2026-10-04): tilt servo operates correctly with its signal on GPIO12. Functional movement is confirmed; reset-level measurement and 10 cold boots with the servo attached are still pending before treating this assignment as final.
