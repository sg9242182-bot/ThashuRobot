THASHU ENGINEERING CHECKLIST

Project: Thashu — Intelligent Self-Reliant Robot  
Checklist status: Active  
Authoritative project checklist: Yes

Engineering Rules

Work on one phase at a time.

Reuse existing files and architecture whenever they are suitable.

Do not create new files/modules without a demonstrated architectural need.

Do not mark a phase complete because code merely runs.

A phase is complete only when its implementation, tests, and acceptance criteria pass.

Completed phases remain frozen unless a later test exposes a genuine regression.

Record actual file-level changes and their purpose.

Do not silently delete or abandon existing code; document orphaned/obsolete components first.

Safety functions must remain available even when AI/vision processing is paused.

\---

Hardware Baseline

Raspberry Pi 4

ESP32 NodeMCU

2 × Makerbazar TA6586 dual-channel DC motor-driver modules (four independent motor channels total)

2 × 0.96-inch OLED displays (robot eyes)

3 × VL53LDK ToF sensors:

Front-left

Front-center

Front-right

1 × rear ultrasonic sensor

Echo line uses a voltage divider for ESP32 safety

Camera

Existing servos, where retained and confirmed during Phase 1

Hardware Responsibility

Raspberry Pi

High-level robot behavior

AI / LLM

Whisper / speech recognition

Piper / speech output

Camera processing

Face recognition

Person/place memory

High-level decisions

Supervisor/state machine

ESP32

Motor control

Hardware-level motor stop/safety

OLED displays

ToF sensors

Rear ultrasonic

Servo hardware, if retained

Pi ↔ hardware communication

\---

Memory Rules

Temporary / Expiring Memory

Normal conversation that has no lasting importance should not become permanent memory.

Examples:

Greetings

Casual conversation

Repetitive questions

Temporary context

Permanent Person Memory

Store only useful, lasting information such as:

Confirmed name

Confirmed face/identity

Important facts explicitly provided by the person

Significant interactions

Relevant preferences

Important events

Where/how the person was known, when meaningful

A face alone does not establish identity.

Unknown person flow:

Detect unknown person.

If interacting, ask their name when appropriate.

Store the person only after their name is known/confirmed.

Associate the face representation with the confirmed identity.

Store important interaction memories, not a permanent transcript of every sentence.

Permanent Place Memory

Thashu must not invent semantic place names.

A place becomes semantically known when the user explicitly labels it, for example:

"This is our house."

"This is my school."

"This is a road."

Store:

User-provided place label

Visual/environmental reference information

Important observations/events associated with the place

Later recognition must use the stored reference information and confidence thresholds. If confidence is insufficient, report the place as unknown rather than inventing an identity.

Memory Layers

Short-term: current conversation/context; expires.

Episodic: important interactions/events.

Long-term semantic: stable facts about people and places.

\---

Phase Status

Phase 0 — Architecture \& Source Audit

Status: COMPLETE

Completed

\[x] Source repository structure audited.

\[x] Imports/dependencies traced.

\[x] Threads/processes/data paths examined.

\[x] Vision/voice concurrency problem identified.

\[x] Face/person pipeline orphaning identified.

\[x] Motor STOP command-path problem identified.

\[x] Duplicate eye hardware ownership identified.

\[x] TTS timeout/recovery issue identified.

\[x] Existing architecture assessed for refactoring rather than blind rewrite.

Phase 0 Acceptance

\[x] Baseline architecture understood.

\[x] Major architectural risks documented.

\---

Phase 1 — Hardware Abstraction \& ESP32 Migration

Status: COMPLETE

Existing Files to Inspect First

\[x] `hardware/gpio\_control.py`

\[x] `hardware/motors.py`

\[x] `hardware/eyes.py`

\[x] `hardware/servo\_tracking.py`

\[x] `hardware/shutdown\_button.py`

\[x] `hardware/\_\_init\_\_.py`

\[x] Relevant `core/` hardware-command paths

\[x] Existing Pi ↔ hardware/serial communication

\[x] Existing tests related to hardware

Hardware Mapping

\[x] Map current motor implementation to 2 × TA6586 dual-channel modules. TA6586 paired-input control is implemented in both MotorManager copies and was physically tested.

\[x] Validate the integrated encoder/TA6586 GPIO map. Final tested map: M0 inputs GPIO13/33, M1 GPIO27/26, M2 GPIO25/23, M3 GPIO19/18; encoder IDs use GPIO15/35/39/34, GPIO36 remains HC-SR04 ECHO, GPIO32 is TRIG, and tilt-servo signal is GPIO12. TA6586 sleep/fault assumptions were removed. Motor, encoder, sensor, STOP/obstacle-stop, and startup checks passed.

