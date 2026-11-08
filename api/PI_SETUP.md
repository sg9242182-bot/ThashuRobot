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

Stop the robot and API together with `Ctrl+C`.

## Recovery checks (development only)

These steps help identify which process needs attention. They do not prove that
the physical robot is safe, and they do not replace Tharun's robot checks.

| Situation | Check and response |
|---|---|
| Pi reboot | Start the robot process using the setup steps above. The API starts inside it and uses the same `RobotCommandManager` and ESP32 transport. Check `/health` for API liveness and `/api/v1/status` for the reported transport state. The API does not replay commands left in flight; their stored result becomes `unknown`. |
| ESP32 disconnected | `/api/v1/status` reports `disconnected` or `unavailable`; do not treat serial reconnect as controller readiness. The Pi retries serial discovery with a 1, 2, 4, 8, 16, then 30 second capped backoff. Movement remains subject to the manager's mode, ACK, and fresh-sensor checks. A disconnected link cannot confirm STOP; the ESP32 watchdog is a separate hardware safety layer. |
| API startup failure | Read the robot process console for the structured `api_start_failed` event. The API does not log the Bearer token. Check the configured host/port and whether another process is using the port. Do not start a second API beside `thashu/main.py` while it owns the ESP32 serial connection. |
| API process shutdown | Use `Ctrl+C` in the robot process terminal. The embedded API receives a graceful shutdown request and waits up to five seconds for its server thread. A structured `api_shutdown_timeout` warning means shutdown did not finish within that wait; inspect the process before restarting it. |
| Configuration error | Review setting names and allowed values in the environment-variable table below. Correct the value in the process environment and restart. Never paste the token into logs, screenshots, GitHub, or chat. |

Do not delete the SQLite state file during its 24-hour request retry window. Do
not enable automatic restart or a system service until Tharun confirms the Pi
paths, serial permissions, and safe restart procedure.

## 5. Prepare app access later

`127.0.0.1` works only on the Pi itself. Do not expose port 8000 to the public internet. For private-LAN phone access, set `THASHU_API_HOST=0.0.0.0` and configure both TLS paths in the robot process environment. The certificate SAN must match the Pi hostname/IP entered in Flutter, and Flutter must trust its CA/certificate. Without TLS configured, the server refuses a non-loopback bind. Share any test token only through a secure channel.

## Backend environment settings

Settings are read and validated by `thashu/core/config.py`:

| Variable | Default | Purpose |
|---|---|---|
| `THASHU_API_HOST` | `127.0.0.1` | API bind address. Non-loopback binds require TLS files. |
| `THASHU_API_TLS_CERTFILE` | unset | TLS certificate path; required with key for non-loopback access. |
| `THASHU_API_TLS_KEYFILE` | unset | Matching TLS private-key path; keep it outside the repo and restrict file permissions. |
| `THASHU_API_PORT` | `8000` | API port, from 1 through 65535. |
| `THASHU_API_TOKEN` | unset | Bearer token; control routes fail closed until set. |
| `THASHU_API_STATE_DB` | OS-specific persistent user state path | SQLite command/idempotency records. |
| `THASHU_MODELS_DIR` | `~/.local/share/thashu/models` | Installed model files. |
| `THASHU_DATA_DIR` | `~/.local/share/thashu/data` | Persistent robot data. |
| `THASHU_PIPER_BIN` | `~/piper/piper/piper` | Piper executable. |
| `THASHU_VOICE_CACHE_DIR` | `$XDG_DATA_HOME/thashu/voice_responses` | Generated voice cache. |
| `THASHU_FACE_MATCH_DEBUG` | `0` | Enables extra face-match debug output when set to `1`. |

Invalid ports, blank path overrides, or a face-match debug value other than `0`/`1` stop startup/use with a configuration error.

## Automatic startup

Do not enable an automatic-start service until Tharun confirms the Pi's install location, service account, serial-device permissions, and private-network setup. Store the token in a root-readable environment file outside the repository; never put it in a committed service file.


## HTTPS setup for private-LAN phone access

TLS listener support is implemented, but deployment is not complete: no certificate, trust anchor, or stable Pi hostname has been selected or installed. Vishal and Tharun need to choose the stable address (a DHCP-reserved IP or a hostname that resolves on the phone's local network) and coordinate the certificate trust method with Niteshvar. The app currently requires HTTPS and uses Android's normal certificate validation; it does not disable checks or include a private CA.

Create or install a certificate and matching key outside the repository. The
certificate must include the Pi's chosen private hostname or static LAN IP as
a Subject Alternative Name. Set the runtime environment securely, for example
in the systemd environment file:

```ini
THASHU_API_HOST=0.0.0.0
THASHU_API_PORT=8000
THASHU_API_TLS_CERTFILE=/etc/thashu/tls/pi-api.crt
THASHU_API_TLS_KEYFILE=/etc/thashu/tls/pi-api.key
```

Restrict the private key to the robot service account. The Android app must
trust the certificate chain or an explicitly pinned certificate; never turn
off TLS hostname or certificate verification. Keep the API on the private LAN
and firewall its port to trusted clients. No internet connection is required
for the robot or this local API.
