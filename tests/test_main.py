"""Tests for main module — scheduler and entry point."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# run_scheduler
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_scheduler_scrapes_on_first_iteration(mock_db):
    """Scheduler should call run_scraping on the first iteration."""
    from ai_price_monitor.main import run_scheduler

    mock_scraper_cls = MagicMock()
    mock_run = AsyncMock(return_value=[])

    with (
        patch("ai_price_monitor.main.DemoScraper", return_value=mock_scraper_cls),
        patch("ai_price_monitor.main.run_scraping", mock_run),
        patch("ai_price_monitor.main.settings") as mock_settings,
        patch("asyncio.sleep", side_effect=asyncio.CancelledError),
    ):
        mock_settings.scrape_interval_hours = 6
        mock_settings.report_hour = 99  # won't trigger report
        mock_settings.telegram_chat_id = 0
        with pytest.raises(asyncio.CancelledError):
            await run_scheduler(None)

    mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_run_scheduler_sends_alerts_to_telegram(mock_db):
    """When alerts exist and bot is provided, send Telegram message."""
    from aiogram import Bot

    from ai_price_monitor.main import run_scheduler

    alerts = [
        {
            "alert_type": "price_drop",
            "product_name": "Brake Pads",
            "competitor_name": "AutoDoc",
        },
    ]
    mock_run = AsyncMock(return_value=alerts)
    mock_bot = MagicMock(spec=Bot)
    mock_bot.send_message = AsyncMock()

    with (
        patch("ai_price_monitor.main.DemoScraper"),
        patch("ai_price_monitor.main.run_scraping", mock_run),
        patch("ai_price_monitor.main.settings") as mock_settings,
        patch("asyncio.sleep", side_effect=asyncio.CancelledError),
    ):
        mock_settings.scrape_interval_hours = 6
        mock_settings.report_hour = 99
        mock_settings.telegram_chat_id = 12345
        with pytest.raises(asyncio.CancelledError):
            await run_scheduler(mock_bot)

    mock_bot.send_message.assert_called_once()
    sent_text = mock_bot.send_message.call_args[0][1]
    assert "price_drop" in sent_text
    assert "Brake Pads" in sent_text


@pytest.mark.asyncio
async def test_run_scheduler_no_alerts_no_telegram(mock_db):
    """When there are no alerts, no Telegram message is sent."""
    from aiogram import Bot

    from ai_price_monitor.main import run_scheduler

    mock_run = AsyncMock(return_value=[])
    mock_bot = MagicMock(spec=Bot)
    mock_bot.send_message = AsyncMock()

    with (
        patch("ai_price_monitor.main.DemoScraper"),
        patch("ai_price_monitor.main.run_scraping", mock_run),
        patch("ai_price_monitor.main.settings") as mock_settings,
        patch("asyncio.sleep", side_effect=asyncio.CancelledError),
    ):
        mock_settings.scrape_interval_hours = 6
        mock_settings.report_hour = 99
        mock_settings.telegram_chat_id = 12345
        with pytest.raises(asyncio.CancelledError):
            await run_scheduler(mock_bot)

    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_run_scheduler_without_bot_instance(mock_db):
    """Scheduler works fine when bot_instance is None."""
    from ai_price_monitor.main import run_scheduler

    alerts = [
        {
            "alert_type": "price_drop",
            "product_name": "Brake Pads",
            "competitor_name": "AutoDoc",
        },
    ]
    mock_run = AsyncMock(return_value=alerts)

    with (
        patch("ai_price_monitor.main.DemoScraper"),
        patch("ai_price_monitor.main.run_scraping", mock_run),
        patch("ai_price_monitor.main.settings") as mock_settings,
        patch("asyncio.sleep", side_effect=asyncio.CancelledError),
    ):
        mock_settings.scrape_interval_hours = 6
        mock_settings.report_hour = 99
        mock_settings.telegram_chat_id = 12345
        with pytest.raises(asyncio.CancelledError):
            await run_scheduler(None)

    # Should not raise — bot_instance is None, not a Bot


@pytest.mark.asyncio
async def test_run_scheduler_generates_report_at_configured_hour(mock_db):
    """When the current hour matches report_hour, generate a report."""
    from ai_price_monitor.main import run_scheduler

    mock_run = AsyncMock(return_value=[])
    mock_report = AsyncMock(return_value="Daily report text")
    now = datetime.now(timezone.utc)

    with (
        patch("ai_price_monitor.main.DemoScraper"),
        patch("ai_price_monitor.main.run_scraping", mock_run),
        patch("ai_price_monitor.main.generate_daily_report", mock_report),
        patch("ai_price_monitor.main.settings") as mock_settings,
        patch("asyncio.sleep", side_effect=asyncio.CancelledError),
    ):
        mock_settings.scrape_interval_hours = 6
        mock_settings.report_hour = now.hour  # match current hour
        mock_settings.telegram_chat_id = 0
        with pytest.raises(asyncio.CancelledError):
            await run_scheduler(None)

    mock_report.assert_called_once()


@pytest.mark.asyncio
async def test_run_scheduler_sends_report_to_telegram(mock_db):
    """Generated report is sent to Telegram."""
    from aiogram import Bot

    from ai_price_monitor.main import run_scheduler

    mock_run = AsyncMock(return_value=[])
    mock_report = AsyncMock(return_value="## Report\nContent here")
    mock_bot = MagicMock(spec=Bot)
    mock_bot.send_message = AsyncMock()
    now = datetime.now(timezone.utc)

    with (
        patch("ai_price_monitor.main.DemoScraper"),
        patch("ai_price_monitor.main.run_scraping", mock_run),
        patch("ai_price_monitor.main.generate_daily_report", mock_report),
        patch("ai_price_monitor.main.settings") as mock_settings,
        patch("asyncio.sleep", side_effect=asyncio.CancelledError),
    ):
        mock_settings.scrape_interval_hours = 6
        mock_settings.report_hour = now.hour
        mock_settings.telegram_chat_id = 12345
        with pytest.raises(asyncio.CancelledError):
            await run_scheduler(mock_bot)

    # send_message called once for alert summary (empty) is skipped,
    # but once for the report
    assert mock_bot.send_message.call_count == 1
    sent_text = mock_bot.send_message.call_args[0][1]
    assert "Report" in sent_text


@pytest.mark.asyncio
async def test_run_scheduler_report_not_duplicate_same_day(mock_db):
    """Report is generated only once per day even with multiple iterations."""
    from ai_price_monitor.main import run_scheduler

    mock_run = AsyncMock(return_value=[])
    mock_report = AsyncMock(return_value="Report")
    now = datetime.now(timezone.utc)
    call_count = 0

    async def mock_sleep(_seconds: float) -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise asyncio.CancelledError

    with (
        patch("ai_price_monitor.main.DemoScraper"),
        patch("ai_price_monitor.main.run_scraping", mock_run),
        patch("ai_price_monitor.main.generate_daily_report", mock_report),
        patch("ai_price_monitor.main.settings") as mock_settings,
        patch("asyncio.sleep", side_effect=mock_sleep),
    ):
        mock_settings.scrape_interval_hours = 6
        mock_settings.report_hour = now.hour
        mock_settings.telegram_chat_id = 0
        with pytest.raises(asyncio.CancelledError):
            await run_scheduler(None)

    # Despite 2 iterations, report only generated once
    assert mock_report.call_count == 1


@pytest.mark.asyncio
async def test_run_scheduler_handles_scraping_error(mock_db):
    """Scheduler continues after a scraping error."""
    from ai_price_monitor.main import run_scheduler

    call_count = 0

    async def failing_then_cancel(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Scraping failed")
        raise asyncio.CancelledError

    mock_run = AsyncMock(side_effect=RuntimeError("DB error"))

    with (
        patch("ai_price_monitor.main.DemoScraper"),
        patch("ai_price_monitor.main.run_scraping", mock_run),
        patch("ai_price_monitor.main.settings") as mock_settings,
        patch("asyncio.sleep", side_effect=asyncio.CancelledError),
    ):
        mock_settings.scrape_interval_hours = 6
        mock_settings.report_hour = 99
        mock_settings.telegram_chat_id = 0
        # Should not raise — error is caught and logged
        with pytest.raises(asyncio.CancelledError):
            await run_scheduler(None)


@pytest.mark.asyncio
async def test_run_scheduler_truncates_long_report(mock_db):
    """Reports longer than 4096 chars are truncated for Telegram."""
    from aiogram import Bot

    from ai_price_monitor.main import run_scheduler

    long_report = "x" * 5000
    mock_run = AsyncMock(return_value=[])
    mock_report = AsyncMock(return_value=long_report)
    mock_bot = MagicMock(spec=Bot)
    mock_bot.send_message = AsyncMock()
    now = datetime.now(timezone.utc)

    with (
        patch("ai_price_monitor.main.DemoScraper"),
        patch("ai_price_monitor.main.run_scraping", mock_run),
        patch("ai_price_monitor.main.generate_daily_report", mock_report),
        patch("ai_price_monitor.main.settings") as mock_settings,
        patch("asyncio.sleep", side_effect=asyncio.CancelledError),
    ):
        mock_settings.scrape_interval_hours = 6
        mock_settings.report_hour = now.hour
        mock_settings.telegram_chat_id = 12345
        with pytest.raises(asyncio.CancelledError):
            await run_scheduler(mock_bot)

    sent_text = mock_bot.send_message.call_args[0][1]
    assert len(sent_text) <= 4096


@pytest.mark.asyncio
async def test_run_scheduler_limits_alert_lines(mock_db):
    """Only first 10 alerts are sent to Telegram."""
    from aiogram import Bot

    from ai_price_monitor.main import run_scheduler

    alerts = [
        {
            "alert_type": "price_drop",
            "product_name": f"Product {i}",
            "competitor_name": "AutoDoc",
        }
        for i in range(15)
    ]
    mock_run = AsyncMock(return_value=alerts)
    mock_bot = MagicMock(spec=Bot)
    mock_bot.send_message = AsyncMock()

    with (
        patch("ai_price_monitor.main.DemoScraper"),
        patch("ai_price_monitor.main.run_scraping", mock_run),
        patch("ai_price_monitor.main.settings") as mock_settings,
        patch("asyncio.sleep", side_effect=asyncio.CancelledError),
    ):
        mock_settings.scrape_interval_hours = 6
        mock_settings.report_hour = 99
        mock_settings.telegram_chat_id = 12345
        with pytest.raises(asyncio.CancelledError):
            await run_scheduler(mock_bot)

    sent_text = mock_bot.send_message.call_args[0][1]
    assert "Product 9" in sent_text
    assert "Product 10" not in sent_text


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_main_starts_and_shuts_down():
    """main() creates bot, starts scheduler, handles shutdown."""
    from ai_price_monitor.main import main

    mock_pool = AsyncMock()
    mock_bot = MagicMock()
    mock_bot.session = MagicMock()
    mock_bot.session.close = AsyncMock()
    mock_dp = MagicMock()
    mock_dp.start_polling = AsyncMock(
        side_effect=asyncio.CancelledError
    )

    with (  # noqa: SIM117
        patch("ai_price_monitor.main.db.get_pool", return_value=mock_pool),
        patch("ai_price_monitor.main.db.close_pool", new_callable=AsyncMock),
        patch(
            "ai_price_monitor.main.create_bot",
            return_value=(mock_bot, mock_dp),
        ),
        patch("ai_price_monitor.main.run_scheduler", new_callable=AsyncMock),
    ):
        with pytest.raises(asyncio.CancelledError):
            await main()

    mock_bot.session.close.assert_called_once()


@pytest.mark.asyncio
async def test_main_closes_pool_on_shutdown():
    """main() always closes DB pool in finally block."""
    from ai_price_monitor.main import main

    mock_pool = AsyncMock()
    mock_close = AsyncMock()
    mock_bot = MagicMock()
    mock_bot.session = MagicMock()
    mock_bot.session.close = AsyncMock()
    mock_dp = MagicMock()
    mock_dp.start_polling = AsyncMock(
        side_effect=KeyboardInterrupt
    )

    with (  # noqa: SIM117
        patch("ai_price_monitor.main.db.get_pool", return_value=mock_pool),
        patch("ai_price_monitor.main.db.close_pool", mock_close),
        patch(
            "ai_price_monitor.main.create_bot",
            return_value=(mock_bot, mock_dp),
        ),
        patch("ai_price_monitor.main.run_scheduler", new_callable=AsyncMock),
    ):
        with pytest.raises(KeyboardInterrupt):
            await main()

    mock_close.assert_called_once()
