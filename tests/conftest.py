"""Shared test fixtures."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

SAMPLE_PRODUCTS: list[dict[str, Any]] = [
    {
        "id": 1, "name": "Brake Pads Front (BMW 3 Series)",
        "sku": "BP-BMW3-F", "category": "Brakes", "our_price": 45.90,
    },
    {
        "id": 2, "name": "Oil Filter (Mercedes C-Class)",
        "sku": "OF-MBC-01", "category": "Filters", "our_price": 12.80,
    },
    {
        "id": 3, "name": "Spark Plugs Set x4 (Universal)",
        "sku": "SP-UNI-4X", "category": "Ignition", "our_price": 24.60,
    },
]

SAMPLE_COMPETITORS: list[dict[str, Any]] = [
    {"id": 1, "name": "AutoDoc", "base_url": "https://www.autodoc.de", "is_active": True},
    {"id": 2, "name": "KFZteile24", "base_url": "https://www.kfzteile24.de", "is_active": True},
]

SAMPLE_PRICES: list[dict[str, Any]] = [
    {
        "id": 1, "product_id": 1, "competitor_id": 1, "price": 42.50, "in_stock": True,
        "scraped_at": "2026-01-01T12:00:00Z", "product_name": "Brake Pads Front (BMW 3 Series)",
        "sku": "BP-BMW3-F", "our_price": 45.90, "category": "Brakes", "competitor_name": "AutoDoc",
    },
    {
        "id": 2, "product_id": 1, "competitor_id": 2, "price": 47.80, "in_stock": True,
        "scraped_at": "2026-01-01T12:00:00Z", "product_name": "Brake Pads Front (BMW 3 Series)",
        "sku": "BP-BMW3-F", "our_price": 45.90,
        "category": "Brakes", "competitor_name": "KFZteile24",
    },
    {
        "id": 3, "product_id": 2, "competitor_id": 1, "price": 11.90, "in_stock": False,
        "scraped_at": "2026-01-01T12:00:00Z", "product_name": "Oil Filter (Mercedes C-Class)",
        "sku": "OF-MBC-01", "our_price": 12.80, "category": "Filters", "competitor_name": "AutoDoc",
    },
]

SAMPLE_CHANGES: list[dict[str, Any]] = [
    {
        "product_id": 1, "product_name": "Brake Pads Front (BMW 3 Series)",
        "competitor_id": 1, "competitor_name": "AutoDoc",
        "old_price": 44.00, "new_price": 42.50, "in_stock": True,
    },
]

SAMPLE_ALERTS: list[dict[str, Any]] = [
    {
        "id": 1, "product_id": 1, "competitor_id": 1,
        "alert_type": "price_drop", "old_price": 44.00, "new_price": 42.50,
        "product_name": "Brake Pads Front (BMW 3 Series)", "competitor_name": "AutoDoc",
        "created_at": "2026-01-01T12:00:00Z",
    },
]

SAMPLE_REPORT: dict[str, Any] = {
    "id": 1, "report_type": "daily", "content": "Daily report content",
    "product_count": 3, "generated_at": "2026-01-01T08:00:00Z",
}


@pytest.fixture
def products() -> list[dict[str, Any]]:
    return SAMPLE_PRODUCTS


@pytest.fixture
def competitors() -> list[dict[str, Any]]:
    return SAMPLE_COMPETITORS


@pytest.fixture
def prices() -> list[dict[str, Any]]:
    return SAMPLE_PRICES


@pytest.fixture
def mock_db() -> Any:
    """Patch all database functions with AsyncMocks."""
    with (
        patch("ai_price_monitor.database.get_products", new_callable=AsyncMock) as get_products,
        patch("ai_price_monitor.database.get_competitors", new_callable=AsyncMock)
            as get_competitors,
        patch("ai_price_monitor.database.get_latest_prices", new_callable=AsyncMock) as get_latest,
        patch("ai_price_monitor.database.get_price_history", new_callable=AsyncMock) as get_history,
        patch("ai_price_monitor.database.get_recent_alerts", new_callable=AsyncMock) as get_alerts,
        patch("ai_price_monitor.database.get_latest_report", new_callable=AsyncMock) as get_report,
        patch("ai_price_monitor.database.get_product_by_name", new_callable=AsyncMock)
            as get_by_name,
        patch("ai_price_monitor.database.save_price_record", new_callable=AsyncMock) as save_price,
        patch("ai_price_monitor.database.save_report", new_callable=AsyncMock) as save_report,
        patch("ai_price_monitor.database.save_alert", new_callable=AsyncMock) as save_alert,
        patch("ai_price_monitor.database.detect_price_changes", new_callable=AsyncMock) as detect,
    ):
        get_products.return_value = SAMPLE_PRODUCTS
        get_competitors.return_value = SAMPLE_COMPETITORS
        get_latest.return_value = SAMPLE_PRICES
        get_history.return_value = SAMPLE_PRICES
        get_alerts.return_value = SAMPLE_ALERTS
        get_report.return_value = SAMPLE_REPORT
        get_by_name.return_value = SAMPLE_PRODUCTS[0]
        save_price.return_value = 1
        save_report.return_value = 1
        save_alert.return_value = 1
        detect.return_value = SAMPLE_CHANGES

        yield {
            "get_products": get_products,
            "get_competitors": get_competitors,
            "get_latest_prices": get_latest,
            "get_price_history": get_history,
            "get_recent_alerts": get_alerts,
            "get_latest_report": get_report,
            "get_product_by_name": get_by_name,
            "save_price_record": save_price,
            "save_report": save_report,
            "save_alert": save_alert,
            "detect_price_changes": detect,
        }
