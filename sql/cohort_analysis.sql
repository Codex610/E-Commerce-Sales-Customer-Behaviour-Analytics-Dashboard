-- ============================================================
-- cohort_analysis.sql
-- Retention analysis: group customers by their first purchase month,
-- then track how many come back in each subsequent month (M0-M11).
-- ============================================================


-- step 1: tag each customer with their acquisition cohort month
CREATE VIEW IF NOT EXISTS v_cohort_base AS
SELECT
    customer_id,
    strftime('%Y-%m', date(MIN(order_date))) AS cohort_month
FROM orders
WHERE status = 'Delivered'
GROUP BY customer_id;


-- step 2: for every order, calculate how many months after acquisition it happened
-- e.g. if cohort_month = 2009-12 and order is in 2010-03, period = 3
CREATE VIEW IF NOT EXISTS v_cohort_activity AS
SELECT
    cb.customer_id,
    cb.cohort_month,
    (
        (CAST(strftime('%Y', date(o.order_date)) AS INT) -
         CAST(strftime('%Y', cb.cohort_month || '-01') AS INT)) * 12 +
        (CAST(strftime('%m', date(o.order_date)) AS INT) -
         CAST(strftime('%m', cb.cohort_month || '-01') AS INT))
    ) AS period
FROM orders o
JOIN v_cohort_base cb ON o.customer_id = cb.customer_id
WHERE o.status = 'Delivered';


-- step 3: count how many customers from each cohort are active in each period
-- retention_pct = active_in_period / cohort_size * 100
CREATE VIEW IF NOT EXISTS v_cohort_retention AS
WITH cohort_sizes AS (
    SELECT cohort_month, COUNT(DISTINCT customer_id) AS cohort_size
    FROM v_cohort_base
    GROUP BY cohort_month
),
activity AS (
    SELECT
        cohort_month,
        period,
        COUNT(DISTINCT customer_id) AS active
    FROM v_cohort_activity
    WHERE period BETWEEN 0 AND 11
    GROUP BY cohort_month, period
)
SELECT
    a.cohort_month,
    cs.cohort_size,
    a.period,
    a.active,
    ROUND(a.active * 100.0 / cs.cohort_size, 1) AS retention_pct
FROM activity a
JOIN cohort_sizes cs ON a.cohort_month = cs.cohort_month
ORDER BY a.cohort_month, a.period;


-- average retention across all cohorts, by period
-- useful for the retention curve chart
CREATE VIEW IF NOT EXISTS v_avg_retention AS
SELECT
    period,
    ROUND(AVG(retention_pct), 1) AS avg_pct,
    ROUND(MIN(retention_pct), 1) AS min_pct,
    ROUND(MAX(retention_pct), 1) AS max_pct,
    COUNT(*)                     AS num_cohorts
FROM v_cohort_retention
GROUP BY period
ORDER BY period;


-- new vs returning customers per month
-- "new" = the month matches their first order month
CREATE VIEW IF NOT EXISTS v_new_vs_returning AS
WITH first_purchase AS (
    SELECT customer_id, MIN(date(order_date)) AS first_date
    FROM orders
    WHERE status = 'Delivered'
    GROUP BY customer_id
)
SELECT
    strftime('%Y-%m', date(o.order_date))   AS month,
    CASE
        WHEN date(o.order_date) = fp.first_date THEN 'New'
        ELSE 'Returning'
    END                                     AS customer_type,
    COUNT(DISTINCT o.customer_id)           AS customers,
    COUNT(DISTINCT o.order_id)              AS orders
FROM orders o
JOIN first_purchase fp ON o.customer_id = fp.customer_id
WHERE o.status = 'Delivered'
GROUP BY month, customer_type
ORDER BY month, customer_type;
