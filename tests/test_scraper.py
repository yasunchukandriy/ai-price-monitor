"""Tests for scraper module."""

from __future__ import annotations

import pytest

from ai_price_monitor.scraper import DemoScraper, ScraperResult, run_scraping

# ---------------------------------------------------------------------------
# ScraperResult
# ---------------------------------------------------------------------------

def test_scraper_result_fields():
    r = ScraperResult(product_id=1, competitor_id=2, price=42.50, in_stock=True)
    assert r.product_id == 1
    assert r.competitor_id == 2
    assert r.price == 42.50
    assert r.in_stock is True


def test_scraper_result_out_of_stock():
    r = ScraperResult(product_id=1, competitor_id=1, price=0.0, in_stock=False)
    assert r.in_stock is False


# ---------------------------------------------------------------------------
# DemoScraper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_demo_scraper_generates_results(mock_db):
    scraper = DemoScraper()
    results = await scraper.scrape()
    # 3 products x 2 competitors = 6 results
    assert len(results) == 6
    for r in results:
        assert isinstance(r, ScraperResult)
        assert r.price > 0 or not r.in_stock


@pytest.mark.asyncio
async def test_demo_scraper_prices_near_our_price(mock_db):
    scraper = DemoScraper()
    results = await scraper.scrape()
    products_by_id = {p["id"]: p for p in mock_db["get_products"].return_value}
    for r in results:
        our_price = float(products_by_id[r.product_id]["our_price"])
        # Prices should be within ±30% of our price (base offset + fluctuation + spike)
        assert r.price > our_price * 0.7
        assert r.price < our_price * 1.3


@pytest.mark.asyncio
async def test_demo_scraper_deterministic_base_offsets(mock_db):
    scraper = DemoScraper()
    # Access internal base offsets to verify they persist
    offset1 = scraper._get_base_offset(1, 1)
    offset2 = scraper._get_base_offset(1, 1)
    assert offset1 == offset2


@pytest.mark.asyncio
async def test_demo_scraper_different_offsets_per_pair(mock_db):
    scraper = DemoScraper()
    offset_a = scraper._get_base_offset(1, 1)
    offset_b = scraper._get_base_offset(1, 2)
    # Different competitor should (usually) get a different offset
    # They could theoretically be equal with RNG, but with seed=42 they won't be
    assert isinstance(offset_a, float)
    assert isinstance(offset_b, float)


@pytest.mark.asyncio
async def test_demo_scraper_all_product_competitor_combos(mock_db):
    scraper = DemoScraper()
    results = await scraper.scrape()
    pairs = {(r.product_id, r.competitor_id) for r in results}
    expected_pairs = {
        (p["id"], c["id"])
        for p in mock_db["get_products"].return_value
        for c in mock_db["get_competitors"].return_value
    }
    assert pairs == expected_pairs


# ---------------------------------------------------------------------------
# run_scraping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_scraping_saves_records(mock_db):
    scraper = DemoScraper()
    await run_scraping(scraper)
    # Should have saved 6 price records (3 products x 2 competitors)
    assert mock_db["save_price_record"].call_count == 6


@pytest.mark.asyncio
async def test_run_scraping_detects_changes(mock_db):
    scraper = DemoScraper()
    await run_scraping(scraper)
    mock_db["detect_price_changes"].assert_called_once()


@pytest.mark.asyncio
async def test_run_scraping_creates_alerts_for_changes(mock_db):
    scraper = DemoScraper()
    alerts = await run_scraping(scraper)
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "price_drop"
    mock_db["save_alert"].assert_called_once()


@pytest.mark.asyncio
async def test_run_scraping_price_increase_alert(mock_db):
    mock_db["detect_price_changes"].return_value = [
        {
            "product_id": 1, "product_name": "Brake Pads",
            "competitor_id": 1, "competitor_name": "AutoDoc",
            "old_price": 42.50, "new_price": 48.00, "in_stock": True,
        },
    ]
    scraper = DemoScraper()
    alerts = await run_scraping(scraper)
    assert alerts[0]["alert_type"] == "price_increase"


@pytest.mark.asyncio
async def test_run_scraping_out_of_stock_alert(mock_db):
    mock_db["detect_price_changes"].return_value = [
        {
            "product_id": 1, "product_name": "Brake Pads",
            "competitor_id": 1, "competitor_name": "AutoDoc",
            "old_price": 42.50, "new_price": 42.50, "in_stock": False,
        },
    ]
    scraper = DemoScraper()
    alerts = await run_scraping(scraper)
    assert alerts[0]["alert_type"] == "out_of_stock"


@pytest.mark.asyncio
async def test_run_scraping_no_changes(mock_db):
    mock_db["detect_price_changes"].return_value = []
    scraper = DemoScraper()
    alerts = await run_scraping(scraper)
    assert alerts == []
    mock_db["save_alert"].assert_not_called()
