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

Status: COMPLETE — all movement, STOP, safety, and Pi–ESP32 link-loss/recovery acceptance checks are user-reported as passed.

Tasks:

\[x] Trace Whisper → intent → decision path.

\[x] Connect explicit STOP phrases to the existing ESP32 STOP command.

\[x] Handle STOP before Brain/LLM response generation; the ESP32 receives its dedicated STOP frame.

\[x] Keep the LLM out of the actuator command path; voice STOP dispatch is deterministic.

\[x] Validate movement commands — forward, backward, left, right, and slow/medium/fast operation verified by the user.

\[x] Validate unsafe command rejection — obstacle stops and safety rejection behavior verified by the user.\n\n\[x] Validate Pi–ESP32 no-link and recovery behavior.

Implementation note (2026-10-23): `thashu/core/decision.py` now recognizes a bounded set of explicit STOP phrases instead of matching any incidental use of “stop”. `thashu/main.py` dispatches those phrases through `MotorController.stop()` before Brain/LLM handling, and reports whether the serial frame could be sent. `thashu/hardware/motors.py` returns the transport sequence result. No movement commands were changed. User-reported Pi test (2026-10-25): voice STOP recognition and command dispatch passed with the robot stationary. Strictly matched forward commands now use Pi-side PWM presets: slow 150, medium 200, and fast 255; plain “forward” defaults to medium. Commands schedule a Pi-side STOP after 30 seconds, and explicit STOP cancels the timer and sends STOP immediately. ESP32 obstacle protection can stop motion sooner. PWM 100 was unreliable in the user's motor tests, so the slow preset starts above it. These are PWM levels, not calibrated wheel speeds; verify all four motors start reliably at slow and retain the desired speed separation on the chassis. ESP32 encoder PID and front/rear safety checks remain authoritative. The ESP32 emits `EVENT|0|STOP|OBSTACLE` when an obstacle stops active motion and `EVENT|0|BLOCKED|OBSTACLE` when an obstacle prevents motion from starting. Pi GPIOControl queues these events; main.py speaks the matching stopped/blocked report. User-reported Raspberry Pi/robot validation (2026-10-25): movement commands for forward, backward, left, and right worked, including the Whisper turn-phrase aliases; slow/medium/fast presets and the 30-second automatic stop were confirmed. An obstacle stopped active movement and Thashu announced the reason; voice STOP during motion stopped the motors and vision did not restart them. Unsafe movement was rejected under the tested safety conditions with an audible explanation. The user confirms all four Phase 3 acceptance criteria passed. The Pi serial reconnect behavior earlier showed repeated two-second receive-silence reconnects. User-reported Pi–ESP32 link-loss/recovery test (2026-10-25): link loss was detected, motors stopped safely, and commands worked after reconnection.

Acceptance:

\[x] Voice STOP physically stops motors.

\[x] STOP cannot be overridden by vision following.

\[x] Movement commands reach ESP32 correctly.

\[x] Safety restrictions are enforced.\n\n\[x] Pi–ESP32 link loss is reported, motors stop safely, and commands work again after reconnection.

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

Phase 5 — Commanded Person Follow & Upper-Body Tracking

Status: IN PROGRESS — bounded follow and stop-on-obstacle behavior are implemented; user reports movement/obstacle-stop tests passed. Cached WAV playback and remaining failure/acceptance tests remain open. Autonomous pathfinding/rerouting is explicitly out of scope.

Initial architecture audit (2026-10-25; before the implementation below):
- `VisionCore` is perception-only and pauses inference outside IDLE, preserving Phase 4. It currently publishes face boxes/names/presence, but not track IDs or observation timestamps.
- `CentroidTracker` uses nearest-centroid greedy matching with no distance gate or ambiguity signal. A crossing/overlap can silently change target identity. Existing `FollowLogic` chooses the largest face and is not safe for this phase; it is not currently wired into the Phase 4 `VisionCore` or main actuator path.
- `ServoTracker` exists but is not instantiated by `main.py`. Its Pi angle limits (30–150°) differ from ESP32 `ServoManager` limits (45–135°); control must be clamped consistently before physical servo testing.
- Voice movement handling in `main.py` is deterministic and exact-phrase based; no follow-mode command/state exists. `RuntimeStateMachine` already pauses vision outside IDLE, so follow must stop chassis motion on transition and require fresh target/sensor validation before resuming.
- `GPIOControl` receives timestamped sensor telemetry for follow decisions. ESP32 `SafetyManager` remains authoritative: forward requires all three front ToF readings clear; reverse requires rear ultrasonic clear. If the direct path is blocked, stop and report; no alternate-route/pathfinding behavior is in scope.
- Motor commands persist until STOP. The current Pi heartbeat is independent of command generation, so follow needs bounded command leases/automatic stops; ordinary heartbeat alone is not a movement lease.
- The ToFs are fixed front sensors, and no verified mapping from a selected camera target to an individual ToF beam or calibrated follow-distance hysteresis is recorded. Therefore chassis follow must remain disabled until target-range mapping, limits, and short-step behavior pass physical calibration. Servo-only tracking can be validated independently.


