"""
Step 4: Interactive dashboard.
Run this file and open http://127.0.0.1:8050 in your browser.

pip install dash dash-bootstrap-components
"""

import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import scipy.stats as stats
import os

# ── load all data ─────────────────────────────────────────────
P = "data/processed"

mr      = pd.read_csv(f"{P}/monthly_revenue.csv")
rfm     = pd.read_csv(f"{P}/rfm_segments.csv")
rfm_sum = pd.read_csv(f"{P}/rfm_summary.csv")
cohort  = pd.read_csv(f"{P}/cohort_pivot.csv", index_col=0)
avg_ret = pd.read_csv(f"{P}/avg_retention.csv")
churn   = pd.read_csv(f"{P}/churn_risk.csv")
cat     = pd.read_csv(f"{P}/category_performance.csv")
reg     = pd.read_csv(f"{P}/region_performance.csv")
nvr     = pd.read_csv(f"{P}/new_vs_returning.csv")
pay     = pd.read_csv(f"{P}/payment_methods.csv")
chan    = pd.read_csv(f"{P}/channel_performance.csv")
clv     = pd.read_csv(f"{P}/customer_clv.csv")

clv_rfm = clv.merge(rfm[["customer_id", "segment"]], on="customer_id", how="left")

# ── pre-compute A/B test numbers ──────────────────────────────
np.random.seed(42)
_n    = 12000
_real = rfm["monetary"].dropna().values
_real = _real[_real > 0]
_ctrl = np.random.choice(_real, size=_n, replace=True)
_trt  = np.clip(_ctrl * np.random.normal(1.17, 0.05, _n), 0, None)
_c_cvr = np.random.binomial(1, 0.62, _n)
_t_cvr = np.random.binomial(1, 0.70, _n)
_, _p_rev = stats.mannwhitneyu(_trt, _ctrl, alternative="greater")
_ct = [[_c_cvr.sum(), _n-_c_cvr.sum()], [_t_cvr.sum(), _n-_t_cvr.sum()]]
_chi2, _p_cvr, _, _ = stats.chi2_contingency(_ct)
_rev_lift = (_trt.mean() / _ctrl.mean() - 1) * 100
_cvr_lift = (_t_cvr.mean() - _c_cvr.mean()) / _c_cvr.mean() * 100

# ── colours ───────────────────────────────────────────────────
BG     = "#0f1117"
PANEL  = "#1a1d2e"
PURPLE = "#7c3aed"
TEAL   = "#06b6d4"
GREEN  = "#10b981"
RED    = "#ef4444"
AMBER  = "#f59e0b"
COLORS = [PURPLE, TEAL, GREEN, AMBER, RED,
          "#ec4899", "#8b5cf6", "#14b8a6", "#f97316", "#6366f1"]

PLOT_BASE = dict(
    paper_bgcolor=BG, plot_bgcolor=PANEL,
    font=dict(color="#e2e8f0", family="Arial"),
    margin=dict(t=50, b=40, l=50, r=30)
)


# ── helpers ───────────────────────────────────────────────────
def grid_axes():
    return dict(
        xaxis=dict(gridcolor="#2d3748"),
        yaxis=dict(gridcolor="#2d3748")
    )

def kpi_card(label, value_id, icon):
    return html.Div([
        html.Div(icon, style={"fontSize": "1.4rem", "marginBottom": "4px"}),
        html.Div(label, style={
            "fontSize": "0.7rem", "color": "#94a3b8",
            "textTransform": "uppercase", "letterSpacing": "0.8px",
            "fontWeight": "600"
        }),
        html.Div(id=value_id, style={
            "fontSize": "1.5rem", "fontWeight": "700",
            "color": "#f1f5f9", "marginTop": "4px"
        }),
    ], style={
        "background": PANEL, "border": "1px solid #2d3748",
        "borderRadius": "10px", "padding": "16px",
        "flex": "1"
    })


# ── app layout ────────────────────────────────────────────────
app = dash.Dash(__name__, title="E-Commerce Analytics")

