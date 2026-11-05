# Raspberry Pi API setup

This guide is for Tharun to prepare the Pi when it is available. It installs and runs the API; it does not verify robot movement.

## 1. Get the backend code

Use the team's approved repository access and the `vishal-phase1` branch. From the repository root on the Pi:

```bash
git status --short
git switch vishal-phase1
git pull
```

If the Pi already has uncommitted work, stop before switching branches or pulling and review it first.

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

## 5. Prepare app access later

`127.0.0.1` works only on the Pi itself. Do not expose port 8000 to the public internet. Before the Flutter app connects, Tharun and Vishal need to arrange a private, encrypted connection and restrict access with the Pi firewall. Then set `THASHU_API_HOST=0.0.0.0` in the robot process environment, and provide Niteshvar the Pi's private-network address and a fresh test token through a secure channel. Rotate the test token after the test.

## Backend environment settings

Settings are read and validated by `thashu/core/config.py`:

| Variable | Default | Purpose |
|---|---|---|
| `THASHU_API_HOST` | `127.0.0.1` | API bind address; use `0.0.0.0` only after private-network/firewall setup. |
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
