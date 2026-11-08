# Bluetooth Wi-Fi setup

The Pi advertises a BLE provisioning service only while its physical button is
held for 3 seconds. The app must also be used to scan, connect, and send the
hotspot credentials. The BLE credential characteristic requires an encrypted
link. The window closes after 60 seconds or after one credential write.

## Pi prerequisites

This implementation targets Raspberry Pi OS Bookworm with BlueZ and
NetworkManager. Install them if missing:

```sh
sudo apt update
sudo apt install -y bluez network-manager
```

With the project's virtual environment active, install the project requirements
(which include `bluez-peripheral`), then install the service template:

```sh
cd ~/ThashuRobot/thashu
source ~/.venvs/thashu/bin/activate
python -m pip install -r requirements.txt
sudo install -m 0644 deploy/systemd/thashu-wifi-provisioning@.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now thashu-wifi-provisioning@tharun.service
```

Replace `tharun` in the final command if the Pi account has a different name.
The system service runs the BLE server as root because BlueZ requires the default
pairing agent to be registered with elevated permission. The server polls GPIO
17 but never drives it. The normal Thashu process also reads that pin: a quick
press still requests clean shutdown; a 3-second hold is reserved for setup.

## Phone flow

1. Turn on the phone hotspot and keep this page open.
2. Hold the Pi's shutdown button for 3 seconds. The Pi logs that its setup window
   is open; it remains advertised for 60 seconds.
3. Enter the hotspot SSID and password, then tap **Connect & send** in the app.
4. The app connects to the Thashu Setup BLE service, sends credentials once,
   clears the password field, and reads the result.
5. The Pi creates a dedicated NetworkManager profile with root-only permissions
   and attempts to connect. Existing Wi-Fi profiles are preserved.

The hotspot must use WPA2 personal (WPA-PSK). SSIDs are limited to the Wi-Fi
standard's 32-byte limit; WPA passphrases must be 8–63 characters (or 64 hex
digits). Passwords are never written to application logs. The app does not
persist them. NetworkManager necessarily stores the accepted key locally so it
can reconnect after reboot.

The Pi and app use the same custom GATT UUIDs defined in
`hardware/wifi_provisioning.py`. Status values are `waiting`, `received`,
`connecting`, `connected`, `failed`, `invalid`, and `expired`.

## Safety and security notes

The device does not advertise continuously and rejects credential writes outside
the physical-button window. BLE link encryption is required; this setup uses
BlueZ's no-input/no-output pairing agent, so pairing is Just Works and does not
provide a human-verified passkey. The button and short advertising window are
the authorization gate. Do not run setup in a public place.

The phone and Pi must be in BLE range. This provisions Wi-Fi only; app API
controls still require the Pi API service and its separately configured
address/token.
