# Pi Diagnostics Contract — Review Draft

**Status: PROPOSAL ONLY — not approved for implementation.**

This draft prepares the Phase 6 decisions. It does not change the existing API
or authorize a new route. Current API behavior remains the contract in
[`api/README.md`](../../api/README.md).

## What the backend can currently prove

- `GET /health` proves that the FastAPI process answered the request. It is a
  liveness check, not proof that the robot or ESP32 is ready.
- `GET /api/v1/status` reports API liveness, ESP32 transport as
  `connected`, `disconnected`, or `unavailable`, the Pi control mode, and
  `controller_readiness: "unknown"` because the API does not track
  `EVENT|0|READY` or firmware fault state.
- `WS /api/v1/telemetry` sends timestamped raw ESP32 lines and command-result
  events. Flutter derives sensor freshness from received sensor frames using
  the agreed one-second interval. The Pi status response does not currently
  expose parsed sensor freshness.
- Move and STOP outcomes are recorded in structured API logs. The logs are not
  available through an HTTP endpoint.

## Decisions requested

Please confirm or edit each proposal before backend implementation:

1. **Diagnostics route and access:** Should the API add a read-only,
   Bearer-authenticated `GET /api/v1/diagnostics` route? Existing `/health` and
   `/api/v1/status` remain unchanged and public.
2. **Check statuses:** Proposed values are `PASS`, `WARNING`, `FAIL`, and
   `UNKNOWN`.
   - `PASS`: the check ran and its documented evidence met the healthy rule.
   - `WARNING`: the check ran and found a degraded condition that does not
     establish a complete failure.
   - `FAIL`: the check ran and its evidence met a documented failure rule.
   - `UNKNOWN`: the check could not run or available evidence cannot decide.
3. **Initial checks and evidence:** Proposed initial checks are:
   - `api`: successful local process response.
   - `esp32_transport`: the existing transport connection state.
   - `controller_readiness`: only a tracked firmware READY/FAULT event; until
     that tracker exists, report `UNKNOWN` with reason
     `READINESS_NOT_TRACKED`.
   - `sensor_telemetry`: only a parsed sensor frame timestamped at Pi receipt;
     use the agreed one-second freshness interval. Do not treat `NA` or `FAR`
     as a stale stream. If the Pi cannot parse/track the stream, report
     `UNKNOWN`, not `PASS`.
   - Do not report voice, camera, model, or other subsystem health until that
     subsystem exposes an explicit check and its owner agrees on the evidence.
4. **Response shape:** Proposed envelope:

   ```json
   {
     "observed_at": "<UTC ISO 8601>",
     "checks": [
       {
         "name": "esp32_transport",
         "status": "WARNING",
         "reason_code": "TRANSPORT_DISCONNECTED",
         "checked_at": "<UTC ISO 8601>"
       }
     ]
   }
   ```

   Should each check also include `age_ms` or `last_success_at` when relevant?
   Reason codes should be stable machine-readable values; no exception text,
   tokens, private user content, face identity, image, or embedding is included.
5. **Logs:** Recommended for the first mobile API contract: do not expose log
   retrieval over HTTP. Keep operational logs on the Pi for its administrator,
   with redaction and bounded local retention. Confirm whether the app needs a
   remote log view; if yes, agree its authorization, filtering, size cap, and
   redaction before implementing it.
6. **Owners:** Tharun confirms which firmware READY/FAULT and sensor evidence
   the Pi may rely on. Niteshvar confirms whether the app needs this route,
   response shape, and remote log access.

## Approval record

- Tharun: pending
- Niteshvar: pending
- Backend implementation: blocked until route, statuses, evidence rules, and
  log-access decision are approved.
