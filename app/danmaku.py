"""Danmaku rules: input validation and per-connection rate limiting.

Pure logic, deliberately free of Flask/WebSocket types so it can be unit
tested and reused by both the HTTP history API and the WS endpoint.
"""

from __future__ import annotations

MAX_CONTENT_LEN = 200
MAX_NICKNAME_LEN = 30
DEFAULT_INTERVAL = 1.0  # one message per second per connection


class ValidationError(ValueError):
    def __init__(self, message: str, code: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


def validate_content(raw) -> str:
    if not isinstance(raw, str):
        raise ValidationError("弹幕内容必须是非空字符串", "empty_content")
    content = raw.strip()
    if not content:
        raise ValidationError("弹幕内容不能为空", "empty_content")
    if len(content) > MAX_CONTENT_LEN:
        raise ValidationError(f"弹幕内容长度不能超过 {MAX_CONTENT_LEN} 字", "content_too_long")
    return content


def validate_nickname(raw) -> str:
    if not isinstance(raw, str):
        raise ValidationError("昵称必须是非空字符串", "invalid_nickname")
    nickname = raw.strip()
    if not nickname:
        raise ValidationError("昵称不能为空", "invalid_nickname")
    if len(nickname) > MAX_NICKNAME_LEN:
        raise ValidationError(f"昵称长度不能超过 {MAX_NICKNAME_LEN} 字", "invalid_nickname")
    return nickname


def validate_title(raw) -> str:
    if not isinstance(raw, str):
        raise ValidationError("房间标题必须是非空字符串", "invalid_title")
    title = raw.strip()
    if not title:
        raise ValidationError("房间标题不能为空", "invalid_title")
    if len(title) > 80:
        raise ValidationError("房间标题长度不能超过 80 字", "invalid_title")
    return title


def validate_anchor_name(raw) -> str:
    if not isinstance(raw, str):
        raise ValidationError("主播名必须是非空字符串", "invalid_anchor_name")
    name = raw.strip()
    if not name:
        raise ValidationError("主播名不能为空", "invalid_anchor_name")
    if len(name) > 30:
        raise ValidationError("主播名长度不能超过 30 字", "invalid_anchor_name")
    return name


class RateLimiter:
    """Allow one message per ``interval`` seconds on a single connection."""

    def __init__(self, interval: float = DEFAULT_INTERVAL):
        self.interval = float(interval)
        self._last: float | None = None

    def allow(self, now: float) -> bool:
        if self._last is None or (now - self._last) >= self.interval:
            self._last = now
            return True
        return False

    def retry_after(self, now: float) -> float:
        if self._last is None:
            return 0.0
        return round(max(0.0, self.interval - (now - self._last)), 3)