\[x] Map current eye implementation to 2 × 0.96-inch OLEDs.

\[x] Map three VL53LDK sensors: left/center/right.

\[x] Map rear ultrasonic sensor and echo voltage-divider interface.

\[x] Determine whether existing servo hardware remains.

\[x] Identify obsolete hardware dependencies. DRV8833-specific sleep/fault assumptions were removed for TA6586.

\[x] Identify code that must remain on Pi versus move to ESP32.

ESP32 Communication

\[x] Inspect existing communication mechanism.

\[x] Define reliable Pi ↔ ESP32 command/telemetry responsibilities; protocol was exercised with Pi-format serial commands.

\[x] Define motor command handling.

\[x] Define high-priority STOP behavior.

\[x] Define sensor telemetry.

\[x] Define OLED commands.

\[x] Define servo commands if retained.

\[x] Define disconnect/failure behavior.

\[x] Test command/telemetry framing and acknowledgements using the serial monitor.

Safety

\[x] ESP32 can independently stop motors.

\[x] Front ToF protection works independently of Pi vision processing.

\[x] Rear ultrasonic protection works independently of Pi vision processing.

\[x] Unsafe movement commands are rejected at hardware level.

\[x] Stale/lost Pi commands cannot leave motors running indefinitely.

Phase 1 Acceptance Criteria

\[x] Both TA6586 dual-channel modules operate correctly across all four independently controlled motors.

\[x] All three VL53LDK sensors return reliable measurements.

\[x] Rear ultrasonic returns reliable measurements.

\[x] Both OLED displays operate correctly.

\[x] Pi ↔ ESP32 USB-serial communication passed on the Raspberry Pi: five HEARTBEAT commands received ALIVE acknowledgements, ENCODERS returned a response, sensor telemetry arrived, and STOP returned OK.

\[x] ESP32 can perform a hardware-level motor STOP.

\[x] Safety sensors remain active independently of Pi AI/vision workload.

\[x] Existing required robot functionality is preserved.

Phase 1 completion: All Phase 1 acceptance criteria passed on 2026-10-23. Integrated behavior and M0 startup/encoder remap were verified by the user.

Motor subsystem implementation note (2026-10-02; pin candidate updated 2026-10-03): `ESP32Firmware/motors/motor_manager.cpp`, `ESP32Firmware/motors/motor_manager.h`, the former `ESP32Firmware/motors/motor_manager.ino` was the initial monolithic serial runtime; its protocol and safety responsibilities have since been moved to dedicated managers. `ESP32Firmware/motors/motor_manager.cpp` / `.h` currently own motor outputs and encoder counts. The prior code assumes DRV8833 sleep control; the newly identified TA6586 modules use paired D inputs and provide no documented sleep/fault output. Firmware adaptation, compile, and physical validation are still pending. Candidate encoder-ID mapping is GPIO15/35/39/33 for encoder IDs 1–4 (mounted on motors 4/2/3/1); GPIO36 remains HC-SR04 ECHO. `ESP32Firmware/servomanager/servo_manager.cpp` provisionally moves TILT from GPIO15 to GPIO12 to free GPIO15. User reported on 2026-10-04 that the tilt servo operates correctly on GPIO12. Confirmed movement does not close the reset check: GPIO12 must still be verified low during reset and pass 10 cold boots with the servo attached. The USB-serial bench query `CMD|n|ENCODERS` returns `ENC|n|count1|count2|count3|count4`. Temporary build-tool files `platformio.ini`, `ESP32Firmware/motors/platformio_main.cpp`, and `ESP32Firmware/ArduinoMotorEncoderTest/ArduinoMotorEncoderTest.ino` were removed on 2026-10-05 at the user's direction. Finish the integrated ESP32 firmware before choosing and setting up a build/test environment. Host syntax checks from the earlier source state do not validate the latest pin edits. A real ESP32 toolchain/build, wheel-channel mapping, shared driver fault/sleep electrical behavior, current/thermal limits, cold-boot behavior, and physical acceptance remain unverified. Do not mark Phase 1 complete.

\---

Phase 2 — Runtime Supervisor \& State Machine

Status: COMPLETE

Target states:

\[x] IDLE

\[x] WAKE\_DETECTED

\[x] LISTENING

\[x] THINKING

\[x] SPEAKING

\[x] RETURN\_TO\_IDLE

Tasks:

\[x] Inspect existing `core/state.py`.

