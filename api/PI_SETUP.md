# Raspberry Pi API setup

This guide is for Tharun to prepare the Pi when it is available. It installs and runs the API; it does not verify robot movement.

## 1. Get the backend code

Use the reviewed backend revision. The current integration branch is `phase-12-pi-api-https`, based on current `main`; it contains the API, shared Pi runtime integration, and HTTPS configuration. From the repository root on the Pi:

```bash
git status --short
git switch phase-12-pi-api-https
git pull --ff-only origin phase-12-pi-api-https
```

If the Pi has uncommitted work, stop before switching or pulling and review it first. Do not pull the older `vishal-phase1` branch for this integration.

## 2. Install the Python dependencies

The target Pi runs Raspberry Pi OS Bookworm (Debian, no desktop) with Python 3.11.2, confirmed by Tharun. The API supports Python 3.10 or newer, so this target meets the code's minimum. A desktop environment is not needed. From the repository root:

```bash
sudo apt update
sudo apt install -y python3-venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r api/requirements.txt
```

## 3. Create a private test token

Generate a fresh token on the Pi:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Keep it out of GitHub, screenshots, and group chat. For a first local run, set it only in the terminal that starts the API:

```bash
export THASHU_API_TOKEN='paste-the-new-token-here'
```

## 4. Start the robot and API together

The API now runs inside the robot process and shares its single ESP32 serial connection. Do not start Uvicorn separately while the robot process is running.

From the repository root on the Pi:

```bash
cd thashu
python main.py
```

The API listens on `127.0.0.1:8000` by default. In another terminal on the Pi, open `http://127.0.0.1:8000/docs`. The health route checks only that the API process is responding. Do not send movement requests as part of setup; Tharun handles robot verification.

Command IDs and retry records are stored in SQLite for 24 hours at
`~/.local/state/thashu/api_state.sqlite3`. Keep this file on writable,
persistent storage. To choose another location, set `THASHU_API_STATE_DB` in
the robot process environment before starting it.

Stop the robot and API together with `Ctrl+C`. The API invalidates any active
movement lease and sends normal STOP during graceful shutdown. The startup STOP
and lease timeout preserve the selected mode; they do not perform a reset.

## Recovery checks (development only)

These steps help identify which process needs attention. They do not prove that
the physical robot is safe, and they do not replace Tharun's robot checks.

| Situation | Check and response |
|---|---|
| Pi reboot | The API starts inside the robot process and sends normal STOP before serving requests, without changing the selected mode. Movement leases are in memory and are lost; persisted in-flight commands become `unknown` and are never replayed. If startup STOP is not acknowledged, movement remains inhibited. Require a fresh move request after restart; never restore a prior lease. |
| ESP32 disconnected/restarted | `/api/v1/status` reports `disconnected` or `unavailable`; do not treat serial reconnect as controller readiness. The Pi retries serial discovery with a 1, 2, 4, 8, 16, then 30 second capped backoff. Disconnect and a new `EVENT|0|READY` clear the old sensor snapshot. Movement remains blocked until the serial link is open and a new complete sensor frame passes freshness checks. A disconnected link cannot confirm STOP; the ESP32 watchdog is a separate hardware safety layer. |
| Mobile app disconnect | No authenticated telemetry WebSocket means the API rejects new move and lease-renewal requests. An active manual movement lease expires after a provisional 500 ms without renewal and the Pi sends normal STOP. It does not change mode or issue a reset. A reconnect does not revive the lease; a fresh move request is required. |
| API startup failure | Read the robot process console for the structured `api_start_failed` event. The API does not log the Bearer token. Check the configured host/port and whether another process is using the port. Do not start a second API beside `thashu/main.py` while it owns the ESP32 serial connection. |
| API process shutdown | Use `Ctrl+C` in the robot process terminal. The embedded API receives a graceful shutdown request and waits up to five seconds for its server thread. A structured `api_shutdown_timeout` warning means shutdown did not finish within that wait; inspect the process before restarting it. |
| Configuration error | Review setting names and allowed values in the environment-variable table below. Correct the value in the process environment and restart. Never paste the token into logs, screenshots, GitHub, or chat. |

