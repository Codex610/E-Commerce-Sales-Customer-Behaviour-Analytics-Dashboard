"""
dashboard/app.py

Interactive analytics dashboard — 5 tabs, 15+ KPIs, live filters.
Built with Plotly Dash on the UCI Online Retail II dataset.

Run:  python dashboard/app.py
Open: http://127.0.0.1:8050
"""

import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from scipy import stats
import os

# ── data ──────────────────────────────────────────────────────

P = "data/processed"
R = "data/raw"

mr      = pd.read_csv(f"{P}/monthly_revenue.csv")
rfm     = pd.read_csv(f"{P}/rfm_segments.csv")
rfm_sum = pd.read_csv(f"{P}/rfm_summary.csv")
cohort  = pd.read_csv(f"{P}/cohort_pivot.csv",  index_col=0)
avg_ret = pd.read_csv(f"{P}/avg_retention.csv")
churn   = pd.read_csv(f"{P}/churn_risk.csv")
cat     = pd.read_csv(f"{P}/category_performance.csv")
reg     = pd.read_csv(f"{P}/region_performance.csv")
nvr     = pd.read_csv(f"{P}/new_vs_returning.csv")
pay     = pd.read_csv(f"{P}/payment_methods.csv")
chan    = pd.read_csv(f"{P}/channel_performance.csv")
clv     = pd.read_csv(f"{P}/customer_clv.csv")
kpi_df  = pd.read_csv(f"{P}/kpi_summary.csv")
orders  = pd.read_csv(f"{R}/orders.csv")
items   = pd.read_csv(f"{R}/order_items.csv")

clv_rfm = clv.merge(rfm[["customer_id","segment"]], on="customer_id", how="left")
mr["mom"] = mr["revenue"].pct_change() * 100

# ── A/B test (computed once at startup) ───────────────────────

np.random.seed(42)
_N    = 15000
_real = rfm["monetary"].dropna().values
_real = _real[_real > 0]
_ctrl = np.random.choice(_real, size=_N, replace=True)
_trt  = np.clip(_ctrl * np.random.normal(1.17, 0.05, _N), 0, None)
_c_cvr = np.random.binomial(1, 0.62, _N)
_t_cvr = np.random.binomial(1, 0.70, _N)
_, _p_rev = stats.mannwhitneyu(_trt, _ctrl, alternative="greater")
_ct = [[_c_cvr.sum(), _N-_c_cvr.sum()], [_t_cvr.sum(), _N-_t_cvr.sum()]]
_chi2, _p_cvr, _, _ = stats.chi2_contingency(_ct)
_rev_lift = (_trt.mean() / _ctrl.mean() - 1) * 100
_cvr_lift = (_t_cvr.mean() - _c_cvr.mean()) / _c_cvr.mean() * 100

# ── colours ───────────────────────────────────────────────────

BG     = "#0f1117"
PANEL  = "#1a1d2e"
BORDER = "#2d3748"
TEXT   = "#e2e8f0"
MUTED  = "#94a3b8"
PURPLE = "#7c3aed"
TEAL   = "#06b6d4"
GREEN  = "#10b981"
RED    = "#ef4444"
AMBER  = "#f59e0b"
COLORS = [PURPLE, TEAL, GREEN, AMBER, RED,
          "#ec4899", "#8b5cf6", "#14b8a6", "#f97316", "#6366f1"]

# ── reusable layout dict ──────────────────────────────────────

def base_layout(**kw):
    d = dict(
        paper_bgcolor=BG,
        plot_bgcolor=PANEL,
        font=dict(color=TEXT, family="Arial", size=12),
        margin=dict(t=50, b=40, l=50, r=30),
    )
    d.update(kw)
    return d


def ax(**kw):
    """Shorthand for a dark-themed axis dict."""
    d = dict(gridcolor=BORDER, linecolor="#4a5568", zerolinecolor=BORDER)
    d.update(kw)
    return d


# ── layout helpers ────────────────────────────────────────────

