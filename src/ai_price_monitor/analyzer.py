"""AI analyzer — generates daily reports via Claude API."""

from __future__ import annotations

import logging
from typing import Any

import anthropic

from ai_price_monitor import database as db
from ai_price_monitor.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a pricing analyst for an auto parts company. You analyze competitor pricing data \
and generate actionable reports.

Your reports should include:
1. **Summary** — brief overview of the market situation
2. **Price Alerts** — significant price changes detected
3. **Competitive Position** — how our prices compare to competitors
4. **Recommendations** — concrete pricing actions to consider

Keep the report concise and structured. Use markdown formatting. \
Focus on actionable insights, not raw data repetition. \
Write numbers with 2 decimal places and EUR currency.\
"""


def _format_prices_for_prompt(
    prices: list[dict[str, Any]],
    products: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    products_by_id = {p["id"]: p for p in products}

    grouped: dict[int, list[dict[str, Any]]] = {}
    for p in prices:
        grouped.setdefault(p["product_id"], []).append(p)

    for product_id, records in sorted(grouped.items()):
        product = products_by_id.get(product_id)
        if not product:
            continue
        our = f"{float(product['our_price']):.2f}"
        lines.append(f"\n### {product['name']} (SKU: {product['sku']}) — Our price: {our} EUR")
        for r in records:
            stock = "In stock" if r["in_stock"] else "OUT OF STOCK"
            price = f"{float(r['price']):.2f}"
            lines.append(f"  - {r['competitor_name']}: {price} EUR ({stock})")

    return "\n".join(lines)


def _format_changes_for_prompt(changes: list[dict[str, Any]]) -> str:
    if not changes:
        return "No price changes detected in the last scraping cycle."
    lines: list[str] = []
    for ch in changes:
        old_p = float(ch["old_price"])
        new_p = float(ch["new_price"])
        diff = new_p - old_p
        pct = (diff / old_p * 100) if old_p else 0
        direction = "UP" if diff > 0 else "DOWN"
        lines.append(
            f"- {ch['product_name']} @ {ch['competitor_name']}: "
            f"{old_p:.2f} -> {new_p:.2f} EUR ({direction} {abs(pct):.1f}%)"
        )
    return "\n".join(lines)


async def generate_daily_report() -> str:
    """Gather pricing data and generate an AI-powered daily report."""
    products = await db.get_products()
    prices = await db.get_latest_prices()
    changes = await db.detect_price_changes()

    user_prompt = (
        "Generate a daily pricing report based on the following data.\n\n"
        "## Current Competitor Prices\n"
        f"{_format_prices_for_prompt(prices, products)}\n\n"
        "## Recent Price Changes\n"
        f"{_format_changes_for_prompt(changes)}\n\n"
        f"Total products tracked: {len(products)}\n"
        f"Total price points: {len(prices)}\n"
        f"Price changes detected: {len(changes)}"
    )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    message = await client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    report = message.content[0].text  # type: ignore[union-attr]
    logger.info("Generated daily report (%d chars)", len(report))

    await db.save_report(report, report_type="daily", product_count=len(products))
    return report
