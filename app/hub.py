"""In-process room presence + broadcast.

Keys are room ids, values are live WebSocket connections. Kept independent of
the WS transport so fan-out (and dead-connection cleanup) is unit testable.
"""

from __future__ import annotations

import json
import threading


class RoomHub:
    def __init__(self):
        self._rooms: dict[int, list] = {}
        self._lock = threading.Lock()

    def join(self, room_id: int, conn) -> int:
        with self._lock:
            self._rooms.setdefault(room_id, []).append(conn)
            return len(self._rooms[room_id])

    def leave(self, room_id: int, conn) -> int:
        with self._lock:
            conns = self._rooms.get(room_id, [])
            if conn in conns:
                conns.remove(conn)
            if not conns:
                self._rooms.pop(room_id, None)
            return len(conns)

    def viewers(self, room_id: int) -> int:
        with self._lock:
            return len(self._rooms.get(room_id, []))

    def broadcast(self, room_id: int, payload: dict) -> int:
        """Send ``payload`` as JSON to every live connection of one room.

        Connections that raise on send are dropped; the frame is encoded once
        so all viewers receive byte-identical payloads. Returns the number of
        connections that received it.
        """
        text = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            conns = list(self._rooms.get(room_id, []))
        delivered = 0
        for conn in conns:
            try:
                conn.send(text)
                delivered += 1
            except Exception:
                self.leave(room_id, conn)
        return delivered