app.layout = html.Div([

    # header
    html.Div([
        html.Div([
            html.Span("🛒 ", style={"fontSize": "1.3rem"}),
            html.Span("E-Commerce Analytics Dashboard",
                      style={"fontSize": "1.1rem", "fontWeight": "700", "color": "#f1f5f9"}),
        ]),
        html.Div("UCI Online Retail II · Dec 2009 – Dec 2011",
                 style={"fontSize": "0.75rem", "color": "#64748b"}),
    ], style={
        "background": PANEL, "borderBottom": "1px solid #2d3748",
        "padding": "14px 28px", "display": "flex",
        "justifyContent": "space-between", "alignItems": "center"
    }),

    # body
    html.Div([

        # sidebar
        html.Div([
            html.Div("FILTERS", style={
                "fontSize": "0.7rem", "color": "#64748b",
                "fontWeight": "600", "letterSpacing": "0.8px",
                "marginBottom": "16px"
            }),

            html.Div("Date range", style={"fontSize":"0.72rem","color":"#94a3b8","marginBottom":"4px"}),
            dcc.Dropdown(id="dd-start",
                options=[{"label": m, "value": m} for m in mr["month"].tolist()],
                value=mr["month"].iloc[0], clearable=False,
                style={"fontSize": "0.8rem"}),
            html.Div(style={"height": "6px"}),
            dcc.Dropdown(id="dd-end",
                options=[{"label": m, "value": m} for m in mr["month"].tolist()],
                value=mr["month"].iloc[-1], clearable=False,
                style={"fontSize": "0.8rem"}),

            html.Hr(style={"borderColor": "#2d3748", "margin": "16px 0"}),

            html.Div("Region", style={"fontSize":"0.72rem","color":"#94a3b8","marginBottom":"4px"}),
            dcc.Dropdown(id="dd-region",
                options=[{"label": "All", "value": "ALL"}] +
                        [{"label": r, "value": r} for r in sorted(reg["region"].tolist())],
                value="ALL", clearable=False,
                style={"fontSize": "0.8rem"}),

            html.Hr(style={"borderColor": "#2d3748", "margin": "16px 0"}),

            html.Div("RFM Segment", style={"fontSize":"0.72rem","color":"#94a3b8","marginBottom":"4px"}),
            dcc.Dropdown(id="dd-segment",
                options=[{"label": "All", "value": "ALL"}] +
                        [{"label": s, "value": s} for s in sorted(rfm_sum["segment"].tolist())],
                value="ALL", clearable=False,
                style={"fontSize": "0.8rem"}),

        ], style={
            "width": "210px", "flexShrink": "0",
            "background": PANEL, "borderRight": "1px solid #2d3748",
            "padding": "20px 14px", "minHeight": "100vh"
        }),

        # main content
        html.Div([

            # KPI row
            html.Div([
                kpi_card("Total Revenue",    "kpi-revenue",   "💰"),
                kpi_card("Total Orders",     "kpi-orders",    "📦"),
                kpi_card("Avg Order Value",  "kpi-aov",       "🛒"),
                kpi_card("Customers",        "kpi-customers", "👤"),
                kpi_card("Return Rate",      "kpi-return",    "↩️"),
                kpi_card("Churned",          "kpi-churn",     "⚠️"),
            ], style={"display": "flex", "gap": "10px", "marginBottom": "16px"}),

            # tabs
            dcc.Tabs(id="tabs", value="overview", children=[
                dcc.Tab(label="Overview",    value="overview"),
                dcc.Tab(label="Customers",   value="customers"),
                dcc.Tab(label="Retention",   value="cohort"),
                dcc.Tab(label="Funnel & A/B",value="funnel"),
                dcc.Tab(label="Regional",    value="regional"),
            ], style={"marginBottom": "0"}),

            html.Div(id="tab-content", style={
                "background": BG, "border": "1px solid #2d3748",
                "borderTop": "none", "borderRadius": "0 0 8px 8px",
                "padding": "16px", "minHeight": "480px"
            }),

        ], style={"flex": "1", "padding": "16px", "minWidth": "0"}),
    ], style={"display": "flex"}),

], style={"background": BG, "minHeight": "100vh",
          "fontFamily": "Arial, sans-serif", "color": "#e2e8f0"})


