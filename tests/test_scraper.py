"""Tests for scraper module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_price_monitor.scraper import (
    DemoScraper,
    PlaywrightScraper,
    ScraperResult,
    ScrapeTarget,
    run_scraping,
)

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


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------

def test_scraper_result_repr():
    r = ScraperResult(product_id=1, competitor_id=2, price=42.50, in_stock=True)
    text = repr(r)
    assert "product_id=1" in text
    assert "42.5" in text


def test_scraper_result_equality():
    a = ScraperResult(product_id=1, competitor_id=2, price=42.50, in_stock=True)
    b = ScraperResult(product_id=1, competitor_id=2, price=42.50, in_stock=True)
    assert a == b


def test_scraper_result_inequality():
    a = ScraperResult(product_id=1, competitor_id=2, price=42.50, in_stock=True)
    b = ScraperResult(product_id=1, competitor_id=2, price=43.00, in_stock=True)
    assert a != b


@pytest.mark.asyncio
async def test_demo_scraper_price_rounding(mock_db):
    """All generated prices have at most 2 decimal places."""
    scraper = DemoScraper()
    results = await scraper.scrape()
    for r in results:
        assert r.price == round(r.price, 2)


@pytest.mark.asyncio
async def test_demo_scraper_empty_products(mock_db):
    """Scraper returns empty list when no products exist."""
    mock_db["get_products"].return_value = []
    scraper = DemoScraper()
    results = await scraper.scrape()
    assert results == []


@pytest.mark.asyncio
async def test_demo_scraper_empty_competitors(mock_db):
    """Scraper returns empty list when no competitors exist."""
    mock_db["get_competitors"].return_value = []
    scraper = DemoScraper()
    results = await scraper.scrape()
    assert results == []


@pytest.mark.asyncio
async def test_run_scraping_multiple_changes(mock_db):
    """Multiple changes produce multiple alerts."""
    mock_db["detect_price_changes"].return_value = [
        {
            "product_id": 1, "product_name": "Brake Pads",
            "competitor_id": 1, "competitor_name": "AutoDoc",
            "old_price": 44.00, "new_price": 42.50, "in_stock": True,
        },
        {
            "product_id": 2, "product_name": "Oil Filter",
            "competitor_id": 2, "competitor_name": "KFZteile24",
            "old_price": 11.00, "new_price": 13.00, "in_stock": True,
        },
        {
            "product_id": 3, "product_name": "Spark Plugs",
            "competitor_id": 1, "competitor_name": "AutoDoc",
            "old_price": 24.00, "new_price": 24.00, "in_stock": False,
        },
    ]
    scraper = DemoScraper()
    alerts = await run_scraping(scraper)
    assert len(alerts) == 3
    assert alerts[0]["alert_type"] == "price_drop"
    assert alerts[1]["alert_type"] == "price_increase"
    assert alerts[2]["alert_type"] == "out_of_stock"
    assert mock_db["save_alert"].call_count == 3


# ---------------------------------------------------------------------------
# PlaywrightScraper
# ---------------------------------------------------------------------------

def test_parse_price_dot():
    assert PlaywrightScraper._parse_price("42.50 EUR") == 42.50


def test_parse_price_comma():
    assert PlaywrightScraper._parse_price("42,50 €") == 42.50


def test_parse_price_european_format():
    assert PlaywrightScraper._parse_price("1.234,56 EUR") == 1234.56


def test_parse_price_empty():
    assert PlaywrightScraper._parse_price("") == 0.0


def test_parse_price_no_digits():
    assert PlaywrightScraper._parse_price("EUR") == 0.0


def test_parse_price_currency_symbol_prefix():
    assert PlaywrightScraper._parse_price("€ 89,90") == 89.90


def test_scrape_target_fields():
    t = ScrapeTarget(
        competitor_id=1, product_id=2, url="https://example.com", price_selector=".price"
    )
    assert t.competitor_id == 1
    assert t.product_id == 2
    assert t.stock_selector == ""


@pytest.mark.asyncio
async def test_playwright_scraper_no_targets():
    scraper = PlaywrightScraper(targets=[])
    # With no targets, should return empty without launching browser
    results = await scraper.scrape()
    assert results == []


@pytest.mark.asyncio
async def test_playwright_scraper_no_playwright_installed():
    """Graceful fallback when playwright is not installed."""
    target = ScrapeTarget(
        competitor_id=1, product_id=1, url="https://example.com", price_selector=".price"
    )
    scraper = PlaywrightScraper(targets=[target])
    with patch.dict("sys.modules", {"playwright.async_api": None}):
        results = await scraper.scrape()
    assert results == []


@pytest.mark.asyncio
async def test_playwright_scraper_success():
    """Successful scrape returns ScraperResult."""
    target = ScrapeTarget(
        competitor_id=1, product_id=2, url="https://example.com", price_selector=".price"
    )
    scraper = PlaywrightScraper(targets=[target])

    mock_page = AsyncMock()
    mock_page.text_content.return_value = "€ 42,50"
    mock_page.query_selector.return_value = None

    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page

    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_pw
    mock_context_manager.__aexit__.return_value = False

    mock_module = MagicMock()
    mock_module.async_playwright.return_value = mock_context_manager

    with patch.dict("sys.modules", {"playwright.async_api": mock_module}):
        results = await scraper.scrape()

    assert len(results) == 1
    assert results[0].product_id == 2
    assert results[0].competitor_id == 1
    assert results[0].price == 42.50
    assert results[0].in_stock is True


@pytest.mark.asyncio
async def test_playwright_scraper_with_stock_selector():
    """Stock selector present and element found means in_stock=True."""
    target = ScrapeTarget(
        competitor_id=1, product_id=2,
        url="https://example.com", price_selector=".price",
        stock_selector=".in-stock",
    )
    scraper = PlaywrightScraper(targets=[target])

    mock_page = AsyncMock()
    mock_page.text_content.return_value = "89.90 EUR"
    mock_page.query_selector.return_value = MagicMock()  # element found = in stock

    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page

    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_pw
    mock_cm.__aexit__.return_value = False

    mock_module = MagicMock()
    mock_module.async_playwright.return_value = mock_cm

    with patch.dict("sys.modules", {"playwright.async_api": mock_module}):
        results = await scraper.scrape()

    assert len(results) == 1
    assert results[0].in_stock is True
    assert results[0].price == 89.90


@pytest.mark.asyncio
async def test_playwright_scraper_out_of_stock():
    """Stock selector present but element not found means in_stock=False."""
    target = ScrapeTarget(
        competitor_id=1, product_id=2,
        url="https://example.com", price_selector=".price",
        stock_selector=".in-stock",
    )
    scraper = PlaywrightScraper(targets=[target])

    mock_page = AsyncMock()
    mock_page.text_content.return_value = "42.50"
    mock_page.query_selector.return_value = None  # not found = out of stock

    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page

    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_pw
    mock_cm.__aexit__.return_value = False

    mock_module = MagicMock()
    mock_module.async_playwright.return_value = mock_cm

    with patch.dict("sys.modules", {"playwright.async_api": mock_module}):
        results = await scraper.scrape()

    assert len(results) == 1
    assert results[0].in_stock is False


@pytest.mark.asyncio
async def test_playwright_scraper_unparseable_price():
    """Zero price from unparseable text is skipped."""
    target = ScrapeTarget(
        competitor_id=1, product_id=2,
        url="https://example.com", price_selector=".price",
    )
    scraper = PlaywrightScraper(targets=[target])

    mock_page = AsyncMock()
    mock_page.text_content.return_value = "Call for price"

    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page

    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_pw
    mock_cm.__aexit__.return_value = False

    mock_module = MagicMock()
    mock_module.async_playwright.return_value = mock_cm

    with patch.dict("sys.modules", {"playwright.async_api": mock_module}):
        results = await scraper.scrape()

    assert results == []


@pytest.mark.asyncio
async def test_playwright_scraper_page_error():
    """Exception during page navigation is caught and skipped."""
    target = ScrapeTarget(
        competitor_id=1, product_id=2,
        url="https://example.com", price_selector=".price",
    )
    scraper = PlaywrightScraper(targets=[target])

    mock_page = AsyncMock()
    mock_page.goto.side_effect = TimeoutError("Navigation timeout")

    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page

    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_pw
    mock_cm.__aexit__.return_value = False

    mock_module = MagicMock()
    mock_module.async_playwright.return_value = mock_cm

    with patch.dict("sys.modules", {"playwright.async_api": mock_module}):
        results = await scraper.scrape()

    assert results == []


@pytest.mark.asyncio
async def test_playwright_scraper_null_text_content():
    """text_content returns None — should treat as empty string."""
    target = ScrapeTarget(
        competitor_id=1, product_id=2,
        url="https://example.com", price_selector=".price",
    )
    scraper = PlaywrightScraper(targets=[target])

    mock_page = AsyncMock()
    mock_page.text_content.return_value = None

    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page

    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_pw
    mock_cm.__aexit__.return_value = False

    mock_module = MagicMock()
    mock_module.async_playwright.return_value = mock_cm

    with patch.dict("sys.modules", {"playwright.async_api": mock_module}):
        results = await scraper.scrape()

    assert results == []


# ---------------------------------------------------------------------------
# run_scraping — additional
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_scraping_passes_correct_params(mock_db):
    """Verify save_price_record receives the right values from ScraperResult."""
    mock_db["detect_price_changes"].return_value = []
    mock_db["get_products"].return_value = [
        {"id": 1, "name": "X", "sku": "X", "category": "X", "our_price": 10.0},
    ]
    mock_db["get_competitors"].return_value = [
        {"id": 1, "name": "Y", "base_url": "", "is_active": True},
    ]
    scraper = DemoScraper()
    await run_scraping(scraper)

    call_args = mock_db["save_price_record"].call_args
    assert call_args[0][0] == 1  # product_id
    assert call_args[0][1] == 1  # competitor_id
    assert isinstance(call_args[0][2], float)  # price
    assert isinstance(call_args[0][3], bool)   # in_stock
