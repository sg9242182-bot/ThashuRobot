"""Physical-button-gated BLE provisioning for a NetworkManager Wi-Fi profile.

Run as root under the project virtualenv. Advertising is enabled only after the
GPIO 17 button is held for three seconds; credential writes require an encrypted
BLE link and an active 60-second window. Secrets are never logged.
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
from bluez_peripheral.agent import NoIoAgent
from bluez_peripheral.advert import Advertisement
from bluez_peripheral.gatt import CharacteristicFlags as CharFlags
from bluez_peripheral.gatt import Service, characteristic
from bluez_peripheral.util import Adapter, get_message_bus


BUTTON_PIN = 17
HOLD_SECONDS = 3.0
WINDOW_SECONDS = 60.0
SERVICE_UUID = "8c6d0001-7a4b-4f61-b7a5-927f4e2a1000"
CREDENTIALS_UUID = "8c6d0002-7a4b-4f61-b7a5-927f4e2a1000"
STATUS_UUID = "8c6d0003-7a4b-4f61-b7a5-927f4e2a1000"
PROFILE_PATH = Path("/etc/NetworkManager/system-connections/thashu-phone-hotspot.nmconnection")


class ProvisionState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.armed_until = 0.0
        self.status = "idle"

    def armed(self) -> bool:
        with self.lock:
            return time.monotonic() < self.armed_until

    def arm(self) -> None:
        with self.lock:
            self.armed_until = time.monotonic() + WINDOW_SECONDS
            self.status = "waiting"

    def disarm(self) -> None:
        with self.lock:
            self.armed_until = 0.0

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

    @characteristic(CREDENTIALS_UUID, CharFlags.WRITE | CharFlags.ENCRYPT_WRITE | CharFlags.RELIABLE_WRITE)
    def credentials(self, _options):
        pass

    @credentials.setter
    def credentials(self, value: bytes, _options) -> None:
        if not STATE.armed():
            raise DBusError("org.bluez.Error.NotPermitted", "Provisioning window is closed.")
        try:
            ssid, password = _validate_credentials(value)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            STATE.set_status("invalid")
            raise DBusError("org.bluez.Error.InvalidArgs", "Invalid Wi-Fi credentials.")
        STATE.disarm()
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
    agent = NoIoAgent()
    await agent.register(bus)
    adapter = await Adapter.get_first(bus)
    print("[BLE SETUP] Ready; hold the Pi button for 3 seconds to open a 60-second setup window.")

    press_started = None
    advertised_until = 0.0
    advert = None
    try:
        while True:
            now = time.monotonic()
            pressed = GPIO.input(BUTTON_PIN) == GPIO.LOW
            if pressed and press_started is None:
                press_started = now
            elif not pressed:
                press_started = None

            if press_started is not None and now - press_started >= HOLD_SECONDS and now >= advertised_until:
                STATE.arm()
                advertised_until = now + WINDOW_SECONDS
                advert = Advertisement("Thashu Setup", [SERVICE_UUID], timeout=int(WINDOW_SECONDS))
                await advert.register(bus, adapter)
                print("[BLE SETUP] Pairing window open for 60 seconds.")
            if advertised_until and now >= advertised_until:
                advertised_until = 0.0
                if STATE.get_status() == "waiting":
                    STATE.set_status("expired")
                STATE.disarm()
                print("[BLE SETUP] Pairing window closed.")
            await asyncio.sleep(0.05)
    finally:
        STATE.disarm()
        GPIO.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
