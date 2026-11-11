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
- [x] Obtain Niteshvar's explicit review/approval of the production API contract. Tharun confirmed on 2026-11-09 that Niteshvar agreed to the production API contract; Flutter PR #9 is merged against `api/README.md`. Hardware/protocol behavior with Tharun is confirmed for deployed protocol v0.
- [x] Record unresolved decisions in repository documentation or a focused issue.
- [x] Do not claim an interface is approved solely because it appears in an AI-generated draft.

**Phase 0 completion evidence (2026-11-09):** Tharun reports Niteshvar explicitly agreed to the production API contract; this closes the last open Phase 0 approval item. Existing behavior, unresolved decisions, and owners were documented before changes.

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
- [x] Complete the Phase 1 API module, logging, and service-foundation review and verification. Tharun reports Phase 1 is complete; this status is based on his team verification report.
- [x] Keep the API token in environment configuration, outside source control.
- [x] Centralize and validate backend environment settings (API host/port, API token/state DB, model/data/cache paths, Piper binary, face-match debug flag) in `thashu/core/config.py`; invalid ports, blank path overrides, and invalid debug values fail explicitly.
- [x] Add structured JSON logs for move/stop outcomes with severity, timestamp, component, command ID, and sanitized error codes.
- [x] Complete the Phase 1 structured-logging review and verification. Tharun reports the remaining Phase 1 work is complete; preserve the existing privacy requirements for logs.
- [x] Document startup/shutdown commands and handle unavailable serial hardware without crashing the API; status reports unavailable transport. Full startup behavior on the target Pi has not been verified.
- [x] Add baseline API/protocol tests and document development test commands.

### Exit criteria
- [x] API backend starts in local development and inside the target Pi robot process; live `/health`, `/api/v1/status`, mode, and STOP requests succeeded on 2026-11-08.
- [x] Phase 1 service configuration, logging, and module review are complete per Tharun's verification report.
- [x] Software handles unavailable/disconnected serial hardware as a degraded state; API status tests cover unavailable transport. Physical Pi behavior remains unverified.

**Phase 1 evidence (updated 2026-11-08):** Tharun reports the Phase 1 review and verification are complete. Target-Pi environment, API health/status, authenticated mode/STOP requests, configuration, and service lifecycle were verified. Exact test output and deployed revision were not included with the latest completion confirmation.

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
- [x] Document the deployed v0 protocol.
- [x] Add a language-neutral shared-vector file and connect Pi tests to it. `thashu/tests/protocol_vectors.json` is consumed by `test_shared_protocol_v0_vectors` in `thashu/tests/test_hardware_protocol.py`; Tharun ran `PYTHONPATH=thashu python -m unittest thashu.tests.test_hardware_protocol` on commit `f3a646f` and all 6 tests passed. The vectors cover Pi transmit frames; the ESP32 parser does not yet consume the fixture, and no standalone parser harness is present.
- [x] Do not invent pin mappings or assume the current motor driver; the integrated firmware remains the hardware source of truth.
- [x] Record Tharun-reported v0 parser checks: HEARTBEAT, STOP, EYES, invalid EYES argument, unknown command, partial frames, oversized-frame discard, and recovery. Unsupported-version testing does not apply to v0.
- [x] Verify live ESP32 telemetry and heartbeat on the Pi without reflashing. Tharun's 2026-11-08 run received 377 telemetry frames (mean interval 80 ms, longest 108 ms) and 20/20 HEARTBEAT ACKs (mean round trip 41.3 ms, maximum 66.6 ms). The API STOP command lookup also returned `acknowledged` with no error.
- [x] Complete Phase 2 serial-protocol verification with Tharun. Tharun reports Phase 2 testing is complete; do not require a standalone ESP32 parser harness. Exact test output and firmware/backend revisions were not included with the latest completion confirmation.

### Exit criteria
- [x] Both sides agree on the same documented v0 contract; CMD/ACK frames do not include a protocol-version field.
- [x] Valid, invalid, partial, stale, and unknown messages have defined behavior.
- [x] Transport failures are detectable and cannot silently appear as success.

**Phase 2 evidence (updated 2026-11-09):** Tharun reports Phase 2 testing is complete. Existing records cover deployed v0 framing, Pi protocol/shared-vector tests, firmware parser checks, live telemetry/heartbeat, and STOP acknowledgement. Exact test output and firmware/backend revisions were not included with the latest completion confirmation. No reflash is planned. Protocol v0 correlates ACKs by sequence only and cannot distinguish a delayed ACK after Pi restart if that sequence is reused.

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
- [x] Confirm Emergency Stop is outside Phase 3 scope by team decision. Phase 3 does not implement or claim a latched ESP32 Emergency Stop.
- [x] Keep API routes from independently mutating low-level state; they dispatch through the robot manager.
- [x] Keep motor actuation and hardware safety logic on the ESP32; the Pi sends semantic commands.

