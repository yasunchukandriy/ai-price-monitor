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


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_truncate_default_limit():
    """_truncate uses 4096 as the default limit."""
    short = "x" * 4096
    assert _truncate(short) == short

    long = "x" * 4097
    result = _truncate(long)
    assert len(result) <= 4096
    assert "truncated" in result


@pytest.mark.asyncio
async def test_cmd_alerts_without_prices(mock_db):
    """Alert with None old_price/new_price shows without price range."""
    mock_db["get_recent_alerts"].return_value = [
        {
            "id": 2, "product_id": 1, "competitor_id": 1,
            "alert_type": "out_of_stock",
            "old_price": None, "new_price": None,
            "product_name": "Oil Filter", "competitor_name": "AutoDoc",
            "created_at": "2026-01-01T12:00:00Z",
        },
    ]
    msg = make_message("/alerts")
    await cmd_alerts(msg)
    text = msg.answer.call_args[0][0]
    assert "Oil Filter" in text
    assert "OOS" in text
    assert "->" not in text  # no price range shown


@pytest.mark.asyncio
async def test_cmd_alerts_unknown_type(mock_db):
    """Unknown alert_type shows '?' icon."""
    mock_db["get_recent_alerts"].return_value = [
        {
            "id": 3, "product_id": 1, "competitor_id": 1,
            "alert_type": "unknown_type",
            "old_price": 10.0, "new_price": 12.0,
            "product_name": "Wiper Blades", "competitor_name": "KFZteile24",
            "created_at": "2026-01-01T12:00:00Z",
        },
    ]
    msg = make_message("/alerts")
    await cmd_alerts(msg)
    text = msg.answer.call_args[0][0]
    assert "[?]" in text


@pytest.mark.asyncio
async def test_cmd_prices_shows_diff_sign(mock_db):
    """Specific product prices show +/- diff from our_price."""
    mock_db["get_latest_prices"].return_value = [
        {
            "id": 1, "product_id": 1, "competitor_id": 1,
            "price": 42.50, "in_stock": True,
            "competitor_name": "AutoDoc",
        },
        {
            "id": 2, "product_id": 1, "competitor_id": 2,
            "price": 48.90, "in_stock": True,
            "competitor_name": "KFZteile24",
        },
    ]
    msg = make_message("/prices brake")
    await cmd_prices(msg)
    text = msg.answer.call_args[0][0]
    # 42.50 - 45.90 = -3.40 (negative, no + sign)
    assert "-3.40" in text
    # 48.90 - 45.90 = +3.00 (positive, + sign)
    assert "+3.00" in text


@pytest.mark.asyncio
async def test_cmd_prices_shows_out_of_stock(mock_db):
    """Out-of-stock items show [OUT] marker."""
    mock_db["get_latest_prices"].return_value = [
        {
            "id": 1, "product_id": 1, "competitor_id": 1,
            "price": 42.50, "in_stock": False,
            "product_name": "Brake Pads Front (BMW 3 Series)",
            "our_price": 45.90,
            "competitor_name": "AutoDoc",
        },
    ]
    msg = make_message("/prices")
    await cmd_prices(msg)
    text = msg.answer.call_args[0][0]
    assert "[OUT]" in text


@pytest.mark.asyncio
async def test_cmd_prices_message_is_none(mock_db):
    """Handle message.text being None."""
    msg = make_message("")
    msg.text = None
    await cmd_prices(msg)
    msg.answer.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_trends_message_is_none():
    """Handle message.text being None for /trends."""
    msg = make_message("")
    msg.text = None
    await cmd_trends(msg)
    text = msg.answer.call_args[0][0]
    assert "Usage" in text


@pytest.mark.asyncio
async def test_cmd_trends_multiple_competitors(mock_db):
    """Trends aggregate stats correctly across multiple competitors."""
    mock_db["get_price_history"].return_value = [
        {"competitor_name": "AutoDoc", "price": 40.00},
        {"competitor_name": "AutoDoc", "price": 44.00},
        {"competitor_name": "KFZteile24", "price": 50.00},
    ]
    msg = make_message("/trends brake")
    await cmd_trends(msg)
    text = msg.answer.call_args[0][0]
    assert "AutoDoc" in text
    assert "KFZteile24" in text
    # AutoDoc: min=40, avg=42, max=44
    assert "40.00" in text
    assert "42.00" in text
    assert "44.00" in text


@pytest.mark.asyncio
async def test_cmd_status_shows_all_fields(mock_db):
    """Status shows product count, competitors, scrape interval."""
    report_with_dt = {
        **mock_db["get_latest_report"].return_value,
        "generated_at": datetime(2026, 3, 15, 8, 0, tzinfo=timezone.utc),
    }
    mock_db["get_latest_report"].return_value = report_with_dt
    msg = make_message("/status")
    await cmd_status(msg)
    text = msg.answer.call_args[0][0]
    assert "Products tracked: 3" in text
    assert "Active competitors: 2" in text
    assert "2026-03-15" in text


@pytest.mark.asyncio
async def test_cmd_report_truncates_long_output(mock_db):
    """Long report is truncated to fit Telegram limit."""
    long_report = "x" * 5000
    with patch(
        "ai_price_monitor.bot.generate_daily_report",
        new_callable=AsyncMock,
        return_value=long_report,
    ):
        msg = make_message("/report")
        await cmd_report(msg)
    report_text = msg.answer.call_args_list[1][0][0]
    assert len(report_text) <= 4096
