# THASHU Flutter App Setup and Handoff

## Project and tools

- Project folder: `D:\ThashuRobot-phase1\mobile\flutter`
- Flutter SDK used for the current local checks: `D:\flutter` (Flutter 3.47.8)
- Target: Android phone or emulator
- API contract source: the integrated `api/README.md` on `phase-10` (Phase 10 API acceptance commit `057190a`)

## Prepare the terminal

Open VS Code PowerShell and enter the project folder:

```powershell
cd D:\ThashuRobot-phase1\mobile\flutter
$env:ANDROID_HOME = 'C:\Users\NITESHVAR.A\AppData\Local\Android\Sdk'
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:Path = "$env:ANDROID_HOME\platform-tools;$env:Path"
```

Download Flutter packages:

```powershell
D:\flutter\bin\flutter.bat pub get
```

## Run on a phone

Enable Developer options and USB debugging on the Android phone, connect it by USB, accept the phone's debugging prompt, and list devices:

```powershell
D:\flutter\bin\flutter.bat devices
```

Copy the device ID shown for the phone, then run (replace the example ID):

```powershell
D:\flutter\bin\flutter.bat run -d TCOR49Q8VCF6IBEQ
```

Press `q` in the terminal to stop the debug session. The ID can change; always use the ID shown by `flutter devices`.

## Run checks and build

Run these from the Flutter project folder:

```powershell
D:\flutter\bin\dart.bat format lib test
D:\flutter\bin\flutter.bat analyze
D:\flutter\bin\flutter.bat test
D:\flutter\bin\flutter.bat build apk --debug
```

The debug APK is written to `build\app\outputs\flutter-apk\app-debug.apk`.

## Network setup notes

- An Android emulator's `localhost` points to the emulator. For a development API running on the host computer, Android Emulator exposes the host loopback through `10.0.2.2`; use this only in a development configuration.
- A physical phone and Pi must be on a reachable private network. Use the Pi's private address over the same reachable LAN or a team-approved VPN; do not expose the API to the public internet or use port forwarding.
- Keep the Bearer token out of source code, screenshots, commits, and this file.
- The current app entry point calls `MyApp()` without API clients. The Settings screen does not collect a Pi URL or token. Until approved runtime configuration is implemented and credentials are supplied, Dashboard, Diagnostics, and movement controls correctly show unavailable states.

## Current Flutter/API integration notes

The Flutter client follows the integrated Phase 10 API contract in `api/README.md`. Health/status are unauthenticated; mode, move, STOP, command lookup, and telemetry use Bearer authentication. Moves require MANUAL mode. STOP uses `POST /api/v1/robot/stop` with a UUID `request_id`, cancels motion, and returns the Pi mode to AUTO paused. A dispatched response means the Pi wrote the serial command; the app checks the command-result route and telemetry event for the ESP32 result. An acknowledgement is not proof of physical movement or stopping.

Current contract details and ownership are in the API owner's `api/README.md`. The latest reviewed contract limits move/mode to a shared token bucket (capacity 10, refill 5 requests/second); STOP is authenticated, exempt from that limit, and prioritized ahead of queued move/mode requests. The Flutter REST client handles 429 rate limits and 503 busy-queue rejections; these errors do not become success states, and normal STOP remains available. The telemetry socket is `/api/v1/telemetry`; `esp32_line` frames carry Pi `received_at` timestamps. The Flutter Diagnostics page parses sensor frames, marks readings stale after 1 second without a valid sensor frame, and refreshes on the next valid frame, including frames with `NA` or `FAR`. Keepalive is WebSocket Ping/Pong, not a JSON heartbeat. Pairing and production TLS/pinning were not configured in the checked-in mobile entry point at this handoff. Confirm the API commit and security setup with Vishal before live use.

## Troubleshooting

- If no Android device appears, check `adb devices -l`, unlock the phone, accept the USB debugging prompt, and confirm `ANDROID_HOME` points to the installed Android SDK.
- If `flutter` or `dart` is not on PATH, use the full `D:\flutter\bin\flutter.bat` and `D:\flutter\bin\dart.bat` commands above.
- If movement controls are unavailable, check that API clients are configured and that the Pi reports the required connected/manual state. The app intentionally fails closed when the Pi address or token is absent.
- Never use physical movement as a connectivity test. Before hardware testing, agree a safe test area, secure the robot, and use the team's test procedure.

## Phase 8 verification record

- API documentation snapshot reviewed: integrated `api/README.md` on `phase-10` (Phase 10 API acceptance commit `057190a`).
- Local verification: Dart format completed, Flutter analyze reported no issues, and all 53 Flutter tests passed. Fake transports and widget fixtures cover REST, telemetry, sensor freshness, and control UI behavior.
- Tharun reported local Pi/ESP32 API checks passed for health/status, authenticated mode switching, telemetry, brief low-speed movement, and acknowledged STOP. Phone-to-Pi integration remains pending because the API currently binds to localhost; private LAN access details will be shared for a short test window. Flutter verifies connection/status/telemetry/mode/STOP first; movement awaits the agreed safe procedure.
- Android debug APK build: succeeded with Android Studio JBR on 2026-11-08. The latest APK is at `build\app\outputs\flutter-apk\app-debug.apk`; it was installed on phone `TCOR49Q8VCF6IBEQ` and Android reported `com.example.thashu_app/.MainActivity` as resumed.
- Pull request and teammate reviews: this focused Flutter PR is prepared for API/client compatibility and control-safety review; phone integration remains pending the private-LAN test window.
