"""
etl/pipeline.py

Weekly ETL pipeline for the e-commerce analytics project.
Reads raw CSVs, validates them, runs all SQL views,
exports processed CSVs, and logs what happened.

Can be run manually:  python etl/pipeline.py
Or scheduled weekly:  python etl/pipeline.py --schedule

Replaces ~6 hours/week of manual Excel work.
"""

import sqlite3
import pandas as pd
import os
import sys
import logging
import time
import argparse
from datetime import datetime

# optional: 'pip install schedule' for the weekly scheduler
try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False


# ── config ────────────────────────────────────────────────────

DB_PATH   = "data/ecommerce.db"
RAW_DIR   = "data/raw"
OUT_DIR   = "data/processed"
SQL_DIR   = "sql"
LOG_FILE  = "etl/etl.log"

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs("etl", exist_ok=True)


# ── logging ───────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────

def load_sql_file(path):
    with open(path) as f:
        return f.read()


def run_query(conn, label, sql, outfile):
    try:
        df = pd.read_sql_query(sql, conn)
        df.to_csv(f"{OUT_DIR}/{outfile}", index=False)
        log.info(f"  {label:40s} {len(df):>7,} rows  →  {outfile}")
        return df
    except Exception as e:
        log.error(f"  FAILED: {label} — {e}")
        return None


# ── validation ────────────────────────────────────────────────

def validate_raw_data(conn):
    """
    Basic data quality checks before running the pipeline.
    Raises ValueError if something looks wrong.
    """
    log.info("Validating raw data...")

    checks = {
        "customers":   "SELECT COUNT(*) FROM customers",
        "products":    "SELECT COUNT(*) FROM products",
        "orders":      "SELECT COUNT(*) FROM orders",
        "order_items": "SELECT COUNT(*) FROM order_items",
    }

    for table, sql in checks.items():
        count = conn.execute(sql).fetchone()[0]
        if count == 0:
            raise ValueError(f"Table '{table}' is empty. Run 1_load_data.py first.")
        log.info(f"  {table}: {count:,} rows  OK")

    # check for nulls in critical columns
    null_customers = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE customer_id IS NULL"
    ).fetchone()[0]
    if null_customers > 0:
        log.warning(f"  Found {null_customers} orders with NULL customer_id")

    # check date range makes sense
    date_range = conn.execute(
        "SELECT MIN(order_date), MAX(order_date) FROM orders"
    ).fetchone()
    log.info(f"  Order date range: {date_range[0]} to {date_range[1]}")


# ── SQL views ─────────────────────────────────────────────────

def create_views(conn):
    """
    Load and execute all SQL files to create views in the database.
    Safe to re-run — uses CREATE VIEW IF NOT EXISTS everywhere.
    """
    sql_files = [
        "schema.sql",
        "kpi_queries.sql",
        "cohort_analysis.sql",
        "rfm_segmentation.sql",
    ]

    log.info("Creating SQL views...")
    for fname in sql_files:
        fpath = os.path.join(SQL_DIR, fname)
        if not os.path.exists(fpath):
            log.warning(f"  SQL file not found: {fpath}")
            continue
        sql = load_sql_file(fpath)
        try:
            conn.executescript(sql)
            log.info(f"  Loaded: {fname}")
        except Exception as e:
            log.error(f"  Error in {fname}: {e}")

    conn.commit()


# ── export queries ────────────────────────────────────────────

