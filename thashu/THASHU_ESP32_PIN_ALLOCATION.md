# THASHU ESP32 HARDWARE PIN ALLOCATION

**Project:** Thashu — Intelligent Self-Reliant Robot  
**Phase:** Phase 1 — Hardware Abstraction & ESP32 Migration  
**Status:** ALLOCATION FROZEN — revised after PAN GPIO5 validation; remaining Phase 1 hardware validation pending  
**MCU:** ESP32-WROOM-32, 38-pin NodeMCU  
**Expansion:** Purple ESP32 38-pin expansion board

## Current hardware

- 4 DC motors
- 2 × HW-627 / DRV8833 motor-driver modules
- 3 × VL53LDK ToF sensors: front-left, front-center, front-right
- 2 × 0.96-inch OLED displays
- 1 × HC-SR04 rear ultrasonic sensor
- 2 × MG90S servos: camera pan and camera tilt
- Ear servos are NOT part of the current design.

## Frozen GPIO allocation

| GPIO | Function | Direction | Hardware |
|---:|---|---|---|
| 2 | HC-SR04 TRIG | OUT | HC-SR04 |
| 4 | Front-left ToF X | OUT | VL53LDK |
| 5 | Camera PAN servo signal | OUT | MG90S |
| 13 | HW-627 #1 IN1 | OUT | Motor driver |
| 14 | HW-627 #1 IN2 | OUT | Motor driver |
| 15 | Camera TILT servo signal | OUT | MG90S |
| 16 | Front-center ToF X | OUT | VL53LDK |
| 17 | Front-right ToF X | OUT | VL53LDK |
| 18 | HW-627 #2 IN4 | OUT | Motor driver |
| 19 | HW-627 #2 IN3 | OUT | Motor driver |
| 21 | I2C SDA | I/O | 3 ToF + 2 OLED |
| 22 | I2C SCL | I/O | 3 ToF + 2 OLED |
| 23 | HW-627 #2 IN2 | OUT | Motor driver |
| 25 | HW-627 #2 IN1 | OUT | Motor driver |
| 26 | HW-627 #1 IN4 | OUT | Motor driver |
| 27 | HW-627 #1 IN3 | OUT | Motor driver |
| 32 | HW-627 #1 EEP / SLEEP | OUT | Motor driver |
| 33 | HW-627 #2 EEP / SLEEP | OUT | Motor driver |
| 34 | HW-627 #1 ULT / fault | IN | Motor driver |
| 35 | HW-627 #2 ULT / fault | IN | Motor driver |
| 36 | HC-SR04 ECHO | IN | HC-SR04 |

## I2C bus

GPIO21 and GPIO22 are shared by all five I2C devices:

- Left OLED
- Right OLED
- Left ToF
- Center ToF
- Right ToF

The three ToF X lines provide independent startup/address-management control because the sensors initially use the same default I2C address.

## HW-627 #1

- IN1 → GPIO13
- IN2 → GPIO14
- IN3 → GPIO27
- IN4 → GPIO26
- ULT → GPIO34
- EEP → GPIO32 (software-controlled)
- OUT1/OUT2 → motor channel 1
- OUT3/OUT4 → motor channel 2

## HW-627 #2

- IN1 → GPIO25
- IN2 → GPIO23
- IN3 → GPIO19
- IN4 → GPIO18
- ULT → GPIO35
- EEP → GPIO33 (software-controlled)
- OUT1/OUT2 → motor channel 1
- OUT3/OUT4 → motor channel 2

## Camera pan/tilt

- GPIO5 → PAN MG90S signal
- GPIO15 → TILT MG90S signal

Servo power is separate from ESP32 GPIO power, with a common ground.

Servo control will use ESP32 hardware PWM with software rate/position limiting for smooth movement.

## HC-SR04

- GPIO2 → TRIG
- GPIO36 → ECHO
- Existing voltage divider remains on ECHO before the ESP32 input.

## Pin safety

The allocation avoids GPIO6–11 (flash-connected) and GPIO1/3 (primary serial/programming). GPIO34/35 are used only as inputs.

GPIO5 is used for PAN after successful functional and cold-boot validation. GPIO15 is used for TILT. GPIO2 is used for HC-SR04 TRIG. GPIO34/35 are input-only fault inputs, and GPIO36 is used for HC-SR04 ECHO.

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

## Freeze rule

This file freezes logical GPIO ownership. It does NOT declare all of Phase 1 complete.

Remaining Phase 1 validation must cover the motor drivers, all three ToFs, ultrasonic, OLEDs, Pi↔ESP32 communication, and hardware safety.

Only change this allocation if testing exposes a genuine electrical, boot, timing, or reliability problem. Document any such change in this file and in the authoritative engineering checklist.
