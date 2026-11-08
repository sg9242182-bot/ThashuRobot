# Pi Diagnostics Contract

**Status:** Approved by Vishal and confirmed by Niteshvar for Flutter alignment. The read-only authenticated route is implemented on `phase-12-pi-api-https`; verification is pending.

This is the approved response contract for `GET /api/v1/diagnostics`. Existing health, status, REST command, and WebSocket telemetry contracts remain unchanged; see [`api/README.md`](../../api/README.md).

## Approved constraints

- Add a read-only, Bearer-authenticated `GET /api/v1/diagnostics`.
- The allowed `status` values are `PASS`, `WARNING`, `FAIL`, and `UNKNOWN`.
- Keep existing public `GET /health` and `GET /api/v1/status` unchanged.
- Do not add remote log retrieval. Keep detailed logs on the Pi for local troubleshooting. Any future remote log feature needs a separate bounded, redacted contract.
- Report API liveness, ESP32 transport connectivity, telemetry freshness, and controller readiness. Do not report unimplemented checks as passing.
- A connected serial port is not proof of controller readiness. Keep readiness `UNKNOWN` until an ESP32 READY signal is actually observed.

## Exact JSON shape

Top-level object fields:

| Field | Type | Meaning |
|---|---|---|
| `observed_at` | string, UTC RFC 3339 timestamp | Time the Pi assembled this diagnostic snapshot. It is independent of WebSocket frame timestamps. |
| `checks` | array of check objects | One result for each defined check. There is no aggregate status. |

Each check object:

| Field | Type | Meaning |
|---|---|---|
| `name` | string enum | One of `api_liveness`, `esp32_transport`, `sensor_telemetry`, `controller_readiness`. |
| `status` | string enum | One of `PASS`, `WARNING`, `FAIL`, `UNKNOWN`. The check-specific mappings are below. |
| `observed_at` | string, UTC RFC 3339 timestamp | Time the Pi evaluated this check. For telemetry, `age_ms` is computed at this time. |
| `source` | string enum | One of `diagnostics_request`, `gpio_control_connection_state`, `complete_sensor_tel_received_at`, `esp32_ready_event_tracker`. |
| `reason_code` | string | Stable uppercase snake-case code matching `^[A-Z][A-Z0-9_]*$`; codes are listed below. No exception text or free-form private data. |
| `age_ms` | integer or null; sensor check only | Age of the latest complete sensor frame at the check's `observed_at`. Always include this field on `sensor_telemetry`; use `null` if no valid frame has been observed or freshness cannot be measured. Omit it from the other check objects. |

Timestamps use UTC with a trailing `Z`, for example `2026-11-08T12:00:00Z`. The WebSocket telemetry contract remains unchanged: ESP32 line events keep `received_at`; complete sensor frames and their Pi receipt time are used for freshness. Diagnostics `observed_at` describes when the diagnostic snapshot/check was evaluated, not when a WebSocket event was sent.

## Example response

This example shows the approved response shape. Controller readiness remains UNKNOWN until a READY event has been observed.

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
      "source": "complete_sensor_tel_received_at",
      "reason_code": "TELEMETRY_FRESH",
      "age_ms": 180
    },
    {
      "name": "controller_readiness",
      "status": "UNKNOWN",
      "observed_at": "2026-11-08T12:00:00Z",
      "source": "esp32_ready_event_tracker",
      "reason_code": "READY_TRACKING_NOT_IMPLEMENTED"
    }
  ]
}
```

## Proposed check rules and reason codes

| Check | Status rule | Allowed reason codes |
|---|---|---|
| `api_liveness` | `PASS` when the API handles the diagnostics request. If the process cannot handle it, no diagnostics response is available. | `API_RESPONDING` |
| `esp32_transport` | `PASS` when connected; `WARNING` when disconnected; `UNKNOWN` if the state cannot be read. This check does not imply controller readiness. | `TRANSPORT_CONNECTED`, `TRANSPORT_DISCONNECTED`, `TRANSPORT_STATE_UNAVAILABLE` |
| `sensor_telemetry` | `PASS` if a complete valid sensor `TEL` frame was received within 1,000 ms; `WARNING` if the last complete valid frame is older than 1,000 ms; `UNKNOWN` if none has been observed or freshness cannot be measured. `NA` and `FAR` readings count as fresh when in a complete valid frame. | `TELEMETRY_FRESH`, `TELEMETRY_STALE`, `TELEMETRY_NOT_OBSERVED`, `TELEMETRY_STATE_UNAVAILABLE` |
| `controller_readiness` | `UNKNOWN` until READY is observed. It may be `PASS` only after a READY signal is observed. A serial connection alone never makes it `PASS`. | `READY_OBSERVED`, `READY_NOT_OBSERVED`, `READY_TRACKING_NOT_IMPLEMENTED` |

`FAIL` is an allowed status value, but the initial checks above do not assign it without an explicitly tracked and approved failure condition. This avoids treating a connection or missing observation as proof of a firmware failure.

## Approval record

- Vishal: route, Bearer authentication, read-only behavior, status vocabulary, no remote logs, evidence limits, and one-second telemetry freshness confirmed.
- Niteshvar: confirmed field names, enums, reason codes, timestamp semantics, and required-but-nullable sensor `age_ms` on 2026-11-09; no field changes requested.
- Backend implementation: read-only Bearer-authenticated route and READY event tracking implemented; automated verification pending.
- Tharun / firmware READY evidence: live readiness observation is not yet claimed. The Pi reports `UNKNOWN` until the READY frame is observed on the current serial connection.
