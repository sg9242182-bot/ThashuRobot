# Vishal Raj Engineering Checklist — Raspberry Pi Backend and Integration

**Project:** THASHU — Intelligent Self-Reliant Robot  
**Owner:** Vishal Raj  
**Area:** Raspberry Pi API, WebSocket, robot/backend integration, telemetry, diagnostics, logging, service management  
**Status:** Phased implementation plan  
**Source of truth:** Approved repository architecture, API/protocol contracts, hardware records, and recorded architecture decisions.

> Implement the backend in dependency order. Do not freeze or invent a contract unilaterally. A backend component is complete only when its interface, failure behavior, tests, and integration evidence are documented.

---

## Mission and boundaries

Build the Raspberry Pi software layer that exposes a stable, safe interface to the mobile app and coordinates with the ESP32 hardware controller.

The Pi owns high-level robot services, API orchestration, command validation, state coordination, telemetry aggregation, diagnostics, logging, and service recovery. The ESP32 owns time-critical motor/sensor/actuator control and hardware-level safety. Flutter must not talk directly to ESP32 hardware protocols.

## Fixed architecture and collaboration rules

- REST is for request/response operations; WebSocket is for live telemetry/state, according to the approved contracts.
- Pi–ESP32 communication must use a documented, versioned contract with message types, validation, acknowledgements, errors, heartbeat/timeout behavior, and telemetry. JSON over reliable serial may be a proposed starting point, but it is not final until the team approves the exact schema and transport behavior.
- Coordinate the Pi–ESP32 protocol with Tharun, who owns hardware and ESP32 behavior. Coordinate mobile-facing API changes with Niteshvar.
- Do not expose an unrestricted shell-command endpoint or arbitrary GPIO/motor operations through the REST API.
- Do not report a command as successful merely because the HTTP request was received. Distinguish received, validated, dispatched, accepted, completed, rejected, timed out, and unknown outcomes as the agreed contract supports.
- On app disconnect, the Pi must apply the approved command/session timeout behavior and ensure the ESP32 safety watchdog remains effective. Phone, Pi, and ESP32 safety layers are complementary; none should be silently substituted for another.
- Manual and Auto modes must not drive concurrently. Mode transitions must follow the agreed safe-stop and acknowledgement sequence.
- Use structured logs and explicit PASS/WARNING/FAIL/UNKNOWN diagnostic states where approved.
- AI suggestions do not override the repository's architecture or team decisions.

## Phase 0 — Architecture and contract inventory

### Objective
Identify current implementation, approved interfaces, and unresolved decisions before backend changes.

### Checklist
- [x] Read README, architecture docs, protocol docs, hardware notes, and current Pi/ESP32/mobile implementation.
- [x] Confirm actual repository paths and existing code before creating duplicate modules.
- [x] Inventory API routes already implemented and distinguish them from planned routes.
- [x] Inventory the current Pi–ESP32 transport, parser, command format, and telemetry format from code and hardware evidence.
- [x] Create a contract-gap list: endpoint/schema, mode transition, command acknowledgement, timeout, heartbeat, error taxonomy, versioning, and auth.
- [ ] Finalize the mobile-facing production API behavior with Niteshvar; his proposed contract still awaits review. Hardware/protocol behavior with Tharun is confirmed for deployed protocol v0.
- [x] Record unresolved decisions in repository documentation or a focused issue.
- [x] Do not claim an interface is approved solely because it appears in an AI-generated draft.

### Exit criteria
- [x] Existing behavior and gaps are documented.
- [x] Owners are identified for each unresolved shared contract.
- [x] No incompatible replacement contract is introduced.

## Phase 1 — Raspberry Pi service foundation

### Objective
Create a maintainable, testable backend structure and reproducible local development environment.

### Checklist
- [x] Confirm supported Python/runtime versions and Raspberry Pi OS assumptions from the repository. Pi Setup records Raspberry Pi OS Bookworm and Python 3.11.2; the API supports Python 3.10 or newer.
- [x] Set up dependency management, environment-backed API token configuration, and automated test commands.
- [ ] Create and verify the virtual environment on the target Pi.
- [ ] Keep API routes, robot orchestration, ESP32 communication, safety policy, telemetry, diagnostics, and logging in separate modules consistent with the existing repository structure. The broader diagnostics/logging separation still needs review.
- [x] Keep the API token in environment configuration, outside source control.
- [x] Centralize and validate backend environment settings (API host/port, API token/state DB, model/data/cache paths, Piper binary, face-match debug flag) in `thashu/core/config.py`; invalid ports, blank path overrides, and invalid debug values fail explicitly.
- [x] Add structured JSON logs for move/stop outcomes with severity, timestamp, component, command ID, and sanitized error codes.
- [ ] Extend structured logging across other backend services and request flows. API HTTP requests and robot-process API startup now emit JSON records; other voice, vision, and transport services still use console messages and need a scoped logging pass.
- [x] Document startup/shutdown commands and handle unavailable serial hardware without crashing the API; status reports unavailable transport. Full startup behavior on the target Pi has not been verified.
- [x] Add baseline API/protocol tests and document development test commands.

