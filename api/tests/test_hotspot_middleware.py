import unittest
from unittest.mock import patch

from api.hotspot_access import HotspotListenerAccessMiddleware


class HotspotListenerAccessMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def _call(self, scope):
        messages = []
        called = []

        async def app(_scope, _receive, _send):
            called.append(True)

        async def send(message):
            messages.append(message)

        middleware = HotspotListenerAccessMiddleware(app)
        with patch("core.local_api_access.local_api_peer_allowed", return_value=False):
            await middleware(scope, lambda: None, send)
        return messages, called

    async def test_http_denies_non_phone_clients_on_local_listener(self):
        messages, called = await self._call({
            "type": "http",
            "server": ("192.168.43.10", 8443),
            "client": ("192.168.43.2", 51234),
        })
        self.assertFalse(called)
        self.assertEqual(messages[0]["status"], 403)

    async def test_websocket_denies_non_phone_clients_before_accept(self):
        messages, called = await self._call({
            "type": "websocket",
            "server": ("192.168.43.10", 8443),
            "client": ("192.168.43.2", 51234),
        })
        self.assertFalse(called)
        self.assertEqual(messages, [{"type": "websocket.close", "code": 1008}])

    async def test_loopback_listener_is_not_changed(self):
        messages, called = await self._call({
            "type": "http",
            "server": ("127.0.0.1", 8000),
            "client": ("127.0.0.1", 51234),
        })
        self.assertEqual(messages, [])
        self.assertEqual(called, [True])


if __name__ == "__main__":
    unittest.main()
