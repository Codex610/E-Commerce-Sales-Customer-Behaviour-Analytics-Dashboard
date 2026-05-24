"""
01_eda_and_rfm.py
-----------------
Exploratory data analysis on the UCI Online Retail II dataset.
Generates 13 charts saved as HTML files in the charts/ folder.
Open any chart file in your browser to view it.

What this covers:
  - Revenue trends and seasonality
  - Cohort retention analysis
  - RFM customer segmentation
  - Funnel analysis
  - Regional and category breakdown
  - CLV distribution
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import os

os.makedirs("charts", exist_ok=True)

# colours for all charts
BG     = "#0f1117"   # page background
PANEL  = "#1a1d2e"   # chart background
PURPLE = "#7c3aed"
TEAL   = "#06b6d4"
GREEN  = "#10b981"
RED    = "#ef4444"
AMBER  = "#f59e0b"
COLORS = [PURPLE, TEAL, GREEN, AMBER, RED, "#ec4899", "#8b5cf6", "#14b8a6", "#f97316"]


def dark(fig, title, height=380, xangle=0):
    """Apply dark theme to any chart. Keep it simple - same style everywhere."""
    fig.update_layout(
        title=title,
        paper_bgcolor=BG,
        plot_bgcolor=PANEL,
        font=dict(color="#e2e8f0", family="Arial", size=12),
        margin=dict(t=60, b=50, l=60, r=40),
        height=height,
    )
    fig.update_xaxes(gridcolor="#2d3748", tickangle=xangle)
    fig.update_yaxes(gridcolor="#2d3748")
    return fig


def save(fig, filename):
    fig.write_html(f"charts/{filename}", include_plotlyjs="cdn")
    print(f"  saved: {filename}")


# ── load data ──────────────────────────────────────────────────────────────────

print("Loading data...")

orders   = pd.read_csv("data/raw/orders.csv", parse_dates=["order_date"])
items    = pd.read_csv("data/raw/order_items.csv")
products = pd.read_csv("data/raw/products.csv")
customers = pd.read_csv("data/raw/customers.csv")

mr       = pd.read_csv("data/processed/monthly_revenue.csv")
rfm      = pd.read_csv("data/processed/rfm_segments.csv")
rfm_sum  = pd.read_csv("data/processed/rfm_summary.csv")
cohort   = pd.read_csv("data/processed/cohort_pivot.csv", index_col=0)
avg_ret  = pd.read_csv("data/processed/avg_retention.csv")
churn    = pd.read_csv("data/processed/churn_risk.csv")
cat_perf = pd.read_csv("data/processed/category_performance.csv")
reg_perf = pd.read_csv("data/processed/region_performance.csv")
nvr      = pd.read_csv("data/processed/new_vs_returning.csv")
pay      = pd.read_csv("data/processed/payment_methods.csv")
chan     = pd.read_csv("data/processed/channel_performance.csv")
clv      = pd.read_csv("data/processed/customer_clv.csv")

items["line_revenue"] = items["quantity"] * items["unit_price"]

print(f"  {len(orders):,} orders  |  {len(items):,} items  |  {len(customers):,} customers  |  {len(products):,} products")
print(f"  Date range: {orders['order_date'].min().date()} to {orders['order_date'].max().date()}")

print("\nBasic checks...")
print(f"  Total revenue:   £{items['line_revenue'].sum():,.0f}")
print(f"  Avg basket size: {items.groupby('order_id')['quantity'].sum().mean():.1f} items")
print(f"  Return rate:     {items['return_flag'].mean()*100:.1f}%")
print(f"  Top country:     {customers['city'].value_counts().index[0]}")


# ── chart 1: monthly revenue ───────────────────────────────────────────────────

print("\nGenerating charts...")

mr["mom_growth"] = mr["revenue"].pct_change() * 100

fig = make_subplots(specs=[[{"secondary_y": True}]])

fig.add_trace(
    go.Bar(x=mr["month"], y=mr["revenue"], name="Revenue",
           marker_color=PURPLE, opacity=0.85),
    secondary_y=False
)
fig.add_trace(
    go.Scatter(x=mr["month"], y=mr["mom_growth"], name="MoM Growth %",
               mode="lines+markers", line=dict(color=TEAL, width=2.5), marker=dict(size=6)),
    secondary_y=True
)
fig.add_hline(y=0, line_dash="dot", line_color="#4a5568", secondary_y=True)

fig.update_layout(
    title="Monthly Revenue & Month-over-Month Growth",
    paper_bgcolor=BG, plot_bgcolor=PANEL,
    font=dict(color="#e2e8f0", family="Arial", size=12),
    margin=dict(t=60, b=50, l=60, r=40),
    height=380,
    legend=dict(bgcolor=PANEL),
    bargap=0.2,
)
fig.update_xaxes(gridcolor="#2d3748", tickangle=-45)
fig.update_yaxes(gridcolor="#2d3748", title_text="Revenue (£)", secondary_y=False)
fig.update_yaxes(gridcolor="#1a1d2e", title_text="MoM Growth %", secondary_y=True)

save(fig, "01_monthly_revenue.html")


# ── chart 2: cohort retention heatmap ─────────────────────────────────────────

z    = cohort.values.tolist()
x    = cohort.columns.tolist()
y    = cohort.index.tolist()

# build cell labels like "35%"
text = [
    [f"{v:.0f}%" if not (isinstance(v, float) and np.isnan(v)) else "" for v in row]
    for row in z
]

fig = go.Figure(go.Heatmap(
    z=z, x=x, y=y,
    text=text, texttemplate="%{text}", textfont=dict(size=9, color="white"),
    colorscale=[[0, "#1a1d2e"], [0.3, "#312e81"], [0.6, "#4f46e5"], [1.0, "#ddd6fe"]],
    colorbar=dict(title="Retention %", tickfont=dict(color="#e2e8f0")),
))

fig.update_layout(
    title="Cohort Retention — % of Cohort Still Purchasing Each Month",
    paper_bgcolor=BG, plot_bgcolor=BG,
    font=dict(color="#e2e8f0", family="Arial"),
    margin=dict(t=70, b=70, l=110, r=40),
    height=520,
)
fig.update_xaxes(title="Months Since First Purchase")
fig.update_yaxes(title="Acquisition Cohort", autorange="reversed")

save(fig, "02_cohort_heatmap.html")


# ── chart 3: average retention curve ──────────────────────────────────────────

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=avg_ret["period"], y=avg_ret["avg_pct"],
    name="Average retention",
    mode="lines+markers",
    line=dict(color=PURPLE, width=3), marker=dict(size=8),
    fill="tozeroy", fillcolor="rgba(124,58,237,0.12)",
))
fig.add_trace(go.Scatter(
    x=avg_ret["period"], y=avg_ret["max_pct"],
    name="Best cohort",
    line=dict(color=GREEN, width=1.5, dash="dash"),
))
fig.add_trace(go.Scatter(
    x=avg_ret["period"], y=avg_ret["min_pct"],
    name="Worst cohort",
    line=dict(color=RED, width=1.5, dash="dash"),
))

fig = dark(fig, "Average Cohort Retention Curve (M0 – M11)", height=360)
fig.update_xaxes(
    title="Months Since First Purchase",
    tickvals=list(range(12)),
    ticktext=[f"M{i}" for i in range(12)],
)
fig.update_yaxes(title="Retention (%)")
fig.update_layout(legend=dict(bgcolor=PANEL))

save(fig, "03_retention_curve.html")


# ── chart 4: RFM treemap ───────────────────────────────────────────────────────

fig = px.treemap(
    rfm_sum,
    path=["segment"],
    values="total_revenue",
    color="avg_spend",
    color_continuous_scale=["#1a1d2e", "#4f46e5", "#a78bfa"],
    custom_data=["customers", "avg_orders", "avg_spend"],
)

fig.update_traces(
    hovertemplate=(
        "<b>%{label}</b><br>"
        "Revenue: £%{value:,.0f}<br>"
        "Customers: %{customdata[0]:,}<br>"
        "Avg orders: %{customdata[1]:.1f}<br>"
        "Avg spend: £%{customdata[2]:,.0f}<extra></extra>"
    ),
    textfont=dict(size=13),
)
fig.update_layout(
    title="RFM Segments — Revenue by Customer Segment",
    paper_bgcolor=BG,
    font=dict(color="#e2e8f0", family="Arial"),
    margin=dict(t=60, b=10, l=10, r=10),
    height=420,
    coloraxis_colorbar=dict(title="Avg Spend (£)", tickfont=dict(color="#e2e8f0")),
)

save(fig, "04_rfm_treemap.html")


# ── chart 5: RFM segment bar charts ───────────────────────────────────────────

fig = make_subplots(
    rows=1, cols=2,
    subplot_titles=["Customers per Segment", "Revenue per Segment (£)"],
    horizontal_spacing=0.12,
)

by_cust = rfm_sum.sort_values("customers", ascending=True)
fig.add_trace(
    go.Bar(
        y=by_cust["segment"], x=by_cust["customers"], orientation="h",
        marker_color=COLORS[:len(by_cust)],
        text=by_cust["customers"].apply(lambda v: f"{v:,}"), textposition="outside",
    ),
    row=1, col=1,
)

by_rev = rfm_sum.sort_values("total_revenue", ascending=True)
fig.add_trace(
    go.Bar(
        y=by_rev["segment"], x=by_rev["total_revenue"], orientation="h",
        marker_color=COLORS[:len(by_rev)],
        text=by_rev["total_revenue"].apply(lambda v: f"£{v:,.0f}"), textposition="outside",
    ),
    row=1, col=2,
)

fig.update_layout(
    title="RFM Segment Analysis",
    paper_bgcolor=BG, plot_bgcolor=PANEL,
    font=dict(color="#e2e8f0", family="Arial", size=12),
    margin=dict(t=80, b=40, l=170, r=100),
    height=420,
    showlegend=False,
)
fig.update_xaxes(gridcolor="#2d3748")
fig.update_yaxes(gridcolor="#2d3748")

save(fig, "05_rfm_segments.html")


# ── chart 6: RFM scatter ───────────────────────────────────────────────────────

sample = rfm.sample(min(4000, len(rfm)), random_state=42)

fig = px.scatter(
    sample,
    x="recency_days", y="monetary",
    color="f_score", size="frequency",
    color_continuous_scale=[RED, AMBER, GREEN, TEAL, PURPLE],
    hover_data={"customer_id": True, "recency_days": True, "frequency": True, "monetary": ":.0f"},
    labels={
        "recency_days": "Days Since Last Order",
        "monetary": "Total Spend (£)",
        "f_score": "Frequency Score",
    },
)

fig = dark(fig, "Recency vs Spend — Where Each Customer Stands (4,000 sample)", height=420)
fig.update_layout(
    coloraxis_colorbar=dict(title="Freq Score", tickfont=dict(color="#e2e8f0"))
)

save(fig, "06_rfm_scatter.html")


# ── chart 7: churn donut + by region ──────────────────────────────────────────

fig = make_subplots(
    rows=1, cols=2,
    specs=[[{"type": "pie"}, {"type": "xy"}]],
    subplot_titles=["Overall Churn Status", "Churn by Region"],
    horizontal_spacing=0.08,
)

counts = churn["churn_status"].value_counts().reset_index()
counts.columns = ["status", "count"]
cmap = {"Active": GREEN, "At Risk": AMBER, "Churned": RED}

fig.add_trace(
    go.Pie(
        labels=counts["status"], values=counts["count"],
        hole=0.55,
        marker_colors=[cmap.get(s, PURPLE) for s in counts["status"]],
        textinfo="label+percent",
    ),
    row=1, col=1,
)

by_region = churn.groupby(["churn_status", "region"]).size().reset_index(name="count")
for status, color in [("Active", GREEN), ("At Risk", AMBER), ("Churned", RED)]:
    d = by_region[by_region["churn_status"] == status]
    fig.add_trace(
        go.Bar(x=d["region"], y=d["count"], name=status, marker_color=color, opacity=0.85),
        row=1, col=2,
    )

fig.update_layout(
    title="Customer Churn Analysis",
    paper_bgcolor=BG, plot_bgcolor=PANEL,
    font=dict(color="#e2e8f0", family="Arial", size=12),
    margin=dict(t=70, b=50, l=50, r=30),
    height=380,
    barmode="stack",
    legend=dict(bgcolor=PANEL),
)
fig.update_xaxes(gridcolor="#2d3748", row=1, col=2)
fig.update_yaxes(gridcolor="#2d3748", row=1, col=2)

save(fig, "07_churn_analysis.html")


# ── chart 8: order funnel ──────────────────────────────────────────────────────

total_customers  = len(customers)
placed_order     = orders["customer_id"].nunique()
delivered        = orders[orders["status"] == "Delivered"]["order_id"].nunique()
kept_orders      = (
    items.groupby("order_id")["return_flag"].max()
    .reset_index()
    .query("return_flag == 0")
    .shape[0]
)

fig = go.Figure(go.Funnel(
    y=["Registered Customers", "Placed an Order", "Order Delivered", "Kept (No Returns)"],
    x=[total_customers, placed_order, delivered, kept_orders],
    textposition="inside",
    textinfo="value+percent initial",
    textfont=dict(size=13, color="white"),
    marker=dict(color=[PURPLE, "#6d28d9", "#5b21b6", "#4c1d95"]),
    connector=dict(line=dict(color="#4a5568", dash="dot", width=2)),
))

fig.update_layout(
    title="Order Funnel — From Registration to Successful Purchase",
    paper_bgcolor=BG, plot_bgcolor=BG,
    font=dict(color="#e2e8f0", family="Arial"),
    margin=dict(t=70, b=40, l=230, r=40),
    height=360,
)

save(fig, "08_funnel.html")


# ── chart 9: category sunburst ─────────────────────────────────────────────────

fig = px.sunburst(
    cat_perf,
    path=["category", "subcategory"],
    values="revenue",
    color="margin_pct",
    color_continuous_scale=["#1a1d2e", "#4f46e5", "#10b981"],
)

fig.update_traces(
    hovertemplate="<b>%{label}</b><br>Revenue: £%{value:,.0f}<br>Margin: %{color:.1f}%<extra></extra>",
)
fig.update_layout(
    title="Revenue by Category & Subcategory  (colour = margin %)",
    paper_bgcolor=BG,
    font=dict(color="#e2e8f0", family="Arial"),
    margin=dict(t=60, b=10, l=10, r=10),
    height=480,
    coloraxis_colorbar=dict(title="Margin %", tickfont=dict(color="#e2e8f0")),
)

save(fig, "09_category_sunburst.html")


# ── chart 10: regional performance 2×2 ────────────────────────────────────────

fig = make_subplots(
    rows=2, cols=2,
    subplot_titles=["Revenue (£)", "Avg Order Value (£)", "Return Rate (%)", "Gross Margin (%)"],
    vertical_spacing=0.16,
    horizontal_spacing=0.10,
)

metrics = [
    (1, 1, "revenue",         lambda v: f"£{v:,.0f}"),
    (1, 2, "aov",             lambda v: f"£{v:,.0f}"),
    (2, 1, "return_rate_pct", lambda v: f"{v:.1f}%"),
    (2, 2, "margin_pct",      lambda v: f"{v:.1f}%"),
]

for row, col, col_name, fmt in metrics:
    vals = reg_perf[col_name]

    # colour return rate red/amber/green based on threshold
    if col_name == "return_rate_pct":
        bar_colors = [RED if v > 8 else AMBER if v > 6 else GREEN for v in vals]
    else:
        bar_colors = COLORS[:len(reg_perf)]

    fig.add_trace(
        go.Bar(
            x=reg_perf["region"], y=vals,
            marker_color=bar_colors,
            text=[fmt(v) for v in vals], textposition="outside",
            showlegend=False,
        ),
        row=row, col=col,
    )

    if col_name == "return_rate_pct":
        fig.add_hline(y=8, line_dash="dot", line_color=RED,
                      annotation_text="8% threshold",
                      annotation_font_color=RED, row=row, col=col)

fig.update_layout(
    title="Regional Performance Dashboard",
    paper_bgcolor=BG, plot_bgcolor=PANEL,
    font=dict(color="#e2e8f0", family="Arial", size=12),
    margin=dict(t=80, b=50, l=50, r=40),
    height=560,
)
fig.update_xaxes(gridcolor="#2d3748", tickangle=-20)
fig.update_yaxes(gridcolor="#2d3748")

save(fig, "10_regional_performance.html")


# ── chart 11: new vs returning customers ──────────────────────────────────────

fig = go.Figure()

for ctype, color in [("New", GREEN), ("Returning", PURPLE)]:
    d = nvr[nvr["customer_type"] == ctype]
    fig.add_trace(go.Bar(
        x=d["month"], y=d["customers"],
        name=ctype, marker_color=color, opacity=0.85,
    ))

fig.update_layout(
    title="New vs Returning Customers per Month",
    paper_bgcolor=BG, plot_bgcolor=PANEL,
    font=dict(color="#e2e8f0", family="Arial", size=12),
    margin=dict(t=60, b=50, l=60, r=40),
    height=360,
    barmode="stack",
    legend=dict(bgcolor=PANEL),
    bargap=0.2,
)
fig.update_xaxes(gridcolor="#2d3748", tickangle=-45)
fig.update_yaxes(gridcolor="#2d3748", title_text="Customers")

save(fig, "11_new_vs_returning.html")


# ── chart 12: CLV distribution by segment ─────────────────────────────────────

clv_rfm = clv.merge(rfm[["customer_id", "segment"]], on="customer_id", how="left")

# remove top 3% outliers so the chart is readable
cap = clv_rfm["total_spend"].quantile(0.97)
clv_rfm = clv_rfm[clv_rfm["total_spend"] <= cap]

seg_order = rfm_sum.sort_values("total_revenue", ascending=False)["segment"].tolist()

fig = go.Figure()
for i, seg in enumerate(seg_order):
    d = clv_rfm[clv_rfm["segment"] == seg]["total_spend"]
    if len(d) == 0:
        continue
    fig.add_trace(go.Box(
        y=d, name=seg,
        marker_color=COLORS[i % len(COLORS)],
        boxmean="sd",
        showlegend=False,
    ))

fig.update_layout(
    title="Total Spend Distribution by RFM Segment",
    paper_bgcolor=BG, plot_bgcolor=PANEL,
    font=dict(color="#e2e8f0", family="Arial", size=12),
    margin=dict(t=60, b=50, l=60, r=40),
    height=400,
)
fig.update_xaxes(gridcolor="#2d3748", tickangle=-25)
fig.update_yaxes(gridcolor="#2d3748", title_text="Total Spend (£)")

save(fig, "12_clv_by_segment.html")


# ── chart 13: payment method and channel mix ───────────────────────────────────

fig = make_subplots(
    rows=1, cols=2,
    specs=[[{"type": "pie"}, {"type": "pie"}]],
    subplot_titles=["Revenue by Payment Method", "Revenue by Channel"],
)

fig.add_trace(
    go.Pie(labels=pay["payment_method"], values=pay["revenue"],
           hole=0.48, marker_colors=COLORS, textinfo="label+percent"),
    row=1, col=1,
)
fig.add_trace(
    go.Pie(labels=chan["channel"], values=chan["revenue"],
           hole=0.48, marker_colors=COLORS[5:], textinfo="label+percent"),
    row=1, col=2,
)

fig.update_layout(
    title="Revenue Mix — Payment Methods & Channels",
    paper_bgcolor=BG,
    font=dict(color="#e2e8f0", family="Arial"),
    margin=dict(t=70, b=20, l=20, r=20),
    height=380,
)

save(fig, "13_payment_channel.html")


# ── summary ────────────────────────────────────────────────────────────────────

kpi = pd.read_csv("data/processed/kpi_summary.csv").iloc[0]
churn_dist = churn["churn_status"].value_counts()
champ = rfm_sum[rfm_sum["segment"] == "Champions"].iloc[0]

print(f"\nAll charts saved to charts/\n")
print("Key numbers from the dataset:")
print(f"  Total revenue    : £{kpi['total_revenue']:,.0f}")
print(f"  Total orders     : {kpi['total_orders']:,.0f}")
print(f"  Avg order value  : £{kpi['aov']:,.2f}")
print(f"  Gross margin     : {kpi['gross_margin_pct']:.1f}%")
print(f"  Return rate      : {kpi['return_rate_pct']:.1f}%")
print(f"  Active customers : {churn_dist.get('Active', 0):,}")
print(f"  At-risk          : {churn_dist.get('At Risk', 0):,}")
print(f"  Churned          : {churn_dist.get('Churned', 0):,}")
print(f"  Champions        : {champ['customers']:,} → £{champ['total_revenue']:,.0f} ({champ['total_revenue']/kpi['total_revenue']*100:.0f}% of revenue)")
print("\nRun notebooks/02_ab_testing.py next.")
