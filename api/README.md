# Raspberry Pi API and Backend

This directory is the home for the mobile-facing API layer and its API-specific documentation/tests. It is a **component-owned location**, not a separate copy of the robot application.

## Ownership

- **Vishal Raj:** API routes, REST request/response handling, WebSocket endpoint integration, API validation, API tests, and contract documentation.
- **Tharun:** hardware and ESP32 behavior; approve hardware-facing safety/protocol decisions with Vishal.
- **Niteshvar:** Flutter client integration; coordinate any mobile-facing contract changes with him.

## Boundary

- The API must call the existing Pi robot/service layer rather than implementing motor, GPIO, sensor-driver, or ESP32 timing logic itself.
- Flutter talks to the Pi API, never directly to the ESP32.
- REST is for request/response operations; WebSocket is for live telemetry, according to the approved contracts.
- Keep the mobile contract in this document and the OpenAPI schema. The API owner defines request and response payloads; coordinate client integration with the Flutter owner.
- Never add an unrestricted shell-command endpoint or bypass robot-side safety.

## Suggested organization

Add subfolders only when the implementation requires them. For example:

```text
api/
├── README.md
├── routes/          # HTTP routes, if the selected framework needs this separation
├── websocket/       # WebSocket handlers, if separate modules are warranted
├── schemas/         # Validated API request/response models
└── tests/           # API contract and route tests
```

This is a guide, not a requirement to create empty folders now. Reuse the repository's existing framework and conventions before adding modules.

## Initial implementation notes

The endpoints below form the first mobile-facing contract. Flutter sends
requests to the Pi API. The API delegates commands to
`thashu/core/robot_manager.py`, which validates and serializes calls to the
existing motor service. Move and STOP responses report Pi dispatch while
their ESP32 ACK arrives asynchronously. A mode switch waits for the STOP ACK
before changing the selected mode.

| Interface | Behavior |
|---|---|
| `GET /health` | Returns `{"status":"ok"}` when the API process responds. This is liveness only. |
| `GET /api/v1/status` | Reports API liveness, serial transport (`connected`, `disconnected`, or `unavailable`), `controller_readiness: "unknown"`, and the Pi control mode (`AUTO`, `MANUAL`, or `unknown` if the manager cannot start). Opening a serial port does not prove the ESP32 emitted `EVENT|0|READY`. |
| `GET /api/v1/diagnostics` | Read-only diagnostic snapshot with API, ESP32 transport, sensor telemetry freshness, and controller readiness checks. Requires the configured Bearer token. Does not expose logs. |
| `POST /api/v1/robot/mode` | Body: `{"mode":"MANUAL"}` or `{"mode":"AUTO"}`. Cancels motion/follow, sends STOP, waits up to 750 ms for `ACK|sequence|OK`, then selects the mode. A failed STOP leaves the prior mode selected. Selecting AUTO does not start follow. |
| `POST /api/v1/robot/move` | Body: `{"request_id":"<UUID>","direction":"forward","speed":200}`. `request_id` is required; direction is `forward`, `backward`, `left`, or `right`; speed is an integer from 0 to 255 and defaults to 200. Requires MANUAL mode. |
| `POST /api/v1/robot/stop` | Body: `{"request_id":"<UUID>"}`. Cancels active movement/follow output, sends the dedicated STOP command, and selects AUTO paused. It does not restart follow. |
| `GET /api/v1/robot/commands/{command_id}` | Returns the current result for a command. Requires the same Bearer token. Results and request IDs are stored in SQLite for 24 hours and survive API restarts. |
| `WS /api/v1/telemetry` | Bearer-authenticated server-to-client stream of timestamped ESP32 lines and `command_result` events. Raw lines are not represented as command success. |

Diagnostics returns a top-level UTC `observed_at` and four named checks. Each
check has `name`, `status` (`PASS`, `WARNING`, `FAIL`, or `UNKNOWN`),
`observed_at`, `source`, and `reason_code`. Only the
`sensor_telemetry` check includes `age_ms`; it is required and nullable.
Telemetry is fresh for 1,000 ms after receipt of a complete valid sensor
frame, including frames containing `NA` or `FAR`. Controller readiness stays
`UNKNOWN` until the current ESP32 connection emits `EVENT|0|READY`.
Detailed logs remain on the Pi; this API has no remote log retrieval.
See the [diagnostics contract](../docs/development/VISHAL_DIAGNOSTICS_CONTRACT_DRAFT.md)
for the full response schema and reason-code mappings.

Successful move and STOP responses use:

```json
{"request_id":"<uuid>","command_id":"<uuid>","command":"forward","status":"dispatched","control_mode":"MANUAL","error_code":null,"timestamp":"<UTC ISO 8601>"}
```