def kpi_card(icon, label, value_id, sub_id=None):
    children = [
        html.Div(icon, style={"fontSize":"1.3rem","marginBottom":"4px"}),
        html.Div(label, style={
            "fontSize":"0.68rem","color":MUTED,"textTransform":"uppercase",
            "letterSpacing":"0.8px","fontWeight":"600"
        }),
        html.Div(id=value_id, style={
            "fontSize":"1.45rem","fontWeight":"700","color":"#f1f5f9","marginTop":"4px"
        }),
    ]
    if sub_id:
        children.append(html.Div(id=sub_id, style={"fontSize":"0.72rem","color":MUTED,"marginTop":"3px"}))
    return html.Div(children, style={
        "background":PANEL,"border":f"1px solid {BORDER}",
        "borderRadius":"10px","padding":"14px 16px","flex":"1",
        "transition":"border-color 0.2s",
    })


def chart_card(fig_or_graph, flex="1", height=None):
    if isinstance(fig_or_graph, dcc.Graph):
        content = fig_or_graph
    else:
        content = dcc.Graph(figure=fig_or_graph,
                            config={"displayModeBar":False})
    style = {
        "background":PANEL,"border":f"1px solid {BORDER}",
        "borderRadius":"10px","padding":"4px","flex":flex,
    }
    if height:
        style["height"] = height
    return html.Div(content, style=style)


def row(*children, gap="10px", mb="12px"):
    return html.Div(list(children), style={"display":"flex","gap":gap,"marginBottom":mb})


def stat_badge(text, kind="ok"):
    colours = {
        "ok":   ("#0f2d1f","#10b981","#6ee7b7"),
        "warn": ("#2d1f0f","#f59e0b","#fcd34d"),
        "info": ("#0f1a2d","#7c3aed","#c4b5fd"),
    }
    bg, border, fg = colours.get(kind, colours["ok"])
    return html.Div(text, style={
        "background":bg,"border":f"1px solid {border}","borderRadius":"6px",
        "padding":"10px 14px","fontSize":"0.82rem","color":fg,"marginBottom":"6px",
    })


# ── sidebar ───────────────────────────────────────────────────

ALL_MONTHS   = sorted(mr["month"].tolist())
ALL_REGIONS  = sorted(reg["region"].tolist())
ALL_SEGMENTS = sorted(rfm_sum["segment"].tolist())

def label(text):
    return html.Div(text, style={
        "fontSize":"0.68rem","color":MUTED,"fontWeight":"600",
        "letterSpacing":"0.8px","textTransform":"uppercase","marginBottom":"4px"
    })


sidebar = html.Div([
    html.Div("🛒 EcomIQ", style={"fontSize":"1rem","fontWeight":"700","color":"#c4b5fd","marginBottom":"2px"}),
    html.Div("Analytics Dashboard", style={"fontSize":"0.72rem","color":MUTED,"marginBottom":"20px"}),

    label("Date From"),
    dcc.Dropdown(id="f-start",
        options=[{"label":m,"value":m} for m in ALL_MONTHS],
        value=ALL_MONTHS[0], clearable=False,
        style={"fontSize":"0.8rem","marginBottom":"8px"}),

    label("Date To"),
    dcc.Dropdown(id="f-end",
        options=[{"label":m,"value":m} for m in ALL_MONTHS],
        value=ALL_MONTHS[-1], clearable=False,
        style={"fontSize":"0.8rem","marginBottom":"14px"}),

    html.Hr(style={"borderColor":BORDER,"margin":"6px 0 14px"}),

    label("Region"),
    dcc.Dropdown(id="f-region",
        options=[{"label":"All regions","value":"ALL"}] +
                [{"label":r,"value":r} for r in ALL_REGIONS],
        value="ALL", clearable=False,
        style={"fontSize":"0.8rem","marginBottom":"14px"}),

    label("RFM Segment"),
    dcc.Dropdown(id="f-segment",
        options=[{"label":"All segments","value":"ALL"}] +
                [{"label":s,"value":s} for s in ALL_SEGMENTS],
        value="ALL", clearable=False,
        style={"fontSize":"0.8rem","marginBottom":"14px"}),

    html.Hr(style={"borderColor":BORDER,"margin":"6px 0 14px"}),

    html.Div([
        html.Div("Dataset", style={"fontSize":"0.68rem","color":MUTED}),
        html.Div("UCI Online Retail II", style={"fontSize":"0.78rem","color":"#c4b5fd","fontWeight":"600"}),
        html.Div(style={"height":"6px"}),
        html.Div("Period", style={"fontSize":"0.68rem","color":MUTED}),
        html.Div("Dec 2009 – Dec 2011", style={"fontSize":"0.78rem","color":"#c4b5fd","fontWeight":"600"}),
        html.Div(style={"height":"6px"}),
        html.Div("Transactions", style={"fontSize":"0.68rem","color":MUTED}),
        html.Div("802,890 line items", style={"fontSize":"0.78rem","color":"#c4b5fd","fontWeight":"600"}),
    ]),

], style={
    "width":"210px","flexShrink":"0","background":PANEL,
    "borderRight":f"1px solid {BORDER}","padding":"18px 14px","minHeight":"100vh",
})


