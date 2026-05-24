-- ============================================================
-- kpi_queries.sql
-- Core business KPIs used in the dashboard and reports.
-- Run via: python etl/pipeline.py  (or manually in DB Browser)
-- ============================================================


-- monthly revenue, order count, unique customers, average order value
-- also computes month-over-month growth using LAG window function
CREATE VIEW IF NOT EXISTS v_monthly_revenue AS
WITH monthly AS (
    SELECT
        strftime('%Y-%m', o.order_date)            AS month,
        ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue,
        COUNT(DISTINCT o.order_id)                 AS orders,
        COUNT(DISTINCT o.customer_id)              AS customers,
        ROUND(SUM(oi.quantity * oi.unit_price)
              / COUNT(DISTINCT o.order_id), 2)     AS aov
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status = 'Delivered'
    GROUP BY month
)
SELECT
    month,
    revenue,
    orders,
    customers,
    aov,
    LAG(revenue) OVER (ORDER BY month)   AS prev_revenue,
    ROUND(
        (revenue - LAG(revenue) OVER (ORDER BY month)) * 100.0
        / NULLIF(LAG(revenue) OVER (ORDER BY month), 0),
    1) AS mom_growth_pct
FROM monthly
ORDER BY month;


-- single-row overall summary — handy for dashboard KPI cards
CREATE VIEW IF NOT EXISTS v_kpi_summary AS
SELECT
    ROUND(SUM(oi.quantity * oi.unit_price), 2)                  AS total_revenue,
    COUNT(DISTINCT o.order_id)                                   AS total_orders,
    COUNT(DISTINCT o.customer_id)                                AS total_customers,
    ROUND(SUM(oi.quantity * oi.unit_price)
          / COUNT(DISTINCT o.order_id), 2)                       AS aov,
    ROUND(SUM(oi.return_flag) * 100.0 / COUNT(*), 2)            AS return_rate_pct,
    ROUND(SUM(oi.quantity * (oi.unit_price - p.cost_price)), 2) AS gross_profit,
    ROUND(SUM(oi.quantity * (oi.unit_price - p.cost_price))
          * 100.0 / SUM(oi.quantity * oi.unit_price), 2)        AS gross_margin_pct
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p     ON oi.product_id = p.product_id
WHERE o.status = 'Delivered';


-- revenue and margin broken down by region
CREATE VIEW IF NOT EXISTS v_region_kpis AS
SELECT
    o.shipping_region                                            AS region,
    COUNT(DISTINCT o.order_id)                                   AS orders,
    COUNT(DISTINCT o.customer_id)                                AS customers,
    ROUND(SUM(oi.quantity * oi.unit_price), 2)                  AS revenue,
    ROUND(SUM(oi.quantity * oi.unit_price)
          / COUNT(DISTINCT o.order_id), 2)                       AS aov,
    ROUND(SUM(oi.return_flag) * 100.0 / COUNT(*), 2)            AS return_rate_pct,
    ROUND(SUM(oi.quantity * (oi.unit_price - p.cost_price))
          * 100.0 / SUM(oi.quantity * oi.unit_price), 2)        AS margin_pct
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p     ON oi.product_id = p.product_id
WHERE o.status = 'Delivered'
GROUP BY region
ORDER BY revenue DESC;


-- product-level performance: top sellers, worst returners, highest margin
CREATE VIEW IF NOT EXISTS v_product_kpis AS
SELECT
    p.product_id,
    p.name,
    p.category,
    p.subcategory,
    SUM(oi.quantity)                                             AS units_sold,
    ROUND(SUM(oi.quantity * oi.unit_price), 2)                  AS revenue,
    ROUND(SUM(oi.return_flag) * 100.0 / COUNT(*), 2)            AS return_rate_pct,
    ROUND(SUM(oi.quantity * (oi.unit_price - p.cost_price))
          * 100.0 / SUM(oi.quantity * oi.unit_price), 2)        AS margin_pct
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
JOIN orders o   ON oi.order_id   = o.order_id
WHERE o.status = 'Delivered'
GROUP BY p.product_id
ORDER BY revenue DESC;


-- channel and payment method breakdown
CREATE VIEW IF NOT EXISTS v_channel_kpis AS
SELECT
    o.channel,
    COUNT(DISTINCT o.order_id)                                   AS orders,
    COUNT(DISTINCT o.customer_id)                                AS customers,
    ROUND(SUM(oi.quantity * oi.unit_price), 2)                  AS revenue,
    ROUND(SUM(oi.quantity * oi.unit_price)
          / COUNT(DISTINCT o.order_id), 2)                       AS aov
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.status = 'Delivered'
GROUP BY o.channel
ORDER BY revenue DESC;


-- churn risk: flag customers as Active / At Risk / Churned
-- based on days since their last order relative to dataset end date
CREATE VIEW IF NOT EXISTS v_churn_risk AS
WITH last_order AS (
    SELECT
        customer_id,
        MAX(order_date)          AS last_order_date,
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
    lo.last_order_date,
    lo.total_orders,
    CAST(julianday('2011-12-09') - julianday(lo.last_order_date) AS INT) AS days_inactive,
    CASE
        WHEN julianday('2011-12-09') - julianday(lo.last_order_date) > 180 THEN 'Churned'
        WHEN julianday('2011-12-09') - julianday(lo.last_order_date) > 90  THEN 'At Risk'
        ELSE 'Active'
    END AS churn_status
FROM last_order lo
JOIN customers c ON lo.customer_id = c.customer_id
ORDER BY days_inactive DESC;


-- customer lifetime value: AOV × purchase frequency
-- using actual order history, no guesswork
CREATE VIEW IF NOT EXISTS v_customer_clv AS
SELECT
    o.customer_id,
    COUNT(DISTINCT o.order_id)                                       AS total_orders,
    ROUND(SUM(oi.quantity * oi.unit_price), 2)                      AS total_spend,
    ROUND(SUM(oi.quantity * oi.unit_price)
          / COUNT(DISTINCT o.order_id), 2)                           AS aov,
    MIN(o.order_date)                                               AS first_order,
    MAX(o.order_date)                                               AS last_order,
    CAST(julianday(MAX(o.order_date)) - julianday(MIN(o.order_date)) AS INT) AS active_days
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.status = 'Delivered'
GROUP BY o.customer_id
ORDER BY total_spend DESC;
