"""Shared pytest fixtures: build the Flask app against a temporary SQLite file."""

import pytest

from app import create_app

FIXED_NOW = 1_700_000_000


@pytest.fixture
def demo_environ(tmp_path):
    """No CSS credentials -> demo mode."""
    return {
        "DB_PATH": str(tmp_path / "app.db"),
        "SECRET_KEY": "test-secret-key",
    }


@pytest.fixture
def live_environ(tmp_path):
    """Full CSS credentials -> real (signing) mode."""
    return {
        "DB_PATH": str(tmp_path / "app.db"),
        "SECRET_KEY": "test-secret-key",
        "CSS_PUSH_DOMAIN": "push.example.com",
        "CSS_PLAY_DOMAIN": "play.example.com",
        "CSS_PUSH_KEY": "pushkey123",
        "CSS_APP_NAME": "live",
        "CSS_BIZID": "1234",
    }


@pytest.fixture
def app(demo_environ):
    return create_app(environ=demo_environ)


@pytest.fixture
def live_app(live_environ):
    return create_app(environ=live_environ)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def live_client(live_app):
    return live_app.test_client()