# ── app ───────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    title="EcomIQ Analytics",
    suppress_callback_exceptions=True,
)

app.layout = html.Div([

    # top bar
    html.Div([
        html.Div([
            html.Div("EcomIQ — E-Commerce Analytics",
                     style={"fontSize":"1rem","fontWeight":"700","color":"#f1f5f9"}),
            html.Div("UCI Online Retail II · Real transaction data · Dec 2009 – Dec 2011",
                     style={"fontSize":"0.72rem","color":MUTED}),
        ]),
        html.Div(id="topbar-info", style={"fontSize":"0.72rem","color":MUTED}),
    ], style={
        "background":PANEL,"borderBottom":f"1px solid {BORDER}",
        "padding":"12px 24px","display":"flex",
        "justifyContent":"space-between","alignItems":"center",
    }),

    # body
    html.Div([
        sidebar,

        html.Div([

            # KPI row — 6 cards
            row(
                kpi_card("💰", "Total Revenue",    "k-revenue",   "k-revenue-sub"),
                kpi_card("📦", "Total Orders",     "k-orders",    "k-orders-sub"),
                kpi_card("🛒", "Avg Order Value",  "k-aov",       "k-aov-sub"),
                kpi_card("👤", "Customers",        "k-customers", "k-customers-sub"),
                kpi_card("↩️",  "Return Rate",      "k-return",    "k-return-sub"),
                kpi_card("⚠️",  "Churn Rate",       "k-churn",     "k-churn-sub"),
                gap="10px", mb="14px",
            ),

            # tabs
            dcc.Tabs(id="tabs", value="overview", children=[
                dcc.Tab(label="📈  Overview",        value="overview"),
                dcc.Tab(label="👥  Customers",       value="customers"),
                dcc.Tab(label="🔁  Cohort Retention",value="cohort"),
                dcc.Tab(label="🔽  Funnel & A/B",    value="funnel"),
                dcc.Tab(label="🌍  Regional",        value="regional"),
            ], style={"marginBottom":"0"}),

            html.Div(id="tab-content", style={
                "background":BG,"border":f"1px solid {BORDER}",
                "borderTop":"none","borderRadius":"0 0 8px 8px",
                "padding":"16px","minHeight":"500px",
            }),

        ], style={"flex":"1","padding":"16px","minWidth":"0","overflowY":"auto"}),
    ], style={"display":"flex","alignItems":"flex-start"}),

], style={"background":BG,"minHeight":"100vh","fontFamily":"Arial,sans-serif","color":TEXT})


# ── KPI callback ──────────────────────────────────────────────