### Exit criteria
- [x] API-only backend starts in local development (Vishal verified it in Swagger). Full robot-process startup on the Pi remains unverified.
- [ ] Configuration and logs are consistent across the full backend. Configuration is centralized; structured logging remains partial.
- [x] Software handles unavailable/disconnected serial hardware as a degraded state; API status tests cover unavailable transport. Physical Pi behavior remains unverified.

**Phase 1 evidence (2026-11-05):** Shared environment settings are centralized and validated in `thashu/core/config.py`; API request completion and robot-process API startup emit structured JSON logs. Configuration tests cover defaults, valid overrides, and invalid values. Phase 1 remains in progress because the target-Pi virtual environment/startup has not been verified, broader service logging/module separation still needs review, and full robot-process startup remains unverified.

## Phase 2 — Pi–ESP32 protocol contract and transport

### Objective
Make hardware communication explicit and reliable before exposing movement controls.

### Checklist
- [x] Collaborate with Tharun to approve transport, framing, message schema, and deployed protocol revision. Tharun confirmed v0 command, ACK, telemetry, and event frames on 2026-11-03; CMD/ACK carry no version field.
- [x] Define command correlation by sequence, acknowledgements, response/error codes, telemetry fields, and compatibility behavior. Record that v0 has no session-aware stale-ACK protection or duplicate-command detection.
- [x] Define serial connection startup, partial reads, message boundaries, malformed frames, buffer limits, and reconnect behavior. Pi buffering, frame-size limits, and reconnect handling are implemented and documented.
- [x] Define heartbeat/timeout responsibilities and safe behavior on missed heartbeat or lost connection.
- [x] Validate incoming messages and reject unknown or out-of-range commands in the integrated ESP32 parser; Pi ACK handling matches the v0 sequence number.
- [x] Ensure one authoritative robot manager path dispatches API movement commands to the motor service.
- [x] Separate transport parsing from robot behavior and API code.
- [x] Add protocol documentation and language-neutral test vectors; Pi tests consume the shared vectors.
- [x] Do not invent pin mappings or assume the current motor driver; the integrated firmware remains the hardware source of truth.
- [x] Record Tharun-reported v0 parser checks: HEARTBEAT, STOP, EYES, invalid EYES argument, unknown command, partial frames, oversized-frame discard, and recovery. Unsupported-version testing does not apply to v0.
- [ ] Capture live serial output from the existing firmware showing `EVENT|0|READY`, `TEL|0|SENSORS|...`, `ACK|sequence|ALIVE` for HEARTBEAT, and `ACK|sequence|OK` for STOP. Do not reflash; record the firmware/backend revisions with the output. No standalone ESP32 parser-test harness is present in the branch.

### Exit criteria
- [x] Both sides agree on the same documented v0 contract; CMD/ACK frames do not include a protocol-version field.
- [x] Valid, invalid, partial, stale, and unknown messages have defined behavior.
- [x] Transport failures are detectable and cannot silently appear as success.

**Phase 2 evidence (2026-11-03):** The `vishal-phase1` branch uses the deployed v0 framing in the integrated ESP32 parser, Pi client, tests, and shared vectors. Pi framing tests passed 9/9 and hardware-protocol tests passed 5/5 after pulling v0. Tharun reports the listed v0 parser checks passed; this is reported evidence, not a standalone parser-test harness result. Tharun reports the existing ESP32 firmware and Pi connection work reliably; live serial output for READY, telemetry, HEARTBEAT ACK, and STOP ACK is pending. No reflash is planned. v0 matches ACKs by sequence only and cannot distinguish a delayed ACK after a Pi restart if the sequence is reused.

## Phase 3 — Robot manager, modes, and command lifecycle

### Objective
Provide one authoritative high-level component for robot state and command coordination.

