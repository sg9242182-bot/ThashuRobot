# Niteshvar Engineering Checklist — Flutter Mobile Application

**Project:** THASHU — Intelligent Self-Reliant Robot  
**Owner:** Niteshvar  
**Area:** Flutter Android application  
**Status:** Phased implementation plan  
**Source of truth:** Approved repository architecture, API contracts, protocol documents, and recorded architecture decisions.

> This checklist defines Niteshvar's work. Complete phases in order unless a dependency is explicitly approved. A phase is complete only when its exit criteria are met and the result is committed. A screen that merely looks finished is not considered integrated.

---

## Mission and boundaries

Build the Android-first Flutter application that lets a person monitor and command Thashu through the Raspberry Pi's approved API.

The mobile app owns presentation, user interaction, client-side state, request/response handling, and display of telemetry. It does **not** own robot decisions, direct GPIO access, motor-driver logic, sensor drivers, or the Pi–ESP32 serial protocol.

### Fixed architectural boundaries

- Flutter communicates with the Raspberry Pi API, not directly with the ESP32.
- Use REST for request/response operations and WebSocket for live telemetry/state, according to the approved API contract.
- Do not invent endpoints, JSON fields, enum values, authentication rules, or WebSocket message shapes. Use the checked-in contract; if a required contract is missing, document the gap and request agreement from Tharun and Vishal.
- Manual and Auto modes must not conflict. Show the authoritative mode reported by the robot and respect backend rejection/error responses.
- A mobile connection loss must not be treated as proof that the robot has stopped. The robot-side timeout and ESP32 safety behavior are implemented by the robot/backend owners.
- An Emergency Stop control must use the approved stop mechanism and clearly report whether the request was accepted. Do not claim a physical stop is confirmed unless the API provides confirmation.
- Never expose shell commands, raw hardware pins, motor-driver details, or unrestricted backend operations in the app.
- Keep Competition Mode simple and predictable; keep advanced diagnostics and development actions in Developer Mode.
- Do not add features or alter architecture solely because an AI assistant suggests them.

## Phase 0 — Architecture and interface readiness

### Objective
Understand the approved system boundaries before writing application logic.

### Checklist
- [ ] Read the root README and relevant architecture/development documentation.
- [ ] Confirm the Flutter app's location in the repository and current Flutter/Dart versions.
- [ ] Identify the API base URL configuration approach for emulator, local network, and eventual robot deployment.
- [ ] Review the approved REST endpoint list and request/response schemas.
- [ ] Review the approved WebSocket connection, telemetry, error, and reconnect contract.
- [ ] Record which API fields or behaviors are not yet specified; do not guess.
- [ ] Confirm the expected Manual/Auto mode behavior and emergency-stop semantics with the backend owner.
- [ ] Confirm ownership: Niteshvar owns mobile UI/client; Vishal owns the Pi API; Tharun owns robot/hardware decisions and safety integration.

### Exit criteria
- [ ] The app can be implemented without inventing backend contracts.
- [ ] Missing interfaces are written down and assigned for agreement.
- [ ] No low-level hardware responsibilities have been moved into Flutter.

## Phase 1 — Flutter project foundation

### Objective
Create a reproducible, runnable Flutter project without losing existing work.

### Checklist
- [ ] Check whether the Flutter project already exists before running `flutter create`.
- [ ] Record the project path and verify `flutter doctor`.
- [ ] Run `flutter pub get` and launch the unmodified app on the available Android emulator/device.
- [ ] Preserve the valid `lib/main.dart` entry point.
- [ ] Establish a small, understandable structure, adapting existing files rather than recreating them blindly:
  - `app/` — app setup, routing, theme
  - `core/` — shared constants and utilities
  - `models/` — typed API/telemetry models
  - `services/` — REST and WebSocket clients
  - `features/` — dashboard, manual control, settings, diagnostics, developer
  - `widgets/` — reusable UI components
