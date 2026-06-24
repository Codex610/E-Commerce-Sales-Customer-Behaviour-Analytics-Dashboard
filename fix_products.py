import pandas as pd

products = pd.read_csv("data/raw/products.csv")

print(f"Before: {len(products)} rows")
print(f"Nulls in product_id: {products['product_id'].isna().sum()}")

# remove nulls and empty values
products = products[products["product_id"].notna()]
products = products[products["product_id"].str.strip() != ""]

# remove duplicates
products = products.drop_duplicates(subset="product_id")

products.to_csv("data/raw/products.csv", index=False)

print(f"After: {len(products)} rows")
print(f"Nulls in product_id: {products['product_id'].isna().sum()}")
print("Done! Now re-import products.csv in Power BI.")