### Checklist
- [x] Verify the single Pi-side `RobotCommandManager` path for API and voice motor commands; tests cover validation, mode tracking, and transport failure.
- [x] Implement explicit MANUAL/AUTO mode selection; switch only after STOP receives `ACK|sequence|OK`, cancel Pi movement/follow work first, and keep AUTO paused until the existing follow behavior is explicitly started.
- [x] Confirm the mode-transition behavior with Tharun on the integrated robot. Tharun reports the Manual/Auto switching and STOP behavior are working; this is team-reported physical verification.
- [x] Route movement commands through request validation, manager dispatch, ACK tracking, and command-result reporting.
- [x] Require a STOP `ACK|sequence|OK` before the first Manual move; tests verify a rejected/missing ACK prevents the move and an already-Manual move does not repeat the transition STOP.
- [x] Require fresh, relevant sensor readings for each movement: 750 ms maximum age, `FAR` is clear, missing/`NA`/stale values block and send STOP, front ToF for forward/turns, rear sensor for backward, and numeric clearance above 300 mm.
- [x] Cancel timer/follow work on STOP or mode switch and reject app moves queued against an older control-state version.
- [x] Implement STOP in either mode so it cancels Pi movement/follow work, sends dedicated STOP, selects AUTO paused, and never resumes autonomously.
- [x] Handle ESP32 ACK rejection and timeout in the command-result flow.
- [x] Require UUID `request_id` values for move and STOP. Persist request ID, action, command ID, and latest result in SQLite for 24 hours; matching retries reuse the command, mismatched actions return 409, and interrupted dispatches become unknown without replay. Tests cover move/STOP retries, process restarts, ACK results, and action conflicts.
- [x] Define stale-state and uncertain-dispatch recovery: an in-flight request found after restart returns `unknown` with its original command ID and is never resent. Expired records can be treated as new requests after 24 hours.
- [ ] Add a latched Emergency Stop only after Tharun implements and tests the proposed ESP32 `ESTOP`/`ESTOP_RESET` protocol, including reboot-persistent latch and safe reset; Pi-side mirroring remains on hold until firmware verification.
- [x] Keep API routes from independently mutating low-level state; they dispatch through the robot manager.
- [x] Keep motor actuation and hardware safety logic on the ESP32; the Pi sends semantic commands.

### Exit criteria
- [x] One authoritative Pi service coordinates API/voice motor dispatch and its tracked mode.
- [x] Conflicting commands are safely serialized through the shared manager lock; a concurrent move/STOP test verifies they do not overlap.
- [x] API responses distinguish Pi dispatch from later ESP32 ACK, safety rejection, or timeout.

**Phase 3 evidence (2026-11-05):** The shared Pi manager now supports an explicit mode request, waits for `ACK|sequence|OK` before switching, inhibits movement after an unconfirmed mode STOP, and keeps AUTO paused until the existing follow-start action enables it. User-requested STOP cancels Pi movement/follow timers and returns to AUTO paused. Movement dispatch requires a fresh sensor snapshot (maximum 750 ms), treats `FAR` as clear, blocks `NA`/missing/stale readings and sends STOP, uses the existing 300 mm threshold, and leaves ESP32 safety interlocks authoritative. Control-state versions prevent a movement waiting across a STOP/mode change from being dispatched afterward. Bounded follow pulses stop without canceling the explicitly started Auto session. After persistent request ID idempotency was added for move and STOP, the combined API and robot-manager suites passed 61/61. In-flight records found after restart return unknown and are never replayed. Tharun reports the integrated mode/STOP behavior is working. Emergency Stop remains open pending a latched ESP32 protocol/firmware change.

## Phase 4 — REST API

### Objective
Expose a stable, validated mobile-facing API.

### Planned route inventory
The following routes are architectural candidates, not permission to invent their schemas. Confirm each route against the approved API specification before implementation:

- `GET /api/v1/status`
- `POST /api/v1/robot/move`
- `POST /api/v1/robot/stop`
- `POST /api/v1/robot/emergency-stop`
- `POST /api/v1/robot/mode`
- `POST /api/v1/robot/reset`
- Voice, diagnostics, logs, configuration, and system routes only where specified and authorized.

