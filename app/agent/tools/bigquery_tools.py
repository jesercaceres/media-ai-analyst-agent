"""
BigQuery tool functions for the Media Analyst Agent.

Each function is a standalone callable that:
  1. Builds a safe, parameterized SQL query against thelook_ecommerce.
  2. Executes it via the shared BigQuery client.
  3. Returns a structured dict ready for the LLM to interpret.
"""

from __future__ import annotations

from typing import Any

from google.cloud import bigquery
from langchain_core.tools import tool

from app.core.bigquery import run_query

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

_DATASET = "bigquery-public-data.thelook_ecommerce"
_USERS = f"`{_DATASET}.users`"
_ORDERS = f"`{_DATASET}.orders`"
_ORDER_ITEMS = f"`{_DATASET}.order_items`"

_VALID_INTERVALS = {"7 DAY", "30 DAY", "90 DAY", "180 DAY", "365 DAY"}
_VALID_SOURCES = {"Search", "Organic", "Facebook", "Email", "Display"}

# ──────────────────────────────────────────────────────────────────────────────
# Tool 1 — Traffic Volume
# ──────────────────────────────────────────────────────────────────────────────


@tool
def get_traffic_volume(
    traffic_source: str | None = None,
    interval_days: int = 30,
) -> dict[str, Any]:
    """
    Returns the number of new users per traffic channel within a date window.

    Use this tool to answer questions like:
      - "How many users came from Search last month?"
      - "Show me the traffic volume by channel in the last 90 days."

    Args:
        traffic_source: Optional filter for a specific channel
                        (Search, Organic, Facebook, Email, Display).
                        Pass None to return all channels.
        interval_days:  Number of days to look back from today (default 30).
    """
    if interval_days <= 0:
        interval_days = 30

    interval_str = f"{interval_days} DAY"

    source_filter = ""
    params: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("interval_days", "INT64", interval_days),
    ]

    if traffic_source:
        source_filter = "AND traffic_source = @traffic_source"
        params.append(
            bigquery.ScalarQueryParameter("traffic_source", "STRING", traffic_source)
        )

    sql = f"""
        SELECT
            traffic_source                          AS channel,
            COUNT(*)                                AS new_users,
            MIN(DATE(created_at))                   AS earliest_date,
            MAX(DATE(created_at))                   AS latest_date
        FROM {_USERS}
        WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @interval_days DAY)
          {source_filter}
        GROUP BY traffic_source
        ORDER BY new_users DESC
    """

    rows = run_query(sql, params)
    return {
        "tool": "get_traffic_volume",
        "interval_days": interval_days,
        "filter_source": traffic_source,
        "results": rows,
        "total_users": sum(r["new_users"] for r in rows),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Tool 2 — Channel Performance (conversion rate + revenue)
# ──────────────────────────────────────────────────────────────────────────────


@tool
def get_channel_performance(interval_days: int = 30) -> dict[str, Any]:
    """
    Returns a full performance breakdown per traffic channel, including:
      - Total unique users (traffic)
      - Total buyers (users who placed at least one non-cancelled order)
      - Total orders
      - Total revenue (sum of sale_price on completed/processing/shipped orders)
      - Conversion rate (buyers / total users)
      - Average order value (AOV)
      - Revenue per user (RPU)

    Use this tool to answer questions like:
      - "Which channel has the best performance?"
      - "What is the conversion rate per channel?"
      - "Which channel generates the most revenue?"

    Args:
        interval_days: Number of days to look back from today (default 30).
    """
    if interval_days <= 0:
        interval_days = 30

    params = [bigquery.ScalarQueryParameter("interval_days", "INT64", interval_days)]

    sql = f"""
        WITH user_base AS (
            SELECT
                id          AS user_id,
                traffic_source AS channel
            FROM {_USERS}
            WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @interval_days DAY)
        ),
        order_data AS (
            SELECT
                o.user_id,
                o.order_id,
                SUM(oi.sale_price) AS order_revenue
            FROM {_ORDERS} o
            JOIN {_ORDER_ITEMS} oi ON o.order_id = oi.order_id
            WHERE o.status NOT IN ('Cancelled', 'Returned')
              AND o.created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @interval_days DAY)
            GROUP BY o.user_id, o.order_id
        )
        SELECT
            ub.channel,
            COUNT(DISTINCT ub.user_id)              AS total_users,
            COUNT(DISTINCT od.user_id)              AS buyers,
            COUNT(DISTINCT od.order_id)             AS total_orders,
            ROUND(COALESCE(SUM(od.order_revenue), 0), 2)    AS total_revenue,
            ROUND(
                SAFE_DIVIDE(COUNT(DISTINCT od.user_id), COUNT(DISTINCT ub.user_id)) * 100,
                2
            )                                               AS conversion_rate_pct,
            ROUND(
                SAFE_DIVIDE(SUM(od.order_revenue), NULLIF(COUNT(DISTINCT od.order_id), 0)),
                2
            )                                               AS avg_order_value,
            ROUND(
                SAFE_DIVIDE(SUM(od.order_revenue), NULLIF(COUNT(DISTINCT ub.user_id), 0)),
                2
            )                                               AS revenue_per_user
        FROM user_base ub
        LEFT JOIN order_data od ON ub.user_id = od.user_id
        GROUP BY ub.channel
        ORDER BY total_revenue DESC
    """

    rows = run_query(sql, params)
    return {
        "tool": "get_channel_performance",
        "interval_days": interval_days,
        "results": rows,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Tool 3 — Revenue Trend (monthly breakdown per channel)
# ──────────────────────────────────────────────────────────────────────────────


@tool
def get_revenue_trend(
    traffic_source: str | None = None,
    interval_days: int = 180,
) -> dict[str, Any]:
    """
    Returns monthly revenue and order volume trends, optionally filtered
    by a specific traffic channel.

    Use this tool to answer questions like:
      - "How has the revenue from Facebook evolved over the last 6 months?"
      - "Show the monthly revenue trend for all channels."

    Args:
        traffic_source: Optional channel filter (Search, Organic, Facebook, etc.).
        interval_days:  Look-back window in days (default 180 = ~6 months).
    """
    if interval_days <= 0:
        interval_days = 180

    params: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("interval_days", "INT64", interval_days),
    ]

    source_filter = ""
    if traffic_source:
        source_filter = "AND u.traffic_source = @traffic_source"
        params.append(
            bigquery.ScalarQueryParameter("traffic_source", "STRING", traffic_source)
        )

    sql = f"""
        SELECT
            FORMAT_DATE('%Y-%m', DATE(o.created_at))    AS month,
            u.traffic_source                             AS channel,
            COUNT(DISTINCT o.order_id)                   AS total_orders,
            ROUND(SUM(oi.sale_price), 2)                 AS total_revenue
        FROM {_ORDERS} o
        JOIN {_USERS} u     ON o.user_id = u.id
        JOIN {_ORDER_ITEMS} oi ON o.order_id = oi.order_id
        WHERE o.status NOT IN ('Cancelled', 'Returned')
          AND o.created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @interval_days DAY)
          {source_filter}
        GROUP BY month, channel
        ORDER BY month DESC, total_revenue DESC
    """

    rows = run_query(sql, params)
    return {
        "tool": "get_revenue_trend",
        "interval_days": interval_days,
        "filter_source": traffic_source,
        "results": rows,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Tool 4 — User Demographics by Channel
# ──────────────────────────────────────────────────────────────────────────────


@tool
def get_user_demographics(
    traffic_source: str | None = None,
    interval_days: int = 30,
) -> dict[str, Any]:
    """
    Returns demographic breakdown (age group, gender, country) of users
    per traffic channel.

    Use this tool to answer questions like:
      - "What is the profile of users coming from Facebook?"
      - "Which countries do Email channel users come from?"

    Args:
        traffic_source: Optional filter for a specific channel.
        interval_days:  Look-back window in days (default 30).
    """
    if interval_days <= 0:
        interval_days = 30

    params: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("interval_days", "INT64", interval_days),
    ]

    source_filter = ""
    if traffic_source:
        source_filter = "AND traffic_source = @traffic_source"
        params.append(
            bigquery.ScalarQueryParameter("traffic_source", "STRING", traffic_source)
        )

    sql = f"""
        SELECT
            traffic_source                                          AS channel,
            gender,
            country,
            CASE
                WHEN age < 25  THEN '18-24'
                WHEN age < 35  THEN '25-34'
                WHEN age < 45  THEN '35-44'
                WHEN age < 55  THEN '45-54'
                ELSE '55+'
            END                                                     AS age_group,
            COUNT(*)                                                AS user_count
        FROM {_USERS}
        WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @interval_days DAY)
          {source_filter}
        GROUP BY channel, gender, country, age_group
        ORDER BY channel, user_count DESC
    """

    rows = run_query(sql, params)
    return {
        "tool": "get_user_demographics",
        "interval_days": interval_days,
        "filter_source": traffic_source,
        "results": rows,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Tool 5 — Top Products per Channel
# ──────────────────────────────────────────────────────────────────────────────


@tool
def get_top_products_by_channel(
    traffic_source: str | None = None,
    interval_days: int = 30,
    top_n: int = 10,
) -> dict[str, Any]:
    """
    Returns the best-selling products (by revenue) for a given channel.

    Use this tool to answer questions like:
      - "What are the top products bought by users from Organic search?"
      - "Which products are most popular for Facebook traffic?"

    Args:
        traffic_source: Channel filter (required for meaningful results).
        interval_days:  Look-back window in days (default 30).
        top_n:          Number of top products to return (default 10).
    """
    if interval_days <= 0:
        interval_days = 30
    if top_n <= 0:
        top_n = 10

    params: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("interval_days", "INT64", interval_days),
        bigquery.ScalarQueryParameter("top_n", "INT64", top_n),
    ]

    source_filter = ""
    if traffic_source:
        source_filter = "AND u.traffic_source = @traffic_source"
        params.append(
            bigquery.ScalarQueryParameter("traffic_source", "STRING", traffic_source)
        )

    sql = f"""
        SELECT
            u.traffic_source                        AS channel,
            oi.product_id,
            ANY_VALUE(oi.product_name)              AS product_name,
            ANY_VALUE(oi.category)                  AS category,
            COUNT(DISTINCT o.order_id)              AS times_ordered,
            ROUND(SUM(oi.sale_price), 2)            AS total_revenue
        FROM {_ORDERS} o
        JOIN {_USERS} u        ON o.user_id = u.id
        JOIN {_ORDER_ITEMS} oi ON o.order_id = oi.order_id
        WHERE o.status NOT IN ('Cancelled', 'Returned')
          AND o.created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @interval_days DAY)
          {source_filter}
        GROUP BY channel, oi.product_id
        ORDER BY total_revenue DESC
        LIMIT @top_n
    """

    rows = run_query(sql, params)
    return {
        "tool": "get_top_products_by_channel",
        "interval_days": interval_days,
        "filter_source": traffic_source,
        "top_n": top_n,
        "results": rows,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Exported list used by the agent
# ──────────────────────────────────────────────────────────────────────────────

ALL_TOOLS = [
    get_traffic_volume,
    get_channel_performance,
    get_revenue_trend,
    get_user_demographics,
    get_top_products_by_channel,
]
