"""Telegram bot — aiogram 3.x with price monitoring commands."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message  # noqa: TCH002

from ai_price_monitor import database as db
from ai_price_monitor.analyzer import generate_daily_report
from ai_price_monitor.config import settings

logger = logging.getLogger(__name__)

router = Router()


def _truncate(text: str, limit: int = 4096) -> str:
    """Telegram messages are limited to 4096 characters."""
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n\n... (truncated)"


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Welcome to *AI Price Monitor*\\!\n\n"
        "Available commands:\n"
        "/prices — latest competitor prices\n"
        "/prices <product> — prices for a specific product\n"
        "/report — generate AI analysis report\n"
        "/trends <product> — price trends \\(7 days\\)\n"
        "/alerts — recent price alerts\n"
        "/status — system health check",
        parse_mode="MarkdownV2",
    )


@router.message(Command("prices"))
async def cmd_prices(message: Message) -> None:
    args = (message.text or "").replace("/prices", "").strip()

    if args:
        product = await db.get_product_by_name(args)
        if not product:
            await message.answer(f"Product not found: {args}")
            return
        prices = await db.get_latest_prices(product["id"])
        if not prices:
            await message.answer(f"No price data for: {product['name']}")
            return

        lines = [f"<b>{product['name']}</b> (Our price: {product['our_price']} EUR)\n"]
        for p in prices:
            stock = "OK" if p["in_stock"] else "OUT"
            diff = float(p["price"]) - float(product["our_price"])
            sign = "+" if diff >= 0 else ""
            lines.append(f"  {p['competitor_name']}: {p['price']} EUR ({sign}{diff:.2f}) [{stock}]")
        await message.answer("\n".join(lines), parse_mode="HTML")
    else:
        prices = await db.get_latest_prices()
        if not prices:
            await message.answer("No price data yet. Run a scrape first.")
            return

        grouped: dict[str, list[str]] = {}
        for p in prices:
            name = p["product_name"]
            if name not in grouped:
                grouped[name] = [f"<b>{name}</b> (Our: {p['our_price']} EUR)"]
            stock = "OK" if p["in_stock"] else "OUT"
            grouped[name].append(f"  {p['competitor_name']}: {p['price']} EUR [{stock}]")

        text = "\n\n".join("\n".join(lines) for lines in grouped.values())
        await message.answer(_truncate(text), parse_mode="HTML")


@router.message(Command("report"))
async def cmd_report(message: Message) -> None:
    await message.answer("Generating AI report... please wait.")
    try:
        report = await generate_daily_report()
        await message.answer(_truncate(report))
    except Exception as e:
        logger.exception("Report generation failed")
        await message.answer(f"Report generation failed: {e}")


@router.message(Command("trends"))
async def cmd_trends(message: Message) -> None:
    args = (message.text or "").replace("/trends", "").strip()
    if not args:
        await message.answer("Usage: /trends <product name>")
        return

    product = await db.get_product_by_name(args)
    if not product:
        await message.answer(f"Product not found: {args}")
        return

    history = await db.get_price_history(product["id"], days=7)
    if not history:
        await message.answer(f"No price history for: {product['name']}")
        return

    # Aggregate stats per competitor
    stats: dict[str, dict[str, float]] = {}
    for row in history:
        comp = row["competitor_name"]
        price = float(row["price"])
        if comp not in stats:
            stats[comp] = {"min": price, "max": price, "sum": 0, "count": 0}
        s = stats[comp]
        s["min"] = min(s["min"], price)
        s["max"] = max(s["max"], price)
        s["sum"] += price
        s["count"] += 1

    lines = [f"<b>{product['name']}</b> — 7-day price trends\n"]
    for comp, s in sorted(stats.items()):
        avg = s["sum"] / s["count"]
        lines.append(f"  {comp}: min {s['min']:.2f} / avg {avg:.2f} / max {s['max']:.2f} EUR")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("alerts"))
async def cmd_alerts(message: Message) -> None:
    alerts = await db.get_recent_alerts(limit=15)
    if not alerts:
        await message.answer("No recent alerts.")
        return

    lines = ["<b>Recent Price Alerts</b>\n"]
    for a in alerts:
        icon = {"price_drop": "DOWN", "price_increase": "UP", "out_of_stock": "OOS"}.get(
            a["alert_type"], "?"
        )
        if a["old_price"] and a["new_price"]:
            lines.append(
                f"  [{icon}] {a['product_name']} @ {a['competitor_name']}: "
                f"{a['old_price']} -> {a['new_price']} EUR"
            )
        else:
            lines.append(f"  [{icon}] {a['product_name']} @ {a['competitor_name']}")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    try:
        products = await db.get_products()
        competitors = await db.get_competitors()
        latest_report = await db.get_latest_report()

        report_info = "none"
        if latest_report:
            report_info = latest_report["generated_at"].strftime("%Y-%m-%d %H:%M UTC")

        await message.answer(
            f"<b>System Status</b>\n\n"
            f"Products tracked: {len(products)}\n"
            f"Active competitors: {len(competitors)}\n"
            f"Last report: {report_info}\n"
            f"Scrape interval: {settings.scrape_interval_hours}h\n"
            f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"Status check failed: {e}")


def create_bot() -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    return bot, dp