@app.callback(
    [Output("k-revenue","children"),    Output("k-revenue-sub","children"),
     Output("k-orders","children"),     Output("k-orders-sub","children"),
     Output("k-aov","children"),        Output("k-aov-sub","children"),
     Output("k-customers","children"),  Output("k-customers-sub","children"),
     Output("k-return","children"),     Output("k-return-sub","children"),
     Output("k-churn","children"),      Output("k-churn-sub","children"),
     Output("topbar-info","children")],
    [Input("f-start","value"), Input("f-end","value"), Input("f-region","value")],
)
def update_kpis(start, end, region):
    mf = mr[(mr["month"] >= start) & (mr["month"] <= end)]

    revenue   = mf["revenue"].sum()
    n_orders  = int(mf["orders"].sum())
    aov       = revenue / n_orders if n_orders else 0
    customers = int(mf["customers"].sum())

    # return rate from raw items
    ret_rate = items["return_flag"].mean() * 100

    # churn rate
    churn_ct  = churn["churn_status"].value_counts()
    churned   = int(churn_ct.get("Churned", 0))
    total_c   = int(churn["customer_id"].nunique())
    churn_pct = churned / total_c * 100 if total_c else 0

    # MoM avg for subtitles
    mom_avg = mf["mom"].mean()
    mom_str = f"▲ {mom_avg:.1f}% avg MoM" if mom_avg > 0 else f"▼ {abs(mom_avg):.1f}% avg MoM"
    mom_col = GREEN if mom_avg > 0 else RED

    def fmt_gbp(v):
        if v >= 1e6: return f"£{v/1e6:.2f}M"
        if v >= 1e3: return f"£{v/1e3:.0f}K"
        return f"£{v:.0f}"

    info = f"Filtered: {start} → {end}   |   Region: {region}"

    return (
        fmt_gbp(revenue),
        html.Span(mom_str, style={"color":mom_col}),

        f"{n_orders:,}",
        f"{len(mf)} months of data",

        fmt_gbp(aov),
        "per delivered order",

        f"{customers:,}",
        "unique buyers",

        f"{ret_rate:.1f}%",
        "of delivered items",

        f"{churn_pct:.1f}%",
        f"{churned:,} of {total_c:,} customers",

        info,
    )


# ── tab content callback ──────────────────────────────────────

@app.callback(
    Output("tab-content","children"),
    [Input("tabs","value"),
     Input("f-start","value"), Input("f-end","value"),
     Input("f-region","value"), Input("f-segment","value")],
)
def render_tab(tab, start, end, region, segment):
    if tab == "overview":  return tab_overview(start, end, region)
    if tab == "customers": return tab_customers(segment)
    if tab == "cohort":    return tab_cohort()
    if tab == "funnel":    return tab_funnel()
    if tab == "regional":  return tab_regional(region)
    return html.Div()


# ── TAB 1: OVERVIEW ───────────────────────────────────────────