- [ ] Add only necessary dependencies; document why each non-standard dependency is needed.
- [ ] Ensure secrets and private credentials are not committed.

### Exit criteria
- [ ] App builds and opens on Android.
- [ ] Folder structure is understandable and the entry point remains intact.
- [ ] Setup steps are documented and a baseline commit exists.

## Phase 2 — App shell, navigation, and visual system

### Objective
Build the navigable app foundation before wiring robot behavior.

### Checklist
- [ ] Implement the agreed app theme, typography, spacing, and reusable components.
- [ ] Add navigation for Dashboard, Manual Control, Settings, Diagnostics, and Developer/Recovery.
- [ ] Make loading, empty, offline, unavailable, and error states explicit.
- [ ] Ensure layouts work on the target Android screen sizes and remain accessible.
- [ ] Keep navigation and widgets separate from network implementation.
- [ ] Use mock/sample data only when clearly marked as mock; never present it as live robot data.

### Exit criteria
- [ ] All agreed screens can be navigated.
- [ ] Shared visual components are reused.
- [ ] UI clearly distinguishes real data from placeholders.

## Phase 3 — Typed models and REST client

### Objective
Create one controlled boundary for HTTP requests and responses.

### Checklist
- [ ] Implement typed models only from approved schemas.
- [ ] Centralize base URL, request timeouts, headers, and error translation.
- [ ] Implement the agreed status, movement, stop, emergency-stop, mode, reset, settings, diagnostics, logs, and system calls only where defined by the contract.
- [ ] Validate user inputs and allowed command ranges at the UI/client boundary; backend validation remains authoritative.
- [ ] Handle timeout, unreachable host, malformed response, unsupported version, unauthorized request, and server error states.
- [ ] Prevent duplicate taps/repeated requests where they could create conflicting commands.
- [ ] Never silently convert a failed command into a success state.
- [ ] Add unit tests for parsing, validation, and error mapping.

### Exit criteria
- [ ] API calls match the checked-in contract exactly.
- [ ] Failure states are testable and visible.
- [ ] No guessed endpoints or response fields remain.

## Phase 4 — Dashboard and connection state

### Objective
Present an honest summary of the robot's reported state.

### Checklist
- [ ] Display connection status separately from robot operational status.
- [ ] Display reported mode, readiness/health, and available telemetry fields defined by the contract.
- [ ] Show stale-data/disconnected state when updates stop; do not leave old values looking current.
- [ ] Add deliberate refresh behavior where appropriate.
- [ ] Avoid inferring sensor or motor state from UI actions alone.
- [ ] Test startup when the robot is unavailable and recovery when it becomes reachable.

### Exit criteria
- [ ] Dashboard works online and offline.
- [ ] Stale and unknown values are clearly identified.
- [ ] Status is based on backend-reported data.

## Phase 5 — Manual control and safe interaction

### Objective
Provide predictable operator controls without bypassing robot-side safety.

### Checklist
- [ ] Implement controls only for movement commands and parameters approved by the API contract.
- [ ] Make the current mode and command-in-progress state visible.
- [ ] Prevent manual drive controls from appearing active/usable when the robot reports Auto mode or another incompatible state.
- [ ] Provide an accessible Stop control and the approved Emergency Stop action.
- [ ] Define UI behavior for command accepted, rejected, timed out, and unknown outcome.
- [ ] On app pause/disconnect, do not claim the robot stopped; show connection loss and rely on robot-side watchdogs.
- [ ] Do not implement a phone-only safety timeout as a substitute for Pi/ESP32 safety.
- [ ] Test repeated taps, slow networks, lost responses, mode changes, and reconnection.
- [ ] Coordinate any ambiguous behavior with Tharun and Vishal before implementation.

### Exit criteria
- [ ] Conflicting controls are prevented by state-aware UI and backend responses.
- [ ] Stop/emergency-stop feedback is truthful.
- [ ] Network failures never create false success indicators.