Do not delete the SQLite state file during its 24-hour request retry window. Do
not enable automatic restart or a system service until Tharun confirms the Pi
paths, serial permissions, and safe restart procedure.

## 5. Prepare app access later

`127.0.0.1` works only on the Pi itself. Do not expose port 8000 to the public
internet. For private-network phone access, follow the HTTPS setup below. The
phone needs a stable hostname it can resolve, and the certificate SAN must
match that hostname. The current Flutter app uses Android's normal certificate
validation, so its certificate chain must be trusted by the phone. Without TLS
configured, the server refuses a non-loopback bind. Share any test token only
through a secure channel.

## Backend environment settings

Settings are read and validated by `thashu/core/config.py`:

| Variable | Default | Purpose |
|---|---|---|
| `THASHU_API_HOST` | `127.0.0.1` | API bind address. Non-loopback binds require TLS files. |
| `THASHU_API_TLS_CERTFILE` | unset | Direct Uvicorn TLS certificate path; leave unset when using the approved Caddy proxy. |
| `THASHU_API_TLS_KEYFILE` | unset | Matching direct Uvicorn TLS key; leave unset with Caddy. |
| `THASHU_API_TLS_ANDROID_TRUST_CONFIRMED` | `0` | Direct non-loopback Uvicorn bind attestation; leave `0` with Caddy and the loopback API. |
| `THASHU_API_PORT` | `8000` | API port, from 1 through 65535. |
| `THASHU_API_TOKEN` | unset | Bearer token; control routes fail closed until set. |
| `THASHU_API_STATE_DB` | OS-specific persistent user state path | SQLite command/idempotency records. |
| `THASHU_MODELS_DIR` | `~/.local/share/thashu/models` | Installed model files. |
| `THASHU_DATA_DIR` | `~/.local/share/thashu/data` | Persistent robot data. |
| `THASHU_PIPER_BIN` | `~/piper/piper/piper` | Piper executable. |
| `THASHU_VOICE_CACHE_DIR` | `$XDG_DATA_HOME/thashu/voice_responses` | Generated voice cache. |
| `THASHU_FACE_MATCH_DEBUG` | `0` | Enables extra face-match debug output when set to `1`. |

Invalid ports, blank path overrides, a TLS trust confirmation other than `0`/`1`, or a face-match debug value other than `0`/`1` stop startup/use with a configuration error.

## Automatic startup

Do not enable an automatic-start service until Tharun confirms the Pi's install location, service account, serial-device permissions, and private-network setup. Store the token in a root-readable environment file outside the repository; never put it in a committed service file.


## HTTPS setup and Android verification

**Approved plan (2026-11-08):** Tailscale plus Caddy, with the Pi named
`thashu-robot` in the tailnet. The final URL uses the tailnet's actual DNS name:
`https://thashu-robot.<tailnet-name>.ts.net`. The hostname is stable across
home Wi-Fi and phone hotspots because it resolves through Tailscale, not the
Pi's changing local-network address. The Pi and each test phone must be signed
in to the authorized tailnet. MagicDNS and Tailscale HTTPS certificates must be
enabled by a tailnet administrator.

The API stays on `127.0.0.1:8000` over HTTP. Caddy listens on the Pi's Tailscale
IP at HTTPS port 443 and reverse-proxies to `127.0.0.1:8000`. Do not change the
API host to `0.0.0.0`, expose port 8000, or enable Tailscale Funnel. Keep
`THASHU_API_TLS_CERTFILE`, `THASHU_API_TLS_KEYFILE` unset and
`THASHU_API_TLS_ANDROID_TRUST_CONFIRMED=0`; Caddy handles external TLS. The
routes and Bearer-token requirements remain unchanged.

### Pi setup (run after Tailscale and Caddy are installed)

