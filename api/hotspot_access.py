"""Restrict the optional local HTTPS API to the provisioned hotspot host."""
from __future__ import annotations

import asyncio


class HotspotListenerAccessMiddleware:
    """Apply profile and gateway restrictions on the TLS-only listener."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") in {"http", "websocket"}:
            server = scope.get("server")
            client = scope.get("client")
            if server and client:
                from core.local_api_access import local_api_port, local_api_peer_allowed

                if int(server[1]) == local_api_port():
                    allowed = await asyncio.to_thread(
                        local_api_peer_allowed,
                        str(server[0]),
                        str(client[0]),
                        int(server[1]),
                    )
                    if not allowed:
                        if scope["type"] == "websocket":
                            await send({"type": "websocket.close", "code": 1008})
                        else:
                            body = b'{"detail":{"error":"hotspot_client_only"}}'
                            await send({
                                "type": "http.response.start",
                                "status": 403,
                                "headers": [
                                    (b"content-type", b"application/json"),
                                    (b"content-length", str(len(body)).encode("ascii")),
                                ],
                            })
                            await send({"type": "http.response.body", "body": body})
                        return
        await self.app(scope, receive, send)
