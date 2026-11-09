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
- [x] Read the root README and relevant architecture/development documentation.
- [x] Confirm the Flutter app's location in the repository and current Flutter/Dart versions.
- [x] Identify the API base URL approach: Android emulator uses `10.0.2.2` only for an API on the development host; a physical phone uses the Pi's private address over a reachable local network or a team-approved private VPN. No public exposure or port forwarding.
- [x] Review the REST endpoints and request/response schemas in Vishal's current `api/README.md` from `vishal-phase1` (tip reviewed: `5f196387`; includes `ba78d3d`).
- [x] Review the WebSocket path, event shapes, `received_at`, freshness, Ping/Pong, errors, and reconnect contract in that same API README.
- [x] Record unspecified deployment interfaces: actual Pi/VPN address and temporary token; approved in-app URL/token configuration and secure storage; production TLS/certificate policy; safe test procedure. Do not guess these.
- [x] Confirm mode and stop behavior from the contract: MANUAL is required for app movement; AUTO stays paused unless the existing autonomous behavior is explicitly started; normal STOP is not a latched Emergency Stop. Tharun said not to add Emergency Stop until its behavior is agreed; leave it unavailable.
- [x] Confirm ownership: Niteshvar owns mobile UI/client; Vishal owns the Pi API; Tharun owns robot/hardware decisions and safety integration.

### Exit criteria
- [x] The app can be implemented against the documented API without inventing contracts; remaining deployment/safety gaps are shown as unavailable.
- [x] Missing interfaces are written down and assigned: Vishal for API/network/configuration details; Tharun and Vishal for safety/test procedure.
- [x] No low-level hardware responsibilities have been moved into Flutter.

## Phase 1 — Flutter project foundation

### Objective
Create a reproducible, runnable Flutter project without losing existing work.

### Checklist
- [x] Check whether the Flutter project already exists before running `flutter create`.
- [x] Record the project path and verify `flutter doctor`.
- [x] Run `flutter pub get` and launch the unmodified app on the available Android emulator/device.
- [x] Preserve the valid `lib/main.dart` entry point.
- [x] Establish a small, understandable structure, adapting existing files rather than recreating them blindly:
  - `app/` — app setup, routing, theme
  - `core/` — shared constants and utilities
  - `models/` — typed API/telemetry models
  - `services/` — REST and WebSocket clients
  - `features/` — dashboard, manual control, settings, diagnostics, developer
  - `widgets/` — reusable UI components
- [x] Add only necessary dependencies; document why each non-standard dependency is needed.
- [x] Ensure secrets and private credentials are not committed.

### Exit criteria
- [x] App builds and opens on Android.
- [x] Folder structure is understandable and the entry point remains intact.
- [x] Setup steps are documented and a baseline commit exists.

## Phase 2 — App shell, navigation, and visual system

### Objective
Build the navigable app foundation before wiring robot behavior.

### Checklist
- [x] Implement the agreed app theme, typography, spacing, and reusable components.
- [x] Add navigation for Dashboard, Manual Control, Settings, Diagnostics, and Developer/Recovery.
- [x] Make loading, empty, offline, unavailable, and error states explicit.
- [x] Ensure layouts work on the target Android screen sizes and remain accessible.
- [x] Keep navigation and widgets separate from network implementation.
- [x] Use mock/sample data only when clearly marked as mock; never present it as live robot data.

### Exit criteria
- [x] All agreed screens can be navigated.
- [x] Shared visual components are reused.
- [x] UI clearly distinguishes real data from placeholders.

## Phase 3 — Typed models and REST client

### Objective
Create one controlled boundary for HTTP requests and responses.

