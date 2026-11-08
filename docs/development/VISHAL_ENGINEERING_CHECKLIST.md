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
- [ ] Obtain Niteshvar's explicit review/approval of the production API contract. Niteshvar's Flutter PR #9 is merged and states that the client targets the Pi API contract documented in `api/README.md`; this confirms implementation alignment, but no separate written contract approval is recorded. Hardware/protocol behavior with Tharun is confirmed for deployed protocol v0.
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
- [x] Create and verify the virtual environment on the target Pi. Tharun ran the robot/API in the Raspberry Pi virtual environment and live health/status/command requests succeeded on 2026-11-08.
- [ ] Keep API routes, robot orchestration, ESP32 communication, safety policy, telemetry, diagnostics, and logging in separate modules consistent with the existing repository structure. The broader diagnostics/logging separation still needs review.
- [x] Keep the API token in environment configuration, outside source control.
- [x] Centralize and validate backend environment settings (API host/port, API token/state DB, model/data/cache paths, Piper binary, face-match debug flag) in `thashu/core/config.py`; invalid ports, blank path overrides, and invalid debug values fail explicitly.
- [x] Add structured JSON logs for move/stop outcomes with severity, timestamp, component, command ID, and sanitized error codes.
- [ ] Extend structured logging across other backend services and request flows. API HTTP requests, robot-process API lifecycle, and ESP32 transport connection/rejection/fault events now emit JSON records. Voice, vision, and user-interaction output still includes console messages and needs a scoped logging review.
- [x] Document startup/shutdown commands and handle unavailable serial hardware without crashing the API; status reports unavailable transport. Full startup behavior on the target Pi has not been verified.
- [x] Add baseline API/protocol tests and document development test commands.

### Exit criteria
- [x] API backend starts in local development and inside the target Pi robot process; live `/health`, `/api/v1/status`, mode, and STOP requests succeeded on 2026-11-08.
- [ ] Configuration and logs are consistent across the full backend. Configuration is centralized; structured logging remains partial.
- [x] Software handles unavailable/disconnected serial hardware as a degraded state; API status tests cover unavailable transport. Physical Pi behavior remains unverified.

**Phase 1 evidence (updated 2026-11-08):** The target Pi virtual environment and embedded robot/API process were exercised. Tharun's live checks returned HTTP 200 for health and status, with ESP32 transport `connected`; authenticated mode and STOP requests also succeeded. Configuration/lifecycle tests on the backend source branch cover invalid settings and server start/stop outcomes. Phase 1 remains in progress because broader voice/vision logging and API module separation need review, and startup/shutdown should be recorded against the exact deployed revision.

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
- [x] Document the deployed v0 protocol and shared test vectors.
- [ ] Add a Pi test that consumes the shared vectors. The current `test_hardware_protocol` test uses fake serial and does not read the vector file; no shared-vector parser harness is present on this branch.
- [x] Do not invent pin mappings or assume the current motor driver; the integrated firmware remains the hardware source of truth.
- [x] Record Tharun-reported v0 parser checks: HEARTBEAT, STOP, EYES, invalid EYES argument, unknown command, partial frames, oversized-frame discard, and recovery. Unsupported-version testing does not apply to v0.
- [ ] Capture live serial output from the existing firmware showing `EVENT|0|READY`, `TEL|0|SENSORS|...`, `ACK|sequence|ALIVE` for HEARTBEAT, and `ACK|sequence|OK` for STOP. Do not reflash; record the firmware/backend revisions with the output. No standalone ESP32 parser-test harness is present in the branch.

### Exit criteria
- [x] Both sides agree on the same documented v0 contract; CMD/ACK frames do not include a protocol-version field.
- [x] Valid, invalid, partial, stale, and unknown messages have defined behavior.
- [x] Transport failures are detectable and cannot silently appear as success.

**Phase 2 evidence (updated 2026-11-08):** The deployed v0 framing is used by the integrated ESP32 parser, Pi client, tests, and shared vectors. Pi protocol tests passed 12/12 on the backend source branch; earlier hardware-protocol tests passed 5/5 after pulling v0. Tharun reports the listed parser checks passed. On the Phase 12 Pi run, status reported transport `connected`, and STOP reached ESP32 `ACK|sequence|OK` (command result `acknowledged`). The exact `EVENT|0|READY`, raw `TEL|0|SENSORS|...`, and HEARTBEAT `ALIVE` capture with firmware/backend revisions is still needed for the live-capture checklist item. No reflash is planned. Protocol v0 correlates ACKs by sequence only and cannot distinguish a delayed ACK after Pi restart if that sequence is reused.

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

