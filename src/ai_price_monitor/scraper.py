"""Price scraper — BaseScraper protocol and DemoScraper with realistic fake data."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any, Protocol

from ai_price_monitor import database as db

logger = logging.getLogger(__name__)


@dataclass
class ScraperResult:
    product_id: int
    competitor_id: int
    price: float
    in_stock: bool


class BaseScraper(Protocol):
    async def scrape(self) -> list[ScraperResult]: ...


class DemoScraper:
    """Generate realistic auto parts prices for demo purposes.

    Each competitor has a base price offset per product (±5-15% from our_price).
    Each scrape run applies random fluctuations on top.
    """

    def __init__(self) -> None:
        self._base_offsets: dict[tuple[int, int], float] = {}
        self._rng = random.Random(42)

    def _get_base_offset(self, product_id: int, competitor_id: int) -> float:
        key = (product_id, competitor_id)
        if key not in self._base_offsets:
            self._base_offsets[key] = self._rng.uniform(-0.15, 0.15)
        return self._base_offsets[key]

    async def scrape(self) -> list[ScraperResult]:
        products = await db.get_products()
        competitors = await db.get_competitors()
        results: list[ScraperResult] = []

        for product in products:
            our_price: float = float(product["our_price"])
            for competitor in competitors:
                base_offset = self._get_base_offset(product["id"], competitor["id"])
                base_price = our_price * (1 + base_offset)

                # Random fluctuation ±3%
                fluctuation = random.uniform(-0.03, 0.03)
                price = base_price * (1 + fluctuation)

                # Occasional price spike/drop (10% chance)
                if random.random() < 0.10:
                    spike = random.choice([-1, 1]) * random.uniform(0.05, 0.12)
                    price *= 1 + spike

                # Occasional out-of-stock (5% chance)
                in_stock = random.random() > 0.05

                results.append(
                    ScraperResult(
                        product_id=product["id"],
                        competitor_id=competitor["id"],
                        price=round(price, 2),
                        in_stock=in_stock,
                    )
                )

        logger.info("DemoScraper generated %d price records", len(results))
        return results


async def run_scraping(scraper: BaseScraper) -> list[dict[str, Any]]:
    """Orchestrate: scrape -> save records -> detect changes -> create alerts."""
    results = await scraper.scrape()

    # Save all price records
    for r in results:
        await db.save_price_record(r.product_id, r.competitor_id, r.price, r.in_stock)
    logger.info("Saved %d price records to database", len(results))

    # Detect changes and create alerts
    changes = await db.detect_price_changes()
    alerts: list[dict[str, Any]] = []
    for ch in changes:
        old_price = float(ch["old_price"])
        new_price = float(ch["new_price"])

        if not ch["in_stock"]:
            alert_type = "out_of_stock"
        elif new_price < old_price:
            alert_type = "price_drop"
        else:
            alert_type = "price_increase"

        await db.save_alert(
            ch["product_id"], ch["competitor_id"], alert_type, old_price, new_price
        )
        alerts.append({**ch, "alert_type": alert_type})

    logger.info("Created %d price alerts", len(alerts))
    return alerts