Purpose:
Provide two distinct behaviors using the existing vision and actuator architecture. While IDLE, passive face tracking may pan/tilt the camera toward one stable, unambiguous detected face whether recognized or unknown; it never starts chassis motion or enables follow mode, and it stops when the wake word moves the runtime out of IDLE. Person/upper-body follow mode starts only after an explicit voice command such as “follow me.”

Ownership and constraints:
- `VisionCore` remains perception-only. It publishes upper-body/person detections with stable short-lived track identifiers, bounding boxes, positions, and freshness; face detections may supplement identity cues, but the selected target must remain trackable by the upper body when the face turns or is partly occluded. VisionCore does not call motors or servos.
- Follow-mode state and decisions belong in the existing runtime/supervisor and follow logic after an architecture audit. Reuse `vision/follow_logic.py`, `hardware/servo_tracking.py`, `hardware/motors.py`, and existing ESP32 safety. Add no module unless the audit shows the existing files cannot preserve these ownership boundaries.
- Pi motor requests go only through `MotorController`; servo requests go through the existing servo interface and ESP32 protocol. ESP32 obstacle interlocks, watchdog, and STOP remain authoritative.
- Follow mode is OFF at boot and after restart. It is enabled only by an explicit deterministic voice command; LLM output cannot enable or steer it. “Stop following” and explicit “stop” cancel the mode and stop motors immediately.
- Passive face tracking is separate from follow mode: while IDLE, a single stable, unambiguous face can drive camera servos whether its identity is known or unknown. Multiple/ambiguous faces do not cause arbitrary selection. This passive servo behavior never starts chassis movement and stops as soon as the wake word is detected and the runtime leaves IDLE.
- Upper-body/person servo and chassis following are active only while follow mode is explicitly enabled. Following pauses and motors stop whenever the runtime leaves IDLE; re-entry requires fresh target and safety validation.

Target selection and multiple people:
- With no upper body/person visible, do not move; report that no target is available.
- With exactly one upper-body/person track visible at “follow me,” select that track for this session. A face can provide optional identity cues but is not the sole tracking box.
- With multiple people, do not choose the largest/nearest person or move by default. Ask the user to select a unique visible target (left/center/right). If the selection maps to zero or multiple person tracks, ask again or cancel safely.
- Lock the selected short-lived upper-body/person tracker identity. Never silently transfer following to another person when tracks cross, overlap, disappear, or identity becomes uncertain.
- On target loss or ambiguous reacquisition, stop chassis motion immediately, hold the servo safely, and require the same target to be reacquired with high confidence or ask the user to select again. Do not chase/search with the chassis while target identity is uncertain.
- Name-based selection is deferred until Person Recognition (now Phase 6) provides verified identities. Do not infer that the voice speaker is a face without a validated association method.

Movement, servo, and safety behavior:
- In explicit upper-body follow mode, hold camera tilt at a fixed calibrated upward angle and move only pan to keep the selected person visible. Normal idle face tracking may continue to use pan and tilt. Calibrate direction, center/dead zones, hard angle limits, rate limits, smoothing, and loss-of-target behavior; never oscillate or drive into mechanical stops.
- Chassis movement requires a reliable target-distance estimate and calibrated follow-distance hysteresis. Calibrate camera-only range from the selected upper-body box's apparent height at known physical distances while resolution and tilt are fixed; use a measured lookup/interpolation and a conservative deadband rather than assuming every person's torso has the same size. Box clipping, target loss, pose change that invalidates the calibration, or stale frames must stop motion. Low-mounted front ToFs and rear ultrasonic are obstacle/route sensors only; do not treat them as target-range measurements. If camera range cannot be established or validated, keep chassis follow disabled.
- Define bounded follow speed/acceleration and command refresh/lease behavior. Loss of target, stale camera frames, stale sensor data, ESP32 link loss, invalid safety readings, STOP, or controller errors must stop chassis motion; no stale command may persist.
- Front ToF and rear ultrasonic checks remain in force. When an obstacle blocks the direct route, ESP32 must stop motion immediately and the Pi must announce the stop once. Follow mode must wait while the path remains blocked and may resume only along the same direct path after fresh sensors report clear and the same target remains fresh/stable. Do not turn, reverse, map, invoke SLAM, or attempt autonomous pathfinding/rerouting to get around the obstacle. If readings are stale/ambiguous or the target is uncertain, remain stopped. Never bypass ESP32 interlocks, STOP, or manual-control precedence.
- Manual movement commands must have a defined precedence: stop follow before taking manual control; STOP always wins. Follow mode must never override voice STOP or a safety stop.
- Do not store face images, embeddings, or identity associations for follow mode unless a separate user-approved memory requirement explicitly authorizes it.