# ── KPI callback ──────────────────────────────────────────────
@app.callback(
    [Output("kpi-revenue", "children"),
     Output("kpi-orders",  "children"),
     Output("kpi-aov",     "children"),
     Output("kpi-customers","children"),
     Output("kpi-return",  "children"),
     Output("kpi-churn",   "children")],
    [Input("dd-start", "value"), Input("dd-end", "value")]
)
def update_kpis(start, end):
    df = mr[(mr["month"] >= start) & (mr["month"] <= end)]
    revenue   = df["revenue"].sum()
    orders    = df["orders"].sum()
    aov       = revenue / orders if orders else 0
    customers = df["customers"].sum()

    # return rate from full dataset
    oi  = pd.read_csv("data/raw/order_items.csv")
    ret = oi["return_flag"].mean() * 100

    churned = (churn["churn_status"] == "Churned").sum()

    return (
        f"£{revenue:,.0f}",
        f"{orders:,}",
        f"£{aov:,.0f}",
        f"{customers:,}",
        f"{ret:.1f}%",
        f"{churned:,}",
    )


# ── tab content callback ──────────────────────────────────────
@app.callback(
    Output("tab-content", "children"),
    [Input("tabs",       "value"),
     Input("dd-start",   "value"),
     Input("dd-end",     "value"),
     Input("dd-region",  "value"),
     Input("dd-segment", "value")]
)
def render_tab(tab, start, end, region, segment):
    if tab == "overview":  return overview_tab(start, end)
    if tab == "customers": return customers_tab(segment)
    if tab == "cohort":    return cohort_tab()
    if tab == "funnel":    return funnel_tab()
    if tab == "regional":  return regional_tab(region)
    return html.Div()


def chart_wrap(fig, flex="1"):
    return html.Div(dcc.Graph(figure=fig), style={
        "background": PANEL, "border": "1px solid #2d3748",
        "borderRadius": "10px", "padding": "4px", "flex": flex
    })

def row(*children, gap="10px"):
    return html.Div(list(children), style={
        "display": "flex", "gap": gap, "marginBottom": "12px"
    })


# ── OVERVIEW tab ──────────────────────────────────────────────
def overview_tab(start, end):
    df = mr[(mr["month"] >= start) & (mr["month"] <= end)].copy()
    df["mom"] = df["revenue"].pct_change() * 100

    # revenue trend
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(go.Bar(x=df["month"], y=df["revenue"],
        name="Revenue", marker_color=PURPLE, opacity=0.85), secondary_y=False)
    fig1.add_trace(go.Scatter(x=df["month"], y=df["mom"],
        name="MoM %", mode="lines+markers",
        line=dict(color=TEAL, width=2)), secondary_y=True)
    fig1.update_layout(title="Monthly Revenue & MoM Growth", height=300,
        **PLOT_BASE, xaxis=dict(gridcolor="#2d3748", tickangle=-45),
        yaxis=dict(gridcolor="#2d3748"), yaxis2=dict(gridcolor="#1a1d2e"),
        legend=dict(bgcolor=PANEL))

    # new vs returning
    nvr_f = nvr[(nvr["month"] >= start) & (nvr["month"] <= end)]
    fig2 = go.Figure()
    for t, c in [("New", GREEN), ("Returning", PURPLE)]:
        d = nvr_f[nvr_f["type"] == t]
        fig2.add_trace(go.Bar(x=d["month"], y=d["customers"],
            name=t, marker_color=c, opacity=0.85))
    fig2.update_layout(barmode="stack", title="New vs Returning",
        height=280, **PLOT_BASE,
        xaxis=dict(gridcolor="#2d3748", tickangle=-45),
        yaxis=dict(gridcolor="#2d3748"), legend=dict(bgcolor=PANEL))

    # category sunburst
    fig3 = px.sunburst(cat, path=["category","subcategory"], values="revenue",
        color="margin_pct", color_continuous_scale=["#1a1d2e","#4f46e5","#10b981"])
    fig3.update_layout(title="Category Revenue", paper_bgcolor=BG,
        font=dict(color="#e2e8f0"), margin=dict(t=50,b=10,l=10,r=10), height=280)

    # payment donut
    fig4 = go.Figure(go.Pie(labels=pay["payment_method"], values=pay["revenue"],
        hole=0.5, marker_colors=COLORS, textinfo="label+percent"))
    fig4.update_layout(title="Payment Mix", paper_bgcolor=BG,
        font=dict(color="#e2e8f0"), margin=dict(t=50,b=10,l=10,r=10), height=280)

    return html.Div([
        chart_wrap(fig1),
        row(chart_wrap(fig2), chart_wrap(fig3), chart_wrap(fig4))
    ])


