-- ============================================================
-- rfm_segmentation.sql
-- RFM = Recency, Frequency, Monetary
-- Score each customer 1-5 on each dimension, then assign
-- a business segment label (Champions, At Risk, etc.)
-- ============================================================


-- step 1: calculate raw RFM values per customer
-- recency = days since last order (lower = more recent = better)
-- frequency = number of distinct orders
-- monetary = total spend
CREATE VIEW IF NOT EXISTS v_rfm_raw AS
SELECT
    o.customer_id,
    CAST(julianday('2011-12-09') - julianday(MAX(o.order_date)) AS INT) AS recency_days,
    COUNT(DISTINCT o.order_id)                                           AS frequency,
    ROUND(SUM(oi.quantity * oi.unit_price), 2)                          AS monetary
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.status = 'Delivered'
GROUP BY o.customer_id;


-- step 2: score each dimension 1-5 using NTILE (quintile ranking)
-- for recency: fewer days = higher score, so we order DESC
-- for frequency and monetary: more = higher score, order ASC
CREATE VIEW IF NOT EXISTS v_rfm_scored AS
SELECT
    customer_id,
    recency_days,
    frequency,
    monetary,
    NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
    NTILE(5) OVER (ORDER BY frequency ASC)     AS f_score,
    NTILE(5) OVER (ORDER BY monetary ASC)      AS m_score
FROM v_rfm_raw;


-- step 3: assign human-readable segment labels based on score combinations
-- segments follow the standard RFM framework used in CRM analytics
CREATE VIEW IF NOT EXISTS v_rfm_segments AS
SELECT
    customer_id,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    (r_score + f_score + m_score) AS rfm_score,
    CASE
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
        WHEN f_score >= 4 AND r_score >= 3                  THEN 'Loyal Customers'
        WHEN r_score >= 4 AND f_score < 3                   THEN 'Potential Loyalists'
        WHEN r_score >= 3 AND f_score = 2                   THEN 'Promising'
        WHEN r_score = 3  AND f_score >= 3 AND m_score >= 3 THEN 'Needs Attention'
        WHEN r_score = 2  AND f_score <= 2                  THEN 'About to Sleep'
        WHEN r_score <= 2 AND f_score >= 3                  THEN 'At Risk'
        WHEN r_score = 1  AND f_score >= 4 AND m_score >= 4 THEN 'Cannot Lose Them'
        WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2 THEN 'Hibernating'
        WHEN r_score = 1                                     THEN 'Lost'
        ELSE 'Others'
    END AS segment
FROM v_rfm_scored;


-- step 4: segment-level summary for charts
CREATE VIEW IF NOT EXISTS v_rfm_summary AS
SELECT
    segment,
    COUNT(*)                   AS customers,
    ROUND(AVG(recency_days), 0) AS avg_recency_days,
    ROUND(AVG(frequency), 1)   AS avg_orders,
    ROUND(AVG(monetary), 0)    AS avg_spend,
    ROUND(SUM(monetary), 0)    AS total_revenue,
    ROUND(AVG(r_score), 1)     AS avg_r,
    ROUND(AVG(f_score), 1)     AS avg_f,
    ROUND(AVG(m_score), 1)     AS avg_m
FROM v_rfm_segments
GROUP BY segment
ORDER BY total_revenue DESC;