\[x] Inspect existing `core/event\_bus.py`.

\[x] Reuse suitable existing architecture.

\[x] Define state ownership.

\[x] Define state transitions.

\[x] Define subsystem behavior per state.

\[x] Keep hardware safety active in every state.

\[x] Prevent motor following during conversation.

\[x] Prevent duplicate hardware ownership.

Acceptance:

\[x] State transitions are deterministic.

\[x] No subsystem can silently bypass the supervisor.

\[x] Safety remains active in all states.

\[x] Existing voice behavior remains functional.

\---

Phase 3 — Voice → Command → Hardware

Status: IN PROGRESS — stationary voice STOP dispatch passed; a bounded forward command is implemented for active-motion STOP testing. Movement and safety acceptance remain pending.

Tasks:

\[x] Trace Whisper → intent → decision path.

\[x] Connect explicit STOP phrases to the existing ESP32 STOP command.

\[x] Handle STOP before Brain/LLM response generation; the ESP32 receives its dedicated STOP frame.

\[x] Keep the LLM out of the actuator command path; voice STOP dispatch is deterministic.

\[ ] Validate movement commands.

\[ ] Validate unsafe command rejection.

Implementation note (2026-10-23): `thashu/core/decision.py` now recognizes a bounded set of explicit STOP phrases instead of matching any incidental use of “stop”. `thashu/main.py` dispatches those phrases through `MotorController.stop()` before Brain/LLM handling, and reports whether the serial frame could be sent. `thashu/hardware/motors.py` returns the transport sequence result. No movement commands were changed. User-reported Pi test (2026-10-25): voice STOP recognition and command dispatch passed with the robot stationary. Strictly matched forward commands now use Pi-side PWM presets: slow 150, medium 200, and fast 255; plain “forward” defaults to medium. Commands schedule a Pi-side STOP after 30 seconds, and explicit STOP cancels the timer and sends STOP immediately. ESP32 obstacle protection can stop motion sooner. PWM 100 was unreliable in the user's motor tests, so the slow preset starts above it. These are PWM levels, not calibrated wheel speeds; verify all four motors start reliably at slow and retain the desired speed separation on the chassis. ESP32 encoder PID and front/rear safety checks remain authoritative. The ESP32 emits `EVENT|0|STOP|OBSTACLE` when an obstacle stops active motion and `EVENT|0|BLOCKED|OBSTACLE` when an obstacle prevents motion from starting. Pi GPIOControl queues these events; main.py speaks the matching stopped/blocked report. The user must verify the spoken reports for front and rear obstacle cases on hardware. Active-motion STOP, movement ACK/rejection behavior, and no-link behavior still require hardware validation. Whisper was switched from multilingual `tiny` to English-only `tiny.en` after the user observed an incorrect transcript for “move forward”; verify normal speech and movement phrases on the Pi because no hardware transcript retest has run yet.

Acceptance:

\[ ] Voice STOP physically stops motors.

\[ ] STOP cannot be overridden by vision following.

\[ ] Movement commands reach ESP32 correctly.

\[ ] Safety restrictions are enforced.

\---

Phase 4 — Vision Lifecycle

Status: COMPLETE — SOFTWARE, MOCK TESTS, AND RASPBERRY PI VALIDATION COMPLETE

Files to inspect/reuse:

\[x] `vision/vision\_core.py`

\[x] `vision/camera.py`

\[x] `vision/face\_detection.py`

\[x] `vision/face\_recognition.py`

\[x] `vision/tracker.py`

\[x] `vision/follow\_logic.py`

\[x] `vision/auto\_capture.py`

\[x] `vision/face\_database.py`

Tasks:

\[x] Keep expensive models resident where appropriate.

\[x] Pause vision processing during LISTENING.

\[x] Pause vision processing during THINKING.

\[x] Pause vision processing during SPEAKING.

\[x] Resume vision cleanly after TTS.

\[x] Ensure camera ownership is singular.

\[x] Ensure vision cannot drive motors during conversation.

Acceptance:

\[x] Vision processing genuinely stops during voice/AI processing.

\[x] Vision resumes without unnecessary model reloads.

\[x] No camera/thread duplication.

\[x] No race condition with hardware control.