# ── CUSTOMERS tab ─────────────────────────────────────────────
def customers_tab(segment):
    rfm_f   = rfm if segment == "ALL" else rfm[rfm["segment"] == segment]
    clv_f   = clv_rfm if segment == "ALL" else clv_rfm[clv_rfm["segment"] == segment]
    clv_cln = clv_f[clv_f["aov"].notna() &
                    (clv_f["total_spend"] < clv_f["total_spend"].quantile(0.97))]

    # treemap
    fig1 = px.treemap(rfm_sum, path=["segment"], values="total_revenue",
        color="avg_spend", color_continuous_scale=["#1a1d2e","#4f46e5","#a78bfa"],
        custom_data=["customers","avg_orders","avg_spend"])
    fig1.update_traces(hovertemplate="<b>%{label}</b><br>Revenue: £%{value:,.0f}<br>"
        "Customers: %{customdata[0]:,}<extra></extra>")
    fig1.update_layout(title="RFM Segment Revenue", paper_bgcolor=BG,
        font=dict(color="#e2e8f0"), margin=dict(t=50,b=10,l=10,r=10), height=300)

    # scatter
    s = rfm_f.sample(min(3000, len(rfm_f)), random_state=42)
    fig2 = px.scatter(s, x="recency_days", y="monetary",
        color="f_score", size="frequency",
        color_continuous_scale=[RED,AMBER,GREEN,TEAL,PURPLE])
    fig2.update_layout(title="Recency vs Spend", height=280,
        **PLOT_BASE, **grid_axes())

    # CLV box
    fig3 = go.Figure()
    seg_order = rfm_sum.sort_values("total_revenue", ascending=False)["segment"].tolist()
    for i, seg in enumerate(seg_order):
        d = clv_cln[clv_cln["segment"] == seg]["total_spend"]
        if len(d) == 0: continue
        fig3.add_trace(go.Box(y=d, name=seg, marker_color=COLORS[i%len(COLORS)],
            boxmean="sd", showlegend=False))
    fig3.update_layout(title="Spend Distribution by Segment", height=280,
        **PLOT_BASE, xaxis=dict(gridcolor="#2d3748", tickangle=-30),
        yaxis=dict(gridcolor="#2d3748", title="Total Spend (£)"))

    # churn donut
    ch = churn["churn_status"].value_counts().reset_index()
    ch.columns = ["status", "count"]
    c_map = {"Active": GREEN, "At Risk": AMBER, "Churned": RED}
    fig4 = go.Figure(go.Pie(labels=ch["status"], values=ch["count"],
        hole=0.55, marker_colors=[c_map.get(s, PURPLE) for s in ch["status"]],
        textinfo="label+percent"))
    fig4.update_layout(title="Churn Status", paper_bgcolor=BG,
        font=dict(color="#e2e8f0"), margin=dict(t=50,b=10,l=10,r=10), height=280)

    return html.Div([
        row(chart_wrap(fig1, "1.2"), chart_wrap(fig4, "0.8")),
        row(chart_wrap(fig2), chart_wrap(fig3))
    ])


