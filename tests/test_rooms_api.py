"""HTTP contract for the room lifecycle: create -> list -> watch -> stop -> history."""

import pytest

from app import db


def _create(client, title="周五夜聊", anchor="小美"):
    resp = client.post("/api/rooms", json={"title": title, "anchor_name": anchor})
    return resp


def test_create_room_returns_stream_urls(client):
    resp = _create(client)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["room"]["title"] == "周五夜聊"
    assert body["room"]["status"] == "running"
    assert body["room"]["stream_name"]
    assert body["room"]["id"] > 0
    assert body["live"]["push_url"]
    assert body["live"]["play_urls"]["hls"].endswith(".m3u8")
    assert body["live"]["play_urls"]["flv"].endswith(".flv")
    assert body["live"]["demo"] is True
    assert body["room"]["url"].endswith(f"/room/{body['room']['id']}")


def test_create_room_rejects_blank_title(client):
    resp = client.post("/api/rooms", json={"anchor_name": "小美"})
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "invalid_title"


def test_create_room_rejects_blank_anchor(client):
    resp = client.post("/api/rooms", json={"title": "t", "anchor_name": "  "})
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "invalid_anchor_name"


def test_create_room_rejects_too_long_title(client):
    resp = _create(client, title="x" * 81)
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "invalid_title"


def test_list_rooms_is_empty_initially(client):
    assert client.get("/api/rooms").get_json()["rooms"] == []


def test_list_rooms_reports_viewer_count_and_running_first(client):
    _create(client, title="A")
    _create(client, title="B")
    rooms = client.get("/api/rooms").get_json()["rooms"]
    assert [r["title"] for r in rooms] == ["B", "A"]
    assert all(r["viewers"] == 0 for r in rooms)


def test_get_room_detail(client):
    room_id = _create(client).get_json()["room"]["id"]
    body = client.get(f"/api/rooms/{room_id}").get_json()
    assert body["room"]["id"] == room_id
    assert body["live"]["obs"]["server"]
    assert body["live"]["obs"]["stream_key"]


def test_get_unknown_room_returns_404(client):
    resp = client.get("/api/rooms/999")
    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "not_found"


def test_stop_room_marks_it_ended(client):
    room_id = _create(client).get_json()["room"]["id"]
    resp = client.post(f"/api/rooms/{room_id}/stop")
    assert resp.status_code == 200
    room = resp.get_json()["room"]
    assert room["status"] == "ended"
    assert room["ended_at"]


def test_stop_room_is_idempotent(client):
    room_id = _create(client).get_json()["room"]["id"]
    first = client.post(f"/api/rooms/{room_id}/stop").get_json()
    second = client.post(f"/api/rooms/{room_id}/stop")
    assert second.status_code == 200
    assert second.get_json()["room"]["ended_at"] == first["room"]["ended_at"]


def test_stop_unknown_room_returns_404(client):
    assert client.post("/api/rooms/999/stop").status_code == 404


def test_message_history_empty_then_echoed(app, client):
    room_id = _create(client).get_json()["room"]["id"]
    assert client.get(f"/api/rooms/{room_id}/messages").get_json()["messages"] == []

    db.add_message(app.config["SETTINGS"].db_path, room_id, "小明", "你好")
    messages = client.get(f"/api/rooms/{room_id}/messages").get_json()["messages"]
    assert len(messages) == 1
    assert messages[0]["nickname"] == "小明"
    assert messages[0]["content"] == "你好"


def test_message_history_unknown_room_returns_404(client):
    assert client.get("/api/rooms/999/messages").status_code == 404


def test_index_page_lists_rooms(client):
    _create(client, title="压轴戏")
    body = client.get("/").get_data(as_text=True)
    assert "压轴戏" in body
    assert "进行中" in body


def test_watch_page_renders_player_for_room(client):
    room_id = _create(client).get_json()["room"]["id"]
    body = client.get(f"/room/{room_id}").get_data(as_text=True)
    assert "<video" in body
    assert "/ws/room/" in body


def test_watch_page_unknown_room_returns_404(client):
    assert client.get("/room/999").status_code == 404


def test_broadcast_page_renders_form(client):
    body = client.get("/broadcast").get_data(as_text=True)
    assert "create-room" in body


def test_live_mode_uses_signed_push_url(live_client):
    body = _create(live_client).get_json()
    assert body["live"]["demo"] is False
    assert "txSecret=" in body["live"]["push_url"]
    assert "txTime=" in body["live"]["push_url"]
    assert body["live"]["push_url"].startswith("rtmp://1234.push.example.com/live/")


@pytest.mark.parametrize("payload", [{}, {"title": ""}, {"title": 123, "anchor_name": "a"}])
def test_create_room_validates_payload_shapes(client, payload):
    resp = client.post("/api/rooms", json=payload)
    assert resp.status_code == 400
    assert "error" in resp.get_json()

def test_live_mode_pages_hide_the_demo_notice(live_client):
    room_id = _create(live_client).get_json()["room"]["id"]
    index_html = live_client.get("/").get_data(as_text=True)
    room_html = live_client.get(f"/room/{room_id}").get_data(as_text=True)
    assert "演示模式" not in index_html
    assert 'data-demo="false"' in room_html
    assert 'data-role="placeholder" hidden' in room_html


def test_demo_mode_pages_show_the_demo_notice(client):
    room_id = _create(client).get_json()["room"]["id"]
    assert "演示模式" in client.get("/").get_data(as_text=True)
    room_html = client.get(f"/room/{room_id}").get_data(as_text=True)
    assert 'data-demo="true"' in room_html
    assert "演示模式" in room_html