Implementation and validation note (2026-10-17): Updated `thashu/vision/vision_core.py` to gate detection, recognition, tracking, servo updates, and motor following to IDLE; transition-time motor STOP and servo center are synchronized against vision outputs. Existing detector/recognizer instances remain resident, and tracks are reset on resume. Updated `thashu/vision/camera.py` to prevent duplicate capture threads and to join the thread on stop; added `CentroidTracker.reset()` in `thashu/vision/tracker.py`. In `thashu/main.py`, vision starts after the startup audio. Added unit tests in `thashu/tests/test_vision_lifecycle.py` and `thashu/tests/test_camera_lifecycle.py`. Offline lifecycle tests pass (4 tests) with fake camera/actuator dependencies. User-reported Raspberry Pi validation (2026-10-23): real camera and voice pipeline tests confirmed vision pauses during interaction and resumes afterward; lifecycle tests passed. Phase 4 acceptance is complete.

\---

Phase 5 — Person Recognition

Status: NOT STARTED

Existing files:

\[ ] `vision/face\_recognition.py`

\[ ] `vision/face\_database.py`

\[ ] `vision/auto\_capture.py`

\[ ] `memory/people.py`

\[ ] `data/people.py`

Tasks:

\[ ] Trace existing face-recognition pipeline.

\[ ] Determine why `FaceDatabase.add\_person()` is currently unused.

\[ ] Determine whether `AutoCapture` should be reconnected.

\[ ] Define unknown-person behavior.

\[ ] Define confirmed-name registration.

\[ ] Define recognition confidence/verification requirements.

\[ ] Prevent automatic identity invention.

Acceptance:

\[ ] Known person is recognized reliably.

\[ ] Unknown person remains unknown until identity is confirmed.

\[ ] Confirmed name + face creates persistent identity.

\[ ] False identity assignment is prevented.

\---

Phase 6 — Person \& Conversation Memory

Status: NOT STARTED

Existing files:

\[ ] `memory/short\_term.py`

\[ ] `memory/long\_term.py`

\[ ] `memory/storage.py`

\[ ] `memory/people.py`

\[ ] `data/people.py`

\[ ] Related core/personality modules

Tasks:

\[ ] Separate short-term and permanent memory.

\[ ] Define permanent person facts.

\[ ] Define significant interaction/episodic memory.

\[ ] Associate memories with confirmed people.

\[ ] Avoid permanent storage of irrelevant conversation.

\[ ] Define memory retrieval behavior.

\[ ] Preserve existing useful memory mechanisms.

Acceptance:

\[ ] Temporary conversation expires appropriately.

\[ ] Important person facts persist.

\[ ] Significant interactions persist.

\[ ] Memories are correctly associated with people.

\[ ] Memory retrieval is relevant and bounded.

\---

Phase 7 — Place / Environment Memory

Status: NOT STARTED

Existing files to inspect first:

\[ ] `vision/camera.py`

\[ ] `vision/vision\_core.py`

\[ ] Existing storage/memory files

\[ ] Existing image/vision utilities

Tasks:

\[ ] Define explicit user labeling flow.

\[ ] Store reference images/features for labeled places.

\[ ] Define place recognition confidence threshold.

\[ ] Support labels such as house, school, road.

\[ ] Associate significant observations/events with places.

\[ ] Return UNKNOWN when confidence is insufficient.

\[ ] Prevent invented place identities.

Acceptance:

\[ ] User can explicitly teach a place.

\[ ] Thashu can later recognize the place using references.

\[ ] Unknown places remain unknown.

\[ ] Important place memories persist.

\---

Phase 8 — Unified Person + Place + Episodic Memory

Status: NOT STARTED

Tasks:

\[ ] Connect person identity with important events.

\[ ] Connect place identity with important events.

\[ ] Connect person + place + event + time when relevant.

\[ ] Ensure memory retrieval remains bounded and useful.

\[ ] Avoid duplicate/conflicting records.

Acceptance:

\[ ] Thashu can associate significant interactions with people.

\[ ] Thashu can associate significant events with places.

\[ ] Person/place context can be retrieved together when useful.

\---

Phase 9 — Reliability \& Recovery

Status: NOT STARTED

Tasks:

\[ ] Piper timeout/recovery.

\[ ] Whisper failure recovery.

\[ ] Camera failure recovery.

\[ ] ESP32 disconnect/reconnect.

\[ ] Sensor failure handling.

\[ ] Motor stale-command protection.

\[ ] Process/thread cleanup.

\[ ] Graceful shutdown.

\[ ] Restart/recovery behavior.

Acceptance:

\[ ] Major subsystem failures do not permanently brick the robot.

\[ ] Motors fail safely.

\[ ] ESP32 reconnects or enters a safe state.

\[ ] Robot can recover from common runtime failures.

\---

Phase 10 — Performance Optimization

Status: NOT STARTED

