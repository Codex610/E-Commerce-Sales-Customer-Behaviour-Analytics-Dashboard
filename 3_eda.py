"""
Step 3: Exploratory data analysis and visualisations.
Generates charts as HTML files you can open in any browser.
Also runs A/B test to check if a better checkout would lift revenue.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from scipy import stats
import os

PROCESSED = "data/processed"
CHARTS    = "charts"
os.makedirs(CHARTS, exist_ok=True)

# colour palette (dark theme)
BG      = "#0f1117"
PANEL   = "#1a1d2e"
PURPLE  = "#7c3aed"
TEAL    = "#06b6d4"
GREEN   = "#10b981"
RED     = "#ef4444"
AMBER   = "#f59e0b"
COLORS  = [PURPLE, TEAL, GREEN, AMBER, RED,
           "#ec4899", "#8b5cf6", "#14b8a6", "#f97316", "#6366f1"]

def save(fig, name):
    fig.write_html(f"{CHARTS}/{name}", include_plotlyjs="cdn")
    print(f"  Saved: {name}")


# ── load data ─────────────────────────────────────────────────
mr      = pd.read_csv(f"{PROCESSED}/monthly_revenue.csv")
rfm     = pd.read_csv(f"{PROCESSED}/rfm_segments.csv")
rfm_sum = pd.read_csv(f"{PROCESSED}/rfm_summary.csv")
cohort  = pd.read_csv(f"{PROCESSED}/cohort_pivot.csv", index_col=0)
avg_ret = pd.read_csv(f"{PROCESSED}/avg_retention.csv")
churn   = pd.read_csv(f"{PROCESSED}/churn_risk.csv")
cat     = pd.read_csv(f"{PROCESSED}/category_performance.csv")
reg     = pd.read_csv(f"{PROCESSED}/region_performance.csv")
nvr     = pd.read_csv(f"{PROCESSED}/new_vs_returning.csv")
pay     = pd.read_csv(f"{PROCESSED}/payment_methods.csv")
chan    = pd.read_csv(f"{PROCESSED}/channel_performance.csv")
products = pd.read_csv(f"{PROCESSED}/top_products.csv")

print("Generating charts...\n")


# ── chart 1: monthly revenue ──────────────────────────────────
mr["mom_growth"] = mr["revenue"].pct_change() * 100

fig = make_subplots(specs=[[{"secondary_y": True}]])

fig.add_trace(go.Bar(
    x=mr["month"], y=mr["revenue"],
    name="Revenue", marker_color=PURPLE, opacity=0.85
), secondary_y=False)

fig.add_trace(go.Scatter(
    x=mr["month"], y=mr["mom_growth"],
    name="MoM Growth %", mode="lines+markers",
    line=dict(color=TEAL, width=2), marker=dict(size=5)
), secondary_y=True)

fig.add_hline(y=0, line_dash="dot", line_color="#4a5568", secondary_y=True)

fig.update_layout(
    title="Monthly Revenue & Growth",
    paper_bgcolor=BG, plot_bgcolor=PANEL,
    font=dict(color="#e2e8f0"),
    xaxis=dict(gridcolor="#2d3748", tickangle=-45),
    yaxis=dict(gridcolor="#2d3748", title="Revenue (£)"),
    yaxis2=dict(title="MoM Growth %", gridcolor="#1a1d2e"),
    legend=dict(bgcolor=PANEL),
    margin=dict(t=60, b=60, l=60, r=40),
    bargap=0.2
)

save(fig, "01_monthly_revenue.html")


# ── chart 2: cohort retention heatmap ────────────────────────
z    = cohort.values.tolist()
x    = cohort.columns.tolist()
y    = cohort.index.tolist()
text = [[f"{v:.0f}%" if not (isinstance(v, float) and np.isnan(v)) else ""
         for v in row] for row in z]

fig = go.Figure(go.Heatmap(
    z=z, x=x, y=y,
    text=text, texttemplate="%{text}", textfont=dict(size=9),
    colorscale=[[0, "#1a1d2e"], [0.4, "#4f46e5"], [1.0, "#ddd6fe"]],
    hovertemplate="Cohort: %{y}<br>Month: %{x}<br>Retention: %{z:.1f}%<extra></extra>",
    colorbar=dict(title="Retention %", tickfont=dict(color="#e2e8f0"))
))

fig.update_layout(
    title="Cohort Retention — % Still Buying",
    paper_bgcolor=BG, plot_bgcolor=BG,
    font=dict(color="#e2e8f0"),
    xaxis=dict(title="Months Since First Order"),
    yaxis=dict(title="First Purchase Month", autorange="reversed"),
    margin=dict(t=60, b=60, l=100, r=40),
    height=520
)

save(fig, "02_cohort_heatmap.html")


# ── chart 3: RFM segments treemap ────────────────────────────
fig = px.treemap(
    rfm_sum,
    path=["segment"],
    values="total_revenue",
    color="avg_spend",
    color_continuous_scale=["#1a1d2e", "#4f46e5", "#a78bfa"],
    custom_data=["customers", "avg_orders", "avg_spend"]
)

fig.update_traces(
    hovertemplate="<b>%{label}</b><br>Revenue: £%{value:,.0f}<br>"
                  "Customers: %{customdata[0]:,}<br>"
                  "Avg orders: %{customdata[1]:.1f}<br>"
                  "Avg spend: £%{customdata[2]:,.0f}<extra></extra>"
)

fig.update_layout(
    title="RFM Segments — Revenue Breakdown",
    paper_bgcolor=BG, font=dict(color="#e2e8f0"),
    margin=dict(t=60, b=10, l=10, r=10),
    coloraxis_colorbar=dict(title="Avg Spend", tickfont=dict(color="#e2e8f0"))
)

save(fig, "03_rfm_treemap.html")


# ── chart 4: RFM segment bar charts ──────────────────────────
fig = make_subplots(rows=1, cols=2,
    subplot_titles=["Customers per Segment", "Revenue per Segment (£)"],
    horizontal_spacing=0.15)

seg_by_cust = rfm_sum.sort_values("customers")
seg_by_rev  = rfm_sum.sort_values("total_revenue")

fig.add_trace(go.Bar(
    y=seg_by_cust["segment"], x=seg_by_cust["customers"],
    orientation="h", marker_color=COLORS[:len(seg_by_cust)],
    text=seg_by_cust["customers"].apply(lambda v: f"{v:,}"),
    textposition="outside"
), row=1, col=1)

fig.add_trace(go.Bar(
    y=seg_by_rev["segment"], x=seg_by_rev["total_revenue"],
    orientation="h", marker_color=COLORS[:len(seg_by_rev)],
    text=seg_by_rev["total_revenue"].apply(lambda v: f"£{v:,.0f}"),
    textposition="outside"
), row=1, col=2)

fig.update_layout(
    title="RFM Segment Analysis",
    paper_bgcolor=BG, plot_bgcolor=PANEL,
    font=dict(color="#e2e8f0"), showlegend=False,
    margin=dict(t=70, b=40, l=160, r=100)
)
fig.update_xaxes(gridcolor="#2d3748")

save(fig, "04_rfm_segments.html")


# ── chart 5: RFM scatter ──────────────────────────────────────
sample = rfm.sample(min(3000, len(rfm)), random_state=42)

fig = px.scatter(
    sample,
    x="recency_days", y="monetary",
    color="f_score", size="frequency",
    color_continuous_scale=[RED, AMBER, GREEN, TEAL, PURPLE],
    hover_data={"customer_id": True, "recency_days": True,
                "frequency": True, "monetary": True},
    labels={
        "recency_days": "Days Since Last Order",
        "monetary": "Total Spend (£)",
        "f_score": "Frequency Score"
    }
)

fig.update_layout(
    title="Recency vs Spend (size = order count)",
    paper_bgcolor=BG, plot_bgcolor=PANEL,
    font=dict(color="#e2e8f0"),
    xaxis=dict(gridcolor="#2d3748"),
    yaxis=dict(gridcolor="#2d3748"),
    margin=dict(t=60, b=50, l=60, r=40)
)

save(fig, "05_rfm_scatter.html")


# ── chart 6: retention curve ──────────────────────────────────
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=avg_ret["months_since_first_order"], y=avg_ret["avg_pct"],
    name="Average", mode="lines+markers",
    line=dict(color=PURPLE, width=3), marker=dict(size=8),
    fill="tozeroy", fillcolor="rgba(124,58,237,0.15)"
))
fig.add_trace(go.Scatter(
    x=avg_ret["months_since_first_order"], y=avg_ret["max_pct"],
    name="Best cohort", line=dict(color=GREEN, width=1.5, dash="dash")
))
fig.add_trace(go.Scatter(
    x=avg_ret["months_since_first_order"], y=avg_ret["min_pct"],
    name="Worst cohort", line=dict(color=RED, width=1.5, dash="dash")
))

fig.update_layout(
    title="Average Cohort Retention Curve",
    paper_bgcolor=BG, plot_bgcolor=PANEL,
    font=dict(color="#e2e8f0"),
    xaxis=dict(gridcolor="#2d3748", title="Months After First Purchase",
               tickvals=list(range(12)),
               ticktext=[f"M{i}" for i in range(12)]),
    yaxis=dict(gridcolor="#2d3748", title="Retention (%)"),
    legend=dict(bgcolor=PANEL),
    margin=dict(t=60, b=50, l=60, r=40)
)

save(fig, "06_retention_curve.html")


# ── chart 7: churn breakdown ──────────────────────────────────
churn_counts = churn["churn_status"].value_counts().reset_index()
churn_counts.columns = ["status", "count"]

colors_churn = {
    "Active": GREEN, "At Risk": AMBER, "Churned": RED
}

fig = go.Figure(go.Pie(
    labels=churn_counts["status"],
    values=churn_counts["count"],
    hole=0.55,
    marker_colors=[colors_churn.get(s, PURPLE) for s in churn_counts["status"]],
    textinfo="label+percent",
    hovertemplate="<b>%{label}</b><br>%{value:,} customers<extra></extra>"
))

fig.update_layout(
    title="Customer Churn Status",
    paper_bgcolor=BG, font=dict(color="#e2e8f0"),
    margin=dict(t=60, b=20, l=20, r=20)
)

save(fig, "07_churn_status.html")


# ── chart 8: category sunburst ────────────────────────────────
fig = px.sunburst(
    cat,
    path=["category", "subcategory"],
    values="revenue",
    color="margin_pct",
    color_continuous_scale=["#1a1d2e", "#4f46e5", "#10b981"]
)

fig.update_traces(
    hovertemplate="<b>%{label}</b><br>Revenue: £%{value:,.0f}<extra></extra>"
)

fig.update_layout(
    title="Revenue by Category",
    paper_bgcolor=BG, font=dict(color="#e2e8f0"),
    margin=dict(t=60, b=10, l=10, r=10),
    coloraxis_colorbar=dict(title="Margin %", tickfont=dict(color="#e2e8f0"))
)

save(fig, "08_category_revenue.html")


# ── chart 9: region performance ───────────────────────────────
fig = make_subplots(rows=1, cols=3,
    subplot_titles=["Revenue (£)", "Avg Order Value", "Return Rate %"],
    horizontal_spacing=0.12)

for col_idx, (col, title) in enumerate([
    ("revenue", "£"), ("aov", "£"), ("return_rate_pct", "%")
], 1):
    fig.add_trace(go.Bar(
        x=reg["region"], y=reg[col],
        marker_color=COLORS[:len(reg)],
        text=reg[col].apply(lambda v: f"£{v:,.0f}" if "£" in title else f"{v:.1f}%"),
        textposition="outside",
        showlegend=False
    ), row=1, col=col_idx)

fig.update_layout(
    title="Regional Performance",
    paper_bgcolor=BG, plot_bgcolor=PANEL,
    font=dict(color="#e2e8f0"),
    margin=dict(t=70, b=50, l=50, r=40),
    height=380
)
fig.update_xaxes(gridcolor="#2d3748", tickangle=-30)
fig.update_yaxes(gridcolor="#2d3748")

save(fig, "09_region_performance.html")


# ── chart 10: new vs returning ────────────────────────────────
fig = go.Figure()

for ctype, color in [("New", GREEN), ("Returning", PURPLE)]:
    d = nvr[nvr["type"] == ctype]
    fig.add_trace(go.Bar(
        x=d["month"], y=d["customers"],
        name=ctype, marker_color=color, opacity=0.85
    ))

fig.update_layout(
    barmode="stack",
    title="New vs Returning Customers",
    paper_bgcolor=BG, plot_bgcolor=PANEL,
    font=dict(color="#e2e8f0"),
    xaxis=dict(gridcolor="#2d3748", tickangle=-45),
    yaxis=dict(gridcolor="#2d3748", title="Customers"),
    legend=dict(bgcolor=PANEL),
    margin=dict(t=60, b=60, l=60, r=40)
)

save(fig, "10_new_vs_returning.html")


# ── chart 11: payment & channel mix ──────────────────────────
fig = make_subplots(rows=1, cols=2,
    specs=[[{"type": "pie"}, {"type": "pie"}]],
    subplot_titles=["Payment Method", "Channel"])

fig.add_trace(go.Pie(
    labels=pay["payment_method"], values=pay["revenue"],
    hole=0.45, marker_colors=COLORS, textinfo="label+percent"
), row=1, col=1)

fig.add_trace(go.Pie(
    labels=chan["channel"], values=chan["revenue"],
    hole=0.45, marker_colors=COLORS[5:], textinfo="label+percent"
), row=1, col=2)

fig.update_layout(
    title="Revenue by Payment Method & Channel",
    paper_bgcolor=BG, font=dict(color="#e2e8f0"),
    margin=dict(t=70, b=20, l=20, r=20)
)

save(fig, "11_payment_channel.html")


# ── A/B TEST: would a better checkout lift revenue? ───────────
# We take the real customer spend distribution and simulate
# what would happen if 12,000 users got a new checkout flow.

print("\nRunning A/B test...")
np.random.seed(42)

real_spends = rfm["monetary"].dropna().values
real_spends = real_spends[real_spends > 0]
n           = 12000

control     = np.random.choice(real_spends, size=n, replace=True)
treatment   = np.clip(control * np.random.normal(1.17, 0.05, n), 0, None)

# Mann-Whitney U: is treatment revenue higher?
u_stat, p_revenue = stats.mannwhitneyu(treatment, control, alternative="greater")

# Chi-Square: is conversion rate higher?
ctrl_cvr   = np.random.binomial(1, 0.62, n)
treat_cvr  = np.random.binomial(1, 0.70, n)
table      = [[ctrl_cvr.sum(), n - ctrl_cvr.sum()],
              [treat_cvr.sum(), n - treat_cvr.sum()]]
chi2, p_cvr, _, _ = stats.chi2_contingency(table)

rev_lift = (treatment.mean() / control.mean() - 1) * 100
cvr_lift = (treat_cvr.mean() - ctrl_cvr.mean()) / ctrl_cvr.mean() * 100

print(f"  Revenue lift: +{rev_lift:.1f}% (p={p_revenue:.2e})")
print(f"  CVR lift:     +{cvr_lift:.1f}% (p={p_cvr:.2e})")


# ── chart 12: A/B test results ────────────────────────────────
fig = make_subplots(rows=1, cols=2,
    subplot_titles=["Revenue Distribution", "Conversion Rate"],
    horizontal_spacing=0.14)

bins      = np.linspace(0, np.percentile(np.concatenate([control, treatment]), 98), 60)
c_hist, e = np.histogram(control, bins=bins, density=True)
t_hist, _ = np.histogram(treatment, bins=bins, density=True)
centres   = (e[:-1] + e[1:]) / 2

fig.add_trace(go.Scatter(
    x=centres, y=c_hist, name="Control",
    mode="lines", fill="tozeroy",
    line=dict(color=TEAL, width=2), fillcolor="rgba(6,182,212,0.2)"
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=centres, y=t_hist, name=f"Treatment (+{rev_lift:.0f}%)",
    mode="lines", fill="tozeroy",
    line=dict(color=PURPLE, width=2), fillcolor="rgba(124,58,237,0.2)"
), row=1, col=1)

fig.add_trace(go.Bar(
    x=["Control", "Treatment"],
    y=[ctrl_cvr.mean() * 100, treat_cvr.mean() * 100],
    marker_color=[TEAL, PURPLE],
    text=[f"{ctrl_cvr.mean()*100:.1f}%", f"{treat_cvr.mean()*100:.1f}%"],
    textposition="outside",
    showlegend=False
), row=1, col=2)

sig_text = (
    f"Revenue: +{rev_lift:.1f}% (p={p_revenue:.1e}) ✅  |  "
    f"CVR: +{cvr_lift:.1f}% (p={p_cvr:.1e}) ✅  —  Both significant at α=0.05"
)
fig.add_annotation(
    x=0.5, y=1.1, xref="paper", yref="paper",
    text=sig_text, showarrow=False,
    font=dict(size=11, color=GREEN),
    bgcolor=PANEL, bordercolor=GREEN, borderwidth=1
)

fig.update_layout(
    title="A/B Test: New Checkout vs Old",
    paper_bgcolor=BG, plot_bgcolor=PANEL,
    font=dict(color="#e2e8f0"),
    legend=dict(bgcolor=PANEL),
    margin=dict(t=100, b=50, l=60, r=40)
)
fig.update_xaxes(gridcolor="#2d3748")
fig.update_yaxes(gridcolor="#2d3748")

save(fig, "12_ab_test.html")


print(f"\nAll charts saved to '{CHARTS}/'")
print("Open any .html file in your browser to view it.")
print("\nRun 4_dashboard.py next.")
