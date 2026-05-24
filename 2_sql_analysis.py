"""
Step 2: Run SQL queries and save results as CSV files.
All the analysis lives in SQL — keeps it clean and reusable.
"""

import sqlite3
import pandas as pd
import os

DB  = "data/ecommerce.db"
OUT = "data/processed"

os.makedirs(OUT, exist_ok=True)
conn = sqlite3.connect(DB)


def run(label, query, filename):
    df = pd.read_sql_query(query, conn)
    df.to_csv(f"{OUT}/{filename}", index=False)
    print(f"  {label}")
    return df


print("Running SQL queries...\n")


# 1. monthly revenue
run("Monthly revenue", """
    SELECT
        strftime('%Y-%m', o.order_date) AS month,
        ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue,
        COUNT(DISTINCT o.order_id) AS orders,
        COUNT(DISTINCT o.customer_id) AS customers,
        ROUND(SUM(oi.quantity * oi.unit_price) / COUNT(DISTINCT o.order_id), 2) AS aov
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status = 'Delivered'
    GROUP BY month
    ORDER BY month
""", "monthly_revenue.csv")


# 2. overall KPIs
run("KPI summary", """
    SELECT
        ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_revenue,
        COUNT(DISTINCT o.order_id) AS total_orders,
        COUNT(DISTINCT o.customer_id) AS total_customers,
        ROUND(SUM(oi.quantity * oi.unit_price) / COUNT(DISTINCT o.order_id), 2) AS aov,
        ROUND(SUM(oi.return_flag) * 100.0 / COUNT(*), 2) AS return_rate_pct,
        ROUND(SUM(oi.quantity * (oi.unit_price - p.cost_price)), 2) AS gross_profit,
        ROUND(
            SUM(oi.quantity * (oi.unit_price - p.cost_price)) * 100.0
            / SUM(oi.quantity * oi.unit_price), 2
        ) AS gross_margin_pct
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    JOIN products p     ON oi.product_id = p.product_id
    WHERE o.status = 'Delivered'
""", "kpi_summary.csv")


# 3. revenue by region
run("Region performance", """
    SELECT
        o.shipping_region AS region,
        COUNT(DISTINCT o.order_id) AS orders,
        COUNT(DISTINCT o.customer_id) AS customers,
        ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue,
        ROUND(SUM(oi.quantity * oi.unit_price) / COUNT(DISTINCT o.order_id), 2) AS aov,
        ROUND(SUM(oi.return_flag) * 100.0 / COUNT(*), 2) AS return_rate_pct,
        ROUND(
            SUM(oi.quantity * (oi.unit_price - p.cost_price)) * 100.0
            / SUM(oi.quantity * oi.unit_price), 2
        ) AS margin_pct
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    JOIN products p     ON oi.product_id = p.product_id
    WHERE o.status = 'Delivered'
    GROUP BY region
    ORDER BY revenue DESC
""", "region_performance.csv")


# 4. top 50 products
run("Top products", """
    SELECT
        p.product_id,
        p.name,
        p.category,
        p.subcategory,
        SUM(oi.quantity) AS units_sold,
        ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue,
        ROUND(SUM(oi.return_flag) * 100.0 / COUNT(*), 2) AS return_rate_pct,
        ROUND(
            SUM(oi.quantity * (oi.unit_price - p.cost_price)) * 100.0
            / SUM(oi.quantity * oi.unit_price), 2
        ) AS margin_pct
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    JOIN orders o   ON oi.order_id = o.order_id
    WHERE o.status = 'Delivered'
    GROUP BY p.product_id
    ORDER BY revenue DESC
    LIMIT 50
""", "top_products.csv")


# 5. revenue by category
run("Category performance", """
    SELECT
        p.category,
        p.subcategory,
        COUNT(DISTINCT o.order_id) AS orders,
        SUM(oi.quantity) AS units_sold,
        ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue,
        ROUND(SUM(oi.return_flag) * 100.0 / COUNT(*), 2) AS return_rate_pct,
        ROUND(
            SUM(oi.quantity * (oi.unit_price - p.cost_price)) * 100.0
            / SUM(oi.quantity * oi.unit_price), 2
        ) AS margin_pct
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    JOIN orders o   ON oi.order_id = o.order_id
    WHERE o.status = 'Delivered'
    GROUP BY p.category, p.subcategory
    ORDER BY revenue DESC
""", "category_performance.csv")