### Exit criteria
- [x] One authoritative Pi service coordinates API/voice motor dispatch and its tracked mode.
- [x] Conflicting commands are safely serialized through the shared manager lock; a concurrent move/STOP test verifies they do not overlap.
- [x] API responses distinguish Pi dispatch from later ESP32 ACK, safety rejection, or timeout.

**Phase 3 evidence (2026-11-05):** The shared Pi manager now supports an explicit mode request, waits for `ACK|sequence|OK` before switching, inhibits movement after an unconfirmed mode STOP, and keeps AUTO paused until the existing follow-start action enables it. User-requested STOP cancels Pi movement/follow timers and returns to AUTO paused. Movement dispatch requires a fresh sensor snapshot (maximum 750 ms), treats `FAR` as clear, blocks `NA`/missing/stale readings and sends STOP, uses the existing 300 mm threshold, and leaves ESP32 safety interlocks authoritative. Control-state versions prevent a movement waiting across a STOP/mode change from being dispatched afterward. Bounded follow pulses stop without canceling the explicitly started Auto session. After persistent request ID idempotency was added for move and STOP, the combined API and robot-manager suites passed 61/61. In-flight records found after restart return unknown and are never replayed. Tharun reports the integrated mode/STOP behavior is working. Emergency Stop was removed from Phase 3 scope by team decision; no latched Emergency Stop behavior is claimed.

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
- [x] Agree the four diagnostic checks and evidence sources with the subsystem owners. Vishal approved the contract and Niteshvar confirmed the exact schema on 2026-11-09.
- [x] Use the approved PASS, WARNING, FAIL, and UNKNOWN status values.
- [x] Include UTC timestamps, stable reason codes, and sensor-only required-but-nullable `age_ms`; compute sensor age from the latest complete valid frame.
- [x] Report only API liveness, ESP32 transport, sensor telemetry freshness, and controller readiness. GPIO tracks `EVENT|0|READY` on the current connection; readiness remains UNKNOWN until observed.
- [x] Keep remote log retrieval out of scope. Detailed logs stay on the Pi for local troubleshooting.
- [x] Distinguish failed checks from unavailable or unobserved checks using the approved reason codes and UNKNOWN status.
- [x] Keep `GET /api/v1/diagnostics` read-only and Bearer-authenticated.
- [x] Add tests for missing/unavailable state, stale telemetry, READY tracking, and the route's authenticated read-only surface. GitHub Actions run 42512821791 passed the combined API and Pi hardware-protocol suites: 73 tests passed on commit `8eff718`. `GPIOControl.get_sensor_freshness(max_age=1.0)` preserves the stricter 200 ms safety snapshot rule and leaves WebSocket `received_at` unchanged.

### Exit criteria
- [x] Reported health reflects evidence, not assumptions; the diagnostics tests cover connected, disconnected, fresh, stale, unobserved, and unavailable states.
- [x] Unknown/unavailable is not silently reported as PASS; tests verify the UNKNOWN mappings and required nullable sensor `age_ms`.
- [x] Diagnostic responses are bounded and safe to expose; the route returns only four fixed checks and no logs, tokens, or free-form exception details.

## Phase 7 — Configuration, service management, and recovery

### Objective
Support predictable startup, shutdown, configuration, and recovery.

### Checklist
- [x] Centralize validated configuration with documented defaults and bounds in `thashu/core/config.py`; tests cover invalid ports, blank path overrides, and invalid boolean values.
- [x] Separate secrets from ordinary configuration and avoid logging them; the API token is environment-backed, auth tests verify fail-closed behavior, and structured API logs exclude the token.
- [x] Define service startup order and readiness checks for API, robot manager, and ESP32 communication. The manager/serial transport is initialized before the embedded API; API startup waits up to five seconds for Uvicorn readiness, while ESP32 controller readiness remains explicitly `unknown` without a READY tracker.
- [x] Handle service shutdown without leaving commands or sockets in an undefined state. API shutdown is requested gracefully, waits up to five seconds, and logs a timeout; telemetry, command tasks, and owned transport have lifespan cleanup.
- [x] Coordinate recovery behavior with Tharun: no remote reset is in scope; normal STOP stays authenticated and audited. Tharun agreed to a 250 ms manual-lease renewal cadence with a provisional 500 ms expiry; Nitesh's Flutter implementation confirmation and hardware stopping-distance test remain pending.
- [x] Never use a generic API endpoint to execute arbitrary shell commands; the API route-surface test guards this boundary.
- [x] Add bounded serial reconnect backoff (1, 2, 4, 8, 16, then 30 seconds capped) and avoid rapid endless reconnect attempts. This is reconnect backoff, not an automatic whole-process restart loop.
- [x] Document recovery behavior for Pi reboot, ESP32 disconnect, API startup/shutdown failure, and configuration error in `api/PI_SETUP.md`.
- [ ] Verify safety behavior remains owned by the Pi/ESP32 layers even if the mobile app disappears. Backend code gates move/renew on an authenticated telemetry connection, expires the manual lease, and dispatches normal STOP. Fake coverage and GitHub Actions run #33 passed on commit `bf702e9`. Tharun confirmed the firmware's 300 mm obstacle-stop threshold; the restrained stopping-distance test for the provisional 500 ms movement lease (Tharun) and Flutter app disconnect/restart integration checks (Niteshvar) remain pending.

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
- [x] Integrate the offline phone-hotspot path with the Flutter client: BLE delivers URL, certificate fingerprint, and token; Flutter pins HTTPS and WSS and stores credentials securely. Tharun reports the integrated debug APK installed on his phone; analysis passed and all 62 Flutter tests passed.
- [x] Keep the main API on loopback and bind the optional local TLS listener only to the current Wi-Fi address. The listener is additionally gated on the exact NetworkManager profile created by provisioning and the hotspot gateway as client source; other profiles/clients are denied.
- [ ] Verify the Android/Pi authenticated BLE numeric-comparison pairing on hardware, including mismatch and timeout rejection. The Pi speaks the six-digit value; the user compares it to Android's system prompt and confirms on the Pi button.
- [ ] Verify the phone's source IP matches the active hotspot gateway, then test pinned HTTPS/WSS status and telemetry, reconnect, IP/certificate change, and Pi restart with internet disabled. Do not send movement commands during onboarding.
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
- [x] Add CI checks for formatting, static analysis, and automated tests. GitHub Actions now runs Ruff formatting checks for the backend configuration modules, Ruff correctness/static checks for the API and Pi backend modules, and the API, robot-manager, hardware-protocol, and runtime-cleanup unit suites (workflow commit `9dc6567`). The first hosted runs exposed formatting differences, test module names that are absent on this branch, and a stale STOP expectation. Those fixes are now committed; rerun result is pending, so do not claim the checks passed until GitHub reports success.
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

