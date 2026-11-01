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
existing motor service. The Pi motor service writes to the ESP32 serial
transport. The API response reports dispatch from the Pi; it does not wait for
a hardware acknowledgement or claim movement completed.

| Interface | Behavior |
|---|---|
| `GET /health` | Returns `{"status":"ok"}` when the API process responds. This is liveness only. |
| `GET /api/v1/status` | Reports API liveness, serial transport (`connected`, `disconnected`, or `unavailable`), `controller_readiness: "unknown"`, and the Pi control mode (`AUTO`, `MANUAL`, or `unknown` if the manager cannot start). Opening a serial port does not prove the ESP32 emitted `EVENT|0|READY`. |
| `POST /api/v1/robot/move` | Body: `{"direction":"forward","speed":200}`. Direction is `forward`, `backward`, `left`, or `right`; speed is an integer from 0 to 255 and defaults to 200. |
| `POST /api/v1/robot/stop` | Empty body. Dispatches the dedicated stop command through the Pi motor service. |
| `WS /api/v1/telemetry` | Server-to-client stream of raw ESP32 lines, each wrapped as `{"type":"esp32_line","line":"..."}`. Lines are not parsed or represented as command success. |

Successful movement and stop responses use:

```json
{"request_id":"<uuid>","command":"forward","status":"dispatched","control_mode":"MANUAL"}
```

`status: "dispatched"` means the Pi motor service successfully wrote the
command to its serial transport. It does not mean the ESP32 acknowledged it or
that the robot completed the movement. Invalid directions or speeds receive
HTTP 422. If the Pi cannot write the command, the endpoint returns HTTP 503
with an error code and request ID. Requests are not queued for later delivery.

The Pi manager starts in `AUTO`. A successfully dispatched move changes the
tracked mode to `MANUAL`; a successfully dispatched stop changes it back to
`AUTO`. The status response includes `control_mode`. The current vision code
does not drive the motors automatically, so `AUTO` is a tracked control mode
until an automatic motor controller is integrated. ESP32 hardware safety still
has final authority to stop or reject unsafe motion.

The initial robot manager serializes manual API commands. Manual/automatic mode
arbitration is still open and must be defined before adding mode switching or
autonomous motor commands. The telemetry stream consumes the raw inbound queue exposed by `GPIOControl`;
it is a single-consumer feed and should not run alongside another reader of
that queue.

Movement, stop, and WebSocket telemetry require an HTTP Bearer token configured
in `THASHU_API_TOKEN`. Health and status remain unauthenticated. If the token is
missing, control requests fail closed with HTTP 503; a missing or incorrect
token receives HTTP 401. Configure a long random token in the same shell before
starting Uvicorn. In PowerShell:

```powershell
$env:THASHU_API_TOKEN = "paste-a-long-random-token-here"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Use Swagger's **Authorize** button with the token before trying the protected
routes. Keep the server bound to localhost during development. Before exposing
it to a mobile device on the network, store the token in the Pi service
environment and use a trusted network; do not commit the token to the repo.

Install and run from the repository root:

```powershell
python -m pip install -r api/requirements.txt
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Run API tests with:

```powershell
python -m unittest api.tests.test_api
```

## Error responses for the Flutter client

Robot command endpoints can return these responses:

- **401 Unauthorized** when the Bearer token is missing or incorrect:
  ```json
  {"detail":{"error":"unauthorized"}}
  ```
- **422 Unprocessable Content** when the move body is invalid. FastAPI returns its standard validation format, with a `detail` list describing the invalid field. For example, an unsupported direction such as `spin` is rejected before any motor command is sent.
- **503 Service Unavailable** when no API token is configured:
  ```json
  {"detail":{"error":"authentication_not_configured"}}
  ```
- **503 Service Unavailable** when the Pi cannot dispatch a robot command:
  ```json
  {"detail":{"error":"robot_unavailable","request_id":"<uuid>"}}
  ```

The app should treat `dispatched` as “the Pi wrote the command to its serial transport,” not as confirmation that the robot moved. A disconnected screen can be shown for `robot_unavailable` or when the server cannot be reached.

## Command logs

The API writes one sanitized JSON log record for each move or stop outcome. Records include a timestamp, component, request ID, command, outcome, HTTP status, and the control mode on dispatch. Failure records include a stable error code. Bearer tokens and request authorization headers are not included.

Example:

```json
{"command":"forward","component":"pi_api","control_mode":"MANUAL","event":"robot_command","http_status":200,"outcome":"dispatched","request_id":"<uuid>","timestamp":"<UTC timestamp>"}
```

Use the response's `request_id` to find its matching API log entry. A `dispatched` log still means the Pi wrote the command to the serial transport; it does not confirm ESP32 acknowledgement or physical movement.
