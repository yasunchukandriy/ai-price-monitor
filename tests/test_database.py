"""Tests for database module — unit tests with mocked asyncpg."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ai_price_monitor import database as db


class FakeRecord(dict):
    """Mimic asyncpg.Record — subscriptable dict."""
    pass


def make_record(**kwargs):
    return FakeRecord(kwargs)


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    with (
        patch.object(db, "_pool", pool),
        patch("ai_price_monitor.database.get_pool", new_callable=AsyncMock, return_value=pool),
    ):
        yield pool


# ---------------------------------------------------------------------------
# get_products
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_products(mock_pool):
    mock_pool.fetch.return_value = [
        make_record(id=1, name="Brake Pads", sku="BP-01", category="Brakes", our_price=45.90),
    ]
    result = await db.get_products()
    assert len(result) == 1
    assert result[0]["name"] == "Brake Pads"
    mock_pool.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_get_products_empty(mock_pool):
    mock_pool.fetch.return_value = []
    result = await db.get_products()
    assert result == []


# ---------------------------------------------------------------------------
# get_product_by_name
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_product_by_name_found(mock_pool):
    mock_pool.fetchrow.return_value = make_record(id=1, name="Brake Pads")
    result = await db.get_product_by_name("brake")
    assert result is not None
    assert result["name"] == "Brake Pads"


@pytest.mark.asyncio
async def test_get_product_by_name_not_found(mock_pool):
    mock_pool.fetchrow.return_value = None
    result = await db.get_product_by_name("nonexistent")
    assert result is None


# ---------------------------------------------------------------------------
# get_competitors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_competitors(mock_pool):
    mock_pool.fetch.return_value = [
        make_record(id=1, name="AutoDoc", base_url="https://autodoc.de", is_active=True),
        make_record(id=2, name="KFZteile24", base_url="https://kfzteile24.de", is_active=True),
    ]
    result = await db.get_competitors()
    assert len(result) == 2


# ---------------------------------------------------------------------------
# save_price_record
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_price_record(mock_pool):
    mock_pool.fetchrow.return_value = make_record(id=42)
    result = await db.save_price_record(1, 1, 45.90, True)
    assert result == 42


@pytest.mark.asyncio
async def test_save_price_record_out_of_stock(mock_pool):
    mock_pool.fetchrow.return_value = make_record(id=43)
    result = await db.save_price_record(1, 1, 45.90, False)
    assert result == 43


# ---------------------------------------------------------------------------
# get_latest_prices
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_latest_prices_all(mock_pool):
    mock_pool.fetch.return_value = [
        make_record(id=1, product_id=1, competitor_id=1, price=42.50, in_stock=True),
    ]
    result = await db.get_latest_prices()
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_latest_prices_filtered(mock_pool):
    mock_pool.fetch.return_value = [
        make_record(id=1, product_id=1, competitor_id=1, price=42.50, in_stock=True),
    ]
    result = await db.get_latest_prices(product_id=1)
    assert len(result) == 1
    # Verify the query used the product_id parameter
    mock_pool.fetch.assert_called_once()
    call_args = mock_pool.fetch.call_args
    assert call_args[0][1] == 1  # product_id passed as parameter


# ---------------------------------------------------------------------------
# get_price_history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_price_history(mock_pool):
    mock_pool.fetch.return_value = [
        make_record(
            id=1, product_id=1, price=42.50,
            product_name="Brake Pads", competitor_name="AutoDoc",
        ),
        make_record(
            id=2, product_id=1, price=43.10,
            product_name="Brake Pads", competitor_name="AutoDoc",
        ),
    ]
    result = await db.get_price_history(1, days=7)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_price_history_empty(mock_pool):
    mock_pool.fetch.return_value = []
    result = await db.get_price_history(999, days=7)
    assert result == []


# ---------------------------------------------------------------------------
# detect_price_changes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_price_changes(mock_pool):
    mock_pool.fetch.return_value = [
        make_record(
            product_id=1, product_name="Brake Pads",
            competitor_id=1, competitor_name="AutoDoc",
            old_price=44.00, new_price=42.50, in_stock=True,
        ),
    ]
    result = await db.detect_price_changes()
    assert len(result) == 1
    assert result[0]["old_price"] == 44.00


@pytest.mark.asyncio
async def test_detect_price_changes_none(mock_pool):
    mock_pool.fetch.return_value = []
    result = await db.detect_price_changes()
    assert result == []


# ---------------------------------------------------------------------------
# save_report
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_report(mock_pool):
    mock_pool.fetchrow.return_value = make_record(id=1)
    result = await db.save_report("Test report content", "daily", 10)
    assert result == 1


# ---------------------------------------------------------------------------
# get_latest_report
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_latest_report(mock_pool):
    mock_pool.fetchrow.return_value = make_record(
        id=1, report_type="daily", content="Report", product_count=10
    )
    result = await db.get_latest_report()
    assert result is not None
    assert result["content"] == "Report"


@pytest.mark.asyncio
async def test_get_latest_report_none(mock_pool):
    mock_pool.fetchrow.return_value = None
    result = await db.get_latest_report()
    assert result is None


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_alert(mock_pool):
    mock_pool.fetchrow.return_value = make_record(id=1)
    result = await db.save_alert(1, 1, "price_drop", 44.00, 42.50)
    assert result == 1


@pytest.mark.asyncio
async def test_get_recent_alerts(mock_pool):
    mock_pool.fetch.return_value = [
        make_record(
            id=1, product_id=1, competitor_id=1, alert_type="price_drop",
            old_price=44.00, new_price=42.50,
            product_name="Brake Pads", competitor_name="AutoDoc",
        ),
    ]
    result = await db.get_recent_alerts(limit=10)
    assert len(result) == 1
    assert result[0]["alert_type"] == "price_drop"


# ---------------------------------------------------------------------------
# Pool management
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_close_pool():
    mock_pool = AsyncMock()
    with patch.object(db, "_pool", mock_pool):
        await db.close_pool()
        mock_pool.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_pool_when_none():
    with patch.object(db, "_pool", None):
        await db.close_pool()  # Should not raise


@pytest.mark.asyncio
async def test_row_to_dict():
    record = make_record(id=1, name="test")
    result = db._row_to_dict(record)
    assert result == {"id": 1, "name": "test"}


# ---------------------------------------------------------------------------
# get_pool (pool creation path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_pool_creates_new_pool():
    mock_created_pool = AsyncMock()
    with (
        patch.object(db, "_pool", None),
        patch(
            "ai_price_monitor.database.asyncpg.create_pool",
            new_callable=AsyncMock,
            return_value=mock_created_pool,
        ) as mock_create,
    ):
        pool = await db.get_pool()

    assert pool is mock_created_pool
    mock_create.assert_called_once_with(
        dsn=db.settings.database_url, min_size=2, max_size=10
    )


@pytest.mark.asyncio
async def test_get_pool_reuses_existing():
    existing_pool = AsyncMock()
    with patch.object(db, "_pool", existing_pool):
        pool = await db.get_pool()
    assert pool is existing_pool


# ---------------------------------------------------------------------------
# SQL parameter verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_product_by_name_uses_like_pattern(mock_pool):
    mock_pool.fetchrow.return_value = None
    await db.get_product_by_name("brake pad")
    call_args = mock_pool.fetchrow.call_args
    assert call_args[0][1] == "%brake pad%"


@pytest.mark.asyncio
async def test_save_price_record_passes_all_params(mock_pool):
    mock_pool.fetchrow.return_value = make_record(id=1)
    await db.save_price_record(5, 3, 99.99, False)
    call_args = mock_pool.fetchrow.call_args[0]
    assert call_args[1] == 5   # product_id
    assert call_args[2] == 3   # competitor_id
    assert call_args[3] == 99.99  # price
    assert call_args[4] is False  # in_stock


@pytest.mark.asyncio
async def test_save_alert_passes_all_params(mock_pool):
    mock_pool.fetchrow.return_value = make_record(id=7)
    await db.save_alert(2, 4, "out_of_stock", 15.00, None)
    call_args = mock_pool.fetchrow.call_args[0]
    assert call_args[1] == 2   # product_id
    assert call_args[2] == 4   # competitor_id
    assert call_args[3] == "out_of_stock"
    assert call_args[4] == 15.00
    assert call_args[5] is None


@pytest.mark.asyncio
async def test_save_report_passes_all_params(mock_pool):
    mock_pool.fetchrow.return_value = make_record(id=1)
    await db.save_report("Report text", "weekly", 5)
    call_args = mock_pool.fetchrow.call_args[0]
    assert call_args[1] == "weekly"
    assert call_args[2] == "Report text"
    assert call_args[3] == 5


@pytest.mark.asyncio
async def test_get_price_history_passes_days(mock_pool):
    mock_pool.fetch.return_value = []
    await db.get_price_history(1, days=30)
    call_args = mock_pool.fetch.call_args[0]
    assert call_args[1] == 1   # product_id
    assert call_args[2] == 30  # days


@pytest.mark.asyncio
async def test_get_recent_alerts_custom_limit(mock_pool):
    mock_pool.fetch.return_value = []
    await db.get_recent_alerts(limit=5)
    call_args = mock_pool.fetch.call_args[0]
    assert call_args[1] == 5
