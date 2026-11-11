import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core import local_api_access


class LocalApiNetworkGateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.profile_path = Path(self.temp_dir.name) / "hotspot-profile.uuid"
        self.profile_uuid = str(uuid.uuid4())
        self.profile_path.write_text(self.profile_uuid, encoding="ascii")

    def _nmcli(self, command, **_kwargs):
        field = command[2]
        value = {
            "GENERAL.CON-UUID": self.profile_uuid,
            "IP4.GATEWAY": "192.168.43.1",
        }[field]
        return SimpleNamespace(returncode=0, stdout=value + "\n")

    def test_profile_uuid_is_persisted_with_private_permissions(self):
        with patch.object(local_api_access, "state_dir", return_value=Path(self.temp_dir.name)):
            local_api_access.remember_hotspot_profile(self.profile_uuid.upper())
        self.assertEqual(self.profile_path.read_text(encoding="ascii").strip(), self.profile_uuid)
        self.assertEqual(self.profile_path.stat().st_mode & 0o777, 0o600)

    def test_only_active_provisioned_phone_gateway_is_allowed(self):
        with (
            patch.object(local_api_access, "provisioned_hotspot_profile_path", return_value=self.profile_path),
            patch.object(local_api_access, "wifi_interface", return_value="wlan0"),
            patch.object(local_api_access, "ipv4_for_interface", return_value="192.168.43.10"),
            patch.object(local_api_access.subprocess, "run", side_effect=self._nmcli, create=True),
        ):
            self.assertTrue(local_api_access.local_api_peer_allowed(
                "192.168.43.10", "192.168.43.1", 8443
            ))
            self.assertFalse(local_api_access.local_api_peer_allowed(
                "192.168.43.10", "192.168.43.2", 8443
            ))
            self.assertFalse(local_api_access.local_api_peer_allowed(
                "192.168.43.11", "192.168.43.1", 8443
            ))

    def test_other_active_network_disables_listener_gate(self):
        def other_profile(command, **_kwargs):
            result = self._nmcli(command)
            if command[2] == "GENERAL.CON-UUID":
                result.stdout = str(uuid.uuid4()) + "\n"
            return result

        with (
            patch.object(local_api_access, "provisioned_hotspot_profile_path", return_value=self.profile_path),
            patch.object(local_api_access, "wifi_interface", return_value="wlan0"),
            patch.object(local_api_access, "ipv4_for_interface", return_value="192.168.43.10"),
            patch.object(local_api_access.subprocess, "run", side_effect=other_profile, create=True),
        ):
            self.assertFalse(local_api_access.local_api_peer_allowed(
                "192.168.43.10", "192.168.43.1", 8443
            ))


if __name__ == "__main__":
    unittest.main()