### Current phase summary (updated 2026-11-09)

| Phase | Status | Remaining item(s) |
|---|---|---|
| 0 — Architecture/contracts | Complete | Niteshvar's explicit API-contract agreement was confirmed by Tharun on 2026-11-09; implementation alignment is also evidenced by merged Flutter PR #9. |
| 1 — Service foundation | Complete | Tharun reports Phase 1 review and verification complete; exact test output/deployed revision should be recorded when available. |
| 2 — Serial protocol | Complete | Tharun reports Phase 2 testing complete; exact test output and firmware/backend revisions should be recorded when available. |
| 3 — Robot manager/modes | Complete | Emergency Stop was removed from Phase 3 scope; remaining mode, STOP, and command-lifecycle work is complete per the checklist and Tharun's report. |
| 4 — REST API | Complete for component implementation | Live Pi/client verification is in Phase 9. |
| 5 — WebSocket/telemetry | In progress | Backend/client contract and component logic are implemented; private-network/server-restart integration is pending. |
| 6 — Diagnostics | Complete | Approved contract and read-only diagnostics endpoint implemented; GitHub Actions run 42512821791 passed 73 API/protocol tests. Flutter client work is tracked in Phase 9. |
| 7 — Configuration/recovery | In progress | Backend movement lease and startup STOP are implemented on `phase-12-pi-api-https`; fake coverage and GitHub Actions run #33 passed on commit `bf702e9`. Tharun confirmed the 300 mm obstacle-stop threshold, but this does not verify the provisional 500 ms movement-lease timeout. Flutter renewal/disconnect/restart integration and the restrained lease stopping-distance test remain open; flashed firmware revision is unknown. |
| 8 — Security/failure tests | In progress | Automated fake-based checks are covered; STOP ACK passed on Pi. Physical watchdog and movement-timeout evidence remains. |
| 9 — Mobile/hardware integration | In progress | App build/tests passed and app installed. Authenticated BLE pairing, hotspot-only listener reachability, pinned HTTPS/WSS, reconnect, and restart still need supervised Pi/phone evidence. |
| 10 — Handoff | In progress | Formatting/static-analysis and backend test checks are configured in GitHub Actions; latest result pending. A second person still needs to reproduce setup and verify the main behaviors on the target Pi. |

**Latest repository evidence (updated 2026-11-11):** Pi-local REST health/status/auth/mode/STOP checks were previously reported passing. The offline Flutter integration was built from commit `0d699b2`; Tharun reports installation on his Android phone, analysis clean, and 62 tests passing. This security update adds authenticated BLE numeric comparison plus a physical confirmation and ties the local TLS listener to the provisioned NetworkManager profile and hotspot gateway. Python syntax and six focused backend gate tests pass; Flutter analysis, 62 tests, and debug APK build pass. The new authenticated pairing and real hotspot gateway behavior have not yet been verified on Pi hardware. Keep Phase 9 in progress until a supervised no-movement phone/Pi test confirms pairing, pinned HTTPS/WSS, status, telemetry, reconnect, changed IP/certificate rejection, and restart behavior.

## Working rules

1. Inspect existing code and actual hardware evidence before changing behavior.
2. Do not make unilateral changes to shared API/protocol contracts.
3. Debug from logs, minimal reproductions, and evidence; do not guess.
4. Keep changes focused and testable.
5. Do not weaken safety behavior to make a demo pass.
6. Report completion with evidence, then stop for review.
