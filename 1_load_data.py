"""
Real Data ETL Pipeline
Transforms UCI Online Retail II dataset into the project's 4-table schema:
  customers, products, orders, order_items
Saves CSVs + SQLite DB
"""

import pandas as pd
import numpy as np
import sqlite3, os, re
from datetime import datetime

np.random.seed(42)

SRC  = "data/online_retail_II.xlsx"
DB   = "data/ecommerce.db"
RAW  = "data/raw"
os.makedirs(RAW, exist_ok=True)
os.makedirs("data/processed", exist_ok=True)

# ── 1. Load raw data ──────────────────────────────────────────
print("📥 Loading Excel sheets …")
df1 = pd.read_excel(SRC, sheet_name="Year 2009-2010")
df2 = pd.read_excel(SRC, sheet_name="Year 2010-2011")
raw = pd.concat([df1, df2], ignore_index=True)
print(f"   Raw rows: {len(raw):,}")

# ── 2. Clean ──────────────────────────────────────────────────
print("🧹 Cleaning …")

# Standardise column names
raw.columns = ["invoice","stock_code","description","quantity",
               "invoice_date","price","customer_id","country"]

# Drop rows with no customer (guest checkouts — can't do RFM)
raw = raw[raw["customer_id"].notna()].copy()
raw["customer_id"] = raw["customer_id"].astype(int).astype(str).str.zfill(5)

# Separate cancellations (Invoice starts with C) — tag as returns
raw["invoice"] = raw["invoice"].astype(str)
raw["is_cancellation"] = raw["invoice"].str.startswith("C")

# Remove service / postage / manual adjustment lines
bad_codes = {"POST","D","M","BANK CHARGES","PADS","DOT","CRUK","S","AMAZONFEE",
             "TEST001","TEST002","gift_0001","DCGSSBOY","DCGSSGIRL"}
raw = raw[~raw["stock_code"].isin(bad_codes)]
raw = raw[~raw["stock_code"].str.match(r"^[A-Za-z]+$", na=False)]  # pure-letter codes = non-product

# Remove zero/negative price (except cancellations handled below)
raw_sales   = raw[~raw["is_cancellation"] & (raw["price"] > 0) & (raw["quantity"] > 0)].copy()
raw_returns = raw[raw["is_cancellation"]].copy()

print(f"   Sales rows   : {len(raw_sales):,}")
print(f"   Return rows  : {len(raw_returns):,}")

# Fill missing descriptions from mode per stock_code
desc_map = raw_sales.groupby("stock_code")["description"].agg(
    lambda x: x.mode().iloc[0] if not x.mode().empty else "Unknown"
)
raw_sales["description"] = raw_sales.apply(
    lambda r: desc_map.get(r["stock_code"], r["description"]) 
              if pd.isna(r["description"]) else r["description"], axis=1
)

# Map invoice_date to date only
raw_sales["order_date"] = pd.to_datetime(raw_sales["invoice_date"]).dt.date

# Compute line revenue
raw_sales["line_revenue"] = raw_sales["quantity"] * raw_sales["price"]

print(f"   Date range   : {raw_sales['order_date'].min()} → {raw_sales['order_date'].max()}")
print(f"   Countries    : {raw_sales['country'].nunique()}")
print(f"   Unique customers: {raw_sales['customer_id'].nunique():,}")


# ── 3. PRODUCTS table ─────────────────────────────────────────
print("\n📦 Building products table …")

