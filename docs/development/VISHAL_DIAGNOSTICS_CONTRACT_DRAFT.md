# Pi Diagnostics Contract — Review Draft

**Status:** Route, access, status vocabulary, and no-remote-logs decision approved by Vishal. **Response field names and schema are proposed; confirm with the Flutter client before route implementation.**

This document does not add or authorize a route. Current API behavior remains the contract in [`api/README.md`](../../api/README.md).

## Approved constraints

- Add a read-only, Bearer-authenticated `GET /api/v1/diagnostics`.
- Use per-check statuses `PASS`, `WARNING`, `FAIL`, and `UNKNOWN`.
- Keep existing public `GET /health` and `GET /api/v1/status` unchanged.
- Do not add remote log retrieval. Keep detailed logs on the Pi for local troubleshooting. Any future remote log feature needs a separate bounded, redacted contract.
- Report only evidence the Pi actually tracks: API liveness, ESP32 transport connectivity, telemetry freshness, and controller readiness only when an ESP32 READY signal has been observed.
- A connected serial port is not proof of controller readiness. Do not represent unimplemented checks as passing.

## Current evidence

- `GET /health` confirms the FastAPI process answered. It does not prove the robot or ESP32 is ready.
- `GET /api/v1/status` reports API liveness, ESP32 transport as `connected`, `disconnected`, or `unavailable`, the Pi control mode, and `controller_readiness: "unknown"`. The API does not currently track READY events.
- `WS /api/v1/telemetry` sends timestamped raw ESP32 lines and command-result events. Flutter currently derives sensor freshness from received sensor frames with the agreed one-second interval. The API does not yet track parsed sensor freshness for a diagnostics response.
- Move and STOP outcomes are logged locally. There is no remote log endpoint.

## Proposed response schema — awaiting Flutter confirmation

There is no overall status. Each check has its own evidence and status so one unknown check cannot be hidden by an aggregate result.

```json
{
  "observed_at": "2026-11-08T12:00:00Z",
  "checks": [
    {
      "name": "api_liveness",
      "status": "PASS",
      "observed_at": "2026-11-08T12:00:00Z",
      "source": "diagnostics_request",
      "reason_code": "API_RESPONDING"
    },
    {
      "name": "esp32_transport",
      "status": "PASS",
      "observed_at": "2026-11-08T12:00:00Z",
      "source": "gpio_control_connection_state",
      "reason_code": "TRANSPORT_CONNECTED"
    },
    {
      "name": "sensor_telemetry",
      "status": "PASS",
      "observed_at": "2026-11-08T12:00:00Z",
      "source": "pi_received_sensor_tel",
      "reason_code": "TELEMETRY_FRESH",
      "age_ms": 180
    },
    {
      "name": "controller_readiness",
      "status": "UNKNOWN",
      "observed_at": "2026-11-08T12:00:00Z",
      "source": "esp32_ready_event_tracker",
      "reason_code": "READY_NOT_OBSERVED"
    }
  ]
}
```

### Proposed status rules

- API liveness: `PASS` when the API handles the request.
- ESP32 transport: `PASS` when connected; `WARNING` when disconnected; `UNKNOWN` when the transport state cannot be read. This check says nothing about controller readiness.
- Sensor telemetry: `PASS` when a valid sensor `TEL` frame was received within 1,000 ms; `WARNING` when the last valid frame is older than 1,000 ms; `UNKNOWN` if no valid frame was observed or freshness cannot be measured. `NA` and `FAR` readings still count as fresh frames.
- Controller readiness: `UNKNOWN` with `READY_NOT_OBSERVED` until an ESP32 READY event is received. A serial connection alone never changes this check to `PASS`.
- `age_ms` is present for telemetry only; should Flutter accept this optional field?

## Confirm before implementation

Please confirm the names `observed_at`, `checks`, `name`, `status`, `source`, `reason_code`, and telemetry-only `age_ms`, plus the example check names and status rules above. If Flutter prefers different names or enum spelling, update this proposal first. No route or response model should be implemented until the schema is confirmed.

## Approval record

- Vishal: route, authentication, read-only behavior, status vocabulary, no-remote-logs decision, evidence limits, and one-second telemetry freshness confirmed.
- Niteshvar / Flutter response-schema confirmation: pending.
- Backend route implementation: pending Flutter schema confirmation.
- Tharun / firmware READY evidence: pending for readiness tracking; until then readiness must stay `UNKNOWN`.