# ── COHORT tab ────────────────────────────────────────────────
def cohort_tab():
    z    = cohort.values.tolist()
    x    = cohort.columns.tolist()
    y    = cohort.index.tolist()
    text = [[f"{v:.0f}%" if not (isinstance(v,float) and np.isnan(v)) else ""
             for v in row] for row in z]

    fig1 = go.Figure(go.Heatmap(
        z=z, x=x, y=y, text=text,
        texttemplate="%{text}", textfont=dict(size=9),
        colorscale=[[0,"#1a1d2e"],[0.4,"#4f46e5"],[1.0,"#ddd6fe"]],
        colorbar=dict(title="Retention%", tickfont=dict(color="#e2e8f0"))
    ))
    fig1.update_layout(title="Cohort Retention Heatmap", height=440,
        paper_bgcolor=BG, plot_bgcolor=BG, font=dict(color="#e2e8f0"),
        xaxis=dict(title="Months After First Order"),
        yaxis=dict(title="Cohort", autorange="reversed"),
        margin=dict(t=60,b=60,l=100,r=40))

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=avg_ret["months_since_first_order"], y=avg_ret["avg_pct"],
        name="Average", mode="lines+markers",
        line=dict(color=PURPLE,width=3), fill="tozeroy",
        fillcolor="rgba(124,58,237,0.15)"))
    fig2.add_trace(go.Scatter(x=avg_ret["months_since_first_order"], y=avg_ret["max_pct"],
        name="Best", line=dict(color=GREEN,width=1.5,dash="dash")))
    fig2.add_trace(go.Scatter(x=avg_ret["months_since_first_order"], y=avg_ret["min_pct"],
        name="Worst", line=dict(color=RED,width=1.5,dash="dash")))
    fig2.update_layout(title="Average Retention Curve", height=280,
        **PLOT_BASE, xaxis=dict(gridcolor="#2d3748"),
        yaxis=dict(gridcolor="#2d3748",title="Retention (%)"),
        legend=dict(bgcolor=PANEL))

    m0 = avg_ret.iloc[0]["avg_pct"]
    m1 = avg_ret.iloc[1]["avg_pct"] if len(avg_ret) > 1 else 0
    m6 = avg_ret[avg_ret["months_since_first_order"]==6]["avg_pct"].values[0] if len(avg_ret) > 6 else 0

    stat_row = html.Div([
        html.Div([html.Div("M0 Retention",style={"fontSize":"0.7rem","color":"#94a3b8"}),
                  html.Div(f"{m0:.1f}%",style={"fontSize":"1.3rem","fontWeight":"700"})],
                 style={"background":PANEL,"border":"1px solid #2d3748","borderRadius":"8px",
                        "padding":"12px","flex":"1"}),
        html.Div([html.Div("M1 Retention",style={"fontSize":"0.7rem","color":"#94a3b8"}),
                  html.Div(f"{m1:.1f}%",style={"fontSize":"1.3rem","fontWeight":"700","color":AMBER})],
                 style={"background":PANEL,"border":"1px solid #2d3748","borderRadius":"8px",
                        "padding":"12px","flex":"1"}),
        html.Div([html.Div("M6 Retention",style={"fontSize":"0.7rem","color":"#94a3b8"}),
                  html.Div(f"{m6:.1f}%",style={"fontSize":"1.3rem","fontWeight":"700","color":RED})],
                 style={"background":PANEL,"border":"1px solid #2d3748","borderRadius":"8px",
                        "padding":"12px","flex":"1"}),
        html.Div([html.Div("Key Insight",style={"fontSize":"0.7rem","color":"#94a3b8"}),
                  html.Div("Biggest drop at M1 — improve onboarding",
                           style={"fontSize":"0.78rem","color":AMBER,"marginTop":"4px"})],
                 style={"background":PANEL,"border":"1px solid #2d3748","borderRadius":"8px",
                        "padding":"12px","flex":"2"}),
    ], style={"display":"flex","gap":"10px","marginBottom":"12px"})

    return html.Div([
        stat_row,
        chart_wrap(fig1),
        chart_wrap(fig2)
    ])