## Phase 6 — WebSocket telemetry and reconnection

### Objective
Show live robot state through the agreed WebSocket contract.

### Checklist
- [ ] Implement the approved connection and message parsing rules.
- [ ] Track connecting, connected, reconnecting, disconnected, and failed states.
- [ ] Handle malformed messages and unknown message types without crashing.
- [ ] Avoid unbounded reconnect loops; use an appropriate bounded/backoff strategy consistent with project requirements.
- [ ] Dispose subscriptions and sockets correctly when services/screens are closed.
- [ ] Mark telemetry stale after the contract's agreed freshness interval.
- [ ] Ensure REST responses and WebSocket updates do not cause contradictory UI state.
- [ ] Test disconnect/reconnect and server restart scenarios.

### Exit criteria
- [ ] Telemetry updates without repeated manual refresh.
- [ ] Stale/offline states are visible.
- [ ] Reconnect and disposal behavior is tested.

## Phase 7 — Settings, diagnostics, Competition Mode, Developer Mode

### Objective
Complete the remaining operator workflows while respecting permissions and ownership.

### Checklist
- [ ] Build Settings only for configuration values supported by the approved API.
- [ ] Display diagnostics using backend-provided PASS, WARNING, FAIL, or UNKNOWN states where that contract is adopted.
- [ ] Show timestamps, useful descriptions, and safe next steps for diagnostic results where available.
- [ ] Keep Competition Mode focused on the agreed, minimal operator workflow.
- [ ] Keep Developer Mode separate and clearly label advanced/recovery operations.
- [ ] Gate any privileged action according to the approved authentication/authorization design.
- [ ] Never expose arbitrary shell execution or unbounded hardware commands.
- [ ] Confirm reset/recovery behavior with the backend owner before exposing controls.
- [ ] Handle unavailable diagnostic data without fabricating results.

### Exit criteria
- [ ] All screens use real contract-backed data or clearly marked placeholders.
- [ ] Developer actions cannot bypass backend authorization or robot safety.
- [ ] Competition Mode remains simple and reliable.

## Phase 8 — Integration testing and handoff

### Objective
Prove the mobile client works against the actual Pi API and document how to run it.

### Checklist
- [ ] Run formatter and static analysis.
- [ ] Run unit/widget tests and fix regressions.
- [ ] Test against a mock server or approved test fixture before live hardware.
- [ ] With the team, test connection loss, Pi restart, WebSocket loss, API errors, mode transitions, and stop behavior.
- [ ] Confirm the API contract version/commit used for testing.
- [ ] Do not run physical movement tests without a safe test area, secured robot, and an agreed test procedure.
- [ ] Document setup, configuration, emulator networking, and troubleshooting.
- [ ] Open a focused PR describing changes, tests, and any remaining gaps.
- [ ] Request review from Vishal for API/client compatibility and Tharun for control/safety behavior.

### Exit criteria
- [ ] Build, analysis, and relevant tests pass.
- [ ] No unresolved contract mismatch is hidden.
- [ ] A teammate can reproduce the setup and understand the changes.

## Phase completion record

For each phase, record:
- **Status:** Not started / In progress / Blocked / Complete
- **Evidence:** commit/PR, test command and result, screenshots only where useful
- **Open issues:** specific blockers, not guesses
- **Dependency owner:** name the teammate who must resolve an interface or integration dependency

Do not mark a phase complete just because the code was written. Complete the phase only when its exit criteria are demonstrated.

## Working rules

1. Work one phase at a time and keep changes small.
2. Do not delete or regenerate an existing project without first checking its contents and preserving working files.
3. Ask for one concrete action at a time when coaching a beginner.
4. Use actual logs and reproducible steps when debugging.
5. Do not independently change architecture, API contracts, or safety semantics.
6. After a requested phase is complete, report the evidence and stop for review.