### Checklist
- [x] Implement route handlers as thin adapters over the robot manager/services.
- [x] Validate payload structure, command ranges, allowed enum values, and request size.
- [x] Validate and document supported request content types: move/stop/mode require `application/json` (optional charset accepted); tests cover missing, non-JSON, and JSON content types.
- [x] Use a consistent REST error envelope: errors stay under `detail`, object errors carry stable `detail.error_code`, validation uses sanitized `detail.issues`, and unexpected failures return a generic 500.
- [x] Bound command-slot waiting to 2 seconds; return HTTP 503 `API_BUSY` before dispatch when saturated. Keep hardware work in worker threads so it does not block the API event loop, and do not cancel an operation after it may have reached the ESP32.
- [x] Define authentication and authorization requirements with the team before exposing privileged operations. Nitesh confirmed public health/status and Bearer authentication for move, STOP, mode, command-result lookup, and telemetry; tokens stay out of chat.
- [x] Protect move and STOP retries from duplicate dispatch using persistent request IDs and a 24-hour SQLite store.
- [x] Apply the approved rate limit: one shared Bearer-token bucket for move/mode, capacity 10 refilling at 5 requests/second; return 429 before dispatch when empty. Authenticated STOP bypasses the limit and has priority over queued move/mode work.
- [x] Do not expose arbitrary shell execution, unrestricted filesystem access, or unrestricted hardware control; a route-surface test guards the current API routes against adding unapproved endpoints.
- [x] Keep OpenAPI/schema documentation and tests synchronized with implementation.
- [x] Test API success, malformed input, unauthorized access, backend unavailable, hardware disconnected, timeout, stable error codes, and validation redaction; the latest API suite passed 50/50 on 2026-11-07.

**Phase 4 evidence (2026-11-07):** Move/stop routes use the shared robot manager through `ApiServices`. Move schema validation rejects unknown fields/directions and invalid speeds; move/stop bodies are capped at 4 KiB with HTTP 413 for oversized requests. Move/stop/mode requests require `application/json`; missing and non-JSON content types receive HTTP 415, with optional charset accepted. REST errors stay under FastAPI's `detail`; object errors include stable `detail.error_code`, validation errors include sanitized `detail.issues`, and unexpected failures return a generic 500. A route-surface test confirms no shell, raw GPIO, or unrestricted control route is exposed. Move/mode requests that wait over 2 seconds return `API_BUSY` before dispatch; STOP has priority over queued move/mode requests and is not rejected by that queue-wait timeout, but does not interrupt an operation already in progress. Move/mode use the approved shared-token bucket (capacity 10, refill 5/second), returning HTTP 429 before dispatch when exhausted; STOP is authenticated and excluded. Authentication requirements are confirmed with Nitesh. Vishal reports the API suite passed 50/50, covering queue priority, STOP bypass, and bucket refill/rejection. Duplicate move/STOP requests are protected by the persistent request-id store.

### Exit criteria
- [ ] Routes match the agreed contract.
- [ ] Invalid and unsafe requests are rejected predictably.
- [ ] API failures do not crash core robot services.

## Phase 5 — WebSocket and telemetry

### Objective
Publish useful, consistent live state to the mobile app.

### Checklist
- [ ] Agree the WebSocket path, handshake, authentication, event/message schema, versioning, and error behavior with Niteshvar.
- [ ] Publish only contract-defined state, sensor summaries, mode, health, and timestamps.
- [ ] Distinguish live, stale, unavailable, and unknown values.
- [ ] Define connection lifecycle, heartbeat, client disconnect, backpressure, and reconnect behavior.
- [ ] Prevent a slow client from blocking robot control or telemetry collection.
- [ ] Ensure REST status and WebSocket events derive from the same authoritative state model.
- [ ] Avoid broadcasting secrets or unnecessary sensitive diagnostics.
- [ ] Test reconnects, server restart, malformed messages, multiple clients, and stale sensor data.

### Exit criteria
- [ ] Mobile receives consistent telemetry under normal and degraded network conditions.
- [ ] Stale/disconnected states are unambiguous.
- [ ] WebSocket traffic cannot block safety-critical processing.

## Phase 6 — Diagnostics, logs, and health reporting

### Objective
Make failures observable and actionable without pretending an untested subsystem is healthy.

### Checklist
- [ ] Define diagnostic checks and their evidence source with each subsystem owner.
- [ ] Use PASS, WARNING, FAIL, and UNKNOWN where that taxonomy is approved.
- [ ] Report timestamps and clear reason codes for failed/unavailable checks.
- [ ] Track API health, ESP32 connection, telemetry freshness, service health, and other implemented components only.
- [ ] Provide bounded log retrieval with redaction; do not expose secrets.
- [ ] Separate a check that failed from a check that could not run.
- [ ] Make diagnostic endpoints read-only unless a separate authorized action is explicitly specified.
- [ ] Add tests for missing devices, stale data, malformed telemetry, and log access boundaries.

### Exit criteria
- [ ] Reported health reflects evidence, not assumptions.
- [ ] Unknown/unavailable is not silently reported as PASS.
- [ ] Logs and diagnostic responses are bounded and safe to expose.

## Phase 7 — Configuration, service management, and recovery