**Phase 4 evidence (2026-11-07):** Move/stop routes use the shared robot manager through `ApiServices`. Move schema validation rejects unknown fields/directions and invalid speeds; move/stop bodies are capped at 4 KiB with HTTP 413 for oversized requests. Move/stop/mode requests require `application/json`; missing and non-JSON content types receive HTTP 415, with optional charset accepted. REST errors stay under FastAPI's `detail`; object errors include stable `detail.error_code`, validation errors include sanitized `detail.issues`, and unexpected failures return a generic 500. A route-surface test confirms no shell, raw GPIO, or unrestricted control route is exposed. Move/mode requests that wait over 2 seconds return `API_BUSY` before dispatch; STOP has priority over queued move/mode requests and is not rejected by that queue-wait timeout, but does not interrupt an operation already in progress. Move/mode use the approved shared-token bucket (capacity 10, refill 5/second), returning HTTP 429 before dispatch when exhausted; STOP is authenticated and excluded. Authentication requirements are confirmed with Nitesh. Vishal reports the API suite passed 51/51, covering rate-limit behavior and recovery after a move transport failure; the follow-up status query and STOP still succeed. Duplicate move/STOP requests are protected by the persistent request-id store.

### Exit criteria
- [x] Routes match the documented contract used by the Flutter client. Niteshvar's PR #9, which targets the API contract in `api/README.md`, is merged; private-network/live Pi verification is tracked in Phase 9.
- [x] Invalid and unsafe requests are rejected predictably by schema and robot-safety checks; API and manager tests cover these rejections.
- [x] API failures do not crash core robot services; a simulated move transport failure returns an error, while follow-up status and STOP still work.

## Phase 5 — WebSocket and telemetry

### Objective
Publish useful, consistent live state to the mobile app.

### Checklist
- [x] Align the WebSocket path, authentication, and event/message schema with Niteshvar. His merged PR #9 says it targets the documented Pi API contract; protocol versioning is not part of the current v0 API contract.
- [x] Publish only documented WebSocket event shapes: `esp32_line` with Pi `received_at` and `command_result`. The API does not claim raw lines are command success.
- [x] Distinguish live, stale, unavailable, and unknown values across backend status and the client. API status distinguishes transport availability and keeps untracked readiness `unknown`; the Flutter client derives sensor staleness from Pi receive timestamps.
- [x] Implement WebSocket client disconnect cleanup, bounded backpressure, and telemetry-reader shutdown/restart after all clients disconnect and reconnect.
- [x] Align keepalive and reconnection behavior with Niteshvar: server Ping/Pong uses 20/10 seconds, while Flutter reconnect behavior is covered by the merged client implementation. Live network/server restart verification remains a Phase 9 task.
- [x] Prevent a slow client from blocking robot control or telemetry collection. Serial input is read once and fanned out through per-client bounded queues; oldest queued events are dropped for slow clients, and missed command results remain recoverable by command ID.
- [x] Ensure REST status and WebSocket events derive from the same authoritative Pi manager/transport. The API attaches the robot process's manager once; status and telemetry read that same transport. Controller readiness stays `unknown` until firmware READY tracking is implemented.
- [x] Keep WebSocket events limited to documented fields; tests verify the configured Bearer token is not broadcast.
- [x] Test multiple clients, slow-client queue bounds, and telemetry-reader restart after the last client disconnects; the API suite passed 54/54.
- [x] Test API server restart cleanup and a fresh telemetry connection after restart; the API suite passed 55/55.
- [x] Verify the Flutter client marks sensor data stale after one second without a new sensor frame and clears stale on the next valid frame, including `NA` and `FAR`. Niteshvar's merged PR #9 contains parser/widget tests for this behavior; its description reports Flutter analysis and tests passed. No robot test is claimed.