Measure before optimizing:

\[ ] Wake-word → Whisper latency.

\[ ] Whisper → Brain latency.

\[ ] Brain → Piper latency.

\[ ] Piper → idle latency.

\[ ] Vision CPU/RAM usage.

\[ ] Face-recognition latency.

\[ ] Camera FPS.

\[ ] Pi ↔ ESP32 latency.

\[ ] Sensor update rate.

Acceptance:

\[ ] Measured latency meets the project's practical target.

\[ ] No optimization causes functional regressions.

\---

Phase 11 — Mobile Control

Status: NOT STARTED

Target:

\[ ] Manual movement.

\[ ] Robot status.

\[ ] Restart.

\[ ] Shutdown.

\[ ] Reset.

\[ ] Error/diagnostic status.

\[ ] Sensor telemetry where useful.

Acceptance:

\[ ] Mobile commands use the same robot supervisor.

\[ ] Mobile control cannot bypass hardware safety.

\[ ] Recovery controls work reliably.

\---

Phase 12 — Full Robot / Expo Validation

Status: NOT STARTED

Voice

\[ ] Wake word.

\[ ] Listening.

\[ ] Thinking.

\[ ] Speaking.

\[ ] Vision resumes.

Safety

\[ ] Front-center obstacle.

\[ ] Front-left obstacle.

\[ ] Front-right obstacle.

\[ ] Rear obstacle.

\[ ] Motor stop.

\[ ] Pi disconnect/failure behavior.

Person

\[ ] Known person recognition.

\[ ] Unknown person interaction.

\[ ] Name confirmation.

\[ ] Persistent person memory.

\[ ] Important interaction memory.

Places

\[ ] Teach house.

\[ ] Teach school.

\[ ] Teach road.

\[ ] Reference-based recognition.

\[ ] Unknown-place behavior.

Reliability

\[ ] Long-duration run.

\[ ] Repeated conversations.

\[ ] Repeated motor commands.

\[ ] ESP32 reconnect.

\[ ] Camera failure/recovery.

\[ ] Voice failure/recovery.

Final status: \[ ] EXPO READY

\---

File Status Register

Use this section to track actual repository files as they are inspected.

File	Status	Phase	Notes

`main.py`	REVIEW	2	Existing entry point

`core/state.py`	REVIEW	2	Existing state module

`core/event\_bus.py`	REVIEW	2	Existing event module

`core/brain.py`	REVIEW	2/3	AI/command path

`core/decision.py`	REVIEW	3	Decision path

`hardware/gpio\_control.py`	REVIEW	1	Existing hardware interface

`hardware/motors.py`	REVIEW	1/3	Motor control

`hardware/eyes.py`	REVIEW	1	Existing eye interface

`hardware/servo\_tracking.py`	REVIEW	1/4	Servo/follow control

`vision/vision\_core.py`	REVIEW	4	Vision lifecycle

`vision/face\_database.py`	REVIEW	5	Face storage

`vision/face\_recognition.py`	REVIEW	5	Recognition

`vision/auto\_capture.py`	REVIEW	5	Existing registration path

`memory/people.py`	REVIEW	5/6	Person memory

`memory/short\_term.py`	REVIEW	6	Short-term memory

`memory/long\_term.py`	REVIEW	6	Long-term memory

`memory/storage.py`	REVIEW	6	Storage

`data/people.py`	REVIEW	5/6	Person data

`voice/audio\_manager.py`	REVIEW	2/4	Existing pause/resume pattern

`voice/speech\_to\_text.py`	REVIEW	2/3	Whisper

`voice/text\_to\_speech.py`	REVIEW	2/9	Piper

`voice/wake\_word.py`	REVIEW	2	Wake-word subsystem

Status meanings: `REVIEW` = must inspect before changing; `MODIFY` = approved for modification; `REUSE` = verified suitable; `ORPHAN` = disconnected but not yet removed; `OBSOLETE` = removal/replacement approved; `COMPLETE` = verified.

\---

Phase Completion Log

Phase	Completion date	Result

Phase 0	2026-08-23	Architecture/source audit complete

Phase 1	2026-10-23	Complete — integrated controller and direct Pi USB-serial test passed; M0 startup twitch fixed; encoder confirmed on GPIO34.

Phase 2	2026-10-23	Complete — runtime supervisor/state machine verified; user confirms hardware safety remains active across states.

Phase 3	—	—

Phase 4	2026-10-23	Vision lifecycle software and Raspberry Pi acceptance passed (user-reported; logged 2026-10-23).

Phase 5	—	—

