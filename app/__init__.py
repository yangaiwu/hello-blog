"""Flask application factory."""

from __future__ import annotations

from flask import Flask
from flask_sock import Sock

from . import db, routes, ws
from .config import Settings
from .hub import RoomHub
from .services.live import LiveService


def create_app(settings: Settings | None = None, environ=None) -> Flask:
    settings = settings or Settings.from_env(environ)

    app = Flask(__name__)
    app.config["SETTINGS"] = settings
    app.secret_key = settings.secret_key

    db.init_db(settings.db_path)

    hub = RoomHub()
    app.extensions["hub"] = hub
    app.extensions["live"] = LiveService(settings)

    app.register_blueprint(routes.bp)

    sock = Sock(app)
    ws.register(sock, settings, hub)

    return app


if __name__ == "__main__":  # pragma: no cover - convenience entry point
    create_app().run(host="127.0.0.1", port=8080, debug=False)