Existing files inspected/reused:
- \[x] `thashu/main.py` and `core/state.py` / supervisor integration
- \[x] `thashu/vision/vision_core.py`, `vision/tracker.py`, `vision/follow_logic.py`
- \[x] `thashu/hardware/servo_tracking.py`, `hardware/motors.py`, `hardware/gpio_control.py`
- \[x] ESP32 servo, motor, communication, and safety managers
- \[x] Existing voice parsing, event, and test patterns

Required failure and interaction cases:
- startup/restart while follow was active; follow must remain OFF after reboot
- no face, one face, multiple faces, invalid/ambiguous location selection
- target crossing another face, temporary occlusion, target leaving frame, stale camera frame, and target reappearing
- STOP during servo tracking and during chassis movement
- explicit manual command while following
- wake/listen/think/speak transitions while following; motion stops and does not resume without fresh validation
- obstacle stop and WAV announcement, waiting while blocked, and safe same-path resumption after sensors clear (no reroute),
- camera, vision worker, servo, motor controller, or audio-command failure
- repeated detections/events must not cause command/audio spam or rapid direction oscillation

Verification plan:
- Unit tests for follow-mode state transitions, exact voice command parsing, target-selection ambiguity, stable target lock, and fail-safe transitions.
- Mocked integration tests proving VisionCore emits perception only, no actuation occurs while mode is OFF, all actions use existing hardware controllers, STOP preempts following, and stale/lost target stops movement.
- Pi camera tests with one and multiple people, including crossing/occlusion and explicit target selection.
- Servo bench tests for direction, limits, center/dead zone, smoothing, and sustained tracking.
- Wheels-raised chassis tests for bounded speed, follow-distance hysteresis, target loss, voice STOP, obstacle stop/WAV playback and wait-until-clear behavior (no reroute),
- Controlled floor tests only after bench and safety tests pass; verify no target switching and no obstacle/sensor bypass.
- Record actual Pi/ESP32 versions, tested sensor states, observed logs, and user-reported physical results before checking acceptance.

Acceptance:
\[ ] Follow mode is OFF on boot; passive face-only servo tracking never moves the chassis or enables follow mode.
\[ ] While IDLE, a unique stable face is passively servo-tracked whether known or unknown; tracking stops on wake-word detection and does not resume until IDLE vision has fresh detections.
\[x] Explicit “follow me” starts the mode; “stop following” and STOP stop it immediately.
\[ ] One visible upper-body/person track can be selected and tracked while moving; multiple people never trigger arbitrary target choice or movement.
\[ ] Target identity remains stable through tested movement; uncertain loss/crossing stops movement and requires safe reacquisition or reselection.
\[x] Servo tracking passes direction, limits, stability, and target-loss tests.
\[ ] Chassis following stays within validated distance/speed bounds; if distance estimation is not validated, chassis following remains disabled.
\[ ] Vision remains perception-only; hardware commands use existing controller interfaces and ESP32 safety.
\[ ] Voice interaction, manual commands, STOP, stale sensors, camera faults, and serial loss all preempt or safely stop following. An obstacle causes an immediate stop and one cached WAV announcement; follow waits until the direct path is clear and the same target/sensors are fresh. Autonomous rerouting/pathfinding/SLAM is intentionally out of scope.
\[ ] Automated tests, Pi integration tests, and controlled physical acceptance pass; no checklist box is checked from code inspection alone.