Phase 6	—	—

Phase 7	—	—

Phase 8	—	—

Phase 9	—	—

Phase 10	—	—

Phase 11	—	—

Phase 12	—	—


Initial integrated-runtime note (2026-10-05): This entry described the first sketch draft, where protocol and safety logic were still in the sketch. It is superseded by the dedicated manager ownership correction recorded below; use that correction as the current architecture status.


ESP32 manager ownership correction (2026-10-05): At the user's direction, the integrated Arduino sketch is now a lifecycle coordinator only. `ESP32Firmware/motors/motor_manager.h/.cpp` owns DRV8833 outputs, low-level STOP, and encoder counts only. New `ESP32Firmware/safetymanager/safety_manager.h/.cpp` owns ToF and rear-ultrasonic initialization/update, movement authorization, obstacle/stale-sensor checks, the 500 ms Pi watchdog, and shared driver-fault input. New `ESP32Firmware/communicationmanager/communication_manager.h/.cpp` owns serial framing, command routing, acknowledgements, and sensor telemetry. Arduino sketch `ESP32Firmware/ThashuController/ThashuController.ino` initializes and updates these managers; `src/*_adapter.cpp` includes their existing implementations for Arduino's sketch build layout. `ESP32Firmware/sensors/ultrasonic_manager` now exposes reading freshness for safety decisions. This is an implementation refactor only: it has not been compiled or tested on ESP32; preserve all Phase 1 checklist boxes as open pending software and physical acceptance.

Legacy runtime cleanup (2026-10-05): The former `ESP32Firmware/motors/motor_manager.ino` duplicated serial command parsing and safety policy outside the new dedicated managers. Its protocol handling now lives in `ESP32Firmware/communicationmanager/communication_manager.cpp`; safety policy lives in `ESP32Firmware/safetymanager/safety_manager.cpp`. The old entry sketch will be removed after this documented replacement; use `ESP32Firmware/ThashuController/ThashuController.ino` as the single integrated entry point.


Required-hardware health update (2026-10-05): `EyeManager.begin()` now reports OLED initialization failure, and `EyeManager.update()` polls the shared OLED I2C address every 500 ms. `ServoManager` and `MotorManager` expose readiness; `SafetyManager` now checks those managers and stops motors on reported loss, while startup refuses `READY` if required initialization fails. These are software health signals only: identical OLEDs sharing address 0x3C cannot be individually distinguished by an I2C probe, and servo attachment status cannot detect a physically disconnected servo. No ESP32 compile or hardware validation has been performed.


Serial capture follow-up (2026-10-11): With the OLED and rear ultrasonic disconnected, the sketch emitted `EVENT|0|READY` while telemetry stayed `NA`. `READY` is emitted by `CommunicationManager.begin()` and is not a live proof that every peripheral is present. The initial serial capture also exposed that `SafetyManager.update()` returned before refreshing ToF/ultrasonic data after OLED/servo health loss. Both integrated and source-folder SafetyManager copies now keep sensor updates running while forcing/staying in a stopped, not-ready state when required hardware is unhealthy. This correction has not yet been built or re-tested on the ESP32; the three ToF telemetry channels and OLED health behavior remain open acceptance checks. Phase 1 remains in progress.


TA6586 motor-driver migration note (2026-10-22): The user confirmed two Makerbazar TA6586 dual-channel modules for four motors and supplied a clear photo showing header labels GND, 3V3, D0–D3, VT. Updated THASHU_ESP32_PIN_ALLOCATION.md with proposed paired inputs and GPIO13/14, 27/26, 25/23, 19/18 mapping. Updated both existing copies of MotorManager (ESP32Firmware/motors and ESP32Firmware/ThashuController) to remove DRV8833 SLEEP GPIO32 handling and label the paired TA6586 control inputs. Updated both existing SafetyManager copies to remove the DRV8833 active-low nFAULT GPIO34 assumption; TA6586 breakout has no documented fault output. Managers remain separate: motor outputs/encoder counts stay in MotorManager; obstacle, watchdog, and reflex policy stay in SafetyManager. Existing software build and all physical checks remain pending. Do not connect GPIO32 or GPIO34 to the TA6586 boards. Use regulated 3–6 V motor power for the 3–6 V motors, common ground, and leave 3V3/VT disconnected. Validate each channel, direction, STOP, safety stop, current/thermal behavior, and cold boots before checking the relevant Phase 1 items.