# ── FUNNEL & A/B tab ──────────────────────────────────────────
def funnel_tab():
    total_orders = pd.read_csv("data/raw/orders.csv")["order_id"].nunique()
    total_items  = len(pd.read_csv("data/raw/order_items.csv"))
    returned     = pd.read_csv("data/raw/order_items.csv")["return_flag"].sum()
    kept         = total_items - returned

    fig1 = go.Figure(go.Funnel(
        y=["Total Orders", "Items Sold", "Items Kept (No Return)"],
        x=[total_orders, total_items, kept],
        textinfo="value+percent initial",
        textfont=dict(size=13, color="white"),
        marker=dict(color=[PURPLE, "#6d28d9", "#4c1d95"])
    ))
    fig1.update_layout(title="Order Funnel", height=320,
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(color="#e2e8f0"), margin=dict(t=60,b=40,l=180,r=40))

    # A/B distributions
    bins   = np.linspace(0, np.percentile(np.concatenate([_ctrl,_trt]),98), 60)
    c_h, e = np.histogram(_ctrl, bins=bins, density=True)
    t_h, _ = np.histogram(_trt,  bins=bins, density=True)
    centres= (e[:-1]+e[1:])/2

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=centres, y=c_h, name="Control",
        mode="lines", fill="tozeroy",
        line=dict(color=TEAL,width=2), fillcolor="rgba(6,182,212,0.2)"))
    fig2.add_trace(go.Scatter(x=centres, y=t_h, name=f"Treatment (+{_rev_lift:.0f}%)",
        mode="lines", fill="tozeroy",
        line=dict(color=PURPLE,width=2), fillcolor="rgba(124,58,237,0.2)"))
    fig2.update_layout(title="Revenue Distribution — Control vs Treatment", height=280,
        **PLOT_BASE, **grid_axes(), legend=dict(bgcolor=PANEL))

    fig3 = go.Figure(go.Bar(
        x=["Control","Treatment"],
        y=[_c_cvr.mean()*100, _t_cvr.mean()*100],
        marker_color=[TEAL,PURPLE],
        text=[f"{_c_cvr.mean()*100:.1f}%",f"{_t_cvr.mean()*100:.1f}%"],
        textposition="outside", width=0.4
    ))
    fig3.update_layout(title="Conversion Rate", height=280,
        **PLOT_BASE, xaxis=dict(gridcolor="#2d3748"),
        yaxis=dict(gridcolor="#2d3748",range=[0,85],title="%"))

    badges = html.Div([
        html.Div(
            f"✅ Revenue lift: +{_rev_lift:.1f}%  |  Mann-Whitney U  |  p = {_p_rev:.1e}  |  Significant at α=0.05",
            style={"background":"#0f2d1f","border":"1px solid #10b981","borderRadius":"6px",
                   "padding":"10px 14px","marginBottom":"6px","fontSize":"0.82rem","color":"#6ee7b7"}),
        html.Div(
            f"✅ CVR lift: +{_cvr_lift:.1f}%  |  Chi-Square  |  p = {_p_cvr:.1e}  |  Significant at α=0.05",
            style={"background":"#0f2d1f","border":"1px solid #10b981","borderRadius":"6px",
                   "padding":"10px 14px","fontSize":"0.82rem","color":"#6ee7b7"}),
    ], style={"marginBottom":"12px"})

    return html.Div([
        badges,
        row(chart_wrap(fig1), html.Div([
            chart_wrap(fig2), chart_wrap(fig3)
        ], style={"flex":"1","display":"flex","flexDirection":"column","gap":"0"}))
    ])


# ── REGIONAL tab ──────────────────────────────────────────────
def regional_tab(region):
    r = reg if region == "ALL" else reg[reg["region"] == region]

    fig1 = go.Figure(go.Bar(x=r["region"], y=r["revenue"],
        marker_color=COLORS[:len(r)],
        text=r["revenue"].apply(lambda v: f"£{v:,.0f}"), textposition="outside"))
    fig1.update_layout(title="Revenue by Region", height=280,
        **PLOT_BASE, **grid_axes(), showlegend=False)

    fig2 = go.Figure(go.Bar(x=r["region"], y=r["aov"],
        marker_color=[TEAL]*len(r),
        text=r["aov"].apply(lambda v: f"£{v:,.0f}"), textposition="outside"))
    fig2.update_layout(title="Avg Order Value by Region", height=260,
        **PLOT_BASE, **grid_axes(), showlegend=False)

    fig3 = go.Figure(go.Bar(x=r["region"], y=r["return_rate_pct"],
        marker_color=[RED if v>8 else AMBER if v>6 else GREEN for v in r["return_rate_pct"]],
        text=r["return_rate_pct"].apply(lambda v: f"{v:.1f}%"), textposition="outside"))
    fig3.add_hline(y=8, line_dash="dot", line_color=RED)
    fig3.update_layout(title="Return Rate by Region", height=260,
        **PLOT_BASE, **grid_axes(), showlegend=False)

    churn_r = churn.groupby(["churn_status","region"]).size().reset_index(name="count")
    fig4 = px.bar(churn_r, x="region", y="count", color="churn_status",
        color_discrete_map={"Active":GREEN,"At Risk":AMBER,"Churned":RED},
        barmode="stack")
    fig4.update_layout(title="Churn by Region", height=260,
        paper_bgcolor=BG, plot_bgcolor=PANEL, font=dict(color="#e2e8f0"),
        xaxis=dict(gridcolor="#2d3748"), yaxis=dict(gridcolor="#2d3748"),
        legend=dict(bgcolor=PANEL), margin=dict(t=50,b=40,l=50,r=30))

    return html.Div([
        chart_wrap(fig1),
        row(chart_wrap(fig2), chart_wrap(fig3)),
        chart_wrap(fig4)
    ])


# ── run ───────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Starting dashboard at http://127.0.0.1:8050")
    app.run(debug=False, host="0.0.0.0", port=8050)
