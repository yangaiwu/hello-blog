"""HTTP routes: room list, broadcast console, watch page and JSON API."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template, request, url_for

from . import db
from .danmaku import ValidationError, validate_anchor_name, validate_title

bp = Blueprint("main", __name__)


# --- helpers ---------------------------------------------------------------
def _settings():
    return current_app.config["SETTINGS"]


def _live():
    return current_app.extensions["live"]


def _hub():
    return current_app.extensions["hub"]


def _error(code: str, message: str, status: int = 400):
    return jsonify({"error": {"code": code, "message": message}}), status


def _room_payload(room: dict) -> dict:
    viewers = _hub().viewers(room["id"]) if room["status"] == "running" else 0
    return {**room, "viewers": viewers, "url": url_for("main.watch", room_id=room["id"])}


def _json_body() -> dict:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValidationError("请求体必须是 JSON 对象", "invalid_payload")
    return body


# --- pages -----------------------------------------------------------------
@bp.get("/")
def index():
    rooms = [_room_payload(room) for room in db.list_rooms(_settings().db_path)]
    return render_template("index.html", rooms=rooms, demo=_settings().is_demo, live=_live())


@bp.get("/broadcast")
def broadcast():
    return render_template("broadcast.html", demo=_settings().is_demo)


@bp.get("/room/<int:room_id>")
def watch(room_id: int):
    room = db.get_room(_settings().db_path, room_id)
    if room is None:
        return render_template("404.html"), 404
    live = _live().describe(room["stream_name"])
    messages = db.list_messages(_settings().db_path, room_id, limit=100)
    return render_template(
        "room.html", room=room, live=live, messages=messages, demo=_settings().is_demo
    )


# --- JSON API --------------------------------------------------------------
@bp.get("/api/rooms")
def api_list_rooms():
    rooms = [_room_payload(room) for room in db.list_rooms(_settings().db_path)]
    return jsonify({"rooms": rooms})


@bp.post("/api/rooms")
def api_create_room():
    try:
        body = _json_body()
        title = validate_title(body.get("title"))
        anchor_name = validate_anchor_name(body.get("anchor_name"))
    except ValidationError as exc:
        return _error(exc.code, exc.message, exc.status)

    room = db.create_room(_settings().db_path, title, anchor_name)
    return (
        jsonify({"room": _room_payload(room), "live": _live().describe(room["stream_name"])}),
        201,
    )


@bp.get("/api/rooms/<int:room_id>")
def api_get_room(room_id: int):
    room = db.get_room(_settings().db_path, room_id)
    if room is None:
        return _error("not_found", f"房间 {room_id} 不存在", 404)
    return jsonify({"room": _room_payload(room), "live": _live().describe(room["stream_name"])})


@bp.post("/api/rooms/<int:room_id>/stop")
def api_stop_room(room_id: int):
    room = db.stop_room(_settings().db_path, room_id)
    if room is None:
        return _error("not_found", f"房间 {room_id} 不存在", 404)
    return jsonify({"room": _room_payload(room)})


@bp.get("/api/rooms/<int:room_id>/messages")
def api_messages(room_id: int):
    if db.get_room(_settings().db_path, room_id) is None:
        return _error("not_found", f"房间 {room_id} 不存在", 404)
    limit = request.args.get("limit", 100)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return _error("invalid_limit", "limit 必须是整数")
    return jsonify({"messages": db.list_messages(_settings().db_path, room_id, limit=limit)})