### Checklist
- [x] Implement typed models only from the current API schemas documented by Vishal. The checked client surface follows the reviewed `api/README.md` snapshot at commit `5f196387`; this backend-owned contract has not yet been merged into the Flutter branch.
- [x] Centralize base URL, request timeouts, headers, and error translation in `PiApiClient`.
- [x] Implement only the currently confirmed calls: `GET /health`, `GET /api/v1/status`, `POST /api/v1/robot/mode`, `POST /api/v1/robot/move`, `POST /api/v1/robot/stop`, and `GET /api/v1/robot/commands/{command_id}`. No unconfirmed backend routes were added.
- [x] Validate user inputs and allowed command ranges at the client boundary; backend validation remains authoritative. Movement UI behavior is also implemented in Phase 5.
- [x] Handle timeout, unreachable host, malformed response, unauthorized request, validation/conflict, unsupported media type, rate limiting, busy queue, unavailable robot, and server errors. The API defines no version field or unsupported-version response.
- [x] Prevent duplicate in-flight move retries and same-ID STOP retries; conflicting in-flight moves and moves during STOP are rejected locally.
- [x] Never silently convert a failed command into a success state; API failures surface as `PiApiException` and the dashboard marks failed status as unavailable/stale.
- [x] Add unit tests for parsing, validation, retry behavior, and error mapping.

### Exit criteria
- [x] API calls match the latest reviewed `api/README.md` contract snapshot (`5f196387`), including STOP's `request_id`, rate limit and queue-busy handling.
- [x] Failure states are testable and visible through typed `PiApiException` results.
- [x] No guessed endpoints or response fields remain.

## Phase 4 — Dashboard and connection state

### Objective
Present an honest summary of the robot's reported state.

### Checklist
- [x] Display connection status separately from robot operational status.
- [x] Display reported mode, readiness/health, and available telemetry fields defined by the contract.
- [x] Show previous status as stale when a refresh fails; ongoing telemetry freshness belongs to Phase 6 because this API's status response has no timestamp.
- [x] Add deliberate manual refresh behavior.
- [x] Avoid inferring sensor or motor state from UI actions alone; display only fields returned by the Pi.
- [x] Test startup when the robot is unavailable and recovery when it becomes reachable.

### Exit criteria
- [x] Dashboard works online and offline through the injectable API client and explicit unconfigured/unavailable states.
- [x] Stale and unknown values are clearly identified.
- [x] Status is based on backend-reported data.

## Phase 5 — Manual control and safe interaction

### Objective
Provide predictable operator controls without bypassing robot-side safety.

### Checklist
- [x] Implement controls only for movement commands and parameters currently confirmed by the API owner; no new routes or safety semantics were added.
- [x] Make the Pi-reported mode, request progress, and command result visible.
- [x] Disable manual drive controls unless the Pi reports a connected ESP32 and MANUAL mode with fresh status; prevent conflicting in-flight commands.
- [x] Provide an accessible normal STOP control and state clearly that dispatch/ACK does not confirm physical stopping.
- [x] Keep Emergency Stop unavailable until Tharun/Vishal approve its backend mechanism and semantics; the UI clearly states that no approved latched E-stop is available.
- [x] Define and test UI behavior for dispatched, safety-rejected, timed-out, and unknown command outcomes.
- [x] On app pause/disconnect, mark status stale and do not claim the robot stopped.
- [x] Do not implement a phone-only safety timeout as a substitute for Pi/ESP32 safety.
- [x] Defer live Pi/robot reconnect and control verification to Phase 8 final integration, as agreed; local tests cover repeated/in-flight requests, delayed responses, errors, and status refresh.
- [x] Keep unapproved/ambiguous safety behavior unavailable; do not expand control behavior until Tharun and Vishal approve it.

### Exit criteria
- [x] Conflicting controls are prevented by state-aware UI and backend responses.
- [x] STOP feedback is truthful; no unapproved Emergency Stop action is presented as available.
- [x] Network failures never create false success indicators.

## Phase 6 — WebSocket telemetry and reconnection

### Objective
Show live robot state through the agreed WebSocket contract.