Implementation snapshot (2026-10-26): Added thashu/vision/person_detection.py because Phase 5 required a separate upper-body detector; reused VisionCore, CentroidTracker, FollowLogic, and ServoTracker. VisionCore now publishes stable face and upper-body tracks separately. The upper-body path has not been tested on the Pi; chassis-follow movement remains disabled pending sensor/target calibration.
- `thashu/core/decision.py`: added exact “follow me”, “stop following”, and unique left/center/right selection phrases. These dispatch deterministically before Brain/LLM.
- `thashu/vision/follow_logic.py`: added OFF-by-default follow session state, fresh-frame checks, unique target selection, no silent target transfer, and one-shot stop/notice decisions. Any target loss, ambiguity, or stale frame requires an explicit reselection; no face images or embeddings are stored.
- `thashu/vision/tracker.py`: added bounded centroid association plus overlap/crossing ambiguity flags.
- `thashu/vision/vision_core.py` and `thashu/vision/camera.py`: publish short-lived face track IDs, ambiguity, frame dimensions, and capture timestamps; clear failed/stale camera frames. VisionCore remains perception-only and IDLE-gated.
- `thashu/hardware/servo_tracking.py`: align Pi pan/tilt bounds with ESP32 ServoManager limits.
- `thashu/main.py`: integrate explicit follow commands, servo tracking only while follow mode is enabled and runtime is IDLE, stop follow before any voice interaction, and stop/report on controller-link loss. Multiple faces prompt for a unique left/center/right choice.
- `thashu/tests/test_follow_mode.py`: added exact-command, target-selection, ambiguity, target-loss, stale-frame, and tracker tests.
- `thashu/tests/test_vision_lifecycle.py`: verifies published short-lived track IDs and capture freshness while preserving the no-actuator VisionCore contract.
- Verification on a temporary mirror of the branch source: Python compile checks passed; 11 follow-mode tests passed; 5 vision lifecycle tests passed. Raspberry Pi camera/servo tests have not been run.
- Chassis motion is intentionally absent from this implementation tranche. No verified mapping connects the selected face to a fixed ToF beam or a safe follow-distance band. The existing ESP32 interlocks also require all front ToFs and rear sonar clear for turns. This was a historical pre-calibration gate and is superseded by the 2026-10-29 bounded-follow implementation and the user's measured camera calibration. The user explicitly excludes autonomous rerouting and SLAM; follow must stop and wait for the direct path to clear.

Pose Lite benchmark and integration update (2026-10-27): The user tested MediaPipe 0.10.15 on the Raspberry Pi 4 (aarch64, Python 3.11) in an isolated venv with the 5.8 MB Pose Landmarker Lite task model. The one-person image-mode benchmark ran at about 6 FPS. Moving-distance trials reported pose/shoulder visibility on 181/182 frames at 150 cm, 182/183 at 160 cm, and 183/183 at 200 cm. Median shoulder widths were 109.8, 103.4, and 95.7 px, with overlapping 10th–90th percentile ranges (94.6–113.0, 64.4–106.8, 93.0–99.7 px); this is insufficient for a safe chassis-distance controller. On 2026-10-27, `thashu/vision/person_detection.py` was changed to use MediaPipe Pose Lite while preserving the existing box interface; `requirements.txt` pins the tested MediaPipe/OpenCV/NumPy/Protobuf/FlatBuffers runtime, and `MODEL_SETUP.md` documents the persistent model path. The new integration configures up to four poses, which was not part of the one-person benchmark. The integrated app, four-person selection, servo tracking with the new detector, dependency installation in the main environment, and chassis control remain unverified. No Phase 5 acceptance box is checked by this benchmark.

\---

Phase 6 — Person Recognition

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

Phase 7 — Person \& Conversation Memory

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

Phase 8 — Place / Environment Memory

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

Phase 9 — Unified Person + Place + Episodic Memory

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

Phase 10 — Reliability \& Recovery

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

Phase 11 — Performance Optimization

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

Phase 12 — Mobile Control

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

Phase 13 — Full Robot / Expo Validation

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

`hardware/motors.py`	REVIEW	1/3/5	Motor control

`hardware/eyes.py`	REVIEW	1	Existing eye interface

`hardware/servo\_tracking.py`	REVIEW	1/4/5	Servo/follow control

`vision/vision\_core.py`	REVIEW	4/5	Perception lifecycle and follow-mode input
`vision/follow\_logic.py`	REVIEW	5	Existing target selection/debounce logic

`vision/face\_database.py`	REVIEW	6	Face storage

`vision/face\_recognition.py`	REVIEW	6	Recognition

`vision/auto\_capture.py`	REVIEW	6	Existing registration path