### Objective
Support predictable startup, shutdown, configuration, and recovery.

### Checklist
- [ ] Centralize validated configuration with documented defaults and bounds.
- [ ] Separate secrets from ordinary configuration and avoid logging them.
- [ ] Define service startup order and readiness checks for API, robot manager, and ESP32 communication.
- [ ] Handle service shutdown without leaving commands or sockets in an undefined state.
- [ ] Coordinate restart/reset/recovery actions with Tharun; ensure privileged actions are authenticated and auditable.
- [ ] Never use a generic API endpoint to execute arbitrary shell commands.
- [ ] Add bounded retries/backoff and avoid endless restart loops.
- [ ] Document recovery behavior for Pi reboot, ESP32 disconnect, API crash, and configuration error.
- [ ] Verify safety behavior remains owned by the Pi/ESP32 layers even if the mobile app disappears.

### Exit criteria
- [ ] Startup and shutdown are repeatable.
- [ ] Recovery is limited, documented, and auditable.
- [ ] Failure of one service does not falsely imply the robot is safe or operational.

## Phase 8 — Security, safety, and failure-injection tests

### Objective
Test boundaries and failure behavior before full hardware integration.

### Checklist
- [ ] Test malformed/oversized requests, invalid commands, stale mode, duplicate requests, and unknown protocol versions.
- [ ] Test Pi–ESP32 cable/serial loss, parser errors, missing heartbeat, and delayed acknowledgements using safe test fixtures.
- [ ] Test mobile disconnect, WebSocket disconnect, API restart, Pi restart, and ESP32 reconnect.
- [ ] Verify the documented command timeout and stop path with Tharun.
- [ ] Ensure a failure does not create contradictory state or an unbounded command queue.
- [ ] Review authentication, authorization, request limits, logs, and secret handling.
- [ ] Use simulated/fake transports for automated tests; physical movement tests require an agreed safe test procedure and controlled environment.
- [ ] Record actual test commands, results, and known limitations.

### Exit criteria
- [ ] Core failure modes have reproducible tests.
- [ ] Safety claims are backed by evidence and the hardware owner’s verification.
- [ ] Remaining risks are explicit.

## Phase 9 — Mobile and hardware integration

### Objective
Validate the end-to-end path with the owners of the connected components.

### Checklist
- [ ] Publish the approved API and WebSocket contracts for Niteshvar and keep them versioned.
- [ ] Confirm the app's client behavior against real backend responses.
- [ ] Confirm command acknowledgements and telemetry match ESP32 behavior with Tharun.
- [ ] Test mode changes, movement, stop, emergency stop, diagnostics, and reconnection in the agreed safe test environment.
- [ ] Verify logs allow a request/command to be traced across API, robot manager, and ESP32 transport where supported.
- [ ] Fix contract mismatches at the agreed source of truth rather than adding one-off client workarounds.
- [ ] Document the tested firmware/backend/app versions and the test result.
- [ ] Open focused PRs and request review from the affected owners.

### Exit criteria
- [ ] API, backend, and firmware agree on contract versions.
- [ ] End-to-end behavior is tested and recorded.
- [ ] No known critical interface mismatch is hidden by mock data.

## Phase 10 — Handoff and maintenance

### Objective
Make the backend maintainable by the team.

### Checklist
- [ ] Document installation, configuration, run, test, service, and recovery procedures.
- [ ] Keep architecture, API, protocol, and troubleshooting docs aligned with implementation.
- [ ] Add CI checks for formatting, static analysis, and relevant tests where feasible.
- [ ] Remove debug shortcuts and temporary bypasses.
- [ ] Record unresolved issues and their owner.
- [ ] Summarize completed phases with commit/PR links and test evidence.

### Exit criteria
- [ ] Another team member can reproduce setup and verify the main behaviors.
- [ ] Documentation matches the committed implementation.
- [ ] Known limitations and next dependencies are explicit.

## Phase completion record

For each phase, record:
- **Status:** Not started / In progress / Blocked / Complete
- **Evidence:** commit/PR, test command and result, relevant logs
- **Open issues:** precise unresolved items
- **Contract/version:** the API/protocol revision used
- **Dependency owner:** Tharun, Niteshvar, or another named owner as applicable

## Working rules

1. Inspect existing code and actual hardware evidence before changing behavior.
2. Do not make unilateral changes to shared API/protocol contracts.
3. Debug from logs, minimal reproductions, and evidence; do not guess.
4. Keep changes focused and testable.
5. Do not weaken safety behavior to make a demo pass.
6. Report completion with evidence, then stop for review.