1. Install Tailscale on Raspberry Pi OS and the authorized Android phones using
   the [official Linux](https://tailscale.com/docs/install/linux) and
   [Android](https://tailscale.com/docs/install/android) instructions, then
   join them to the same tailnet. In the Tailscale admin DNS settings, enable
   MagicDNS and HTTPS certificates. Rename the Pi to the generic machine name
   `thashu-robot`; record the exact full `*.ts.net` hostname and Tailscale IP
   shown for that Pi. Tailscale certificate names are published in the public
   Certificate Transparency log, so use no personal or sensitive name.
2. Keep the robot API configured with `THASHU_API_HOST=127.0.0.1` and
   `THASHU_API_PORT=8000`. Leave API TLS file paths unset. Confirm the runtime
   starts the API on loopback before adding the proxy.
3. Tailscale provisions a Let's Encrypt certificate for the Pi's full
   `*.ts.net` name. The certificate private key is generated and kept in the
   Pi's local Tailscale state; Caddy retrieves the certificate/key from the
   local Tailscale daemon and renews it automatically. Allow the Caddy service
   account to fetch it by setting `TS_PERMIT_CERT_UID=caddy` in
   `/etc/default/tailscaled`, then restart `tailscaled`. Do not copy certificate
   keys into this repository or the Flutter app.
4. Install Caddy using its [official Debian/Raspberry Pi OS
   package](https://caddyserver.com/docs/install). Configure
   `/etc/caddy/Caddyfile`, replacing the placeholders with the Pi's
   actual MagicDNS name and Tailscale IP:

```caddyfile
thashu-robot.<tailnet-name>.ts.net {
    bind 100.x.y.z
    reverse_proxy 127.0.0.1:8000
}
```

5. Validate and reload Caddy using the Pi's service procedure. Restrict tailnet
   access to the approved phones with Tailscale access policy. Do not add a
   router port-forward or use Funnel. Confirm that Caddy listens on the Tailscale
   IP only and the API listens on loopback only.
6. In Flutter connection settings, enter
   `https://thashu-robot.<tailnet-name>.ts.net` (no `:8000`). Enter the test
   Bearer token directly in the app's secure settings; never put it in GitHub,
   this document, logs, or chat.

### Android HTTPS and telemetry test

Use an Android phone signed into the authorized tailnet and with Tailscale
connected. These are verification steps; no live Pi/Android result is claimed
until the output is recorded.

1. Open `https://thashu-robot.<tailnet-name>.ts.net/health` in the Android
   browser. Expect HTTP 200 with no certificate or hostname warning.
2. Open `/api/v1/status` on the same origin. Expect HTTP 200. Confirm that
   unauthenticated control routes remain protected; do not send a movement
   command as part of this transport check.
3. In the Flutter app, save the same HTTPS origin and the test token through
   its secure settings screen. Connect to status and telemetry. Confirm the
   authenticated WebSocket reaches `/api/v1/telemetry` using TLS, telemetry
   frames arrive, and the UI clears stale state when a new frame arrives.
4. When no fresh frame arrives for one second, confirm the UI marks telemetry
   stale; `NA` and `FAR` readings in a received frame remain fresh sensor
   states. Confirm no JSON heartbeat event is required; WebSocket Ping/Pong
   keeps the connection alive.
5. Record the phone model/Android version, app revision, Pi revision, tailnet
   hostname, certificate result, `/health` and `/api/v1/status` results, and
   telemetry/staleness result. Keep tokens and private credentials out of the
   report.

**Movement lease:** Flutter should renew a lease every 250 ms while a manual
movement control is held. The Pi expires the lease after 500 ms without a
successful renewal and sends normal STOP. The 500 ms value is provisional and
must not be called hardware-safe until Tharun completes the restrained
low-speed stopping-distance test. A renewal retry can refresh only a still-live
lease; it cannot revive an expired or STOP-cancelled lease.

**Verification status:** the lease, startup-stop, app-disconnect, restart, and
Android HTTPS/telemetry behaviors require fresh CI and live verification. The
robot's flashed firmware revision is not confirmed.
 This workstation has no `adb` command or
connected Android device, so the live phone test must be run on the project
phone. Android's normal trust uses preinstalled system CAs; no app trust change
is planned. Tailscale documents MagicDNS and certificate provisioning, and
Caddy's Tailscale integration obtains certificates from the local daemon and
supports WebSocket reverse proxying: [MagicDNS](https://tailscale.com/docs/features/magicdns),
[Tailscale HTTPS certificates](https://tailscale.com/docs/how-to/set-up-https-certificates),
[Caddy certificates on Tailscale](https://tailscale.com/docs/integrations/web-servers/caddy/caddy-certificates),
[Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy),
[Android network security](https://developer.android.com/privacy-and-security/security-config).


## App-only offline hotspot API (draft implementation)

The app-only path does not need Tailscale or internet access. The loopback API on
`127.0.0.1:8000` remains available for the existing local/Caddy path. When
explicitly enabled, the robot also serves the same API over HTTPS on the Pi's
current `wlan0` IPv4 address at port `8443`. It binds to that one address;
it does not bind to `0.0.0.0`. The two Uvicorn listeners share one asyncio
event loop and the existing ESP32 manager.

The BLE provisioning service adds encrypted, read-only characteristic
`8c6d0004-7a4b-4f61-b7a5-927f4e2a1000`. After the credentials write succeeds
and the Pi reports `connected`, the app must read it before the existing
60-second button window closes. It returns JSON fields `api_base_url`,
`server_cert_sha256`, and `api_token`. The app must save the URL, pin, and
token in secure storage. It must validate the exact TLS certificate pin for
REST and WebSocket; Android's global cleartext setting is not changed.

The Pi stores the persistent token, TLS key, certificate, and current IP under
`~/.local/share/thashu/local_api/`. Files are owner-only except the public
certificate. The TLS certificate is regenerated when the Wi-Fi IPv4 address
changes, and its IP subject alternative name matches the new URL. The token is
kept stable across address changes and restarts. The certificate pin is
delivered only over the encrypted GATT connection during the Pi-button-gated
window; credentials, token, and private key are not logged.

### Enable only after Flutter certificate pinning is integrated

Do not set the following flags until the app validates the BLE-delivered
certificate fingerprint for both HTTPS and WSS:

```bash
export THASHU_API_LOCAL_ACCESS=1
export THASHU_API_LOCAL_TLS_PINNING_CONFIRMED=1
export THASHU_API_WIFI_INTERFACE=wlan0
export THASHU_API_LOCAL_PORT=8443
```

Start the robot with those variables in its environment. If pin confirmation is
missing, the local listener stays disabled while the normal loopback API
continues to work. The app can then use the current local URL from the BLE
bundle. If DHCP changes the Pi address while running, the local listener closes,
the active WebSocket disconnects, and the existing 500 ms movement lease sends
normal STOP before the new HTTPS listener opens. Mode is preserved and motion
does not resume automatically. A process restart is not required.

Install the physical-button BLE service from
`thashu/deploy/systemd/thashu-wifi-provisioning@.service` after installing
the project's Python requirements. The service runs as root for GPIO/BlueZ,
but stores its generated token/key material for the configured robot account.
It does not own the motor controller or ESP32 serial port. It pre-generates
cached Piper WAV announcements for BLE setup opening, timeout, and shutdown.
On numeric-comparison pairing, it speaks the six-digit code; accept the phone
prompt only when it matches, then short-click GPIO 17 to confirm on the Pi.
The systemd unit points Piper and its voice cache at the robot user's files.

### Verification still required

- The Pi-side connection-info GATT addition and local HTTPS listener have not
  yet been run on hardware.
- Flutter must read the new characteristic, persist the returned URL/token/pin,
  and implement certificate pinning for HTTP and WebSocket.
- Verify from the target phone that it can reach a Pi client connected to that
  phone's hotspot, with internet disabled.
- Verify HTTPS health/status and authenticated telemetry, then repeat after
  changing the Pi hotspot address and after a Pi restart.
- Provisioning tests must not send movement commands. Confirm disconnect/rebind
  expires a movement lease with normal STOP before enabling local access for
  control.

Do not mark Phase 9 complete from code alone. Record the exact Pi/app revisions,
the no-internet phone test results, and the changed-IP/restart results first.