EXPORTS = [
    # (label, sql_or_view, output_filename)
    ("Monthly revenue",      "SELECT * FROM v_monthly_revenue",                    "monthly_revenue.csv"),
    ("KPI summary",          "SELECT * FROM v_kpi_summary",                        "kpi_summary.csv"),
    ("Region KPIs",          "SELECT * FROM v_region_kpis",                        "region_performance.csv"),
    ("Top 50 products",      "SELECT * FROM v_product_kpis LIMIT 50",              "top_products.csv"),
    ("Channel performance",  "SELECT * FROM v_channel_kpis",                       "channel_performance.csv"),
    ("Category performance",
        """SELECT p.category, p.subcategory,
               COUNT(DISTINCT o.order_id) AS orders,
               SUM(oi.quantity) AS units_sold,
               ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue,
               ROUND(SUM(oi.return_flag) * 100.0 / COUNT(*), 2) AS return_rate_pct,
               ROUND(SUM(oi.quantity*(oi.unit_price-p.cost_price))*100.0
                     /SUM(oi.quantity*oi.unit_price),2) AS margin_pct
           FROM order_items oi
           JOIN products p ON oi.product_id=p.product_id
           JOIN orders o ON oi.order_id=o.order_id
           WHERE o.status='Delivered'
           GROUP BY p.category, p.subcategory
           ORDER BY revenue DESC""",
        "category_performance.csv"),
    ("Payment methods",
        """SELECT o.payment_method,
               COUNT(DISTINCT o.order_id) AS orders,
               ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue
           FROM orders o
           JOIN order_items oi ON o.order_id=oi.order_id
           WHERE o.status='Delivered'
           GROUP BY o.payment_method ORDER BY revenue DESC""",
        "payment_methods.csv"),
    ("RFM segments",         "SELECT * FROM v_rfm_segments",                       "rfm_segments.csv"),
    ("RFM summary",          "SELECT * FROM v_rfm_summary",                        "rfm_summary.csv"),
    ("Cohort retention",     "SELECT * FROM v_cohort_retention",                   "cohort_retention.csv"),
    ("Avg retention",        "SELECT * FROM v_avg_retention",                      "avg_retention.csv"),
    ("New vs returning",     "SELECT * FROM v_new_vs_returning",                   "new_vs_returning.csv"),
    ("Churn risk",           "SELECT * FROM v_churn_risk",                         "churn_risk.csv"),
    ("Customer CLV",         "SELECT * FROM v_customer_clv",                       "customer_clv.csv"),
]


def export_all(conn):
    log.info("Exporting processed data...")
    results = {}
    for label, sql, outfile in EXPORTS:
        df = run_query(conn, label, sql, outfile)
        if df is not None:
            results[outfile] = len(df)

    # cohort pivot (wide format — needed for heatmap)
    try:
        cohort = pd.read_csv(f"{OUT_DIR}/cohort_retention.csv")
        pivot = cohort.pivot_table(
            index="cohort_month",
            columns="period",
            values="retention_pct"
        ).rename(columns=lambda c: f"M{int(c):02d}")
        pivot.to_csv(f"{OUT_DIR}/cohort_pivot.csv")
        log.info(f"  {'Cohort pivot (wide)':40s}  shape {pivot.shape}  →  cohort_pivot.csv")
    except Exception as e:
        log.error(f"  Could not build cohort pivot: {e}")

    return results


# ── main pipeline ─────────────────────────────────────────────

def run_pipeline():
    start = time.time()
    log.info("=" * 60)
    log.info(f"ETL pipeline started — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    if not os.path.exists(DB_PATH):
        log.error(f"Database not found at {DB_PATH}. Run 1_load_data.py first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    try:
        validate_raw_data(conn)
        create_views(conn)
        results = export_all(conn)

        elapsed = time.time() - start
        log.info("-" * 60)
        log.info(f"Pipeline finished in {elapsed:.1f}s")
        log.info(f"Exported {len(results)} files to {OUT_DIR}/")

        # print a quick summary of key numbers
        kpi_path = f"{OUT_DIR}/kpi_summary.csv"
        if os.path.exists(kpi_path):
            kpi = pd.read_csv(kpi_path).iloc[0]
            log.info(f"  Revenue: £{kpi['total_revenue']:,.0f}")
            log.info(f"  Orders:  {kpi['total_orders']:,}")
            log.info(f"  AOV:     £{kpi['aov']:,.2f}")
            log.info(f"  Margin:  {kpi['gross_margin_pct']:.1f}%")

    finally:
        conn.close()


# ── scheduler (optional weekly run) ──────────────────────────

def run_scheduled():
    if not SCHEDULE_AVAILABLE:
        print("Install 'schedule' to use this: pip install schedule")
        sys.exit(1)

    print("Scheduler active — pipeline will run every Monday at 08:00")
    print("Press Ctrl+C to stop.\n")

    schedule.every().monday.at("08:00").do(run_pipeline)

    # also run immediately on start
    run_pipeline()

    while True:
        schedule.run_pending()
        time.sleep(60)


# ── entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E-commerce ETL pipeline")
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run on a weekly schedule (every Monday 08:00)"
    )
    args = parser.parse_args()

    if args.schedule:
        run_scheduled()
    else:
        run_pipeline()