**Phase 5 evidence (updated 2026-11-08):** The API reads the shared GPIO transport once, fans documented `esp32_line` and `command_result` events to per-client bounded queues, and restarts collection after subscriber reconnect. REST status and WebSocket collection use the same manager/transport instance; status reports controller readiness as `unknown` until a firmware READY tracker is implemented and agreed. Vishal reported the API suite passed 55/55; protocol tests now pass 16/16 with the current logging/backoff and telemetry-edge tests. The stream timestamps each serial frame at Pi receipt. The agreed client behavior is 1-second sensor freshness, refreshed by a valid sensor frame including `NA`/`FAR`, with Uvicorn Ping/Pong at 20/10 seconds. Niteshvar's PR #9 is merged and its description records Flutter analysis/tests passing and alignment to the documented API; physical phone-to-Pi verification remains pending. The full robot verification remains reserved for the final integration branch.

### Exit criteria
- [x] Mobile receives consistent telemetry in component tests against the documented event schema; real network delivery remains pending in Phase 9.
- [x] Stale/disconnected states are unambiguous in the Flutter client and Pi status response (`unknown` readiness is preserved).
- [x] WebSocket traffic cannot block robot command processing; bounded per-client queues are covered by API tests.

## Phase 6 — Diagnostics, logs, and health reporting

### Objective
Make failures observable and actionable without pretending an untested subsystem is healthy.

### Checklist
- [ ] Define diagnostic checks and their evidence source with each subsystem owner. Current API status only reports API/transport/mode and keeps controller readiness unknown; diagnostics fields/routes need an agreed contract before implementation.
- [ ] Use PASS, WARNING, FAIL, and UNKNOWN where that taxonomy is approved; the app/diagnostics taxonomy has not been agreed as a backend response schema.
- [ ] Report timestamps and clear reason codes for failed/unavailable checks.
- [ ] Track API health, ESP32 connection, telemetry freshness, service health, and other implemented components only. API liveness and transport are reported; firmware readiness/fault state and an approved diagnostics response remain open.
- [ ] Provide bounded log retrieval with redaction; do not expose secrets.
- [ ] Separate a check that failed from a check that could not run.
- [ ] Make diagnostic endpoints read-only unless a separate authorized action is explicitly specified.
- [ ] Add tests for missing devices, stale data, malformed telemetry, and log access boundaries. GPIO/manager/API fake suites cover missing, stale, malformed, and secret-safe event/log behavior; there is no log-retrieval endpoint, so endpoint access tests wait for an approved diagnostics contract.

### Exit criteria
- [ ] Reported health reflects evidence, not assumptions.
- [ ] Unknown/unavailable is not silently reported as PASS.
- [ ] Logs and diagnostic responses are bounded and safe to expose.

## Phase 7 — Configuration, service management, and recovery

### Objective
Support predictable startup, shutdown, configuration, and recovery.

### Checklist
- [x] Centralize validated configuration with documented defaults and bounds in `thashu/core/config.py`; tests cover invalid ports, blank path overrides, and invalid boolean values.
- [x] Separate secrets from ordinary configuration and avoid logging them; the API token is environment-backed, auth tests verify fail-closed behavior, and structured API logs exclude the token.
- [x] Define service startup order and readiness checks for API, robot manager, and ESP32 communication. The manager/serial transport is initialized before the embedded API; API startup waits up to five seconds for Uvicorn readiness, while ESP32 controller readiness remains explicitly `unknown` without a READY tracker.
- [x] Handle service shutdown without leaving commands or sockets in an undefined state. API shutdown is requested gracefully, waits up to five seconds, and logs a timeout; telemetry, command tasks, and owned transport have lifespan cleanup.
- [ ] Coordinate restart/reset/recovery actions with Tharun; ensure privileged actions are authenticated and auditable.
- [x] Never use a generic API endpoint to execute arbitrary shell commands; the API route-surface test guards this boundary.
- [x] Add bounded serial reconnect backoff (1, 2, 4, 8, 16, then 30 seconds capped) and avoid rapid endless reconnect attempts. This is reconnect backoff, not an automatic whole-process restart loop.
- [x] Document recovery behavior for Pi reboot, ESP32 disconnect, API startup/shutdown failure, and configuration error in `api/PI_SETUP.md`.
- [ ] Verify safety behavior remains owned by the Pi/ESP32 layers even if the mobile app disappears.

