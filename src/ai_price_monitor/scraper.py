"""Price scraper — BaseScraper protocol, PlaywrightScraper, and DemoScraper."""

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


@dataclass
class ScrapeTarget:
    """Defines how to scrape a competitor's product page."""

    competitor_id: int
    product_id: int
    url: str
    price_selector: str
    stock_selector: str = ""


class PlaywrightScraper:
    """Scrape real competitor pages using Playwright (headless Chromium).

    Requires the ``scraping`` extra: ``pip install ai-price-monitor[scraping]``.
    Pass a list of :class:`ScrapeTarget` to configure which pages to visit.
    """

    def __init__(self, targets: list[ScrapeTarget] | None = None) -> None:
        self._targets = targets or []

    async def scrape(self) -> list[ScraperResult]:
        if not self._targets:
            return []

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(
                "playwright is not installed — run: pip install ai-price-monitor[scraping]"
            )
            return []

        results: list[ScraperResult] = []
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()

            for target in self._targets:
                try:
                    await page.goto(target.url, timeout=15_000)
                    await page.wait_for_selector(target.price_selector, timeout=5_000)

                    price_text = await page.text_content(target.price_selector) or ""
                    price = self._parse_price(price_text)

                    in_stock = True
                    if target.stock_selector:
                        stock_el = await page.query_selector(target.stock_selector)
                        if stock_el is None:
                            in_stock = False

                    if price > 0:
                        results.append(
                            ScraperResult(
                                product_id=target.product_id,
                                competitor_id=target.competitor_id,
                                price=price,
                                in_stock=in_stock,
                            )
                        )
                    else:
                        logger.warning("Could not parse price from %s", target.url)
                except Exception:
                    logger.exception("Failed to scrape %s", target.url)

            await browser.close()

        logger.info("PlaywrightScraper fetched %d price records", len(results))
        return results

    @staticmethod
    def _parse_price(text: str) -> float:
        """Extract a numeric price from text like '€ 42,50' or '42.50 EUR'."""
        cleaned = ""
        for ch in text:
            if ch.isdigit() or ch in ".,":
                cleaned += ch
        if not cleaned:
            return 0.0
        # Handle European format: 1.234,56 -> 1234.56
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        try:
            return round(float(cleaned), 2)
        except ValueError:
            return 0.0


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
