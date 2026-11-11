"""Physical-button-gated BLE provisioning for a NetworkManager Wi-Fi profile.

Run as root under the project virtualenv. A short GPIO 17 click opens a
60-second BLE setup window; holding the button for three seconds shuts down
the Pi. Credential writes require an encrypted BLE link. Secrets are never logged.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

import RPi.GPIO as GPIO
from dbus_next.errors import DBusError
from bluez_peripheral.agent import YesNoAgent
from bluez_peripheral.advert import Advertisement
from bluez_peripheral.gatt.characteristic import CharacteristicFlags as CharFlags
from bluez_peripheral.gatt.characteristic import characteristic
from bluez_peripheral.gatt.service import Service
from bluez_peripheral.util import Adapter, get_message_bus
from hardware.shutdown_button import (
    BUTTON_PIN,
    HOLD_SECONDS,
    ButtonGesture,
    request_robot_shutdown,
)


WINDOW_SECONDS = 60.0
SERVICE_UUID = "8c6d0001-7a4b-4f61-b7a5-927f4e2a1000"
CREDENTIALS_UUID = "8c6d0002-7a4b-4f61-b7a5-927f4e2a1000"
STATUS_UUID = "8c6d0003-7a4b-4f61-b7a5-927f4e2a1000"
CONNECTION_INFO_UUID = "8c6d0004-7a4b-4f61-b7a5-927f4e2a1000"
PROFILE_PATH = Path("/etc/NetworkManager/system-connections/thashu-phone-hotspot.nmconnection")


class ProvisionState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.armed_until = 0.0
        self.status = "idle"
        self.credentials_accepted = False
        self.pairing_event: asyncio.Event | None = None
        self.pairing_passkey: int | None = None
        self.pairing_approved = False

    def armed(self) -> bool:
        with self.lock:
            return time.monotonic() < self.armed_until

    def arm(self) -> None:
        with self.lock:
            self.armed_until = time.monotonic() + WINDOW_SECONDS
            self.status = "waiting"
            self.credentials_accepted = False

    def disarm(self) -> None:
        with self.lock:
            self.armed_until = 0.0
            event = self.pairing_event
            self.pairing_event = None
            self.pairing_passkey = None
            self.pairing_approved = False
        if event is not None:
            event.set()

    def mark_credentials_accepted(self) -> bool:
        with self.lock:
            if time.monotonic() >= self.armed_until or self.credentials_accepted:
                return False
            self.credentials_accepted = True
            return True

    def may_read_connection_info(self) -> bool:
        with self.lock:
            return (
                time.monotonic() < self.armed_until
                and self.credentials_accepted
                and self.status == "connected"
            )

    def complete_pairing(self) -> None:
        with self.lock:
            self.armed_until = 0.0

    def info(self) -> bytes:
        if not self.may_read_connection_info():
            raise DBusError(
                "org.bluez.Error.NotPermitted",
                "Connection information is available only after hotspot setup in the active button window.",
            )
        try:
            from core.local_api_access import connection_info
            payload = connection_info()
        except Exception as exc:
            raise DBusError(
                "org.bluez.Error.NotReady",
                "Local API connection information is not ready.",
            ) from exc
        self.complete_pairing()
        return payload

    def set_status(self, value: str) -> None:
        with self.lock:
            self.status = value

    def get_status(self) -> str:
        with self.lock:
            if self.armed_until and time.monotonic() >= self.armed_until:
                self.armed_until = 0.0
                if self.status == "waiting":
                    self.status = "expired"
            return self.status

    def begin_pairing_confirmation(self, event: asyncio.Event, passkey: int) -> bool:
        with self.lock:
            if time.monotonic() >= self.armed_until or self.pairing_event is not None:
                return False
            self.pairing_event = event
            self.pairing_passkey = passkey
            self.pairing_approved = False
            return True

    def confirm_pairing(self) -> bool:
        with self.lock:
            event = self.pairing_event
            if event is None or time.monotonic() >= self.armed_until:
                return False
            self.pairing_approved = True
            event.set()
            return True

    def cancel_pairing_confirmation(self) -> None:
        with self.lock:
            event = self.pairing_event
            self.pairing_approved = False
        if event is not None:
            event.set()

    def pairing_was_approved(self) -> bool:
        with self.lock:
            return self.pairing_approved and time.monotonic() < self.armed_until

    def end_pairing_confirmation(self) -> None:
        with self.lock:
            self.pairing_event = None
            self.pairing_passkey = None
            self.pairing_approved = False

    def pairing_confirmation_pending(self) -> bool:
        with self.lock:
            return self.pairing_event is not None


STATE = ProvisionState()


def _keyfile_escape(value: str) -> str:
    escaped = []
    for index, char in enumerate(value):
        if char == "\\":
            escaped.append("\\\\")
        elif char == "\n":
            escaped.append("\\n")
        elif char == "\r":
            escaped.append("\\r")
        elif char == "\t":
            escaped.append("\\t")
        elif char == " " and index in (0, len(value) - 1):
            escaped.append("\\s")
        else:
            escaped.append(char)
    return "".join(escaped)

def _validate_credentials(raw: bytes) -> tuple[str, str]:
    if len(raw) > 512:
        raise ValueError("credentials payload too large")
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict) or set(obj) != {"ssid", "password"}:
        raise ValueError("expected ssid and password")
    ssid, password = obj["ssid"], obj["password"]
    if not isinstance(ssid, str) or not isinstance(password, str):
        raise ValueError("ssid and password must be strings")
    if not (1 <= len(ssid.encode("utf-8")) <= 32) or any(ord(c) < 32 or ord(c) == 127 for c in ssid):
        raise ValueError("invalid SSID")
    if not (8 <= len(password) <= 63 or (len(password) == 64 and re.fullmatch(r"[0-9a-fA-F]{64}", password))):
        raise ValueError("invalid WPA2 password")
    if any(c in password for c in "\r\n\x00"):
        raise ValueError("invalid password")
    return ssid, password


def _write_profile(ssid: str, password: str) -> str:
    connection_uuid = str(uuid.uuid4())
    body = (
        "[connection]\n"
        "id=Thashu phone hotspot\n"
        f"uuid={connection_uuid}\n"
        "type=wifi\n"
        "autoconnect=true\n"
        "\n[wifi]\n"
        "mode=infrastructure\n"
        f"ssid={_keyfile_escape(ssid)}\n"
        "\n[wifi-security]\n"
        "key-mgmt=wpa-psk\n"
        f"psk={_keyfile_escape(password)}\n"
        "\n[ipv4]\nmethod=auto\n"
        "\n[ipv6]\nmethod=auto\n"
    )
    PROFILE_PATH.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    temporary = PROFILE_PATH.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, PROFILE_PATH)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    from core.local_api_access import remember_hotspot_profile
    remember_hotspot_profile(connection_uuid)
    return connection_uuid


def _apply_network(ssid: str, password: str) -> None:
    import subprocess

    try:
        connection_uuid = _write_profile(ssid, password)
        STATE.set_status("connecting")
        reload_result = subprocess.run(
            ["nmcli", "connection", "reload"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
        if reload_result.returncode != 0:
            raise RuntimeError("NetworkManager profile reload failed")
        result = subprocess.run(
            ["nmcli", "--wait", "25", "connection", "up", "uuid", connection_uuid],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
        STATE.set_status("connected" if result.returncode == 0 else "failed")
    except Exception:
        STATE.set_status("failed")


class WifiProvisioningService(Service):
    def __init__(self) -> None:
        super().__init__(SERVICE_UUID, True)

    @characteristic(STATUS_UUID, CharFlags.READ)
    def status(self, _options) -> bytes:
        return STATE.get_status().encode("ascii")

    @characteristic(CREDENTIALS_UUID, CharFlags.WRITE | CharFlags.ENCRYPT_AUTHENTICATED_WRITE | CharFlags.RELIABLE_WRITE)
    def credentials(self, _options):
        pass

    @characteristic(CONNECTION_INFO_UUID, CharFlags.READ | CharFlags.ENCRYPT_AUTHENTICATED_READ)
    def connection_info(self, _options) -> bytes:
        return STATE.info()

    @credentials.setter
    def credentials(self, value: bytes, _options) -> None:
        if not STATE.armed():
            raise DBusError("org.bluez.Error.NotPermitted", "Provisioning window is closed.")
        try:
            ssid, password = _validate_credentials(value)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            STATE.set_status("invalid")
            raise DBusError("org.bluez.Error.InvalidArgs", "Invalid Wi-Fi credentials.")
        if not STATE.mark_credentials_accepted():
            raise DBusError("org.bluez.Error.NotPermitted", "Only one credential write is allowed per pairing window.")
        STATE.set_status("received")
        threading.Thread(
            target=_apply_network,
            args=(ssid, password),
            name="thashu-wifi-provision",
            daemon=True,
        ).start()


async def run() -> None:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    bus = await get_message_bus()
    service = WifiProvisioningService()
    await service.register(bus)
    async def request_pairing_confirmation(passkey: int) -> bool:
        if not STATE.armed():
            return False
        approval = asyncio.Event()
        if not STATE.begin_pairing_confirmation(approval, passkey):
            return False
        try:
            # The phone displays the same number in its Bluetooth pairing
            # prompt. The owner compares it with Thashu's spoken digits and
            # confirms on the phone before short-clicking this Pi button.
            await asyncio.to_thread(_speak_pairing_code, passkey)
            await asyncio.wait_for(approval.wait(), timeout=30.0)
            return STATE.pairing_was_approved()
        except Exception:
            return False
        finally:
            STATE.end_pairing_confirmation()

    def cancel_pairing_confirmation() -> None:
        STATE.cancel_pairing_confirmation()

    agent = YesNoAgent(request_pairing_confirmation, cancel_pairing_confirmation)
    await agent.register(bus)
    adapter = await Adapter.get_first(bus)
    print("[BLE SETUP] Ready; short-click GPIO 17 for setup, or hold for 3 seconds to shut down.")

    button = ButtonGesture(hold_seconds=HOLD_SECONDS)
    advertised_until = 0.0
    try:
        while True:
            now = time.monotonic()
            pressed = GPIO.input(BUTTON_PIN) == GPIO.LOW
            action = button.update(pressed, now)

            if action == "ble":
                if STATE.pairing_confirmation_pending() and STATE.confirm_pairing():
                    print("[BLE SETUP] Numeric comparison approved with the Pi button.")
                elif now >= advertised_until:
                    STATE.arm()
                    advertised_until = now + WINDOW_SECONDS
                    advert = Advertisement(
                        "Thashu Setup",
                        [SERVICE_UUID],
                        appearance=0,
                        timeout=int(WINDOW_SECONDS),
                    )
                    await advert.register(bus, adapter)
                    print("[BLE SETUP] Short click detected; pairing window open for 60 seconds.")
            elif action == "shutdown":
                STATE.disarm()
                print("[SYSTEM] Three-second button hold detected; shutting down cleanly.")
                threading.Thread(
                    target=request_robot_shutdown,
                    name="thashu-button-shutdown",
                    daemon=True,
                ).start()

            if advertised_until and now >= advertised_until:
                advertised_until = 0.0
                if STATE.get_status() not in {"connected", "failed", "invalid"}:
                    STATE.set_status("expired")
                STATE.disarm()
                print("[BLE SETUP] Pairing window closed.")
            await asyncio.sleep(0.05)
    finally:
        STATE.disarm()
        GPIO.cleanup()


def _speak_pairing_code(passkey: int) -> None:
    """Announce the BlueZ numeric-comparison code without logging it."""
    digits = " ".join(f"{passkey:06d}")
    from voice.text_to_speech import speak
    speak(f"Bluetooth pairing code: {digits}. Compare it with the phone.")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
