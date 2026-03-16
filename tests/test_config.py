"""Tests for configuration module."""

from __future__ import annotations

from unittest.mock import patch

from ai_price_monitor.config import Settings


def test_default_settings():
    """Settings have sensible defaults."""
    with patch.dict("os.environ", {}, clear=True):
        s = Settings()
    assert s.database_url == "postgresql://pricebot:pricebot@localhost:5432/pricebot"
    assert s.anthropic_api_key == ""
    assert s.telegram_bot_token == ""
    assert s.telegram_chat_id == 0
    assert s.scrape_interval_hours == 6
    assert s.report_hour == 8


def test_settings_from_env():
    """Settings are loaded from PRICE_ prefixed env vars."""
    env = {
        "PRICE_DATABASE_URL": "postgresql://other:other@db:5432/other",
        "PRICE_ANTHROPIC_API_KEY": "sk-ant-test",
        "PRICE_TELEGRAM_BOT_TOKEN": "999:TOKEN",
        "PRICE_TELEGRAM_CHAT_ID": "12345",
        "PRICE_SCRAPE_INTERVAL_HOURS": "12",
        "PRICE_REPORT_HOUR": "10",
    }
    with patch.dict("os.environ", env, clear=True):
        s = Settings()
    assert s.database_url == "postgresql://other:other@db:5432/other"
    assert s.anthropic_api_key == "sk-ant-test"
    assert s.telegram_bot_token == "999:TOKEN"
    assert s.telegram_chat_id == 12345
    assert s.scrape_interval_hours == 12
    assert s.report_hour == 10


def test_settings_env_prefix():
    """Settings only respond to PRICE_ prefixed vars."""
    env = {
        "DATABASE_URL": "postgresql://wrong:wrong@localhost/wrong",
        "PRICE_DATABASE_URL": "postgresql://right:right@localhost/right",
    }
    with patch.dict("os.environ", env, clear=True):
        s = Settings()
    assert "right" in s.database_url
    assert "wrong" not in s.database_url


def test_settings_partial_env():
    """Settings use defaults for missing env vars."""
    env = {
        "PRICE_ANTHROPIC_API_KEY": "sk-test",
    }
    with patch.dict("os.environ", env, clear=True):
        s = Settings()
    assert s.anthropic_api_key == "sk-test"
    assert s.scrape_interval_hours == 6  # default
