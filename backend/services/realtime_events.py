from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket


class RealtimeEventManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def register(self, websocket: WebSocket):
        async with self._lock:
            self._connections.add(websocket)

    async def unregister(self, websocket: WebSocket):
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, event: dict):
        payload = json.dumps(event, ensure_ascii=False)
        async with self._lock:
            connections = list(self._connections)

        stale_connections: list[WebSocket] = []
        for websocket in connections:
            try:
                await websocket.send_text(payload)
            except Exception:
                stale_connections.append(websocket)

        if not stale_connections:
            return

        async with self._lock:
            for websocket in stale_connections:
                self._connections.discard(websocket)


realtime_event_manager = RealtimeEventManager()


async def broadcast_event(event: dict):
    await realtime_event_manager.broadcast(event)