### Checklist
- [x] Implement the currently documented connection and message parsing rules for `command_result` and `esp32_line`.
- [x] Use the integrated Phase 10 `api/README.md` as the confirmed production telemetry contract.
- [x] Track connecting, connected, reconnecting, disconnected, and failed states.
- [x] Handle malformed messages and unknown message types without crashing.
- [x] Avoid unbounded reconnect loops; retries are manual, with overlapping attempts blocked until the current attempt completes.
- [x] Dispose subscriptions and sockets correctly when services/screens are closed.
- [x] Mark the last event stale when disconnected or until the current connection receives a new event.
- [x] Parse sensor `TEL` frames and Pi `received_at`; mark sensor data stale after 1 second without a new sensor frame, clear stale on the next valid frame, and treat `NA` and `FAR` as fresh.
- [x] Keep WebSocket diagnostics separate from REST-reported robot status; raw ESP32 lines do not change app status.
- [x] Test disconnect/reconnect and simulated server restart scenarios with a local transport fixture.

### Exit criteria
- [x] Telemetry events update the Diagnostics screen without repeated manual refresh.
- [x] Stale/offline states are visible.
- [x] Reconnect and disposal behavior is tested with a local transport fixture.

## Phase 7 — Settings, diagnostics, Competition Mode, Developer Mode

### Objective
Complete the remaining operator workflows while respecting permissions and ownership.

### Checklist
- [x] Build Settings only for configuration values supported by the approved API; show a clear unavailable state when no fields are approved.
- [x] Display backend-provided diagnostics when available; clearly state that results are unavailable when the API provides no diagnostic status contract.
- [x] Show event timestamps and safe connection retry guidance where available; do not invent diagnostic results.
- [x] Keep Competition Mode focused on the existing Dashboard → Manual Control flow and normal STOP; add no new robot actions.
- [x] Keep Developer Mode separate and clearly label advanced/recovery operations.
- [x] Gate any privileged action according to the approved authentication/authorization design; no privileged actions are exposed.
- [x] Never expose arbitrary shell execution or unbounded hardware commands.
- [x] Confirm reset/recovery behavior with the backend owner before exposing controls; no reset/recovery controls are exposed.
- [x] Handle unavailable diagnostic data without fabricating results.

### Exit criteria
- [x] All screens use real contract-backed data or clearly marked placeholders.
- [x] Developer actions cannot bypass backend authorization or robot safety.
- [x] Competition Mode remains simple and reliable by reusing the existing controls and stop guidance.

## Phase 8 — Integration testing and handoff

### Objective
Prove the mobile client works against the actual Pi API and document how to run it.

### Checklist
- [x] Run formatter and static analysis.
- [x] Run unit/widget tests and fix regressions.
- [x] Test against local fake transport and widget fixtures before live hardware.
- [ ] With the team, test connection loss, Pi restart, WebSocket loss, API errors, mode transitions, and stop behavior. The new Phase 12 runtime connection settings have not yet been built/analyzed/tested or exercised against the Pi; prior Flutter evidence predates that change.
- [x] Confirm the API contract version/commit used for testing.
- [x] Build the current Android debug APK.
- [x] Install and launch the current APK on the physical Android phone.
- [x] Document setup, configuration, emulator networking, and troubleshooting.
- [ ] Open a focused PR describing changes, tests, and any remaining gaps.
- [ ] Request review from Vishal for API/client compatibility and Tharun for control/safety behavior.

Physical robot movement tests remain deferred to final project-wide verification until the safe area and team procedure are confirmed.

### Exit criteria
- [x] Build, analysis, and relevant tests pass: Android debug APK build succeeded; Dart analysis reported no issues; all 53 Flutter tests passed.
- [x] No unresolved contract mismatch is hidden; STOP sends the documented `request_id`, and remaining integration limits are recorded in `mobile/flutter/SETUP.md` against the reviewed API snapshot `5f196387`.
- [x] A teammate can reproduce the local setup and understand the current changes from `mobile/flutter/SETUP.md`.

## Phase 9 — App-only offline hotspot onboarding

### Objective
Let an operator provision Thashu from the Thashu app alone and then connect to the Pi locally without requiring Tailscale, nRF Connect, or internet access.

