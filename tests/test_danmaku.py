"""Danmaku rules and the transport-independent room hub (two clients, one room)."""

import json

import pytest

from app.danmaku import (
    MAX_CONTENT_LEN,
    MAX_NICKNAME_LEN,
    RateLimiter,
    ValidationError,
    validate_content,
    validate_nickname,
)
from app.hub import RoomHub


class FakeConn:
    def __init__(self):
        self.sent = []
        self.alive = True

    def send(self, payload):
        if not self.alive:
            raise OSError("connection closed")
        self.sent.append(payload)


def test_validate_content_trims_and_accepts():
    assert validate_content("  你好  ") == "你好"
    assert len(validate_content("x" * MAX_CONTENT_LEN)) == MAX_CONTENT_LEN


@pytest.mark.parametrize("raw", ["", "   ", None, 123])
def test_validate_content_rejects_empty_or_non_string(raw):
    with pytest.raises(ValidationError) as exc:
        validate_content(raw)
    assert exc.value.code == "empty_content"


def test_validate_content_rejects_too_long():
    with pytest.raises(ValidationError) as exc:
        validate_content("x" * (MAX_CONTENT_LEN + 1))
    assert exc.value.code == "content_too_long"
    assert exc.value.status == 400


def test_validate_nickname_rules():
    assert validate_nickname(" 小明 ") == "小明"
    with pytest.raises(ValidationError) as exc:
        validate_nickname("")
    assert exc.value.code == "invalid_nickname"
    with pytest.raises(ValidationError):
        validate_nickname("n" * (MAX_NICKNAME_LEN + 1))


def test_rate_limiter_allows_one_message_per_interval():
    limiter = RateLimiter(interval=1.0)
    assert limiter.allow(now=10.0) is True
    assert limiter.allow(now=10.5) is False
    assert limiter.allow(now=11.0) is True
    assert limiter.allow(now=11.2) is False


def test_rate_limiter_retry_after_is_reported():
    limiter = RateLimiter(interval=2.0)
    limiter.allow(now=0.0)
    assert limiter.retry_after(now=0.5) == pytest.approx(1.5)


def test_hub_tracks_viewers_and_fans_out():
    hub = RoomHub()
    a, b = FakeConn(), FakeConn()
    assert hub.join(1, a) == 1
    assert hub.join(1, b) == 2
    assert hub.viewers(1) == 2

    hub.broadcast(1, {"type": "message", "content": "hi"})
    assert json.loads(a.sent[0])["content"] == "hi"
    assert json.loads(b.sent[0])["content"] == "hi"

    assert hub.leave(1, a) == 1
    assert hub.viewers(1) == 1


def test_hub_survives_broken_connections():
    hub = RoomHub()
    a, b = FakeConn(), FakeConn()
    hub.join(7, a)
    hub.join(7, b)
    a.alive = False
    hub.broadcast(7, {"type": "message", "content": "x"})
    assert hub.viewers(7) == 1
    assert json.loads(b.sent[0])["content"] == "x"


def test_hub_isolated_between_rooms():
    hub = RoomHub()
    a, b = FakeConn(), FakeConn()
    hub.join(1, a)
    hub.join(2, b)
    hub.broadcast(1, {"type": "message", "content": "only-room-1"})
    assert len(a.sent) == 1
    assert b.sent == []


def test_hub_viewers_of_unknown_room_is_zero():
    assert RoomHub().viewers(42) == 0