Motor direction correction (2026-10-23): User reports isolated positive-drive testing showed M0 moved in the intended direction while M1, M2, and M3 moved in reverse. Updated both existing MotorManager implementations (ESP32Firmware/motors/motor_manager.cpp and ESP32Firmware/ThashuController/motor_manager.cpp) with a per-motor polarity map {false, true, true, true} so M1–M3 invert their two TA6586 inputs in software. Wiring is unchanged. The code has not yet been compiled or uploaded after this edit; verify each motor at low speed with wheels raised, then verify forward/reverse at chassis level before floor testing.


Encoder PID implementation note (2026-10-23): Added a non-blocking 250 ms feedback update to both existing MotorManager variants (`ESP32Firmware/motors` and `ESP32Firmware/ThashuController`). For two or more simultaneously driven motors, each motor's HC-89 pulse rate is compared with the active group's mean rate; bounded PID adjusts each channel's base PWM by at most ±35%. The existing command speed is still a PWM feed-forward value. Correct encoder association is applied: M0/M1/M2/M3 use encoder IDs 4/2/3/1. Both integrated and isolated loops now call `motors.update()`. Individual motor commands remain open-loop because there is no active peer reference. HC-89 pulses per wheel revolution and gains remain uncalibrated, so this matches relative wheel speed rather than guaranteeing an absolute RPM. No compile or physical PID test has been run; keep Phase 1 acceptance open pending upload, count comparison, gain tuning if needed, STOP/safety checks, and load tests.

ToF status-2 reporting and clear-range handling (2026-10-23): The user reports reliable measured distances above 300 mm were being shown as `NA`. Updated both existing ToFManager copies (`ESP32Firmware/sensors/tof_manager` and `ESP32Firmware/ThashuController`) so status-2 readings above the 300 mm obstacle threshold are retained as valid clear-path measurements; status-2 readings at or below 300 mm remain fail-safe/invalid, while status-0 readings continue to use the same 300 mm obstacle threshold. Status 2 is defined by ST as signal fail (weak return), so this accepts the user's empirically checked status-2 values and needs re-testing at known distances and with obstacles before acceptance. No ESP32 build or integrated safety test has been run after this edit; Phase 1 acceptance remains open.

ToF out-of-range handling (2026-10-23): Updated both existing ToFManager copies (ESP32Firmware/sensors/tof_manager and ESP32Firmware/ThashuController) to retain a completed VL53L0X status-4 result as a fresh out-of-range state, reported as FAR in telemetry rather than NA. SafetyManager accepts a fresh FAR result as no obstacle detected, while stale/API-failed readings remain NA and continue to block forward/turning motion. Numeric readings at or below 300 mm continue to trigger the existing obstacle stop. Status 4 can represent phase failure as well as no target in range, so this policy requires controlled physical validation (open space, then obstacle within 300 mm); no build or hardware test has yet been run. Phase 1 remains in progress.

HC-SR04 trigger-pin update (2026-10-23): Moved only the HC-SR04 TRIG signal from GPIO2 to GPIO32 in both existing UltrasonicManager headers (ESP32Firmware/sensors/ultrasonic_manager and ESP32Firmware/ThashuController). ECHO remains on GPIO36 through its voltage divider; encoder assignments remain unchanged and GPIO34 remains unused. The user must move the TRIG wire and verify cold boot plus stable rear readings. The ultrasonic acceptance item remains open until validated.




Phase 1 integrated-controller acceptance update (2026-10-23; user-reported physical results): The user completed the final integrated ThashuController checks after the isolated motors.ino checks. Four motor channels and encoder/PID behavior were already tested and reported working; no repeat motor-only test is required. The user reports successful integrated forward movement, automatic timeout stop, explicit STOP, front obstacle stop, three front ToF obstacle checks, rear ultrasonic readings and reverse obstacle stop (clear at 789 mm, blocked at 250 mm), both OLED expressions, servo operation, sensor telemetry, and open-space movement with ToF FAR readings. Marked the corresponding Phase 1 acceptance boxes above as passed based on those reports. Pi-style framing was first tested through the serial monitor, then verified on the Raspberry Pi over USB serial (five heartbeats, encoder response, telemetry, and STOP acknowledgement).

The user confirms the TA6586 modules have been verified, including their operation under the robot's tested conditions. Do not list TA6586 module validation as pending. This does not independently establish the vendor's advertised 5 A/channel as a continuous rating.

The M0 startup twitch was fixed by moving M0 D1 to GPIO33 and its HC-89 DO to GPIO34. The user reports the twitch is gone and the encoder works after upload. Phase 1 is complete.

