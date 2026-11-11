# Offline local API onboarding contract

This document defines the Pi-side extension required for app-only phone-hotspot use. It does not change the REST/WebSocket API routes or the ESP32 protocol.

## Security and connection flow

1. The operator short-clicks the Pi GPIO 17 button. The Pi advertises the existing BLE provisioning service for 60 seconds. Holding the button for 3 seconds requests graceful robot cleanup and Pi shutdown.
2. The operator starts provisioning in the Thashu app. The app writes the hotspot SSID/password through the encrypted GATT credentials characteristic. The password is never logged or persisted by the app.
3. The Pi joins the hotspot and obtains its current Wi-Fi address.
4. During the same physical authorization window, the app reads a new encrypted GATT connection-info characteristic. The Pi returns a small JSON bundle containing:
   - `api_base_url`: `https://<current-pi-wifi-address>:8443`
   - `server_cert_sha256`: SHA-256 of the exact DER server certificate, lowercase hex
   - `api_token`: the persistent random Bearer token for this Pi
5. The app keeps the BLE connection open until it receives the bundle, then stores the URL, certificate pin, and token in platform secure storage. The app validates the server certificate against the pin for both REST and WebSocket TLS connections.
6. REST and telemetry use the existing routes and Bearer-token contract. No movement command is sent during provisioning.

The Pi certificate is self-signed and includes the assigned Wi-Fi address as an IP subject alternative name. The private key and persistent token stay in a Pi-only data directory with owner-only permissions. The certificate is public material; the private key and token are never logged or sent except the token and public certificate fingerprint over the existing encrypted, physically gated BLE pairing session.

## Bind and lifecycle

- The root BLE provisioning service is the sole GPIO 17 owner. `main.py` does not claim that pin; a long hold interrupts the robot process so it runs its normal shutdown cleanup before the Pi powers off. Do not run a second button-monitor process.
- API access on the local hotspot requires HTTPS and a non-loopback bind to the Pi's Wi-Fi address only. Do not bind to `0.0.0.0`, expose port 8000, or enable plain HTTP.
- The existing loopback/Tailscale+Caddy setup remains available for development and is not required for offline hotspot access.
- If NetworkManager assigns a different Pi address after reconnect/reboot, the operator repeats the button-gated app pairing to retrieve the current URL and certificate pin. The API never replays movement after restart; existing startup STOP/lease behavior remains unchanged.
- Preserve public health/status policy and the existing Bearer-token protection on diagnostics, control, command results, and telemetry.
- Do not include the credentials, token, Wi-Fi address, or certificate private key in logs.

## GATT addition

Keep the existing service, credentials, and status UUIDs. Add one read-only `ENCRYPT_READ` connection-info characteristic at:

`8c6d0004-7a4b-4f61-b7a5-927f4e2a1000`

The read is allowed only after the credentials have been accepted in the current open 60-second pairing window and the Pi reports Wi-Fi connected. Before that, return a defined unavailable status without exposing the token. The Pi closes the pairing window after the app successfully reads the connection bundle or when the 60-second window expires. The credentials characteristic remains write-once per window.

## Verification required

- Unit tests: certificate/key and token file permissions; stable token across process restart; IP SAN matches the URL; info read denied outside authorization; no secrets in logs; existing auth and routes unchanged.
- Pi local test: phone app provisions hotspot, obtains connection bundle, connects to HTTPS health/status and authenticated telemetry with internet disabled; repeat after Pi restart and changed DHCP address.
- Confirm from the target Android phone that hotspot client routing lets the phone reach its connected Pi client. If the handset blocks that route, do not declare onboarding complete.
- No movement commands or robot-control tests are part of provisioning verification.