Move and STOP requests require a UUID `request_id`, created once per logical
action. If the app retries the same action with that ID, the API returns the
original `command_id` and latest known result without sending the command
again. Reusing an ID for a different action returns HTTP 409
(`REQUEST_ID_REUSED`). A new STOP press must use a new ID to send a fresh STOP.
The Pi persists request IDs, action payloads, command IDs, and latest results in
SQLite for 24 hours. If the Pi/API restarts while a command is marked
`dispatching` or is awaiting its ESP32 ACK, its result is changed to `unknown` with
`PROCESS_RESTARTED_DURING_DISPATCH`; the Pi does not resend it. Expired IDs can
be used as new requests after the 24-hour retry window.

Example move request:

```json
{"request_id":"b1234567-89ab-4cde-8f01-23456789abcd","direction":"forward","speed":200}
```

Example STOP request:

```json
{"request_id":"c1234567-89ab-4cde-8f01-23456789abcd"}
```

A successful mode switch returns after the ESP32 acknowledges STOP:

```json
{"mode":"MANUAL","status":"switched"}
```

If STOP is rejected or times out, mode remains unchanged and the API returns
HTTP 503 with `error: "mode_switch_failed"` and an `error_code` such as
`STOP_REJECTED` or `STOP_ACK_TIMEOUT`.

`status: "dispatched"` means the Pi wrote the command to serial. It does not
mean the ESP32 acknowledged it or that the robot completed the movement. Move
and stop return HTTP 202 with a `command_id`. A retry with the same request ID
returns the existing ID rather than creating another. The API asynchronously
waits up to 750 ms for the matching ACK. The WebSocket sends a final event:

```json
{"type":"command_result","request_id":"<uuid>","command_id":"<uuid>","status":"acknowledged","error_code":null,"timestamp":"<UTC ISO 8601>"}
```

Final status values are `acknowledged`, `safety_error`, and `timed_out`.
`dispatching` may be returned while dispatch is still underway; `unknown` means
the process restarted or dispatch otherwise could not be confirmed. Replaying
the same request ID in either state never resends the command.
Safety errors include the ESP32 reason as `error_code`; timeouts use
`ACK_TIMEOUT`; acknowledged results have `error_code: null`. An ACK means
the ESP32 acknowledged handling the command, not that movement completed.

Each `esp32_line` event includes `received_at`, an ISO 8601 UTC timestamp
recorded by the Pi when the serial frame arrives. For example:

```json
{"type":"esp32_line","line":"TEL|0|SENSORS|TOF_L|420|TOF_C|FAR|TOF_R|390|US_REAR|NA","received_at":"2026-11-07T12:00:00.123Z"}
```

The ESP32 emits sensor frames at 20 Hz. The Flutter client should mark sensor
telemetry stale after 1 second without a new sensor `TEL` frame, and clear
stale immediately when another arrives. `NA` and `FAR` are sensor values; a
well-formed frame containing either value still refreshes telemetry. Keepalive
uses WebSocket protocol Ping/Pong (Ping every 20 seconds, Pong timeout 10
seconds), not a JSON heartbeat event. This keepalive timeout is separate from
the 1-second sensor freshness timer.

Move, mode, and STOP requests share a serialized command queue. STOP has
priority over queued move/mode requests. It waits for the command already in
progress to finish; it does not interrupt serial work already underway.
Move and mode share one token bucket for the configured Bearer token: capacity
10, refilling at 5 requests per second. The bucket is shared across every app
using that token. A limited request returns HTTP 429 with
`detail.error_code: "RATE_LIMITED"`, `retry_after_seconds`, and a `Retry-After`
header, before entering the command queue. STOP remains authenticated, bypasses
this limit, and has priority over queued move/mode requests. It waits for the
command already in progress to finish; it does not interrupt serial work
already underway. Move and mode requests that wait more than 2 seconds return
HTTP 503 with `detail.error_code: "API_BUSY"` and `retryable: true`; they have
not been dispatched. STOP is not rejected by that queue-wait timeout. Retrying
a move or STOP must reuse its original `request_id`. Hardware dispatch runs in
a worker thread and is not cancelled when an HTTP client disconnects, so a
request timeout never cancels a motor operation that may already have reached
the ESP32.

If Flutter misses the WebSocket event, it can call
`GET /api/v1/robot/commands/{command_id}` with the same Bearer token. The
response contains `request_id`, `command_id`, `command`,
`status`, `error_code`, `timestamp`, and `control_mode`. While pending, the
status is `dispatched`. Results are held in
SQLite for 24 hours and survive API restarts. Invalid directions or speeds receive HTTP 422. If the Pi
cannot write the command, the endpoint returns HTTP 503 with an error code and
command ID. Requests are not queued for later delivery.