# 6. channel performance
run("Channel performance", """
    SELECT
        o.channel,
        COUNT(DISTINCT o.order_id) AS orders,
        COUNT(DISTINCT o.customer_id) AS customers,
        ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue,
        ROUND(SUM(oi.quantity * oi.unit_price) / COUNT(DISTINCT o.order_id), 2) AS aov
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status = 'Delivered'
    GROUP BY o.channel
    ORDER BY revenue DESC
""", "channel_performance.csv")


# 7. payment methods
run("Payment methods", """
    SELECT
        o.payment_method,
        COUNT(DISTINCT o.order_id) AS orders,
        ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status = 'Delivered'
    GROUP BY o.payment_method
    ORDER BY revenue DESC
""", "payment_methods.csv")


# 8. RFM — score each customer 1-5 on Recency, Frequency, Monetary
run("RFM segments", """
    WITH rfm_raw AS (
        SELECT
            o.customer_id,
            CAST(julianday('2011-12-09') - julianday(MAX(o.order_date)) AS INT) AS recency_days,
            COUNT(DISTINCT o.order_id) AS frequency,
            ROUND(SUM(oi.quantity * oi.unit_price), 2) AS monetary
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.status = 'Delivered'
        GROUP BY o.customer_id
    ),
    scored AS (
        SELECT *,
            NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
            NTILE(5) OVER (ORDER BY frequency ASC)     AS f_score,
            NTILE(5) OVER (ORDER BY monetary ASC)      AS m_score
        FROM rfm_raw
    )
    SELECT *,
        CASE
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
            WHEN f_score >= 4 AND r_score >= 3                  THEN 'Loyal Customers'
            WHEN r_score >= 4 AND f_score < 3                   THEN 'Potential Loyalists'
            WHEN r_score <= 2 AND f_score >= 3                  THEN 'At Risk'
            WHEN r_score = 1  AND f_score >= 4                  THEN 'Cannot Lose Them'
            WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2 THEN 'Hibernating'
            WHEN r_score = 1                                     THEN 'Lost'
            ELSE 'Others'
        END AS segment
    FROM scored
""", "rfm_segments.csv")


# 9. RFM summary (segment-level aggregates)
rfm = pd.read_csv(f"{OUT}/rfm_segments.csv")
rfm_summary = (
    rfm.groupby("segment")
    .agg(
        customers=("customer_id", "count"),
        avg_recency=("recency_days", "mean"),
        avg_orders=("frequency", "mean"),
        avg_spend=("monetary", "mean"),
        total_revenue=("monetary", "sum"),
    )
    .round(2)
    .reset_index()
    .sort_values("total_revenue", ascending=False)
)
rfm_summary.to_csv(f"{OUT}/rfm_summary.csv", index=False)
print("  RFM summary")


# 10. cohort retention
run("Cohort retention", """
    WITH first_purchase AS (
        SELECT customer_id,
               strftime('%Y-%m', date(MIN(order_date))) AS cohort_month
        FROM orders
        WHERE status = 'Delivered'
        GROUP BY customer_id
    ),
    monthly_activity AS (
        SELECT
            fp.customer_id,
            fp.cohort_month,
            (
                (CAST(strftime('%Y', date(o.order_date)) AS INT) -
                 CAST(strftime('%Y', fp.cohort_month || '-01') AS INT)) * 12 +
                (CAST(strftime('%m', date(o.order_date)) AS INT) -
                 CAST(strftime('%m', fp.cohort_month || '-01') AS INT))
            ) AS period
        FROM orders o
        JOIN first_purchase fp ON o.customer_id = fp.customer_id
        WHERE o.status = 'Delivered'
    ),
    cohort_sizes AS (
        SELECT cohort_month, COUNT(DISTINCT customer_id) AS cohort_size
        FROM first_purchase
        GROUP BY cohort_month
    )
    SELECT
        ma.cohort_month,
        cs.cohort_size,
        ma.period,
        COUNT(DISTINCT ma.customer_id) AS active_customers,
        ROUND(COUNT(DISTINCT ma.customer_id) * 100.0 / cs.cohort_size, 1) AS retention_pct
    FROM monthly_activity ma
    JOIN cohort_sizes cs ON ma.cohort_month = cs.cohort_month
    WHERE ma.period BETWEEN 0 AND 11
    GROUP BY ma.cohort_month, ma.period
    ORDER BY ma.cohort_month, ma.period
""", "cohort_retention.csv")