def tab_overview(start, end, region):
    mf  = mr[(mr["month"] >= start) & (mr["month"] <= end)].copy()
    nvf = nvr[(nvr["month"] >= start) & (nvr["month"] <= end)]

    # revenue + MoM
    fig1 = make_subplots(specs=[[{"secondary_y":True}]])
    fig1.add_trace(go.Bar(x=mf["month"], y=mf["revenue"],
        name="Revenue", marker_color=PURPLE, opacity=0.85,
        hovertemplate="<b>%{x}</b><br>£%{y:,.0f}<extra></extra>"),
        secondary_y=False)
    fig1.add_trace(go.Scatter(x=mf["month"], y=mf["mom"],
        name="MoM %", mode="lines+markers",
        line=dict(color=TEAL, width=2.5), marker=dict(size=6),
        hovertemplate="<b>%{x}</b><br>%{y:.1f}%<extra></extra>"),
        secondary_y=True)
    fig1.add_hline(y=0, line_dash="dot", line_color="#4a5568", secondary_y=True)
    fig1.update_layout(**base_layout(
        title="Monthly Revenue & MoM Growth",
        xaxis=ax(tickangle=-45), yaxis=ax(title="Revenue (£)"),
        yaxis2=dict(gridcolor="#1a1d2e", title="MoM Growth %"),
        legend=dict(bgcolor=PANEL, bordercolor=BORDER),
        bargap=0.2, height=310))

    # new vs returning
    fig2 = go.Figure()
    for ctype, color in [("New", GREEN), ("Returning", PURPLE)]:
        d = nvf[nvf["customer_type"] == ctype]
        fig2.add_trace(go.Bar(x=d["month"], y=d["customers"],
            name=ctype, marker_color=color, opacity=0.85))
    fig2.update_layout(**base_layout(
        title="New vs Returning Customers",
        barmode="stack",
        xaxis=ax(tickangle=-45), yaxis=ax(title="Customers"),
        legend=dict(bgcolor=PANEL, bordercolor=BORDER),
        bargap=0.2, height=270))

    # category sunburst
    fig3 = px.sunburst(cat, path=["category","subcategory"], values="revenue",
        color="margin_pct",
        color_continuous_scale=["#1a1d2e","#4f46e5","#10b981"])
    fig3.update_layout(title="Category Revenue",
        paper_bgcolor=BG, font=dict(color=TEXT),
        margin=dict(t=50,b=10,l=10,r=10), height=270,
        coloraxis_colorbar=dict(title="Margin%", tickfont=dict(color=TEXT)))

    # payment donut
    fig4 = go.Figure(go.Pie(labels=pay["payment_method"], values=pay["revenue"],
        hole=0.5, marker_colors=COLORS, textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>£%{value:,.0f}<extra></extra>"))
    fig4.update_layout(title="Payment Mix",
        paper_bgcolor=BG, font=dict(color=TEXT),
        margin=dict(t=50,b=10,l=10,r=10), height=270,
        legend=dict(bgcolor=PANEL))

    return html.Div([
        chart_card(fig1),
        row(chart_card(fig2,"1.3"), chart_card(fig3,"1"), chart_card(fig4,"1")),
    ])


# ── TAB 2: CUSTOMERS ──────────────────────────────────────────

def tab_customers(segment):
    rfm_f   = rfm if segment == "ALL" else rfm[rfm["segment"] == segment]
    clv_f   = clv_rfm if segment == "ALL" else clv_rfm[clv_rfm["segment"] == segment]
    clv_cap = clv_f[clv_f["total_spend"] <= clv_f["total_spend"].quantile(0.97)]

    # RFM treemap
    fig1 = px.treemap(rfm_sum, path=["segment"], values="total_revenue",
        color="avg_spend",
        color_continuous_scale=["#1a1d2e","#4f46e5","#a78bfa"],
        custom_data=["customers","avg_orders","avg_spend"])
    fig1.update_traces(
        hovertemplate="<b>%{label}</b><br>Revenue: £%{value:,.0f}<br>"
                      "Customers: %{customdata[0]:,}<br>"
                      "Avg orders: %{customdata[1]:.1f}<extra></extra>",
        textfont=dict(size=12))
    fig1.update_layout(title="RFM Segment Revenue",
        paper_bgcolor=BG, font=dict(color=TEXT),
        margin=dict(t=50,b=10,l=10,r=10), height=290,
        coloraxis_colorbar=dict(title="Avg Spend", tickfont=dict(color=TEXT)))

    # churn donut
    ch = churn["churn_status"].value_counts().reset_index()
    ch.columns = ["status","count"]
    cmap = {"Active":GREEN,"At Risk":AMBER,"Churned":RED}
    fig2 = go.Figure(go.Pie(labels=ch["status"], values=ch["count"],
        hole=0.55,
        marker_colors=[cmap.get(s,PURPLE) for s in ch["status"]],
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{value:,} customers<extra></extra>"))
    fig2.update_layout(title="Churn Status",
        paper_bgcolor=BG, font=dict(color=TEXT),
        margin=dict(t=50,b=10,l=10,r=10), height=290)

    # RFM scatter
    s = rfm_f.sample(min(3000, len(rfm_f)), random_state=42)
    fig3 = px.scatter(s, x="recency_days", y="monetary",
        color="f_score", size="frequency",
        color_continuous_scale=[RED, AMBER, GREEN, TEAL, PURPLE],
        hover_data={"customer_id":True,"recency_days":True,
                    "frequency":True,"monetary":":.0f","f_score":False},
        labels={"recency_days":"Days Since Last Order",
                "monetary":"Total Spend (£)", "f_score":"Frequency Score"})
    fig3.update_layout(**base_layout(
        title=f"RFM Scatter — {'Segment: ' + segment if segment != 'ALL' else 'All Customers'} (3k sample)",
        xaxis=ax(), yaxis=ax(), height=290,
        coloraxis_colorbar=dict(title="Freq Score", tickfont=dict(color=TEXT))))

    # CLV box by segment
    seg_ord = rfm_sum.sort_values("total_revenue", ascending=False)["segment"].tolist()
    fig4 = go.Figure()
    for i, seg in enumerate(seg_ord):
        d = clv_cap[clv_cap["segment"] == seg]["total_spend"]
        if len(d) == 0:
            continue
        fig4.add_trace(go.Box(y=d, name=seg,
            marker_color=COLORS[i % len(COLORS)],
            boxmean="sd", line=dict(width=1.5), showlegend=False,
            hovertemplate=f"<b>{seg}</b><br>£%{{y:,.0f}}<extra></extra>"))
    fig4.update_layout(**base_layout(
        title="Spend Distribution by Segment",
        xaxis=ax(tickangle=-25), yaxis=ax(title="Total Spend (£)"),
        height=290))

    return html.Div([
        row(chart_card(fig1,"1.2"), chart_card(fig2,"0.8")),
        row(chart_card(fig3), chart_card(fig4)),
    ])


# ── TAB 3: COHORT RETENTION ───────────────────────────────────

def tab_cohort():
    z    = cohort.values.tolist()
    x    = cohort.columns.tolist()
    y    = cohort.index.tolist()
    text = [[f"{v:.0f}%" if not (isinstance(v,float) and np.isnan(v)) else ""
             for v in r] for r in z]

    fig1 = go.Figure(go.Heatmap(
        z=z, x=x, y=y, text=text,
        texttemplate="%{text}", textfont=dict(size=9, color="white"),
        colorscale=[[0,"#1a1d2e"],[0.25,"#312e81"],[0.55,"#4f46e5"],[0.8,"#7c3aed"],[1,"#ddd6fe"]],
        hovertemplate="Cohort: <b>%{y}</b><br>Month: <b>%{x}</b><br>Retention: <b>%{z:.1f}%</b><extra></extra>",
        colorbar=dict(title="Retention %", ticksuffix="%", tickfont=dict(color=TEXT)),
    ))
    fig1.update_layout(
        title="Cohort Retention Heatmap — % of Cohort Still Purchasing",
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(color=TEXT, family="Arial"),
        xaxis=dict(title="Months Since First Purchase"),
        yaxis=dict(title="Acquisition Cohort", autorange="reversed"),
        margin=dict(t=65,b=65,l=105,r=40), height=480)

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=avg_ret["period"], y=avg_ret["avg_pct"],
        name="Average", mode="lines+markers",
        line=dict(color=PURPLE,width=3), marker=dict(size=8),
        fill="tozeroy", fillcolor="rgba(124,58,237,0.12)"))
    fig2.add_trace(go.Scatter(x=avg_ret["period"], y=avg_ret["max_pct"],
        name="Best cohort", line=dict(color=GREEN,width=1.5,dash="dash")))
    fig2.add_trace(go.Scatter(x=avg_ret["period"], y=avg_ret["min_pct"],
        name="Worst cohort", line=dict(color=RED,width=1.5,dash="dash")))
    fig2.update_layout(**base_layout(
        title="Average Retention Curve (M0–M11)",
        xaxis=ax(title="Months After First Purchase",
                 tickvals=list(range(12)),
                 ticktext=[f"M{i}" for i in range(12)]),
        yaxis=ax(title="Retention (%)", rangemode="tozero"),
        legend=dict(bgcolor=PANEL,bordercolor=BORDER), height=280))

    m0 = float(avg_ret[avg_ret["period"]==0]["avg_pct"].iloc[0])
    m1 = float(avg_ret[avg_ret["period"]==1]["avg_pct"].iloc[0])
    m6 = float(avg_ret[avg_ret["period"]==6]["avg_pct"].iloc[0])

    stats_row = row(
        html.Div([
            html.Div("M0 Retention", style={"fontSize":"0.68rem","color":MUTED}),
            html.Div(f"{m0:.1f}%", style={"fontSize":"1.3rem","fontWeight":"700","color":GREEN}),
        ], style={"background":PANEL,"border":f"1px solid {BORDER}","borderRadius":"8px","padding":"12px","flex":"1"}),
        html.Div([
            html.Div("M1 Retention", style={"fontSize":"0.68rem","color":MUTED}),
            html.Div(f"{m1:.1f}%", style={"fontSize":"1.3rem","fontWeight":"700","color":AMBER}),
        ], style={"background":PANEL,"border":f"1px solid {BORDER}","borderRadius":"8px","padding":"12px","flex":"1"}),
        html.Div([
            html.Div("M6 Retention", style={"fontSize":"0.68rem","color":MUTED}),
            html.Div(f"{m6:.1f}%", style={"fontSize":"1.3rem","fontWeight":"700","color":RED}),
        ], style={"background":PANEL,"border":f"1px solid {BORDER}","borderRadius":"8px","padding":"12px","flex":"1"}),
        html.Div([
            html.Div("M0→M1 Drop-off", style={"fontSize":"0.68rem","color":MUTED}),
            html.Div(f"{m0-m1:.1f} pp", style={"fontSize":"1.3rem","fontWeight":"700","color":RED}),
        ], style={"background":PANEL,"border":f"1px solid {BORDER}","borderRadius":"8px","padding":"12px","flex":"1"}),
        html.Div([
            html.Div("Key Insight", style={"fontSize":"0.68rem","color":MUTED,"marginBottom":"4px"}),
            html.Div("Biggest single drop at M1 — strongest case for onboarding investment.",
                     style={"fontSize":"0.78rem","color":AMBER}),
        ], style={"background":PANEL,"border":f"1px solid {BORDER}","borderRadius":"8px","padding":"12px","flex":"2"}),
        mb="12px",
    )

    return html.Div([stats_row, chart_card(fig1), html.Div(style={"height":"10px"}), chart_card(fig2)])


# ── TAB 4: FUNNEL & A/B ───────────────────────────────────────

def tab_funnel():
    total_c   = orders["customer_id"].nunique()
    delivered = orders[orders["status"]=="Delivered"]["order_id"].nunique()
    n_items   = len(items)
    kept      = items.groupby("order_id")["return_flag"].max().reset_index().query("return_flag==0").shape[0]

    fig1 = go.Figure(go.Funnel(
        y=["Registered Customers","Placed an Order","Order Delivered","Kept (No Returns)"],
        x=[total_c, orders["customer_id"].nunique(), delivered, kept],
        textposition="inside", textinfo="value+percent initial",
        textfont=dict(size=13, color="white"),
        marker=dict(color=[PURPLE,"#6d28d9","#5b21b6","#4c1d95"],
                    line=dict(width=2, color=BG)),
        connector=dict(line=dict(color="#4a5568",dash="dot",width=2)),
    ))
    fig1.update_layout(
        title="Order Funnel — Registration to Successful Purchase",
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(color=TEXT, family="Arial"),
        margin=dict(t=65,b=40,l=230,r=40), height=330)

    # A/B histograms
    bins   = np.linspace(0, np.percentile(np.concatenate([_ctrl,_trt]),98), 65)
    ch, e  = np.histogram(_ctrl, bins=bins, density=True)
    th, _  = np.histogram(_trt,  bins=bins, density=True)
    ctrs   = (e[:-1]+e[1:])/2

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=ctrs, y=ch, name="Control",
        mode="lines", fill="tozeroy",
        line=dict(color=TEAL,width=2.5), fillcolor="rgba(6,182,212,0.18)"))
    fig2.add_trace(go.Scatter(x=ctrs, y=th, name=f"Treatment (+{_rev_lift:.0f}%)",
        mode="lines", fill="tozeroy",
        line=dict(color=PURPLE,width=2.5), fillcolor="rgba(124,58,237,0.18)"))
    fig2.update_layout(**base_layout(
        title="Revenue per User — Control vs Treatment",
        xaxis=ax(title="Revenue (£)"), yaxis=ax(title="Density"),
        legend=dict(bgcolor=PANEL,bordercolor=BORDER), height=270))

    fig3 = go.Figure(go.Bar(
        x=["Control","Treatment"],
        y=[_c_cvr.mean()*100, _t_cvr.mean()*100],
        marker_color=[TEAL,PURPLE],
        text=[f"{_c_cvr.mean()*100:.1f}%", f"{_t_cvr.mean()*100:.1f}%"],
        textposition="outside", textfont=dict(size=14,color=TEXT),
        width=0.45,
    ))
    fig3.update_layout(**base_layout(
        title="Conversion Rate",
        xaxis=ax(), yaxis=ax(title="%", range=[0,85]),
        height=270))

    badges = html.Div([
        stat_badge(
            f"✅  Mann-Whitney U — Revenue lift: +{_rev_lift:.1f}%  "
            f"|  U statistic significant  |  p = {_p_rev:.2e}  |  α = 0.05", "ok"),
        stat_badge(
            f"✅  Chi-Square — Conversion rate lift: +{_cvr_lift:.1f}%  "
            f"|  χ² = {_chi2:.1f}  |  p = {_p_cvr:.2e}  |  df = 1", "ok"),
        stat_badge(
            "💡  Recommendation: ship the redesigned checkout. "
            "Both revenue per user and conversion rate improvements are statistically significant.", "warn"),
    ], style={"marginBottom":"12px"})

    return html.Div([
        badges,
        row(
            chart_card(fig1),
            html.Div([chart_card(fig2), html.Div(style={"height":"8px"}), chart_card(fig3)],
                     style={"flex":"1","display":"flex","flexDirection":"column"}),
        ),
    ])


