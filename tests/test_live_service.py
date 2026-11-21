"""Pin the Tencent CSS URL-signing contract (fixed inputs -> fixed outputs)."""

import hashlib

import pytest

from app.config import Settings
from app.services.live import LiveService

NOW = 1_700_000_000  # 0x6553F100
TX_TIME = "6553F100"


def _service(**overrides):
    env = {
        "CSS_PUSH_DOMAIN": "push.example.com",
        "CSS_PLAY_DOMAIN": "play.example.com",
        "CSS_PUSH_KEY": "pushkey123",
        "CSS_APP_NAME": "live",
        "CSS_BIZID": "1234",
    }
    env.update(overrides)
    return LiveService(Settings.from_env(env))


def test_tx_secret_matches_md5_of_key_stream_time():
    secret = hashlib.md5(("pushkey123" + "stream1" + TX_TIME).encode()).hexdigest()
    svc = _service()
    assert svc.tx_secret("stream1", int(TX_TIME, 16)) == secret


def test_push_url_has_bizid_domain_secret_and_txtime():
    secret = hashlib.md5(("pushkey123" + "stream1" + TX_TIME).encode()).hexdigest()
    svc = _service()
    assert svc.build_push_url("stream1", now=NOW) == (
        f"rtmp://1234.push.example.com/live/stream1?txSecret={secret}&txTime={TX_TIME}"
    )


def test_obs_config_splits_server_and_stream_key():
    secret = hashlib.md5(("pushkey123" + "stream1" + TX_TIME).encode()).hexdigest()
    svc = _service()
    obs = svc.build_obs_config("stream1", now=NOW)
    assert obs["server"] == "rtmp://1234.push.example.com/live"
    assert obs["stream_key"] == f"stream1?txSecret={secret}&txTime={TX_TIME}"


def test_play_urls_use_play_domain_for_hls_and_flv():
    svc = _service()
    play = svc.build_play_urls("stream1")
    assert play["hls"] == "https://1234.play.example.com/live/stream1.m3u8"
    assert play["flv"] == "http://1234.play.example.com/live/stream1.flv"


def test_push_url_ttl_is_configurable():
    svc = _service()
    svc_ttl = LiveService(
        Settings.from_env(
            {
                "CSS_PUSH_DOMAIN": "push.example.com",
                "CSS_PLAY_DOMAIN": "play.example.com",
                "CSS_PUSH_KEY": "pushkey123",
                "CSS_PUSH_URL_TTL": "60",
            }
        )
    )
    url = svc_ttl.build_push_url("stream1", now=NOW)
    assert f"txTime={format(NOW + 60, 'X')}" in url
    assert svc.build_push_url("stream1", now=NOW) != url


def test_without_credentials_service_runs_in_demo_mode():
    svc = LiveService(Settings.from_env({"CSS_APP_NAME": "live"}))
    info = svc.describe("stream1", now=NOW)
    assert info["demo"] is True
    assert info["play_urls"]["hls"].startswith("https://demo-play")
    assert info["push_url"].startswith("rtmp://demo-push")
    assert info["obs"]["server"].startswith("rtmp://demo-push")


def test_describe_reports_signing_mode_and_expiry():
    svc = _service()
    info = svc.describe("stream1", now=NOW)
    assert info["demo"] is False
    assert info["expires_at"] == NOW + svc.settings.push_url_ttl
    assert info["push_url"] == svc.build_push_url("stream1", now=NOW)


def test_missing_single_credential_falls_back_to_demo():
    svc = _service(CSS_PUSH_KEY="")
    assert svc.settings.is_demo is True


def test_settings_defaults():
    settings = Settings.from_env({"DB_PATH": "/tmp/x.db"})
    assert settings.app_name == "live"
    assert settings.push_url_ttl == 7200
    assert settings.bizid == ""
    assert settings.is_demo is True


@pytest.mark.parametrize("stream", ["stream1", "abc_123"])
def test_push_url_is_stable_for_stream_names(stream):
    svc = _service()
    assert stream in svc.build_push_url(stream, now=NOW)