### Checklist
- [x] The Flutter branch includes the app-side BLE provisioning screen from PR #17: scan for Thashu's provisioning service, send credentials through the encrypted GATT write, and display provisioning status. This implementation predates the new connection-info characteristic and has not yet been revalidated against the Pi branch.
- [x] The Pi backend draft preserves the GPIO 17 three-second button hold, 60-second BLE window, existing service/credential/status UUIDs, and adds an encrypted connection-info read containing the local HTTPS URL, certificate SHA-256 pin, and Bearer token.
- [x] The Pi backend draft keeps the existing loopback API listener and adds an opt-in HTTPS listener on the configured Wi-Fi interface's current IPv4 address; it does not bind to 0.0.0.0 or start a second ESP32 owner.
- [x] The hotspot address-change behavior is defined as automatic API rebind. Closing the prior local listener drops its WebSocket; the Pi waits beyond the current 500 ms movement lease before binding the new address. Mode is preserved and movement is not resumed.
- [ ] Flutter must read the new connection-info characteristic, save the URL/token/pin in secure storage, and pin the certificate for both REST and WebSocket connections before the local HTTPS listener is enabled.
- [ ] Verify the target Android phone can reach the Pi on its own hotspot with internet disabled; retry connection while the listener comes up after NetworkManager reports connected.
- [ ] Test app-only BLE provisioning, hotspot join, pinned HTTPS status, authenticated telemetry/WebSocket, stale recovery, app reconnect, changed hotspot address, and Pi restart. Provisioning tests must not send movement commands.
- [ ] Keep the existing Tailscale connection as an optional developer/test path until the offline app path is verified.

### Exit criteria
- [ ] A fresh phone can complete pairing and local API setup entirely in the Thashu app with no helper app or internet.
- [ ] The phone validates the Pi's pinned local certificate for REST and WSS; no global cleartext exception or public port forwarding is used.
- [ ] Status and telemetry work across app reconnect, hotspot address change, and Pi restart, with no movement command sent by provisioning.
- [ ] Flutter formatting, analysis, tests, Android build, and supervised phone/Pi verification pass; evidence and remaining limits are recorded.