`memory/people.py`	REVIEW	6/7	Person memory

`memory/short\_term.py`	REVIEW	7	Short-term memory

`memory/long\_term.py`	REVIEW	7	Long-term memory

`memory/storage.py`	REVIEW	7	Storage

`data/people.py`	REVIEW	6/7	Person data

`voice/audio\_manager.py`	REVIEW	2/4	Existing pause/resume pattern

`voice/speech\_to\_text.py`	REVIEW	2/3	Whisper

`voice/text\_to\_speech.py`	REVIEW	2/10	Piper

`voice/wake\_word.py`	REVIEW	2	Wake-word subsystem

Status meanings: `REVIEW` = must inspect before changing; `MODIFY` = approved for modification; `REUSE` = verified suitable; `ORPHAN` = disconnected but not yet removed; `OBSOLETE` = removal/replacement approved; `COMPLETE` = verified.

\---

Phase Completion Log

Phase	Completion date	Result

Phase 0	2026-08-23	Architecture/source audit complete

Phase 1	2026-10-23	Complete — integrated controller and direct Pi USB-serial test passed; M0 startup twitch fixed; encoder confirmed on GPIO34.

Phase 2	2026-10-23	Complete — runtime supervisor/state machine verified; user confirms hardware safety remains active across states.

Phase 3	2026-10-25	Complete — movement, STOP, safety, and Pi–ESP32 link-loss/recovery checks verified by the user.

Phase 4	2026-10-23	Vision lifecycle software and Raspberry Pi acceptance passed (user-reported; logged 2026-10-23).

Phase 5	—	—

Phase 6	—	—

Phase 7	—	—

Phase 8	—	—

Phase 9	—	—

Phase 10	—	—

Phase 11	—	—

Phase 12	—	—

Phase 13	—	—


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

Idle obstacle announcement (2026-10-25): Updated `thashu/main.py` so asynchronous ESP32 obstacle STOP/BLOCKED events are spoken immediately from the normal main loop, including while runtime state is IDLE and the wake-word detector is waiting. The replies are now “I stopped because an obstacle was detected.” and “I can't move because an obstacle was detected.” Added exact Piper WAV cache keys in `thashu/voice/text_to_speech.py`; run `python -m voice.text_to_speech` once on the Pi to generate/update those WAVs in user-local storage. Announcements pause audio capture and lock wake-word processing during playback, then resume both. Code-path change only; physical obstacle event/audio behavior remains to be validated, and no Phase 3 acceptance item is marked complete.

Generic ESP32 safety rejection voice (2026-10-25): The Pi log showed `ACK|...|ERROR|SAFETY_STOP`, which the current `motion_failure_response()` intentionally converted to an empty string while expecting a separate BLOCKED event. Updated `thashu/main.py` to speak an accurate generic safety-stop explanation when older firmware sends that ACK without an event. Added the exact response to the Piper command WAV cache in `thashu/voice/text_to_speech.py`. The current phase-3 firmware sources send the more specific `ERROR|OBSTACLE` / `ERROR|SENSOR_NOT_READY` plus `EVENT|0|BLOCKED|OBSTACLE`; receiving `ERROR|SAFETY_STOP` indicates the ESP32 may be running older or different firmware. Generate the new local WAV with `python -m voice.text_to_speech` after pulling. Pi-side code only; physical audio and firmware-version verification remain pending. No tests run.

Whisper turn-command aliases (2026-10-25): Added exact-match aliases `on left`, `done left`, `on right`, and `done right` to the existing direction command parser in `thashu/core/decision.py`, based on the user's observed Whisper transcripts for “turn left/right.” These pass through the same bounded one-second turn command and ESP32 safety checks as existing explicit turn phrases. Pi-side parser update only; no tests or physical validation run. Phase 3 acceptance remains open.



Phase 5 search and eye animation update (2026-10-26): Updated the existing `thashu/vision/follow_logic.py` to delay the initial no-face prompt for 15 seconds, search for up to 12 seconds after loss/staleness, stop chassis motion immediately, and reacquire only the same short-lived track ID; it never silently adopts a different person. Updated `thashu/hardware/servo_tracking.py` and `thashu/main.py` so explicit follow mode sweeps the camera pan (50–125 degrees) and tilt (75–105 degrees) while searching on fresh frames, then stops the sweep and tracks a unique face. Multiple faces still require a unique left/center/right selection. Updated the active controller's `ESP32Firmware/ThashuController/eye_manager.h/.cpp` to blink automatically every four seconds; Pi `Eyes` remains a semantic expression client, while ESP32 owns OLED animation. The face detector detects visible faces, not full standing bodies; usable face size, camera placement, lighting, and servo search coverage require Pi hardware validation. Servo search and autonomous blink are implementation-only; ESP32 reflash is required for blink, and no Phase 5 hardware or acceptance item is marked complete.


