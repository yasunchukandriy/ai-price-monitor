"""Tests for Telegram bot commands."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_price_monitor.bot import (
    _truncate,
    cmd_alerts,
    cmd_prices,
    cmd_report,
    cmd_start,
    cmd_status,
    cmd_trends,
    create_bot,
)


def make_message(text: str = "") -> MagicMock:
    msg = MagicMock()
    msg.text = text
    msg.answer = AsyncMock()
    return msg


# ---------------------------------------------------------------------------
# _truncate
# ---------------------------------------------------------------------------

def test_truncate_short():
    assert _truncate("short", 4096) == "short"


def test_truncate_long():
    text = "x" * 5000
    result = _truncate(text, 4096)
    assert len(result) <= 4096
    assert "truncated" in result


def test_truncate_exact():
    text = "x" * 4096
    assert _truncate(text, 4096) == text


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_start():
    msg = make_message("/start")
    await cmd_start(msg)
    msg.answer.assert_called_once()
    text = msg.answer.call_args[0][0]
    assert "Price Monitor" in text
    assert "/prices" in text


# ---------------------------------------------------------------------------
# /prices
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_prices_all(mock_db):
    msg = make_message("/prices")
    await cmd_prices(msg)
    msg.answer.assert_called_once()
    text = msg.answer.call_args[0][0]
    assert "Brake Pads" in text
    assert "AutoDoc" in text


@pytest.mark.asyncio
async def test_cmd_prices_specific_product(mock_db):
    msg = make_message("/prices brake")
    await cmd_prices(msg)
    msg.answer.assert_called_once()
    text = msg.answer.call_args[0][0]
    assert "Brake Pads" in text


@pytest.mark.asyncio
async def test_cmd_prices_product_not_found(mock_db):
    mock_db["get_product_by_name"].return_value = None
    msg = make_message("/prices nonexistent")
    await cmd_prices(msg)
    text = msg.answer.call_args[0][0]
    assert "not found" in text.lower()


@pytest.mark.asyncio
async def test_cmd_prices_no_data(mock_db):
    mock_db["get_latest_prices"].return_value = []
    msg = make_message("/prices")
    await cmd_prices(msg)
    text = msg.answer.call_args[0][0]
    assert "No price data" in text


@pytest.mark.asyncio
async def test_cmd_prices_specific_no_data(mock_db):
    mock_db["get_latest_prices"].return_value = []
    msg = make_message("/prices brake")
    await cmd_prices(msg)
    text = msg.answer.call_args[0][0]
    assert "No price data" in text


# ---------------------------------------------------------------------------
# /report
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_report_success(mock_db):
    with patch("ai_price_monitor.bot.generate_daily_report", new_callable=AsyncMock) as gen:
        gen.return_value = "## Daily Report\nAll good."
        msg = make_message("/report")
        await cmd_report(msg)
    assert msg.answer.call_count == 2  # "Generating..." + report
    assert "Daily Report" in msg.answer.call_args_list[1][0][0]


@pytest.mark.asyncio
async def test_cmd_report_failure(mock_db):
    with patch("ai_price_monitor.bot.generate_daily_report", new_callable=AsyncMock) as gen:
        gen.side_effect = RuntimeError("API error")
        msg = make_message("/report")
        await cmd_report(msg)
    assert "failed" in msg.answer.call_args_list[1][0][0].lower()


# ---------------------------------------------------------------------------
# /trends
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_trends_success(mock_db):
    msg = make_message("/trends brake")
    await cmd_trends(msg)
    msg.answer.assert_called_once()
    text = msg.answer.call_args[0][0]
    assert "Brake Pads" in text
    assert "min" in text
    assert "avg" in text
    assert "max" in text


@pytest.mark.asyncio
async def test_cmd_trends_no_args():
    msg = make_message("/trends")
    await cmd_trends(msg)
    text = msg.answer.call_args[0][0]
    assert "Usage" in text


@pytest.mark.asyncio
async def test_cmd_trends_product_not_found(mock_db):
    mock_db["get_product_by_name"].return_value = None
    msg = make_message("/trends nonexistent")
    await cmd_trends(msg)
    text = msg.answer.call_args[0][0]
    assert "not found" in text.lower()


@pytest.mark.asyncio
async def test_cmd_trends_no_history(mock_db):
    mock_db["get_price_history"].return_value = []
    msg = make_message("/trends brake")
    await cmd_trends(msg)
    text = msg.answer.call_args[0][0]
    assert "No price history" in text


# ---------------------------------------------------------------------------
# /alerts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_alerts_success(mock_db):
    msg = make_message("/alerts")
    await cmd_alerts(msg)
    text = msg.answer.call_args[0][0]
    assert "Brake Pads" in text
    assert "AutoDoc" in text
    assert "DOWN" in text


@pytest.mark.asyncio
async def test_cmd_alerts_empty(mock_db):
    mock_db["get_recent_alerts"].return_value = []
    msg = make_message("/alerts")
    await cmd_alerts(msg)
    text = msg.answer.call_args[0][0]
    assert "No recent alerts" in text


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_status_success(mock_db):
    report_with_dt = {
        **mock_db["get_latest_report"].return_value,
        "generated_at": datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc),
    }
    mock_db["get_latest_report"].return_value = report_with_dt
    msg = make_message("/status")
    await cmd_status(msg)
    text = msg.answer.call_args[0][0]
    assert "System Status" in text
    assert "Products tracked" in text


@pytest.mark.asyncio
async def test_cmd_status_no_report(mock_db):
    mock_db["get_latest_report"].return_value = None
    msg = make_message("/status")
    await cmd_status(msg)
    text = msg.answer.call_args[0][0]
    assert "none" in text


@pytest.mark.asyncio
async def test_cmd_status_db_error(mock_db):
    mock_db["get_products"].side_effect = RuntimeError("DB down")
    msg = make_message("/status")
    await cmd_status(msg)
    text = msg.answer.call_args[0][0]
    assert "failed" in text.lower()


# ---------------------------------------------------------------------------
# create_bot
# ---------------------------------------------------------------------------

def test_create_bot():
    with patch("ai_price_monitor.bot.settings") as mock_settings:
        mock_settings.telegram_bot_token = "123:ABC"
        bot, dp = create_bot()
    assert bot is not None
    assert dp is not None
