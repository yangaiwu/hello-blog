"""End-to-end WebSocket test: two browser-like clients in one room must see each other.

Runs the real Werkzeug dev server (flask-sock hijacks the connection socket) and
talks to it with simple_websocket.Client, which ships with flask-sock's own
dependency, so no extra test dependency is required.
"""

import json
import threading
import time

import pytest
from werkzeug.serving import make_server

simple_websocket = pytest.importorskip("simple_websocket")


@pytest.fixture
def live_server(app):
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _url(port, room_id, nickname):
    return f"ws://127.0.0.1:{port}/ws/room/{room_id}?nickname={nickname}"


def _recv_until(conn, kind, tries=6, timeout=3.0):
    deadline = time.time() + timeout
    for _ in range(tries):
        if time.time() > deadline:
            break
        frame = json.loads(conn.receive(timeout=timeout))
        if frame.get("type") == kind:
            return frame
    raise AssertionError(f"no {kind!r} frame received")


def _new_room(client, title="双端弹幕"):
    return client.post("/api/rooms", json={"title": title, "anchor_name": "主播"}).get_json()["room"]["id"]


def test_two_clients_broadcast_danmaku_in_real_time(app, client, live_server):
    room_id = _new_room(client)
    alice = simple_websocket.Client.connect(_url(live_server, room_id, "Alice"), timeout=5)
    bob = simple_websocket.Client.connect(_url(live_server, room_id, "Bob"), timeout=5)
    try:
        alice_received = _recv_until(alice, "viewers")
        assert {"type": "viewers", "count": 1} == alice_received
        assert _recv_until(bob, "viewers")["count"] == 2

        alice.send(json.dumps({"content": "第一句弹幕"}))
        echoed = _recv_until(alice, "message")
        relayed = _recv_until(bob, "message")
        assert echoed["content"] == "第一句弹幕"
        assert relayed["nickname"] == "Alice"
        assert relayed["id"] == echoed["id"]

        history = client.get(f"/api/rooms/{room_id}/messages").get_json()["messages"]
        assert [m["content"] for m in history] == ["第一句弹幕"]
    finally:
        alice.close()
        bob.close()


def test_second_message_within_one_second_is_rejected(app, client, live_server):
    room_id = _new_room(client)
    conn = simple_websocket.Client.connect(_url(live_server, room_id, "Cara"), timeout=5)
    try:
        _recv_until(conn, "viewers")
        conn.send(json.dumps({"content": "快的第一条"}))
        assert _recv_until(conn, "message")["content"] == "快的第一条"
        conn.send(json.dumps({"content": "快的第二条"}))
        err = _recv_until(conn, "error")
        assert err["code"] == "rate_limited"
    finally:
        conn.close()


def test_overlong_message_is_rejected_without_disconnect(app, client, live_server):
    room_id = _new_room(client)
    conn = simple_websocket.Client.connect(_url(live_server, room_id, "Dan"), timeout=5)
    try:
        _recv_until(conn, "viewers")
        conn.send(json.dumps({"content": "x" * 201}))
        err = _recv_until(conn, "error")
        assert err["code"] == "content_too_long"
        # still usable after the rejection
        time.sleep(1.05)
        conn.send(json.dumps({"content": "正常长度"}))
        assert _recv_until(conn, "message")["content"] == "正常长度"
    finally:
        conn.close()


def test_malformed_json_is_reported_as_error(app, client, live_server):
    room_id = _new_room(client)
    conn = simple_websocket.Client.connect(_url(live_server, room_id, "Eve"), timeout=5)
    try:
        _recv_until(conn, "viewers")
        conn.send("not-json")
        assert _recv_until(conn, "error")["code"] == "invalid_payload"
    finally:
        conn.close()


def test_join_ended_room_is_refused(app, client, live_server):
    room_id = _new_room(client)
    client.post(f"/api/rooms/{room_id}/stop")
    conn = simple_websocket.Client.connect(_url(live_server, room_id, "Late"), timeout=5)
    try:
        frame = json.loads(conn.receive(timeout=5))
        assert frame["type"] == "error"
        assert frame["code"] == "room_ended"
    finally:
        conn.close()


def test_viewer_count_drops_after_disconnect(app, client, live_server):
    room_id = _new_room(client)
    stay = simple_websocket.Client.connect(_url(live_server, room_id, "Stay"), timeout=5)
    leaving = simple_websocket.Client.connect(_url(live_server, room_id, "Leaving"), timeout=5)
    try:
        _recv_until(stay, "viewers")
        assert client.get(f"/api/rooms/{room_id}").get_json()["room"]["viewers"] == 2
        leaving.close()
        frame = _recv_until(stay, "viewers", tries=4)
        deadline = time.time() + 3
        while frame["count"] != 1 and time.time() < deadline:
            frame = json.loads(stay.receive(timeout=3))
        assert frame["count"] == 1
    finally:
        stay.close()