Rear ultrasonic out-of-range reporting update (2026-10-26): Updated both existing UltrasonicManager copies (`ESP32Firmware/ThashuController/ultrasonic_manager.h/.cpp` and `ESP32Firmware/sensors/ultrasonic_manager/ultrasonic_manager.h/.cpp`), both SafetyManager copies, and both CommunicationManager copies. A completed HC-SR04 attempt with no ECHO rising edge or a measured return beyond 400 cm is now a fresh `FAR` result; telemetry reports `US_REAR|FAR`, and SafetyManager treats fresh FAR as clear for reverse/turn authorization. A malformed pulse (e.g. ECHO rises but never falls) remains `NA`/not-ready and blocks motion; valid numeric readings retain the 300 mm obstacle interlock. HC-SR04 cannot distinguish an open space with no echo from a disconnected/unpowered ECHO line, so FAR assumes the sensor and wiring are present; this must be validated on the robot. ESP32 build/upload and physical range/safety tests remain outstanding; no acceptance item is marked complete.


ToF transient-read reliability correction (phase-5, 2026-10-26): The Adafruit VL53L0X API reports `isRangeComplete()` as true on an underlying I2C/API error, and `readRangeResult()` can return `0xFFFF` for that failed read. Updated both existing ToFManager copies so a failed sentinel read does not erase the last successful sensor sample or refresh its timestamp. One transient bus/read failure therefore does not immediately produce `NA`; the last good reading still expires at the existing 150 ms safety freshness limit, after which movement remains blocked. Status 4 remains a fresh FAR result. No safety threshold or obstacle rule was relaxed. Build and repeated physical validation are still required.


Rear HC-SR04 no-target pulse fix (phase-5, 2026-10-26): Increased the echo timeout from 25 ms to 40 ms in both existing UltrasonicManager copies. HC-SR04 documentation specifies that when no target is detected, ECHO may remain high for 38 ms; the old 25 ms timeout cut this pulse short and marked the rear sensor malformed/NA instead of FAR. The longer timeout allows the falling edge to be measured (>400 cm) and reported as FAR; truly stuck-high ECHO beyond 40 ms remains NA and blocks reverse/turning. The 60 ms minimum trigger interval is retained. This policy assumes HC-SR04-compatible timing; hardware test required after firmware upload.


Common Piper reply cache expansion (2026-10-26): Extended the existing local WAV cache in `thashu/voice/text_to_speech.py` with frequently used sensor-not-ready, acknowledgement failure, controller-unavailable, not-understood, and follow-mode responses. The existing cache uses exact phrase lookup and plays matching WAVs directly, avoiding Piper synthesis during the interaction. Generate missing files once on the Pi with `python -m voice.text_to_speech` from `~/ThashuRobot/thashu` with the Thashu virtual environment active; files remain under the configured user-local voice cache. No Python or audio hardware validation performed.


Voice-controlled head direction and visible blink update (phase-5, 2026-10-26): Added exact spoken commands “look up,” “look down,” “look left,” “look right,” and “look straight” through the existing Pi decision and ServoTracker path. Each directional command moves the corresponding pan/tilt angle by a bounded 15 degrees, clamped to existing servo limits, and waits for the ESP32 acknowledgement; manual look commands are separate from chassis motor commands. Added short Piper cache entries for the acknowledgements. In the integrated ThashuController EyeManager, automatic blink now starts 2.5 seconds after initialization and repeats every 3.5 seconds; full eyelid closure is held for 150 ms inside a 360 ms close/hold/open animation, with `DBG|EYES|AUTO_BLINK` on serial for confirmation. These are implementation changes only: pull the Phase 5 branch, regenerate missing Piper cache files with `python -m voice.text_to_speech`, flash the integrated ESP32 sketch, and test all commands and visible blinking on hardware before marking acceptance complete.


