"""WebSocket danmaku endpoint: one room channel, fan-out via RoomHub."""

from __future__ import annotations

import json
import time

from flask import request
from simple_websocket.errors import ConnectionClosed

from . import db
from .danmaku import RateLimiter, ValidationError, validate_content, validate_nickname

MAX_FRAME_LEN = 4096


def _send(ws, payload: dict) -> bool:
    try:
        ws.send(json.dumps(payload, ensure_ascii=False))
        return True
    except Exception:
        return False


def _error_frame(ws, code: str, message: str, **extra) -> None:
    _send(ws, {"type": "error", "code": code, "message": message, **extra})


def register(sock, settings, hub) -> None:
    @sock.route("/ws/room/<int:room_id>")
    def danmaku(ws, room_id):
        room = db.get_room(settings.db_path, room_id)
        if room is None:
            _error_frame(ws, "room_not_found", "房间不存在")
            return
        if room["status"] != "running":
            _error_frame(ws, "room_ended", "直播已结束")
            return
        try:
            nickname = validate_nickname(request.args.get("nickname", ""))
        except ValidationError as exc:
            _error_frame(ws, exc.code, exc.message)
            return

        hub.join(room_id, ws)
        hub.broadcast(room_id, {"type": "viewers", "count": hub.viewers(room_id)})
        limiter = RateLimiter(interval=1.0)
        try:
            while True:
                raw = ws.receive()
                if raw is None:
                    break
                if hub.is_closed(room_id):
                    _error_frame(ws, "room_ended", "直播已结束")
                    break
                if len(raw) > MAX_FRAME_LEN:
                    _error_frame(ws, "invalid_payload", "消息过大")
                    continue
                try:
                    payload = json.loads(raw)
                except (TypeError, ValueError):
                    _error_frame(ws, "invalid_payload", "消息必须是 JSON")
                    continue
                if not isinstance(payload, dict):
                    _error_frame(ws, "invalid_payload", "消息必须是 JSON 对象")
                    continue
                try:
                    content = validate_content(payload.get("content"))
                except ValidationError as exc:
                    _error_frame(ws, exc.code, exc.message)
                    continue

                now = time.monotonic()
                if not limiter.allow(now):
                    _error_frame(
                        ws,
                        "rate_limited",
                        "发送太快了，请稍后再试",
                        retry_after=limiter.retry_after(now),
                    )
                    continue

                message = db.add_message(settings.db_path, room_id, nickname, content)
                hub.broadcast(room_id, {"type": "message", **message})
        except ConnectionClosed:
            pass
        finally:
            remaining = hub.leave(room_id, ws)
            hub.broadcast(room_id, {"type": "viewers", "count": remaining})