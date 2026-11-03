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
- [ ] Centralize and validate the rest of the backend configuration.
- [x] Add structured JSON logs for move/stop outcomes with severity, timestamp, component, command ID, and sanitized error codes.
- [ ] Extend structured logging across other backend services and request flows.
- [x] Document startup/shutdown commands and handle unavailable serial hardware without crashing the API; status reports unavailable transport. Full startup behavior on the target Pi has not been verified.
- [x] Add baseline API/protocol tests and document development test commands.

### Exit criteria
- [x] API-only backend starts in local development (Vishal verified it in Swagger). Full robot-process startup on the Pi remains unverified.
- [ ] Configuration and logs are consistent across the full backend.
- [x] Software handles unavailable/disconnected serial hardware as a degraded state; API status tests cover unavailable transport. Physical Pi behavior remains unverified.

**Phase 1 evidence (2026-11-03):** Pi Setup documents Bookworm/Python 3.11.2, API dependencies, token configuration, and start/stop commands. Vishal previously reported 13/13 API tests passing; protocol tests passed 9/9 after the latest Pi transport changes. Phase 1 remains in progress because the target-Pi virtual environment/startup and full-backend configuration/logging review are still open.

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
- [ ] Compile/upload the branch-aligned ESP32 firmware and verify Pi integration with the v0 client; record the tested firmware/backend revisions and result. No standalone ESP32 parser-test harness is present in the branch.

### Exit criteria
- [x] Both sides agree on the same documented v0 contract; CMD/ACK frames do not include a protocol-version field.
- [x] Valid, invalid, partial, stale, and unknown messages have defined behavior.
- [x] Transport failures are detectable and cannot silently appear as success.

**Phase 2 evidence (2026-11-03):** The `vishal-phase1` branch uses the deployed v0 framing in the integrated ESP32 parser, Pi client, tests, and shared vectors. Pi framing tests passed 9/9 and hardware-protocol tests passed 5/5 after pulling v0. Tharun reports the listed v0 parser checks passed; this is reported evidence, not a standalone parser-test harness result. Compile/upload of the branch-aligned firmware and Pi integration verification remain open. v0 matches ACKs by sequence only and cannot distinguish a delayed ACK after a Pi restart if the sequence is reused.

## Phase 3 — Robot manager, modes, and command lifecycle

### Objective
Provide one authoritative high-level component for robot state and command coordination.

### Checklist
- [ ] Implement or verify a single robot manager/service that owns the high-level mode and command lifecycle.
- [ ] Define legal mode transitions with Tharun and the team; Manual and Auto must not control the robot simultaneously.
- [ ] Route movement commands through validation, mode checks, dispatch, acknowledgement, and result reporting.
- [ ] Define safe-stop transition behavior before switching modes.
- [ ] Handle command timeout, rejection, duplicate request, stale state, and uncertain dispatch outcomes explicitly.
- [ ] Make Emergency Stop priority and semantics consistent with the approved safety contract.
- [ ] Do not let API routes independently mutate low-level state or bypass the robot manager.
- [ ] Keep hardware-specific timing and motor logic on the ESP32.

### Exit criteria
- [ ] One authoritative service coordinates commands and mode state.
- [ ] Conflicting commands are rejected or safely serialized according to the contract.
- [ ] API responses distinguish known success from unknown outcome.

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
- [ ] Implement route handlers as thin adapters over the robot manager/services.
- [ ] Validate content type, payload structure, command ranges, allowed enum values, and request size.
- [ ] Use consistent response/error envelopes and documented HTTP status codes.
- [ ] Add request timeouts and avoid blocking the API event loop/thread with long-running hardware work.
- [ ] Define authentication and authorization requirements with the team before exposing privileged operations.
- [ ] Apply rate limiting or duplicate-command protection where required by the threat model and command semantics.
- [ ] Do not expose arbitrary shell execution, unrestricted filesystem access, or unrestricted hardware control.
- [ ] Keep OpenAPI/schema documentation and tests synchronized with implementation.
- [ ] Add tests for success, malformed input, unauthorized access, backend unavailable, hardware disconnected, and timeout.

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
