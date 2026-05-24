-- ============================================================
-- ecommerce_analytics: table schema
-- UCI Online Retail II dataset (Dec 2009 – Dec 2011)
-- ============================================================

-- customers
-- one row per unique customer
CREATE TABLE IF NOT EXISTS customers (
    customer_id  TEXT    PRIMARY KEY,
    name         TEXT,
    email        TEXT,
    city         TEXT,
    region       TEXT,   -- e.g. Europe, Asia-Pacific
    signup_date  TEXT,   -- YYYY-MM-DD
    age_group    TEXT,   -- 18-24, 25-34, ...
    gender       TEXT
);

-- products
-- one row per unique stock code
CREATE TABLE IF NOT EXISTS products (
    product_id   TEXT    PRIMARY KEY,
    name         TEXT,
    category     TEXT,   -- e.g. Home & Decor, Seasonal
    subcategory  TEXT,
    unit_price   REAL,   -- median selling price
    cost_price   REAL    -- estimated at 55% of unit_price
);

-- orders
-- one row per invoice (basket)
CREATE TABLE IF NOT EXISTS orders (
    order_id        TEXT PRIMARY KEY,
    customer_id     TEXT REFERENCES customers(customer_id),
    order_date      TEXT,   -- YYYY-MM-DD
    status          TEXT,   -- Delivered / Cancelled
    channel         TEXT,   -- Website, Mobile App, etc.
    payment_method  TEXT,
    shipping_region TEXT,
    discount_pct    REAL    -- 0.0 to 0.30
);

-- order_items
-- one row per line item (product within an order)
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id TEXT PRIMARY KEY,
    order_id      TEXT REFERENCES orders(order_id),
    product_id    TEXT REFERENCES products(product_id),
    quantity      INTEGER,
    unit_price    REAL,
    return_flag   INTEGER DEFAULT 0,  -- 1 = returned
    return_date   TEXT                -- NULL if not returned
);

-- indexes to speed up common joins
CREATE INDEX IF NOT EXISTS idx_orders_customer  ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_date      ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status    ON orders(status);
CREATE INDEX IF NOT EXISTS idx_items_order      ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_items_product    ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_items_return     ON order_items(return_flag);