### Exit criteria
- [x] Startup and shutdown are repeatable in component lifecycle tests; target-Pi behavior remains for Phase 9.
- [x] Recovery is bounded and documented; serial retries cap at 30 seconds and no movement command is automatically replayed after restart.
- [x] API or controller-link failure does not imply robot readiness; health and status separate API liveness, transport, and unknown controller readiness.

## Phase 8 — Security, safety, and failure-injection tests

### Objective
Test boundaries and failure behavior before full hardware integration.

### Checklist
- [x] Test malformed/oversized requests, invalid commands, stale mode, and duplicate requests with fake transports. Unknown-version testing is not applicable to deployed protocol v0, which has no version field; the Pi test rejects a versioned ACK as unsupported input.
- [x] Test serial silence/reconnect, partial and oversized parser frames, delayed acknowledgements, and separation of `ACK|sequence|ALIVE` from command ACKs using fake fixtures. The physical ESP32 watchdog response to a missed Pi heartbeat remains for final integration.
- [x] Exercise mobile/WebSocket disconnect, API service restart with persistent state, and ESP32 transport reconnect in component tests; actual Pi power-cycle verification remains for final integration.
- [ ] Verify the documented command timeout and stop path with Tharun.
- [x] Ensure a failure does not create contradictory state or an unbounded command queue; manager mode/STOP concurrency, API queue limits, failure recovery, and bounded WebSocket queues have fake-based coverage.
- [x] Review authentication, authorization, request limits, logs, and secret handling; API tests cover Bearer authentication, route surface, rate limits, and token exclusion from telemetry events.
- [x] Use simulated/fake transports for automated tests; physical movement tests require an agreed safe test procedure and controlled environment. Physical tests remain reserved for final integration.
- [x] Record actual test commands, results, and known limitations in this checklist and the API/protocol documentation.

### Exit criteria
- [x] Core software failure modes have reproducible fake-based tests; physical watchdog and stop behavior remain pending.
- [ ] Safety claims are backed by evidence and the hardware owner’s verification.
- [x] Remaining risks are explicit in this checklist and the contract-gap document.

**Phase 8 evidence (updated 2026-11-08):** Automated fixtures cover request validation/size limits, modes and command conflicts, idempotent retries, ACK timeout/safety errors, serial framing/recovery/backoff, receive silence, delayed ACK delivery, reconnect, WebSocket disconnect/restart, and bounded queues. Local tests pass: GPIO protocol 16/16, API lifecycle 6/6, and robot manager 25/25. API tests were last reported by Vishal as passing 55/55; this workspace's Windows asyncio event-loop setup prevented rerunning that suite locally. GitHub Actions for prior commit `7a02bba` passed Python 3.11 syntax and the backend test suites (run 42465518411), before the current uncommitted lifecycle/backoff changes. A fresh hosted run is needed after those changes are committed and pushed. The ESP32 physical watchdog and Tharun's hardware timeout/STOP verification remain for final integration. Protocol v0 has no version field, so unknown-version behavior is not a deployed-v0 test case.

## Phase 9 — Mobile and hardware integration

### Objective
Validate the end-to-end path with the owners of the connected components.

### Checklist
- [x] Publish the current API and WebSocket contracts for Niteshvar in `api/README.md`; his merged PR #9 records implementation against this documented contract. Live deployment details remain pending.
- [ ] Confirm the app's client behavior against real backend responses. Pi-local `curl` requests verified basic REST responses. The HTTPS-only Flutter connection form and secure runtime client wiring are now present on `phase-12-pi-api-https`; Flutter build and phone-to-Pi verification remain pending.
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
- [x] Document installation, configuration, run, test, service, and recovery procedures in `api/PI_SETUP.md` and `api/README.md`.
- [x] Keep architecture, API, protocol, and troubleshooting docs aligned with implementation; remaining unapproved diagnostic/E-stop behavior is explicitly listed as pending.
- [ ] Add CI checks for formatting and static analysis where feasible. The current local workflow now also includes API lifecycle tests; hosted run 42465518411 passed Python 3.11 syntax and the earlier API, Pi protocol, and robot-manager suites on commit `7a02bba`. The new lifecycle/backoff/logging changes require a fresh CI run after they are committed/pushed.
- [x] Remove debug shortcuts and temporary bypasses. No authentication or robot-safety bypass is enabled; face-match debug logging is a documented opt-in configuration flag.
- [x] Record unresolved issues and their owners in the phase summary and contract-gap document.
- [x] Summarize completed component work and open dependencies in the phase summary, with commit/PR and test evidence below.