Quick-response Piper cache expansion (phase-5, 2026-10-26): Extended `thashu/voice/text_to_speech.py` to enumerate every possible reply variant from the existing `QuickResponses.data` in `thashu/core/quick_responses.py`, assign each unique text a stable SHA-256-based cache filename, and include them in the existing one-time Piper WAV generation command. `speak()` maps the exact selected reply to its cached WAV, including replies chosen randomly from a phrase's variants. Command replies already present in the fixed cache are excluded from duplicate quick-response WAV generation. Pull Phase 5 and run `python -m voice.text_to_speech` once on the Pi; generation may take a while because it renders many distinct reply clips. WAVs remain in the user-local voice cache outside Git. No Pi generation or playback validation has been performed.


Rear ultrasonic FAR margin follow-up (phase-5, 2026-10-26): User reports the rear ultrasonic still displays `NA` at out-of-range distances. The integrated controller and source-folder UltrasonicManager copies now wait 50 ms (previously 40 ms) for the HC-SR04 echo pulse, allowing extra timing margin for modules that return the nominal ~38 ms no-target pulse with variation. A completed pulse beyond 400 cm remains fresh `FAR`; no pulse is also `FAR`; a pulse that remains high beyond the 50 ms timeout remains `NA`/not-ready. This is a timing-margin implementation change, not a confirmed root-cause fix; pull and flash the integrated controller, then check telemetry in open space. If it still reports `NA`, capture ECHO waveform/voltage and telemetry to distinguish module behavior from wiring or firmware version. No build or hardware verification has been performed.


Left-turn duration adjustment (phase-5, 2026-10-26): Increased the Pi-side bounded LEFT jog from 1.0 to 2.0 seconds after the user reported the robot turned only slightly. RIGHT remains at 1.0 second. The left-turn command log and Pi auto-stop timer use the same 2.0-second setting; ESP32 obstacle interlocks and stop behavior are unchanged. Physical turn angle and safety behavior need a controlled hardware check; no test was run here.


Right-turn duration matched to left (phase-5, 2026-10-26): Per user follow-up, increased RIGHT jog from 1.0 to 2.0 seconds as well. Both left and right now run for two seconds, with their existing bounded Pi STOP timers and ESP32 safety interlocks.


Phase 5 user-reported validation update (2026-10-26): The user confirms both previously listed test groups passed: (1) voice servo directions, two-second left/right turns, visible auto-blinks, and rear ultrasonic FAR reporting; (2) Pi follow-mode tests for face selection/tracking, target loss/reacquisition, servo behavior, and STOP/voice-interaction preemption. Checked the explicit follow start/stop, single/multiple-face selection, and servo tracking acceptance items above. Chassis following and obstacle rerouting remain open; the broader crossing/occlusion, failure-injection, and full automated/physical acceptance criteria have not been claimed complete by this confirmation.


Phase 5 sensor-telemetry prerequisite (2026-10-26): Extended the existing `thashu/hardware/gpio_control.py` to parse ESP32 `TEL|0|SENSORS` frames and expose `get_sensor_snapshot(max_age=0.2)`. The returned copy includes monotonic receive time and left/center/right ToF plus rear ultrasonic values in millimetres; `FAR` and `NA` remain distinct, and missing/stale telemetry returns `None`. This is read-only infrastructure for future route evaluation and does not issue motor commands or enable chassis follow. Verify parsed fresh/stale telemetry on the Pi before relying on it; target-to-ToF mapping and safe-follow-distance calibration remain hardware prerequisites.




Upper-body tracking implementation (2026-10-26): Added thashu/vision/person_detection.py, which uses OpenCV's packaged haarcascade_upperbody.xml; the detector degrades to no person tracks if that cascade is unavailable, preserving face and voice startup. VisionCore stabilizes upper-body detections across three frames and publishes persons with independent short-lived tracker IDs, while retaining separate face detections and recognition. Existing FollowLogic now selects persons from fresh snapshots (with a compatibility fallback for old face-only snapshots), and explicit follow aims the servo at the selected upper-body box. This Haar cascade is an initial frontal upper-body detector; profile views, occlusion, and motion robustness still require Pi camera validation. No tests were run.

Chassis-follow gate (2026-10-26): Follow mode still does not issue forward/turn motor commands. The existing implementation only steers the camera servo and sends STOP on target loss. Do not enable chassis movement until camera apparent upper-body size is calibrated against measured distances with fixed resolution/tilt, the chosen follow-distance deadband and robot clearance are established, and bounded motor leases plus fail-safe obstacle handling are implemented and tested. The front ToFs and rear ultrasonic are mounted near floor level and are for obstacle/route checks, not person-range measurement. Their readings do not prove that an entire side route or swept turning path is clear. Upper-body and chassis-follow acceptance remain unchecked.