The manager starts in `AUTO` paused. App movement requires an explicit switch
to `MANUAL`; a move request in another mode receives HTTP 409. Auto movement
is enabled only when the existing autonomous follow behavior is explicitly
started. A mode switch cancels pending movement and follow timers, sends STOP,
and changes mode only after the ESP32 ACKs `OK`; choosing AUTO never starts
autonomous movement. If STOP cannot be confirmed during a switch, the old mode
remains selected, the Pi sends a best-effort second STOP, and all movement stays
blocked until a later mode switch receives a STOP ACK.

The Pi also requires a sensor snapshot no older than 750 ms. `FAR` is clear;
`NA`, missing, or stale readings block movement and trigger a STOP. Forward, left, and right
commands check all three front ToF sensors; backward checks the rear sensor.
Numeric readings must be greater than 300 mm. The ESP32 retains final authority
and may still reject a command. STOP cancels pending movement and follow output,
returns the selected mode to AUTO paused, and does not restart follow.
Moves that were waiting while a STOP or mode switch completed are rejected
with HTTP 409 instead of being sent under the new state.

The current protocol has no latched Emergency Stop command. Do not claim a
latched Emergency Stop until the ESP32 protocol and firmware add and verify
that behavior. See `docs/development/VISHAL_BACKEND_CONTRACT_GAPS.md` for the
remaining hardware contract. The API uses one serial-reader task for the raw
inbound queue exposed by `GPIOControl`, then fans each event out to connected
WebSocket clients. Each client has a bounded 64-event queue; if a client is
slow, its oldest queued event is dropped so it cannot block serial reading or
robot control. A missed `command_result` can be recovered through the command
result REST route. The app determines sensor freshness from Pi receive times;
the API does not send a separate JSON heartbeat or stale-state event. The API
must share the robot process's existing `RobotCommandManager` and serial
connection; do not run a separate Uvicorn process beside `thashu/main.py` on
the Pi.

Mode, movement, stop, and WebSocket telemetry require an HTTP Bearer token configured
in `THASHU_API_TOKEN`. Health and status remain unauthenticated. If the token is
missing, control requests fail closed with HTTP 503; a missing or incorrect
token receives HTTP 401. Configure a long random token in the same shell before
starting Uvicorn. In PowerShell:

```powershell
$env:THASHU_API_TOKEN = "paste-a-long-random-token-here"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --ws-ping-interval 20 --ws-ping-timeout 10
```

Command retry records are stored by default at
`~/.local/state/thashu/api_state.sqlite3` on Linux and under
`%LOCALAPPDATA%\ThashuRobot\api_state.sqlite3` on Windows. Set
`THASHU_API_STATE_DB` to override the database path. Keep the database on
persistent local storage and do not delete it during an active 24-hour retry
window.

Use Swagger's **Authorize** button with the token before trying the protected
routes. Keep the API bound to `127.0.0.1:8000`. For approved mobile access,
follow the Tailscale + Caddy setup in `api/PI_SETUP.md`: Caddy listens on the
Pi's Tailscale IP and proxies to the loopback API. Do not set
`THASHU_API_HOST=0.0.0.0`, expose port 8000, or commit the token to the repo.

Install the API dependencies from the repository root:

```powershell
python -m pip install -r api/requirements.txt
```

On the Pi, the API starts inside the robot process and shares its controller.
From the `thashu` directory, start the robot with `python main.py`. For a
local API-only development session, Uvicorn may be run separately only while
the robot process is stopped; never let both processes open the ESP32 serial
port at once.

Install the test/runtime dependencies and run the backend unit suites from the
repository root:

```powershell
python -m pip install -r api/requirements-test.txt
python -m unittest api.tests.test_api thashu.tests.test_hardware_protocol thashu.tests.test_robot_manager thashu.tests.test_runtime_cleanup
```

The hardware-protocol unit test uses a fake serial transport and `thashu/tests/protocol_vectors.json` to check Pi command framing and sequence behavior. It does not execute the ESP32 parser or replace hardware verification; the firmware does not yet consume this fixture in a parser test.

## Error responses for the Flutter client

Robot command endpoints can return these responses:

- **415 Unsupported Media Type** when a move, stop, or mode request does not use `application/json`. A `charset` parameter is allowed:
  ```json
  {"detail":{"error":"unsupported_media_type","error_code":"UNSUPPORTED_MEDIA_TYPE","supported":["application/json"]}}
  ```