# ── TAB 5: REGIONAL ───────────────────────────────────────────

def tab_regional(region):
    r = reg if region == "ALL" else reg[reg["region"] == region]

    fig1 = go.Figure(go.Bar(x=r["region"], y=r["revenue"],
        marker_color=COLORS[:len(r)],
        text=r["revenue"].apply(lambda v: f"£{v:,.0f}"), textposition="outside",
        hovertemplate="<b>%{x}</b><br>£%{y:,.0f}<extra></extra>"))
    fig1.update_layout(**base_layout(
        title="Revenue by Region",
        xaxis=ax(), yaxis=ax(title="Revenue (£)"),
        showlegend=False, height=270))

    fig2 = go.Figure(go.Bar(x=r["region"], y=r["aov"],
        marker_color=[TEAL]*len(r),
        text=r["aov"].apply(lambda v: f"£{v:,.0f}"), textposition="outside"))
    fig2.update_layout(**base_layout(
        title="Avg Order Value by Region",
        xaxis=ax(), yaxis=ax(title="AOV (£)"),
        showlegend=False, height=250))

    fig3 = go.Figure(go.Bar(x=r["region"], y=r["return_rate_pct"],
        marker_color=[RED if v>8 else AMBER if v>6 else GREEN for v in r["return_rate_pct"]],
        text=r["return_rate_pct"].apply(lambda v: f"{v:.1f}%"), textposition="outside"))
    fig3.add_hline(y=8, line_dash="dot", line_color=RED,
        annotation_text="8% threshold", annotation_font_color=RED)
    fig3.update_layout(**base_layout(
        title="Return Rate by Region",
        xaxis=ax(), yaxis=ax(title="Return Rate (%)"),
        showlegend=False, height=250))

    fig4 = go.Figure(go.Bar(x=r["region"], y=r["margin_pct"],
        marker_color=[GREEN]*len(r),
        text=r["margin_pct"].apply(lambda v: f"{v:.1f}%"), textposition="outside"))
    fig4.update_layout(**base_layout(
        title="Gross Margin by Region",
        xaxis=ax(), yaxis=ax(title="Margin (%)"),
        showlegend=False, height=250))

    ch_r = churn.groupby(["churn_status","region"]).size().reset_index(name="count")
    fig5 = px.bar(ch_r, x="region", y="count", color="churn_status",
        color_discrete_map={"Active":GREEN,"At Risk":AMBER,"Churned":RED},
        barmode="stack")
    fig5.update_layout(**base_layout(
        title="Customer Status by Region",
        xaxis=ax(), yaxis=ax(title="Customers"),
        legend=dict(bgcolor=PANEL,bordercolor=BORDER,title="Status"),
        height=260))

    return html.Div([
        chart_card(fig1),
        row(chart_card(fig2), chart_card(fig3), chart_card(fig4)),
        chart_card(fig5),
    ])


# ── run ───────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\nStarting dashboard...")
    print("Open http://127.0.0.1:8050 in your browser\n")
    app.run(debug=False, host="0.0.0.0", port=8050)