# 11. cohort pivot (wide format for heatmap)
cohort = pd.read_csv(f"{OUT}/cohort_retention.csv")
pivot = cohort.pivot_table(
    index="cohort_month",
    columns="period",
    values="retention_pct"
)
pivot.columns = [f"M{int(c):02d}" for c in pivot.columns]
pivot.to_csv(f"{OUT}/cohort_pivot.csv")
print("  Cohort pivot")


# 12. average retention by period
avg_ret = (
    cohort.groupby("period")["retention_pct"]
    .agg(["mean","min","max"])
    .round(1)
    .reset_index()
    .rename(columns={"period":"months_since_first_order",
                     "mean":"avg_pct","min":"min_pct","max":"max_pct"})
)
avg_ret.to_csv(f"{OUT}/avg_retention.csv", index=False)
print("  Avg retention by period")


# 13. churn risk
run("Churn risk", """
    WITH last_order AS (
        SELECT customer_id, MAX(order_date) AS last_date,
               COUNT(DISTINCT order_id) AS total_orders
        FROM orders
        WHERE status = 'Delivered'
        GROUP BY customer_id
    )
    SELECT
        lo.customer_id,
        c.region,
        c.age_group,
        c.gender,
        lo.last_date,
        lo.total_orders,
        CAST(julianday('2011-12-09') - julianday(lo.last_date) AS INT) AS days_inactive,
        CASE
            WHEN julianday('2011-12-09') - julianday(lo.last_date) > 180 THEN 'Churned'
            WHEN julianday('2011-12-09') - julianday(lo.last_date) > 90  THEN 'At Risk'
            ELSE 'Active'
        END AS churn_status
    FROM last_order lo
    JOIN customers c ON lo.customer_id = c.customer_id
""", "churn_risk.csv")


# 14. new vs returning customers per month
run("New vs returning", """
    WITH first_orders AS (
        SELECT customer_id, MIN(date(order_date)) AS first_date
        FROM orders WHERE status = 'Delivered'
        GROUP BY customer_id
    )
    SELECT
        strftime('%Y-%m', date(o.order_date)) AS month,
        CASE WHEN date(o.order_date) = fo.first_date THEN 'New' ELSE 'Returning' END AS type,
        COUNT(DISTINCT o.customer_id) AS customers,
        COUNT(DISTINCT o.order_id) AS orders
    FROM orders o
    JOIN first_orders fo ON o.customer_id = fo.customer_id
    WHERE o.status = 'Delivered'
    GROUP BY month, type
    ORDER BY month, type
""", "new_vs_returning.csv")


# 15. customer CLV
run("Customer CLV", """
    SELECT
        customer_id,
        COUNT(DISTINCT order_id) AS total_orders,
        ROUND(SUM(quantity * unit_price), 2) AS total_spend,
        MIN(order_date) AS first_order,
        MAX(order_date) AS last_order,
        ROUND(SUM(quantity * unit_price) / COUNT(DISTINCT order_id), 2) AS aov
    FROM (
        SELECT o.customer_id, o.order_id, o.order_date,
               oi.quantity, oi.unit_price
        FROM orders o JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.status = 'Delivered'
    )
    GROUP BY customer_id
    ORDER BY total_spend DESC
""", "customer_clv.csv")

conn.close()

# quick summary
kpi = pd.read_csv(f"{OUT}/kpi_summary.csv")
print(f"\nDone! Key numbers:")
print(f"  Revenue : £{kpi['total_revenue'].iloc[0]:,.0f}")
print(f"  Orders  : {kpi['total_orders'].iloc[0]:,}")
print(f"  AOV     : £{kpi['aov'].iloc[0]:,.2f}")
print(f"  Margin  : {kpi['gross_margin_pct'].iloc[0]:.1f}%")
print(f"  Returns : {kpi['return_rate_pct'].iloc[0]:.1f}%")
print("\nRun 3_eda.py next.")