- **401 Unauthorized** when the Bearer token is missing or incorrect:
  ```json
  {"detail":{"error":"unauthorized","error_code":"UNAUTHORIZED"}}
  ```
- **429 Too Many Requests** when the shared move/mode token bucket is exhausted. No command is sent:
  ```json
  {"detail":{"error":"rate_limited","error_code":"RATE_LIMITED","retry_after_seconds":0.2}}
  ```
- **409 Conflict** when a move or STOP request ID is reused for a different action:
  ```json
  {"detail":{"error":"request_id_conflict","error_code":"REQUEST_ID_REUSED","request_id":"<uuid>"}}
  ```
- **422 Unprocessable Content** when a request body is invalid. The field-level FastAPI issues are kept under `detail.issues`:
  ```json
  {"detail":{"error":"validation_error","error_code":"VALIDATION_ERROR","issues":[{"loc":["body","direction"],"msg":"Input should be a valid direction"}]}}
  ```
  For example, an unsupported direction such as `spin` is rejected before any motor command is sent.
- **413 Payload Too Large** when a move or stop request body exceeds 4 KiB:
  ```json
  {"detail":{"error":"request_body_too_large","error_code":"PAYLOAD_TOO_LARGE"}}
  ```
- **503 Service Unavailable** when no API token is configured:
  ```json
  {"detail":{"error":"authentication_not_configured","error_code":"AUTHENTICATION_NOT_CONFIGURED"}}
  ```
- **503 Service Unavailable** when the Pi cannot dispatch a robot command:
  ```json
  {"detail":{"error":"robot_unavailable","error_code":"ROBOT_UNAVAILABLE","command_id":"<uuid>"}}
  ```
- **503 Service Unavailable** when a move or mode request waits in the command queue for more than 2 seconds. That request was not dispatched:
  ```json
  {"detail":{"error":"command_queue_busy","error_code":"API_BUSY","retryable":true}}
  ```
- **404 Not Found** when a command result is unknown or outside its retention window:
  ```json
  {"detail":{"error":"command_not_found","error_code":"COMMAND_NOT_FOUND","command_id":"<uuid>"}}
  ```
- **500 Internal Server Error** for an unexpected server failure. Exception details are not returned:
  ```json
  {"detail":{"error":"internal_error","error_code":"INTERNAL_ERROR"}}
  ```

All REST errors remain inside FastAPI's top-level `detail` field. Object details
include `error_code`; request validation includes `detail.error_code` and
field-specific `detail.issues`. `error_code` is the stable machine-readable
backend reason, while `error` is a descriptive category. Internal failures
return `detail.error_code: "INTERNAL_ERROR"` without exposing exception text.

The app should treat `dispatched` as “the Pi wrote the command to its serial transport,” not as confirmation that the robot moved. Use the command result event or lookup route to show whether the ESP32 acknowledged, rejected, or timed out. A disconnected screen can be shown for `robot_unavailable` or when the server cannot be reached.

## Command logs

The API writes one sanitized JSON log record for each move or stop request outcome. Records include a timestamp, component, command ID, command, outcome, HTTP status, and the control mode on dispatch. Failure records include a stable error code. Bearer tokens and request authorization headers are not included.

Example:

```json
{"command":"forward","component":"pi_api","control_mode":"MANUAL","event":"robot_command","http_status":202,"outcome":"dispatched","command_id":"<uuid>","timestamp":"<UTC timestamp>"}
```

Use the response's `command_id` to find its matching API log entry. A `dispatched` log still means the Pi wrote the command to the serial transport; it does not confirm ESP32 acknowledgement or physical movement.


## Phase 12: HTTPS for phone access

**Approved design:** use Tailscale MagicDNS and Caddy. Name the Pi
`thashu-robot` in the tailnet. Caddy obtains its HTTPS certificate from the
local Tailscale daemon and proxies requests to the API on `127.0.0.1:8000`.
Bind Caddy to the Pi's Tailscale IP, restrict tailnet access to approved phones,
and do not use port forwarding or Funnel. The Flutter app continues to use
normal Android certificate validation and the existing routes/Bearer-token
behavior.

**Deployment and phone testing remain pending.** Keep FastAPI on loopback;
leave `THASHU_API_TLS_CERTFILE`, `THASHU_API_TLS_KEYFILE` unset and
`THASHU_API_TLS_ANDROID_TRUST_CONFIRMED=0`. Do not expose API port 8000. The
complete Pi and Android setup/verification steps are in `api/PI_SETUP.md`.
Tailscale HTTPS certificate hostnames are published in Certificate
Transparency logs, so use a generic machine name. The robot's local behavior
remains available offline; phone access over Tailscale requires tailnet
connectivity.