### Current implementation record
- **Status:** In progress — backend implementation is on draft PR #18; end-to-end acceptance remains open.
- **Evidence:** Draft PR [#18](https://github.com/sg9242182-bot/ThashuRobot/pull/18) adds `thashu/core/local_api_access.py`, the opt-in listener in `thashu/main.py`, encrypted BLE connection-info in `thashu/hardware/wifi_provisioning.py`, its systemd unit, and setup documentation. User-reported Pi smoke check (2026-11-09): imports passed in the Pi virtual environment; the draft BLE service opened through the GPIO button; nRF Connect provisioned the phone hotspot, observed connection, and read `...0004` with all three expected fields (`api_base_url`, `server_cert_sha256`, `api_token`). Secret values were not shared. This does not verify Flutter integration, TLS pin validation, API reachability, changed-address rebind, or restart.
- **Open issues:** Flutter connection-info consumption and TLS pinning; local HTTPS/API/WebSocket and address-change/restart checks on the target devices. No movement command was sent during provisioning.
- **Dependency owner:** Tharun — verify the local HTTPS runtime and address-change/restart behavior after app pinning is ready. Niteshvar — connect the app to the info characteristic and pin TLS for REST/WSS. Both — supervised phone/Pi end-to-end check.

## Phase completion record

For each phase, record:
- **Status:** Not started / In progress / Blocked / Complete
- **Evidence:** commit/PR, test command and result, screenshots only where useful
- **Open issues:** specific blockers, not guesses
- **Dependency owner:** name the teammate who must resolve an interface or integration dependency

### Phase 0 — Architecture and interface readiness

- **Status:** Complete — all Phase 0 checklist and exit items are met; this scoped checklist commit records the phase evidence.
- **Evidence:** Reviewed `api/README.md` at the fetched `vishal-phase1` tip `5f196387`, including rate limiting from `ba78d3d`, current REST paths/shapes, WebSocket `esp32_line.received_at`, 1-second sensor freshness, `NA`/`FAR` freshness, and Ping/Pong behavior. Documented emulator and private-network/VPN base URL approach, mode/STOP semantics, ownership, and deployment/security gaps. No hardware or backend responsibilities were moved to Flutter.
- **Open issues:** Pi/VPN address and temporary token; approved runtime URL/token configuration and secure storage; production TLS/certificate policy; safe live-test procedure. Sensor freshness behavior is implemented in Phase 6; live telemetry validation remains pending the private Pi connection.
- **Dependency owner:** Vishal — provide private test connection and confirm deployment/security configuration. Tharun and Vishal — approve safe control-test procedure and any future Emergency Stop semantics. Niteshvar — Flutter frontend only.

### Phase 3 — Typed models and REST client

- **Status:** Complete for the Flutter Phase 3 implementation (100%); private Pi integration validation is pending.
- **Evidence:** `PiApiClient` implements the reviewed routes and error behavior, including 429 `RATE_LIMITED` with retry delay/header, STOP remaining available, 503 `API_BUSY`, and 415 `UNSUPPORTED_MEDIA_TYPE`. Formatting completed; Dart analysis reported no issues; all 53 Flutter tests passed.
- **Open issues:** Phone-to-Pi integration awaits the private-LAN test window and connection details. Unsupported-version behavior is not defined by the API.
- **Dependency owner:** Vishal — provide the private Pi/VPN test address and token. Niteshvar — Flutter client/UI only; do phone integration when access is supplied.

### Phase 4 — Dashboard and connection state

- **Status:** Complete (local client and widget-test scope)
- **Evidence:** The Dashboard displays API connection separately from Pi-reported status, supports deliberate refresh, labels old data stale after a failed refresh, and shows explicit unconfigured/offline states. The Dashboard widget tests passed, including startup unavailable/recovery; the full Flutter suite passed with 53 tests.
- **Open issues:** Phone-to-Pi verification remains pending under Phase 8. Automatic telemetry freshness belongs to Phase 6 because the current REST status response has no timestamp.
- **Dependency owner:** Vishal — provide the Pi address and temporary test token for live integration.

### Phase 5 — Manual control and safe interaction

- **Status:** Complete for Flutter frontend scope (100%). Live Pi/robot verification is tracked in Phase 8; unapproved Emergency Stop remains unavailable by design.
- **Evidence:** Dart analysis reported no issues; all 53 Flutter tests passed. Tests cover API/client validation, manual mode gating, pending/repeated movement, normal STOP, safety rejection, ACK timeout, unknown outcomes after connection loss, and pause/resume state handling. The UI does not claim that an ACK confirms physical stopping and clearly states that no approved latched Emergency Stop is available.
- **Open issues:** Live Pi reconnect/control verification and any future Emergency Stop approval remain external integration/safety work tracked for final project verification; no unapproved behavior is exposed in the Flutter UI.
- **Dependency owner:** Vishal — provide the Pi test connection. Tharun and Vishal — approve any future Emergency Stop semantics. Niteshvar — Flutter UI/client only.

### Phase 6 — WebSocket telemetry and reconnection

- **Status:** Complete for Flutter frontend implementation (100%); all 10 telemetry contract/implementation checklist items are complete. Phone-to-Pi validation remains tracked in Phase 8.
- **Evidence:** The telemetry client targets `/api/v1/telemetry` with Bearer auth, parses `command_result` and `esp32_line.received_at`, and safely represents malformed/unknown messages. It tracks all five connection states, uses manual retry with overlapping attempts blocked, closes the prior socket before retry, and disposes subscriptions. Diagnostics parses sensor `TEL` frames, displays the four readings and Pi timestamp, marks the readings stale after one second without a valid frame, treats `NA`/`FAR` as fresh frames, and clears stale on the next valid frame. Sensor freshness uses local frame-arrival timing to avoid relying on synchronized phone/Pi clocks; `received_at` is parsed and displayed. Formatting completed; analysis reported no issues; all 53 Flutter tests passed, including parser, received timestamp, stale expiry, and freshness reset coverage.
- **Open issues:** Phone-to-Pi telemetry validation awaits the private-LAN test window and connection details; robot movement testing follows the agreed safe procedure.
- **Dependency owner:** Vishal — confirm/merge the production telemetry contract and provide test connection details. Niteshvar — Flutter client/UI only.

### Phase 7 — Settings, diagnostics, Competition Mode, Developer Mode

- **Status:** Complete for the original PR #9 screen scope; runtime Pi connection setup was added later on `phase-12-pi-api-https` and needs fresh Flutter validation.
- **Evidence:** The original Phase 7 build displayed unavailable connection settings and did not collect credentials. The later Phase 12 integration replaces that placeholder with HTTPS-only Pi address/token settings, secure storage, and REST/WebSocket client initialization. Diagnostics still does not invent unavailable API checks; Developer / Recovery exposes no reset, shell, or direct hardware controls; Competition quick start reuses the existing Manual Control and STOP flow. The 53-test/analyze/APK evidence predates the later connection-settings integration and does not validate it.
- **Deferred integration:** Actual robot settings, backend diagnostic result values, and recovery controls remain unavailable until supported API behavior is provided. They are not required for this frontend-only phase completion.
- **Dependency owner:** Vishal — future configuration, diagnostic, or recovery API support. Niteshvar — Flutter UI.

### Phase 8 — Integration testing and handoff

- **Status:** In progress — 7 of 10 checklist items completed (70%). Flutter checks, Android debug build, and physical-phone launch pass; final Pi integration, focused PR, and teammate reviews remain open.
- **Evidence:** Flutter formatting completed; Dart analysis reported no issues; all 53 Flutter tests passed, including API error handling and telemetry sensor parsing/freshness. Reviewed the integrated Phase 10 `api/README.md` contract and documented the remaining security/integration gaps in `mobile/flutter/SETUP.md`. With Android Studio JBR, `D:\flutter\bin\flutter.bat build apk --debug` succeeded and generated `mobile/flutter/build/app/outputs/flutter-apk/app-debug.apk` on 2026-11-08. ADB installed it successfully on `TCOR49Q8VCF6IBEQ`; Android reports `com.example.thashu_app/.MainActivity` as the resumed activity.
- **Open issues:** Phone-to-Pi/restart/WebSocket/control verification awaits a private Pi address, token, and test window. Tharun reports local Pi/ESP32 checks passed; this does not replace Flutter phone integration. Pairing/TLS configuration and teammate reviews remain pending. Movement through Flutter waits for the agreed safe procedure.
- **Dependency owner:** Vishal — confirm backend contract, provide test connection, and review API/client compatibility. Tharun — agree safe hardware/control test procedure and review safety behavior. Niteshvar — Flutter frontend changes and focused PR preparation.

### Phase 2 — App shell, navigation, and visual system

- **Status:** Complete
- **Evidence:** Flutter analysis passed; 4 widget tests passed for the five destinations, all notice states, and a 360×800 Android viewport with accessible navigation targets; Android debug APK built successfully. Niteshvar also confirmed navigation on the physical Android phone.
- **Open issues:** No Phase 2 issues. Robot API integration remains for later phases and is not represented as live data.
- **Dependency owner:** None for Phase 2.

Do not mark a phase complete just because the code was written. Complete the phase only when its exit criteria are demonstrated.

## Working rules

1. Work one phase at a time and keep changes small.
2. Do not delete or regenerate an existing project without first checking its contents and preserving working files.
3. Ask for one concrete action at a time when coaching a beginner.
4. Use actual logs and reproducible steps when debugging.
5. Do not independently change architecture, API contracts, or safety semantics.
6. After a requested phase is complete, report the evidence and stop for review.