# Category assignment based on keywords in description
def assign_category(desc):
    if pd.isna(desc): return "General", "Misc"
    d = desc.upper()
    if any(k in d for k in ["CHRISTMAS","XMAS","ADVENT"]):      return "Seasonal", "Christmas"
    if any(k in d for k in ["BIRTHDAY","PARTY","BALLOON"]):     return "Celebrations", "Party Supplies"
    if any(k in d for k in ["CANDLE","LANTERN","LIGHT","LAMP"]): return "Home & Decor", "Lighting"
    if any(k in d for k in ["BAG","TOTE","SHOPPER","SATCHEL"]): return "Fashion", "Bags"
    if any(k in d for k in ["CARD","POSTCARD","NOTEBOOK","DIARY","STICKER"]): return "Stationery", "Cards & Notes"
    if any(k in d for k in ["MUG","CUP","PLATE","BOWL","GLASS","JAR","BOTTLE"]): return "Kitchen", "Drinkware"
    if any(k in d for k in ["FRAME","PICTURE","PHOTO","ART","POSTER"]): return "Home & Decor", "Wall Art"
    if any(k in d for k in ["TOY","GAME","DOLL","TEDDY","PUPPET"]): return "Toys & Games", "Toys"
    if any(k in d for k in ["CUSHION","PILLOW","BLANKET","THROW"]): return "Home & Decor", "Soft Furnishings"
    if any(k in d for k in ["HEART","LOVE","ROSE","FLORAL","FLOWER"]): return "Gift & Novelty", "Romantic"
    if any(k in d for k in ["STORAGE","BOX","BASKET","CHEST","TIN"]): return "Home & Decor", "Storage"
    if any(k in d for k in ["SIGN","PLAQUE","VINTAGE","RETRO"]):    return "Home & Decor", "Vintage Signs"
    if any(k in d for k in ["NECKLACE","BRACELET","EARRING","RING","JEWEL"]): return "Fashion", "Jewellery"
    if any(k in d for k in ["CLOCK","WATCH"]):                      return "Home & Decor", "Clocks"
    if any(k in d for k in ["GARDEN","BIRD","PLANT","OUTDOOR"]):    return "Garden", "Outdoor"
    if any(k in d for k in ["SOAP","BATH","CREAM","LOTION"]):       return "Beauty", "Bath & Body"
    return "Gift & Novelty", "General Gifts"

# Build product table: one row per stock_code
prod = (raw_sales.groupby("stock_code")
        .agg(
            description=("description","first"),
            avg_price=("price","median"),
            min_price=("price","min"),
            max_price=("price","max"),
        )
        .reset_index()
        .rename(columns={"stock_code":"product_id","description":"name","avg_price":"unit_price"})
)

cats = prod["name"].apply(assign_category)
prod["category"]    = cats.apply(lambda x: x[0])
prod["subcategory"] = cats.apply(lambda x: x[1])
# cost_price = 55% of unit price (typical retail margin assumption)
prod["cost_price"]  = (prod["unit_price"] * 0.55).round(2)
prod["unit_price"]  = prod["unit_price"].round(2)
prod = prod[["product_id","name","category","subcategory","unit_price","cost_price"]]
prod = prod[prod["unit_price"] > 0]

print(f"   Products: {len(prod):,}")
print(f"   Categories:\n{prod['category'].value_counts().to_string()}")


# ── 4. CUSTOMERS table ────────────────────────────────────────
print("\n👥 Building customers table …")

# Country → region mapping
REGION_MAP = {
    "United Kingdom":"Europe", "EIRE":"Europe", "Germany":"Europe",
    "France":"Europe", "Netherlands":"Europe", "Spain":"Europe",
    "Belgium":"Europe", "Switzerland":"Europe", "Portugal":"Europe",
    "Italy":"Europe", "Finland":"Europe", "Sweden":"Europe",
    "Austria":"Europe", "Denmark":"Europe", "Norway":"Europe",
    "Cyprus":"Europe", "Greece":"Europe", "Poland":"Europe",
    "Malta":"Europe", "Iceland":"Europe", "Channel Islands":"Europe",
    "USA":"North America", "Canada":"North America",
    "Australia":"Asia-Pacific", "Japan":"Asia-Pacific",
    "Singapore":"Asia-Pacific", "Hong Kong":"Asia-Pacific",
    "India":"Asia-Pacific","Bahrain":"Middle East",
    "Saudi Arabia":"Middle East","Lebanon":"Middle East",
    "United Arab Emirates":"Middle East",
    "Brazil":"Latin America","RSA":"Africa","Nigeria":"Africa",
}

