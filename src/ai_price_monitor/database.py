"""Database layer — asyncpg pool and CRUD operations."""

from __future__ import annotations

from typing import Any

import asyncpg

from ai_price_monitor.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return the shared connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=2, max_size=10)
    return _pool


async def close_pool() -> None:
    """Gracefully close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    return dict(row)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

async def get_products() -> list[dict[str, Any]]:
    pool = await get_pool()
    rows = await pool.fetch("SELECT * FROM products ORDER BY id")
    return [_row_to_dict(r) for r in rows]


async def get_product_by_name(name: str) -> dict[str, Any] | None:
    pool = await get_pool()
    escaped = name.replace("%", r"\%").replace("_", r"\_")
    row = await pool.fetchrow(
        "SELECT * FROM products WHERE LOWER(name) LIKE LOWER($1) ESCAPE '\\'",
        f"%{escaped}%",
    )
    return _row_to_dict(row) if row else None


# ---------------------------------------------------------------------------
# Competitors
# ---------------------------------------------------------------------------

async def get_competitors() -> list[dict[str, Any]]:
    pool = await get_pool()
    rows = await pool.fetch("SELECT * FROM competitors WHERE is_active = TRUE ORDER BY id")
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Price records
# ---------------------------------------------------------------------------

async def save_price_record(
    product_id: int,
    competitor_id: int,
    price: float,
    in_stock: bool = True,
) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO price_records (product_id, competitor_id, price, in_stock)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        product_id,
        competitor_id,
        price,
        in_stock,
    )
    return row["id"]  # type: ignore[no-any-return]


async def get_latest_prices(product_id: int | None = None) -> list[dict[str, Any]]:
    """Get the most recent price per product per competitor."""
    pool = await get_pool()
    query = """
        SELECT DISTINCT ON (pr.product_id, pr.competitor_id)
            pr.id, pr.product_id, pr.competitor_id, pr.price, pr.in_stock, pr.scraped_at,
            p.name AS product_name, p.sku, p.our_price, p.category,
            c.name AS competitor_name
        FROM price_records pr
        JOIN products p ON p.id = pr.product_id
        JOIN competitors c ON c.id = pr.competitor_id
        ORDER BY pr.product_id, pr.competitor_id, pr.scraped_at DESC
    """
    if product_id is not None:
        query = """
            SELECT DISTINCT ON (pr.competitor_id)
                pr.id, pr.product_id, pr.competitor_id, pr.price, pr.in_stock, pr.scraped_at,
                p.name AS product_name, p.sku, p.our_price, p.category,
                c.name AS competitor_name
            FROM price_records pr
            JOIN products p ON p.id = pr.product_id
            JOIN competitors c ON c.id = pr.competitor_id
            WHERE pr.product_id = $1
            ORDER BY pr.competitor_id, pr.scraped_at DESC
        """
        rows = await pool.fetch(query, product_id)
    else:
        rows = await pool.fetch(query)
    return [_row_to_dict(r) for r in rows]


async def get_price_history(
    product_id: int, days: int = 7
) -> list[dict[str, Any]]:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT pr.*, p.name AS product_name, c.name AS competitor_name
        FROM price_records pr
        JOIN products p ON p.id = pr.product_id
        JOIN competitors c ON c.id = pr.competitor_id
        WHERE pr.product_id = $1
          AND pr.scraped_at >= NOW() - make_interval(days => $2)
        ORDER BY pr.scraped_at DESC
        """,
        product_id,
        days,
    )
    return [_row_to_dict(r) for r in rows]


async def detect_price_changes() -> list[dict[str, Any]]:
    """Compare the two most recent scrapes per product/competitor."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        WITH ranked AS (
            SELECT
                pr.*,
                p.name AS product_name,
                c.name AS competitor_name,
                ROW_NUMBER() OVER (
                    PARTITION BY pr.product_id, pr.competitor_id
                    ORDER BY pr.scraped_at DESC
                ) AS rn
            FROM price_records pr
            JOIN products p ON p.id = pr.product_id
            JOIN competitors c ON c.id = pr.competitor_id
        )
        SELECT
            cur.product_id,
            cur.product_name,
            cur.competitor_id,
            cur.competitor_name,
            prev.price AS old_price,
            cur.price AS new_price,
            cur.in_stock
        FROM ranked cur
        JOIN ranked prev
          ON cur.product_id = prev.product_id
         AND cur.competitor_id = prev.competitor_id
         AND prev.rn = 2
        WHERE cur.rn = 1
          AND (cur.price != prev.price OR cur.in_stock != prev.in_stock)
        """
    )
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

async def save_report(content: str, report_type: str = "daily", product_count: int = 0) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO reports (report_type, content, product_count)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        report_type,
        content,
        product_count,
    )
    return row["id"]  # type: ignore[no-any-return]


async def get_latest_report() -> dict[str, Any] | None:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM reports ORDER BY generated_at DESC LIMIT 1")
    return _row_to_dict(row) if row else None


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

async def save_alert(
    product_id: int,
    competitor_id: int,
    alert_type: str,
    old_price: float | None,
    new_price: float | None,
) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO alerts (product_id, competitor_id, alert_type, old_price, new_price)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        product_id,
        competitor_id,
        alert_type,
        old_price,
        new_price,
    )
    return row["id"]  # type: ignore[no-any-return]


async def get_recent_alerts(limit: int = 20) -> list[dict[str, Any]]:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT a.*, p.name AS product_name, c.name AS competitor_name
        FROM alerts a
        JOIN products p ON p.id = a.product_id
        JOIN competitors c ON c.id = a.competitor_id
        ORDER BY a.created_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [_row_to_dict(r) for r in rows]
