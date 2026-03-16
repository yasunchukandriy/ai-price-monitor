"""Tests for analyzer module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_price_monitor.analyzer import (
    _format_changes_for_prompt,
    _format_prices_for_prompt,
    generate_daily_report,
)
from tests.conftest import SAMPLE_CHANGES, SAMPLE_PRICES, SAMPLE_PRODUCTS

# ---------------------------------------------------------------------------
# _format_prices_for_prompt
# ---------------------------------------------------------------------------

def test_format_prices_basic():
    text = _format_prices_for_prompt(SAMPLE_PRICES, SAMPLE_PRODUCTS)
    assert "Brake Pads Front (BMW 3 Series)" in text
    assert "AutoDoc" in text
    assert "42.50" in text  # corrected to match 42.5 -> 42.50


def test_format_prices_shows_out_of_stock():
    text = _format_prices_for_prompt(SAMPLE_PRICES, SAMPLE_PRODUCTS)
    assert "OUT OF STOCK" in text


def test_format_prices_shows_our_price():
    text = _format_prices_for_prompt(SAMPLE_PRICES, SAMPLE_PRODUCTS)
    assert "45.90" in text  # our_price for Brake Pads


def test_format_prices_empty():
    text = _format_prices_for_prompt([], SAMPLE_PRODUCTS)
    assert text == ""


def test_format_prices_unknown_product():
    prices = [{"product_id": 999, "competitor_name": "X", "price": 10.0, "in_stock": True}]
    text = _format_prices_for_prompt(prices, SAMPLE_PRODUCTS)
    assert text == ""  # Unknown product_id 999 should be skipped


# ---------------------------------------------------------------------------
# _format_changes_for_prompt
# ---------------------------------------------------------------------------

def test_format_changes_basic():
    text = _format_changes_for_prompt(SAMPLE_CHANGES)
    assert "Brake Pads" in text
    assert "AutoDoc" in text
    assert "DOWN" in text


def test_format_changes_price_increase():
    changes = [{
        "product_id": 1, "product_name": "Brake Pads",
        "competitor_id": 1, "competitor_name": "AutoDoc",
        "old_price": 42.50, "new_price": 48.00, "in_stock": True,
    }]
    text = _format_changes_for_prompt(changes)
    assert "UP" in text


def test_format_changes_empty():
    text = _format_changes_for_prompt([])
    assert "No price changes" in text


def test_format_changes_percentage():
    text = _format_changes_for_prompt(SAMPLE_CHANGES)
    # 44.00 -> 42.50 = -3.4%
    assert "3.4%" in text


# ---------------------------------------------------------------------------
# generate_daily_report
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_daily_report(mock_db):
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="## Daily Report\nAll good.")]

    mock_client = AsyncMock()
    mock_client.messages.create.return_value = mock_message

    with patch("ai_price_monitor.analyzer.anthropic.AsyncAnthropic", return_value=mock_client):
        report = await generate_daily_report()

    assert "Daily Report" in report
    mock_db["save_report"].assert_called_once()


@pytest.mark.asyncio
async def test_generate_daily_report_calls_claude_with_data(mock_db):
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Report")]

    mock_client = AsyncMock()
    mock_client.messages.create.return_value = mock_message

    with patch("ai_price_monitor.analyzer.anthropic.AsyncAnthropic", return_value=mock_client):
        await generate_daily_report()

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"
    assert call_kwargs["max_tokens"] == 2000
    assert "pricing analyst" in call_kwargs["system"].lower()

    user_msg = call_kwargs["messages"][0]["content"]
    assert "Brake Pads" in user_msg
    assert "AutoDoc" in user_msg


@pytest.mark.asyncio
async def test_generate_daily_report_saves_to_db(mock_db):
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Test report")]

    mock_client = AsyncMock()
    mock_client.messages.create.return_value = mock_message

    with patch("ai_price_monitor.analyzer.anthropic.AsyncAnthropic", return_value=mock_client):
        await generate_daily_report()

    mock_db["save_report"].assert_called_once_with(
        "Test report", report_type="daily", product_count=3
    )


@pytest.mark.asyncio
async def test_generate_daily_report_includes_changes(mock_db):
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Report")]

    mock_client = AsyncMock()
    mock_client.messages.create.return_value = mock_message

    with patch("ai_price_monitor.analyzer.anthropic.AsyncAnthropic", return_value=mock_client):
        await generate_daily_report()

    user_msg = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "Price Changes" in user_msg
    assert "44.00" in user_msg  # old_price from SAMPLE_CHANGES