cust_stats = raw_sales.groupby("customer_id").agg(
    country=("country","first"),
    first_order=("order_date","min"),
    n_orders=("invoice","nunique"),
    total_spend=("line_revenue","sum"),
).reset_index()

cust_stats["region"] = cust_stats["country"].map(REGION_MAP).fillna("Other")
cust_stats["signup_date"] = pd.to_datetime(cust_stats["first_order"])

# Assign age groups and gender randomly (not in source data)
np.random.seed(42)
n = len(cust_stats)
cust_stats["age_group"] = np.random.choice(
    ["18-24","25-34","35-44","45-54","55+"],
    p=[0.10, 0.32, 0.28, 0.18, 0.12], size=n
)
cust_stats["gender"] = np.random.choice(
    ["Female","Male","Other"], p=[0.62, 0.35, 0.03], size=n
)

# Use city = country (no city in source data)
cust_stats["city"] = cust_stats["country"]

customers = cust_stats[["customer_id","city","region","signup_date",
                          "age_group","gender"]].copy()
customers["name"]  = customers["customer_id"].apply(lambda x: f"Customer {x}")
customers["email"] = customers["customer_id"].apply(
    lambda x: f"customer{x}@retail.example.com"
)
customers["signup_date"] = customers["signup_date"].dt.strftime("%Y-%m-%d")

customers = customers[["customer_id","name","email","city","region",
                        "signup_date","age_group","gender"]]
print(f"   Customers: {len(customers):,}")
print(f"   Regions:\n{customers['region'].value_counts().to_string()}")


# ── 5. ORDERS table ───────────────────────────────────────────
print("\n📋 Building orders table …")

valid_products = set(prod["product_id"])
valid_customers = set(customers["customer_id"])

# Each invoice = one order
orders_raw = (raw_sales[raw_sales["customer_id"].isin(valid_customers)]
              .groupby("invoice")
              .agg(
                  customer_id=("customer_id","first"),
                  order_date=("order_date","first"),
                  country=("country","first"),
              )
              .reset_index()
              .rename(columns={"invoice":"order_id"})
)

# Map country to region for shipping_region
orders_raw["shipping_region"] = orders_raw["country"].map(REGION_MAP).fillna("Other")

# Assign channel and payment method
np.random.seed(42)
n = len(orders_raw)
orders_raw["channel"] = np.random.choice(
    ["Website","Mobile App","Email Campaign","Social Media","Referral"],
    p=[0.45, 0.28, 0.14, 0.09, 0.04], size=n
)
orders_raw["payment_method"] = np.random.choice(
    ["Credit Card","Debit Card","PayPal","Bank Transfer","Gift Card"],
    p=[0.38, 0.25, 0.22, 0.10, 0.05], size=n
)
orders_raw["discount_pct"] = np.random.choice(
    [0, 0.05, 0.10, 0.15, 0.20],
    p=[0.55, 0.18, 0.14, 0.08, 0.05], size=n
)
orders_raw["status"] = "Delivered"

orders = orders_raw[["order_id","customer_id","order_date","status",
                      "channel","payment_method","shipping_region","discount_pct"]]
orders["order_date"] = orders["order_date"].astype(str)
print(f"   Orders: {len(orders):,}")


# ── 6. ORDER_ITEMS table ──────────────────────────────────────
print("\n🛒 Building order_items table …")

# Match returns: find original invoice for each cancellation
return_invoice_map = {}
for _, row in raw_returns.iterrows():
    orig = str(row["invoice"]).lstrip("C")  # e.g. "C536379" → "536379"
    return_invoice_map[orig] = return_invoice_map.get(orig, 0) + 1

items = (raw_sales[
    raw_sales["stock_code"].isin(valid_products) &
    raw_sales["customer_id"].isin(valid_customers)
].copy())

items = items.rename(columns={
    "invoice":"order_id",
    "stock_code":"product_id",
    "quantity":"quantity",
    "price":"unit_price",
})