Phase 4 updates reconciled onto phase1 (2026-10-23): Ported the already Pi-validated Phase 4 model configuration and voice response changes from phase-4 into phase1. Added `thashu/core/model_paths.py` and `thashu/MODEL_SETUP.md`; updated AI, wake-word, Whisper cache, Piper voice, and sound paths to use persistent user-local model storage and project-relative sound files. Updated `thashu/vision/vision_core.py` and its lifecycle tests so VisionCore owns perception only and has no motor or servo controller; face detection, recognition, state pausing/resume, and face-count logs remain. Existing `hardware/servo_tracking.py`, `vision/follow_logic.py`, and ESP32 motor/safety managers were retained. Preserved phase1's corrected audio pause/resume handling in `thashu/main.py`. The replaced vision actuator-follow path is intentionally no longer called from VisionCore, per the ownership rule that vision reports faces while hardware control remains in its own subsystem. The source revisions and Pi model/runtime behavior were reported working on phase-4; the consolidated phase1 branch still needs to be pulled and smoke-checked as a whole.

Phase 2 branch reconciliation (2026-10-23): Compared phase2 with phase1. The Phase 2 runtime integration is already present on phase1: RuntimeStateMachine transitions, EventBus publication, voice-state integration, vision pause/resume, and the wake-word speech hangover are all present. The phase2 branch is 240 commits behind phase1 and contributes no missing Phase 2 runtime files. Kept the newer Phase 4 perception-only VisionCore, which supersedes the older Phase 2 copy that directly drove motors/servos. Phase 2 remains COMPLETE; no Phase 2 source files needed copying or replacement.


Movement voice update (2026-10-25): `thashu/main.py` now uses short fixed replies for slow/medium/fast forward, reverse, and left/right turns. `thashu/core/decision.py` recognizes explicit normalized reverse and turn phrases, and the existing `MotorController` methods dispatch them through the 30-second forward/reverse timer; left/right turn commands are limited to one-second jogs because turn duration and side clearance are not calibrated; ESP32 sensor interlocks and stop behavior remain authoritative. `thashu/voice/text_to_speech.py` can pre-generate nine Piper WAV replies into `~/.local/share/thashu/voice_responses` (or `THASHU_VOICE_CACHE_DIR`), outside the repository, and play cached clips instead of synthesizing those fixed replies at runtime. Generate the clips on the Pi with `python -m voice.text_to_speech` from `~/ThashuRobot/thashu` after activating the project's venv. Implementation is committed on `phase-3`; Python and physical movement/safety acceptance have not been run. Do not check Phase 3 acceptance boxes until the Pi confirms each direction, auto-stop, and obstacle reporting.


Motor command sequence-return fix (2026-10-25): `thashu/hardware/motors.py` now returns GPIOControl's serial sequence from `backward()`, `left()`, and `right()`, matching `forward()`. Previously those commands were sent but returned `None`, causing main.py to report a disconnected ESP32 and skip its bounded auto-stop timer. Pi software fix only; no ESP32 firmware change. Directional hardware acceptance remains pending.


Motion ACK/safety diagnosis (2026-10-25): Updated `thashu/hardware/gpio_control.py` to associate command ACKs by sequence and log ESP32 errors. `thashu/main.py` now says movement began only after an `ACK|sequence|OK`; on missing/error ACK it cancels the Pi motion timer, sends STOP, and reports the reason. Both `ESP32Firmware/ThashuController/communication_manager.cpp` and `ESP32Firmware/communicationmanager/communication_manager.cpp` now distinguish a detected obstacle (`ERROR|OBSTACLE`) from invalid/stale safety sensor data (`ERROR|SENSOR_NOT_READY`); an actual blocked obstacle also retains the BLOCKED event for spoken reporting. This preserves fail-safe reverse behavior when rear ultrasonic data is unavailable. Pi tests, integrated ESP32 build/upload, and hardware validation remain pending; movement and safety acceptance boxes remain unchecked.

Pi serial reconnect hardening (2026-10-25): Updated the existing `thashu/hardware/gpio_control.py` transport to rediscover USB serial devices after disconnects, prefer a persistent `/dev/serial/by-id` path, compare device realpaths so the currently selected symlink remains correctly identified, and reconnect if ESP32 telemetry is silent for two seconds. Reader/writer failures are tied to the connection instance that failed so a delayed old-port error cannot tear down a newer connection. This is Pi-side only; no ESP32 firmware change is required. Must physically validate by running one serial client on the Pi and checking reconnect/log behavior after an ESP32/USB serial interruption. No tests or hardware validation run; Phase 3 and reliability acceptance remain open.

