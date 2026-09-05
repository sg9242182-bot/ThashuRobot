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

2 × DRV8833 2-channel DC motor drivers

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

Status: CURRENT — NOT STARTED

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

\[x] Map current motor implementation to 2 × DRV8833.

\[x] Map current eye implementation to 2 × 0.96-inch OLEDs.

\[x] Map three VL53LDK sensors: left/center/right.

\[x] Map rear ultrasonic sensor and echo voltage-divider interface.

\[x] Determine whether existing servo hardware remains.

\[ ] Identify obsolete hardware dependencies.

\[x] Identify code that must remain on Pi versus move to ESP32.

ESP32 Communication

\[x] Inspect existing communication mechanism.

\[ ] Define reliable Pi ↔ ESP32 command/telemetry responsibilities.

\[ ] Define motor command handling.

\[ ] Define high-priority STOP behavior.

\[ ] Define sensor telemetry.

\[ ] Define OLED commands.

\[ ] Define servo commands if retained.

\[ ] Define disconnect/failure behavior.

\[ ] Test communication reliability.

Safety

\[ ] ESP32 can independently stop motors.

\[ ] Front ToF protection works independently of Pi vision processing.

\[ ] Rear ultrasonic protection works independently of Pi vision processing.

\[ ] Unsafe movement commands are rejected at hardware level.

\[ ] Stale/lost Pi commands cannot leave motors running indefinitely.

Phase 1 Acceptance Criteria

\[ ] Both DRV8833 drivers operate correctly.

\[ ] All three VL53LDK sensors return reliable measurements.

\[ ] Rear ultrasonic returns reliable measurements.

\[ ] Both OLED displays operate correctly.

\[ ] Pi ↔ ESP32 communication is reliable.

\[ ] ESP32 can perform a hardware-level motor STOP.

\[ ] Safety sensors remain active independently of Pi AI/vision workload.

\[ ] Existing required robot functionality is preserved.

Phase 1 completion: Do not mark complete until all acceptance criteria pass.

\---

Phase 2 — Runtime Supervisor \& State Machine

Status: Runtime supervisor/state machine integrated and verified

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

\[ ] Keep hardware safety active in every state.

\[x] Prevent motor following during conversation.

\[x] Prevent duplicate hardware ownership.

Acceptance:

\[x] State transitions are deterministic.

\[x] No subsystem can silently bypass the supervisor.

\[ ] Safety remains active in all states.

\[x] Existing voice behavior remains functional.

\---

Phase 3 — Voice → Command → Hardware

Status: NOT STARTED

Tasks:

\[ ] Trace Whisper → intent → decision path.

\[ ] Connect STOP to actual hardware stop.

\[ ] Define high-priority STOP handling.

\[ ] Prevent LLM from directly bypassing command/safety layer.

\[ ] Validate movement commands.

\[ ] Validate unsafe command rejection.

Acceptance:

\[ ] Voice STOP physically stops motors.

\[ ] STOP cannot be overridden by vision following.

\[ ] Movement commands reach ESP32 correctly.

\[ ] Safety restrictions are enforced.

\---

Phase 4 — Vision Lifecycle

Status: NOT STARTED

Files to inspect/reuse:

\[ ] `vision/vision\_core.py`

\[ ] `vision/camera.py`

\[ ] `vision/face\_detection.py`

\[ ] `vision/face\_recognition.py`

\[ ] `vision/tracker.py`

\[ ] `vision/follow\_logic.py`

\[ ] `vision/auto\_capture.py`

\[ ] `vision/face\_database.py`

Tasks:

\[ ] Keep expensive models resident where appropriate.

\[ ] Pause vision processing during LISTENING.

\[ ] Pause vision processing during THINKING.

\[ ] Pause vision processing during SPEAKING.

\[ ] Resume vision cleanly after TTS.

\[ ] Ensure camera ownership is singular.

\[ ] Ensure vision cannot drive motors during conversation.

Acceptance:

\[ ] Vision processing genuinely stops during voice/AI processing.

\[ ] Vision resumes without unnecessary model reloads.

\[ ] No camera/thread duplication.

\[ ] No race condition with hardware control.

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

Phase 1	—	—

Phase 2	—	—

Phase 3	—	—

Phase 4	—	—

Phase 5	—	—

Phase 6	—	—

Phase 7	—	—

Phase 8	—	—

Phase 9	—	—

Phase 10	—	—

Phase 11	—	—

Phase 12	—	—