# Add return flag: ~8% baseline + higher for cancelled orders
items["return_flag"] = 0
items["return_date"] = None

# Mark returns based on cancellation matches
cancelled_orders = set(raw_returns["invoice"].str.lstrip("C"))
mask_cancelled = items["order_id"].isin(cancelled_orders)
items.loc[mask_cancelled, "return_flag"] = 1

# Additional random ~5% of non-cancelled items as returns
non_cancelled_idx = items[~mask_cancelled].index
n_extra_returns = int(len(non_cancelled_idx) * 0.05)
extra_return_idx = np.random.choice(non_cancelled_idx, size=n_extra_returns, replace=False)
items.loc[extra_return_idx, "return_flag"] = 1

# Assign return dates (7-30 days after order for returns)
order_dates = items.set_index("order_id")["order_date"].to_dict()
def get_return_date(row):
    if row["return_flag"] == 0:
        return None
    od = str(order_dates.get(row["order_id"], "2010-01-01"))
    try:
        base = pd.Timestamp(od)
        rd   = base + pd.Timedelta(days=int(np.random.randint(7, 31)))
        return rd.strftime("%Y-%m-%d")
    except:
        return None

items["return_date"] = items.apply(get_return_date, axis=1)

# Reset index → order_item_id
items = items.reset_index(drop=True)
items.index = items.index + 1
items["order_item_id"] = items.index.map(lambda i: f"OI{i:08d}")

items = items[["order_item_id","order_id","product_id","quantity",
               "unit_price","return_flag","return_date"]]

ret_pct = items["return_flag"].mean() * 100
print(f"   Order items  : {len(items):,}")
print(f"   Return rate  : {ret_pct:.1f}%")


# ── 7. Validate ───────────────────────────────────────────────
print("\n📊 Validation:")
print(f"   Customers  : {len(customers):,}")
print(f"   Products   : {len(prod):,}")
print(f"   Orders     : {len(orders):,}")
print(f"   Order items: {len(items):,}")
print(f"   Date range : {orders['order_date'].min()} → {orders['order_date'].max()}")
total_rev = (items["quantity"] * items["unit_price"]).sum()
print(f"   Total revenue (gross): £{total_rev:,.0f}")


# ── 8. Save CSVs ──────────────────────────────────────────────
print("\n💾 Saving CSVs …")
customers.to_csv(f"{RAW}/customers.csv", index=False)
prod.to_csv(f"{RAW}/products.csv", index=False)
orders.to_csv(f"{RAW}/orders.csv", index=False)
items.to_csv(f"{RAW}/order_items.csv", index=False)
print("   ✓ data/raw/customers.csv")
print("   ✓ data/raw/products.csv")
print("   ✓ data/raw/orders.csv")
print("   ✓ data/raw/order_items.csv")


# ── 9. Save SQLite ────────────────────────────────────────────
print("\n🗄️  Writing SQLite …")
conn = sqlite3.connect(DB)
customers.to_sql("customers",   conn, if_exists="replace", index=False)
prod.to_sql("products",         conn, if_exists="replace", index=False)
orders.to_sql("orders",         conn, if_exists="replace", index=False)
items.to_sql("order_items",     conn, if_exists="replace", index=False)
conn.executescript("""
    CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
    CREATE INDEX IF NOT EXISTS idx_orders_date     ON orders(order_date);
    CREATE INDEX IF NOT EXISTS idx_orders_status   ON orders(status);
    CREATE INDEX IF NOT EXISTS idx_items_order     ON order_items(order_id);
    CREATE INDEX IF NOT EXISTS idx_items_product   ON order_items(product_id);
    CREATE INDEX IF NOT EXISTS idx_items_return    ON order_items(return_flag);
""")
conn.commit()
for tbl in ["customers","products","orders","order_items"]:
    cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f"   ✓ {tbl}: {cnt:,} rows")
conn.close()

print("\n✅ Real data ETL complete!")
