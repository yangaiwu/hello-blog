"""Tencent Cloud CSS (云直播) URL adapter.

Push URLs are signed locally per the CSS rule:

    txTime   = hex(expiry_epoch)
    txSecret = md5(push_key + stream_name + txTime).lower()
    rtmp://<bizid.>push_domain/<app>/<stream>?txSecret=...&txTime=...

so no cloud API call (and no SecretId/SecretKey) is needed. Play URLs point at
the play domain; when ``CSS_PLAY_KEY`` is configured they are signed with the
same scheme against the play key.
"""

from __future__ import annotations

import hashlib
import time

from ..config import Settings

DEMO_PUSH_HOST = "demo-push.css.example.com"
DEMO_PLAY_HOST = "demo-play.css.example.com"


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class LiveService:
    def __init__(self, settings: Settings, clock=time.time):
        self.settings = settings
        self._clock = clock

    # --- signing -----------------------------------------------------------
    def tx_secret(self, stream: str, tx_time: int, key: str | None = None) -> str:
        return _md5(f"{self.settings.push_key if key is None else key}{stream}{format(tx_time, 'X')}")

    def _expiry(self, now: int | None = None) -> int:
        return int(self._clock() if now is None else now) + self.settings.push_url_ttl

    def _push_host(self) -> str:
        if self.settings.is_demo:
            return DEMO_PUSH_HOST
        return f"{self.settings.bizid}.{self.settings.push_domain}" if self.settings.bizid else self.settings.push_domain

    def _play_host(self) -> str:
        if self.settings.is_demo:
            return DEMO_PLAY_HOST
        return f"{self.settings.bizid}.{self.settings.play_domain}" if self.settings.bizid else self.settings.play_domain

    # --- URLs --------------------------------------------------------------
    def build_push_url(self, stream: str, now: int | None = None) -> str:
        base = f"rtmp://{self._push_host()}/{self.settings.app_name}/{stream}"
        if self.settings.is_demo:
            return base
        expires = self._expiry(now)
        return f"{base}?txSecret={self.tx_secret(stream, expires)}&txTime={format(expires, 'X')}"

    def build_obs_config(self, stream: str, now: int | None = None) -> dict:
        """OBS wants the server URL and the stream key separately."""
        server = f"rtmp://{self._push_host()}/{self.settings.app_name}"
        push_url = self.build_push_url(stream, now=now)
        stream_key = push_url.split("/", 3)[-1].split("/", 1)[-1]
        return {"server": server, "stream_key": stream_key}

    def build_play_urls(self, stream: str, now: int | None = None) -> dict:
        host = self._play_host()
        play_key = self.settings.play_key
        query = ""
        if play_key and not self.settings.is_demo:
            expires = self._expiry(now)
            query = f"?txSecret={self.tx_secret(stream, expires, key=play_key)}&txTime={format(expires, 'X')}"
        base = f"{host}/{self.settings.app_name}/{stream}"
        return {"hls": f"https://{base}.m3u8{query}", "flv": f"http://{base}.flv{query}"}

    def describe(self, stream: str, now: int | None = None) -> dict:
        """Everything the pages need: push URL, OBS settings, play URLs, demo flag."""
        return {
            "demo": self.settings.is_demo,
            "push_url": self.build_push_url(stream, now=now),
            "obs": self.build_obs_config(stream, now=now),
            "play_urls": self.build_play_urls(stream, now=now),
            "expires_at": None if self.settings.is_demo else self._expiry(now),
        }