Camera-range follow clarification (2026-10-26): The front ToFs/rear ultrasonic are mounted at foot level, so they must not be used as the person's torso distance measurement. For explicit upper-body follow, keep camera tilt fixed and use pan-only tracking; estimate relative range from calibrated upper-body pixel height at measured distances with camera resolution and tilt held constant. The phase-5 code currently fixes the follow tilt command to 65 degrees (25 degrees upward from the 90-degree neutral command) and pans toward the upper-body center. The user confirmed 65 degrees is preferred for follow range; verify camera framing and servo clearance on the robot. Person-size/pose variation, partial clipping, and profile views can invalidate image-scale distance; stop on target loss or invalid scale. Low-mounted sensors remain for near-ground obstacle detection/route checks. Chassis motor following remains disabled until camera calibration, distance deadband, bounded motor leases, and physical obstacle tests pass.

Follow-target clarification from user (2026-10-26): Follow mode should track a moving person by their visible upper body, not merely keep the face centered. Existing follow implementation was face-box based; face-only Pi tests do not validate upper-body tracking. Upper-body perception uses existing VisionCore/tracker ownership (no actuator calls from VisionCore); face recognition may supplement identity only. After user reported intermittent detections, `thashu/vision/person_detection.py` was tuned for greater sensitivity (scaleFactor 1.05, minNeighbors 3, minSize 48×64); three-frame confirmation and short miss persistence remain to filter flicker. This may increase false candidates, so verify stable tracking on the Pi in varied distance, lighting, pose, and background conditions before acceptance. Do not enable chassis following until upper-body tracking, camera-size distance calibration, bounded motion, and sensor-verified obstacle behavior pass their required tests.

Passive face-tracking clarification from user (2026-10-26): Independently of follow mode, while the runtime is IDLE the Pi servo controller may center one stable, unambiguous face whether recognized or unknown. It must stop issuing tracking updates immediately when the wake word is detected and must not restart until the runtime returns to IDLE with fresh camera frames. Face presence never enables chassis movement. Implementation is in `thashu/main.py`; multiple/ambiguous faces are not arbitrarily selected. Hardware validation remains pending.


Bounded chassis-follow implementation (2026-10-29):


Follow freshness correction (2026-10-29): The user's Pi run showed the selected upper-body remained visible and unambiguous (track 0), while observation ages repeatedly ranged from 0.35 to 0.58 seconds. The previous `FollowLogic.MAX_FRAME_AGE_SECONDS = 0.35` caused fresh-enough-for-this-measured-pipeline snapshots to enter `SEARCHING_FOR_TARGET` and trigger STOP, even though the same track was still present. Increased the threshold to 0.75 seconds in `thashu/vision/follow_logic.py` (commit `212c5f5`); bounded 250 ms motor pulses, sensor freshness checks, and ESP32 safety interlocks are unchanged. This is a code correction based on the supplied Pi log, not yet hardware-retested. Keep chassis-follow and obstacle-reroute acceptance unchecked until the user retests follow behavior safely on the robot.



Obstacle announcement WAV-only playback (2026-10-29): Updated `thashu/main.py` so asynchronous obstacle STOP/BLOCKED announcements call the existing cache-only WAV playback path instead of `speak()`; runtime obstacle announcements do not invoke Piper. Updated `thashu/voice/text_to_speech.py` with `play_cached_response()` and optional named generation in the existing cache-preparation function. On the Pi, pre-render just the two required clips once with:
```python
from voice.text_to_speech import prepare_command_voice_cache
prepare_command_voice_cache({"obstacle_stop", "obstacle_blocked_v2"})
```
This uses Piper only during offline WAV generation; runtime plays `obstacle_stop.wav` or `obstacle_blocked_v2.wav` from the user-local voice cache. If a clip is missing, the code logs a warning and does not fall back to live Piper; ESP32 motor STOP/safety remains independent. User reports follow movement and obstacle stopping worked in the latest test; the WAV-only audio path still needs Pi playback validation. No automated tests run. Phase 5 acceptance remains open.




User scope and hardware test update (2026-10-29): The user explicitly declines automatic obstacle pathfinding/rerouting and SLAM for follow mode. Required behavior is stop on the blocked direct path, announce once, and wait; no turn-around or alternate-route attempt. The user reports the latest follow movement and obstacle-stop test worked correctly after the freshness correction. This report does not validate the new WAV-only playback, all failure cases, or full Phase 5 acceptance. Acceptance remains unchecked pending WAV playback and remaining required tests.

