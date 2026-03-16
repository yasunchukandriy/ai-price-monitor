"""Entry point — scheduler + Telegram bot startup."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from ai_price_monitor import database as db
from ai_price_monitor.analyzer import generate_daily_report
from ai_price_monitor.config import settings
from ai_price_monitor.scraper import DemoScraper, run_scraping

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_scheduler(bot_instance: object | None = None) -> None:
    """Periodically scrape prices and generate daily reports."""
    from aiogram import Bot

    scraper = DemoScraper()
    last_report_date: str | None = None

    while True:
        try:
            logger.info("Starting scheduled scrape...")
            alerts = await run_scraping(scraper)

            # Send alert notifications via Telegram
            if alerts and isinstance(bot_instance, Bot) and settings.telegram_chat_id:
                summary_lines = [f"Price alerts ({len(alerts)}):"]
                for a in alerts[:10]:
                    summary_lines.append(
                        f"  {a['alert_type']}: {a['product_name']} @ {a['competitor_name']}"
                    )
                await bot_instance.send_message(
                    settings.telegram_chat_id, "\n".join(summary_lines)
                )

            # Generate daily report at configured hour
            now = datetime.now(timezone.utc)
            today = now.strftime("%Y-%m-%d")
            if now.hour == settings.report_hour and last_report_date != today:
                logger.info("Generating daily report...")
                report = await generate_daily_report()
                last_report_date = today

                if isinstance(bot_instance, Bot) and settings.telegram_chat_id:
                    text = report[:4096] if len(report) > 4096 else report
                    await bot_instance.send_message(settings.telegram_chat_id, text)

        except Exception:
            logger.exception("Scheduler error")

        await asyncio.sleep(settings.scrape_interval_hours * 3600)


async def main() -> None:
    logger.info("AI Price Monitor starting...")

    # Ensure DB pool is ready
    await db.get_pool()

    bot = None
    dp = None

    if settings.telegram_bot_token:
        from ai_price_monitor.bot import create_bot

        bot, dp = create_bot()
        logger.info("Telegram bot configured")
    else:
        logger.warning("PRICE_TELEGRAM_BOT_TOKEN not set — running without Telegram bot")

    try:
        scheduler_task = asyncio.create_task(run_scheduler(bot))
        logger.info("Scheduler started (interval=%dh)", settings.scrape_interval_hours)

        if dp and bot:
            logger.info("Telegram bot starting polling...")
            await dp.start_polling(bot)
        else:
            # No bot — just keep scheduler running
            await scheduler_task
    finally:
        scheduler_task.cancel()
        await db.close_pool()
        if bot:
            await bot.session.close()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
