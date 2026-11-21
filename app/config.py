"""Application settings, read from environment variables (all optional)."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_APP_NAME = "live"
DEFAULT_PUSH_URL_TTL = 7200  # seconds
DEFAULT_DB_PATH = "live.db"


def _get(env, name: str, default: str = "") -> str:
    raw = env.get(name)
    return default if raw is None else str(raw).strip()


@dataclass(frozen=True)
class Settings:
    """Resolved runtime configuration.

    ``is_demo`` is true whenever any mandatory Tencent CSS credential is
    missing; the site still boots and the closed loop can be exercised.
    """

    push_domain: str
    play_domain: str
    push_key: str
    play_key: str
    app_name: str
    bizid: str
    secret_key: str
    db_path: str
    push_url_ttl: int

    @property
    def is_demo(self) -> bool:
        return not (self.push_domain and self.play_domain and self.push_key)

    @classmethod
    def from_env(cls, environ=None) -> "Settings":
        env = os.environ if environ is None else environ
        try:
            ttl = int(_get(env, "CSS_PUSH_URL_TTL", str(DEFAULT_PUSH_URL_TTL)) or DEFAULT_PUSH_URL_TTL)
        except ValueError:
            ttl = DEFAULT_PUSH_URL_TTL
        return cls(
            push_domain=_get(env, "CSS_PUSH_DOMAIN"),
            play_domain=_get(env, "CSS_PLAY_DOMAIN"),
            push_key=_get(env, "CSS_PUSH_KEY"),
            play_key=_get(env, "CSS_PLAY_KEY"),
            app_name=_get(env, "CSS_APP_NAME", DEFAULT_APP_NAME) or DEFAULT_APP_NAME,
            bizid=_get(env, "CSS_BIZID"),
            secret_key=_get(env, "SECRET_KEY", "dev-secret-change-me"),
            db_path=_get(env, "DB_PATH", DEFAULT_DB_PATH) or DEFAULT_DB_PATH,
            push_url_ttl=max(60, ttl),
        )