### Exit criteria
- [ ] Another team member can reproduce setup and verify the main behaviors on the target Pi; target-Pi setup remains pending.
- [x] Documentation matches the implemented contract and current backend behavior.
- [x] Known limitations and dependencies are explicit, including target-Pi setup, hardware captures, E-stop protocol, private network, diagnostics contract, and formatting/static-analysis CI.

## Phase completion record

For each phase, record:
- **Status:** Not started / In progress / Blocked / Complete
- **Evidence:** commit/PR, test command and result, relevant logs
- **Open issues:** precise unresolved items
- **Contract/version:** the API/protocol revision used
- **Dependency owner:** Tharun, Niteshvar, or another named owner as applicable

### Current phase summary (2026-11-08)

| Phase | Status | Remaining item(s) |
|---|---|---|
| 0 — Architecture/contracts | In progress | Record explicit API-contract approval; implementation alignment is evidenced by merged Flutter PR #9. |
| 1 — Service foundation | In progress | Review broader API module separation and voice/vision logging; capture startup/shutdown against the deployed revision. |
| 2 — Serial protocol | In progress | Capture READY, raw telemetry, and heartbeat ACK with revisions. Pi status and STOP ACK now verified during the Phase 12 run. |
| 3 — Robot manager/modes | In progress | Latched Emergency Stop requires a tested ESP32 protocol/firmware change before Pi support. |
| 4 — REST API | Complete for component implementation | Live Pi/client verification is in Phase 9. |
| 5 — WebSocket/telemetry | In progress | Backend/client contract and component logic are implemented; private-network/server-restart integration is pending. |
| 6 — Diagnostics | In progress | Agree diagnostic checks, state taxonomy, freshness/readiness fields, and any log retrieval contract with owners before adding API surface. |
| 7 — Configuration/recovery | In progress | Coordinate restart/reset procedure and confirm the layered safety behavior with Tharun. |
| 8 — Security/failure tests | In progress | Automated fake-based checks are covered; STOP ACK passed on Pi. Physical watchdog and movement-timeout evidence remains. |
| 9 — Mobile/hardware integration | In progress | Pi-local REST health/status/auth/mode/STOP checks passed; phone-to-Pi HTTPS/WebSocket, API movement, telemetry recovery, and app diagnostics remain. |
| 10 — Handoff | In progress | Run tests/CI for this integration revision, add formatting/static analysis where practical, and verify a second-person setup. |

**Latest repository evidence (updated 2026-11-08):** The API integration is being carried on `phase-12-pi-api-https`, based on current `main`. The Pi-local run verified `/health`, `/api/v1/status`, an unauthenticated 401, MANUAL/AUTO mode switches, and STOP dispatch followed by an acknowledged command result. The HTTPS-only Flutter settings form now stores the Pi origin/token securely and wires REST/WebSocket clients at startup. Flutter dependency resolution/build and phone-to-Pi verification remain pending. Tharun reports the robot movement test passed, but the posted output does not establish that Flutter or the API `/move` route was used. Niteshvar's [Flutter PR #9](https://github.com/sg9242182-bot/ThashuRobot/pull/9) is merged and reports Flutter analysis/tests passing. Phone-to-Pi HTTPS/WebSocket verification, authenticated API movement evidence, latched E-stop, an approved diagnostics contract, and privileged recovery controls remain open. The current Phase 12 branch still needs fresh automated test/CI evidence after its integration changes.

## Working rules

1. Inspect existing code and actual hardware evidence before changing behavior.
2. Do not make unilateral changes to shared API/protocol contracts.
3. Debug from logs, minimal reproductions, and evidence; do not guess.
4. Keep changes focused and testable.
5. Do not weaken safety behavior to make a demo pass.
6. Report completion with evidence, then stop for review.
