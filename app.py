"""Ogaan analytics dashboard (Streamlit).

Run:  streamlit run app.py
Data: data/csv_clean/*.csv  (created by ogaan_eda.py / ogaan_eda.ipynb)
"""
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PURPLE, LIGHT, GREY = "#7c3aed", "#c4b5fd", "#6b6b6b"
DATA = Path(__file__).parent / "data" / "csv_clean"
TODAY = date.today()

st.set_page_config(page_title="Ogaan Analytics", page_icon="📊", layout="wide")
st.markdown(f"""
<style>
.block-container {{padding-top: 2rem; max-width: 1400px;}}
h1 {{font-weight: 700; margin-bottom: 0;}}
.sub {{color: {GREY}; margin: 0 0 1rem 0;}}
div[data-testid="stVerticalBlockBorderWrapper"] {{background:#fafafa; border-radius:16px;}}
.card-title {{font-size:1.05rem; margin-bottom:.4rem;}}
.kpi {{background:#fafafa; border:1px solid #e5e5e5; border-radius:14px; padding:14px 18px;}}
.kpi .l {{color:{GREY}; font-size:.8rem;}} .kpi .v {{font-size:1.6rem; font-weight:700; color:#111;}}
table.clean {{width:100%; border-collapse:collapse; font-size:.95rem;}}
table.clean th {{color:{GREY}; font-weight:500; text-align:left; padding:10px 6px; border-bottom:1px solid #e5e5e5;}}
table.clean td {{padding:10px 6px; border-bottom:1px solid #eee;}}
table.clean td.r, table.clean th.r {{text-align:right;}}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- helpers
@st.cache_data
def load(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / f"{name}.csv")


def inr(x) -> str:
    """Indian digit grouping: 1842788 -> ₹18,42,788"""
    s, neg = str(int(round(abs(x)))), x < 0
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:]); head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if neg else "") + "₹" + s


def num(x, d=0) -> str:
    return f"{x:,.{d}f}"


def kpi(col, label, value):
    col.markdown(f'<div class="kpi"><div class="l">{label}</div><div class="v">{value}</div></div>', unsafe_allow_html=True)


def card(title):
    c = st.container(border=True)
    c.markdown(f'<div class="card-title">{title}</div>', unsafe_allow_html=True)
    return c


def style(fig, h=340):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#444"), legend=dict(orientation="h", y=1.12))
    fig.update_xaxes(showgrid=True, gridcolor="#eee", griddash="dash")
    fig.update_yaxes(showgrid=True, gridcolor="#eee", griddash="dash")
    return fig


def date_header(title, subtitle, key, default_start, default_end, lo=None, hi=None):
    """Title on the left, date range + quick buttons on the right (like the reference dashboard)."""
    left, right = st.columns([3, 2])
    left.markdown(f"# {title}")
    left.markdown(f'<p class="sub">{subtitle}</p>', unsafe_allow_html=True)
    ks, ke = f"{key}_start", f"{key}_end"
    st.session_state.setdefault(ks, default_start)
    st.session_state.setdefault(ke, default_end)
    with right:
        d1, d2 = st.columns(2)
        s = d1.date_input("From", st.session_state[ks], key=f"{key}_in_s", min_value=lo, max_value=hi)
        e = d2.date_input("To", st.session_state[ke], key=f"{key}_in_e", min_value=lo, max_value=hi)
        b = st.columns(4)
        quick = {"Today": (TODAY, TODAY), "Yesterday": (TODAY - timedelta(1),) * 2,
                 "This week": (TODAY - timedelta(TODAY.weekday()), TODAY), "This month": (TODAY.replace(day=1), TODAY)}
        for col, (label, (qs, qe)) in zip(b, quick.items()):
            if col.button(label, key=f"{key}_{label}"):
                st.session_state[ks], st.session_state[ke] = qs, qe
                st.rerun()
    st.session_state[ks], st.session_state[ke] = s, e
    return pd.Timestamp(s), pd.Timestamp(e)


def clean_orders(df: pd.DataFrame) -> pd.DataFrame:
    """Accept a flexible orders export: needs date, designer, units/quantity, revenue/amount."""
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    alias = {"date": ["date", "order_date", "created_at"], "designer": ["designer", "designer_name", "brand"],
             "units": ["units", "quantity", "qty"], "revenue": ["revenue", "amount", "total", "gmv", "sales"]}
    for target, options in alias.items():
        found = next((o for o in options if o in df.columns), None)
        if found is None:
            raise ValueError(f"Missing column for '{target}' (one of {options})")
        df = df.rename(columns={found: target})
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["designer"] = df["designer"].fillna("Unattributed").replace("", "Unattributed")
    return df[["date", "designer", "units", "revenue"]].drop_duplicates()


# ---------------------------------------------------------------- pages
def page_sales():
    s, e = date_header("Sales overview", "Headline revenue trend and the designers driving it.", "sales",
                       date(2026, 9, 29), date(2026, 10, 29))
    up = st.sidebar.file_uploader("Orders CSV (date, designer, units, revenue)", type="csv")
    orders = None
    if up is not None:
        try:
            orders = clean_orders(pd.read_csv(up))
            orders = orders[(orders["date"] >= s) & (orders["date"] <= e)]
        except Exception as ex:  # noqa: BLE001
            st.sidebar.error(f"Could not read file: {ex}")

    with card("Revenue trend"):
        if orders is not None and len(orders):
            tr = orders.groupby("date", as_index=False)["revenue"].sum()
            full = pd.DataFrame({"date": pd.date_range(s, e)}).merge(tr, how="left", on="date").fillna({"revenue": 0})
            fig = go.Figure(go.Scatter(x=full["date"], y=full["revenue"], mode="lines", line=dict(color=PURPLE, width=3, shape="spline"),
                                       hovertext=[f"{d:%Y-%m-%d}<br>revenue : {inr(v)}" for d, v in zip(full["date"], full["revenue"])],
                                       hoverinfo="text"))
            st.plotly_chart(style(fig, 360))
        else:
            st.info("Daily revenue needs the order-level export, which is not in the GA files. "
                    "Upload an orders CSV in the sidebar (columns: date, designer, units, revenue) and this chart fills in.")

    if orders is not None and len(orders):
        des = orders.groupby("designer", as_index=False).agg(units=("units", "sum"), revenue=("revenue", "sum"))
        note = None
    else:
        des = load("sales_designers_snapshot")[["designer", "units", "revenue"]].rename(columns=str)
        note = "Showing the 29-Sep → 29-Oct-2026 snapshot transcribed from the reference dashboard (date filter not applied)."
    des = des.sort_values("revenue", ascending=False).head(10).reset_index(drop=True)

    c1, c2 = st.columns(2)
    with c1:
        with card("Top designers"):
            fig = go.Figure(go.Bar(x=des["designer"], y=des["revenue"], marker_color=PURPLE,
                                   hovertext=[f"{d}<br>{inr(v)}" for d, v in zip(des["designer"], des["revenue"])], hoverinfo="text"))
            st.plotly_chart(style(fig, 380))
    with c2:
        with card("Designer breakdown"):
            rows = "".join(f"<tr><td>{r.designer}</td><td>{int(r.units)}</td><td>{inr(r.revenue)}</td></tr>" for r in des.itertuples())
            st.markdown(f'<table class="clean"><tr><th>Designer</th><th>Units</th><th>Revenue</th></tr>{rows}</table>',
                        unsafe_allow_html=True)
    if note:
        st.caption(note)
    k = st.columns(4)
    kpi(k[0], "Revenue (top 10)", inr(des["revenue"].sum()))
    kpi(k[1], "Units", num(des["units"].sum()))
    kpi(k[2], "Avg price / unit", inr(des["revenue"].sum() / max(des["units"].sum(), 1)))
    kpi(k[3], "Top designer share", f"{des.loc[0, 'revenue'] / des['revenue'].sum() * 100:.1f}%")


def page_traffic():
    st.markdown("# Traffic & acquisition")
    st.markdown('<p class="sub">Where users come from and what they are worth · GA4 · 30-Sep → 27-Oct-2026.</p>', unsafe_allow_html=True)
    t = load("traffic_acquisition")
    ca = load("user_acquisition_cohorts")
    k = st.columns(5)
    kpi(k[0], "Sessions", num(t["sessions"].sum()))
    kpi(k[1], "Engagement rate", f"{t['engaged_sessions'].sum() / t['sessions'].sum() * 100:.1f}%")
    kpi(k[2], "Key events", num(t["key_events"].sum()))
    kpi(k[3], "Revenue (GA units)", num(t["total_revenue"].sum()))
    kpi(k[4], "Avg order value", num(t["total_revenue"].sum() / ca["transactions"].sum(), 0))
    st.write("")

    c1, c2 = st.columns(2)
    with c1:
        with card("Sessions vs revenue by channel"):
            fig = go.Figure()
            fig.add_bar(x=t["channel"], y=t["sessions"], name="Sessions", marker_color=LIGHT)
            fig.add_bar(x=t["channel"], y=t["total_revenue"], name="Revenue", marker_color=PURPLE)
            fig.update_layout(barmode="group")
            st.plotly_chart(style(fig))
    with c2:
        with card("Revenue per session"):
            fig = go.Figure(go.Bar(x=t["channel"], y=t["revenue_per_session"], marker_color=PURPLE,
                                   text=t["revenue_per_session"].round(2), textposition="outside"))
            st.plotly_chart(style(fig))
    st.warning("'Unassigned' shows 172 sessions with 0 engaged sessions yet 18+ min engagement time — an attribution/tracking gap, "
               "so its revenue-per-session is not trustworthy.")

    c3, c4 = st.columns(2)
    with c3:
        with card("Key events by platform"):
            p = load("platform_key_events")
            fig = go.Figure(go.Pie(labels=p["platform"], values=p["key_events"], hole=.55, marker=dict(colors=[PURPLE, LIGHT, "#4c1d95"])))
            st.plotly_chart(style(fig))
    with c4:
        with card("Channel table"):
            show = t[["channel", "sessions", "engagement_rate", "key_events", "session_key_event_rate", "total_revenue"]].copy()
            show["engagement_rate"] = (show["engagement_rate"] * 100).round(1).astype(str) + "%"
            show["session_key_event_rate"] = (show["session_key_event_rate"] * 100).round(1).astype(str) + "%"
            show["total_revenue"] = show["total_revenue"].round(0).astype(int)
            show.columns = ["Channel", "Sessions", "Engagement", "Key events", "Key event rate", "Revenue"]
            st.dataframe(show, hide_index=True)

    st.markdown("### Landing pages / screens")
    lp = load("landing_pages")
    ns = lp.loc[lp["landing_page"] == "(not set)", "sessions"].sum()
    st.warning(f"'(not set)' is {ns / lp['sessions'].sum() * 100:.0f}% of landing-page sessions — screen/page names are not being captured.")
    g = (lp[lp["page_group"] != "(not set)"].groupby("page_group", as_index=False)
         .agg(sessions=("sessions", "sum"), key_events=("key_events", "sum"), revenue=("total_revenue", "sum"))
         .sort_values("sessions"))
    c5, c6 = st.columns(2)
    with c5:
        with card("Sessions by page group (excl. not set)"):
            st.plotly_chart(style(go.Figure(go.Bar(y=g["page_group"], x=g["sessions"], orientation="h", marker_color=PURPLE))))
    with c6:
        with card("Top landing pages"):
            q = st.text_input("Search page", "")
            d = lp[lp["landing_page"].str.contains(q, case=False, regex=False)] if q else lp
            st.dataframe(d[["landing_page", "sessions", "key_events", "total_revenue"]].head(25), hide_index=True)


def page_users():
    daily = load("daily_users_leads")
    daily["date"] = pd.to_datetime(daily["date"])
    lo, hi = daily["date"].min().date(), daily["date"].max().date()
    s, e = date_header("Users & retention", "Daily audience, cohort retention, geography and the lead funnel.", "users", lo, hi, lo, hi)
    d = daily[(daily["date"] >= s) & (daily["date"] <= e)]
    if d.empty:
        st.info(f"No data in that range — GA data covers {lo:%d %b} → {hi:%d %b %Y}.")
        return
    k = st.columns(4)
    kpi(k[0], "New users", num(d["new_users"].sum()))
    kpi(k[1], "Returning users", num(d["returning_users"].sum()))
    kpi(k[2], "Avg daily users", num(d["total_users"].mean(), 1))
    kpi(k[3], "Peak day", f"{d.loc[d['total_users'].idxmax(), 'date']:%d %b} · {int(d['total_users'].max())}")
    st.write("")

    with card("Daily users"):
        fig = go.Figure()
        fig.add_scatter(x=d["date"], y=d["returning_users"], name="Returning", stackgroup="u", line=dict(color=LIGHT, shape="spline"))
        fig.add_scatter(x=d["date"], y=d["new_users"], name="New", stackgroup="u", line=dict(color=PURPLE, shape="spline"))
        fig.add_scatter(x=d["date"], y=d["ma7_total_users"], name="7-day avg", line=dict(color="#f59e0b", width=2))
        st.plotly_chart(style(fig))

    c1, c2 = st.columns(2)
    with c1:
        with card("Weekly retention (% of week-0 users)"):
            r = load("retention_cohorts")
            z = r[[f"w{i}_pct" for i in range(1, 6)]]
            fig = go.Figure(go.Heatmap(z=z.values, x=[f"Week {i}" for i in range(1, 6)], y=r["cohort_week"], colorscale="Purples",
                                       text=z.round(1).astype(str).replace("nan", ""), texttemplate="%{text}", showscale=False))
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(style(fig))
    with c2:
        with card("Active users by market"):
            c = load("cities")
            m = c.groupby("market", as_index=False)["active_users"].sum()
            fig = go.Figure(go.Pie(labels=m["market"], values=m["active_users"], hole=.55, marker=dict(colors=[PURPLE, LIGHT, "#4c1d95"])))
            st.plotly_chart(style(fig))

       with card("Top 10 cities"):
        top = c.groupby("metro", as_index=False)["active_users"].sum().sort_values("active_users", ascending=False).head(10)
        st.plotly_chart(style(go.Figure(go.Bar(x=top["metro"], y=top["active_users"], marker_color=PURPLE))))
    st.caption("Delhi and New Delhi are combined into one city (Delhi).")

    st.markdown("### Lead funnel")
    f = [int(d["new_users"].sum()), int(d["qualified_leads"].sum()), int(d["converted_leads"].sum())]
    st.plotly_chart(style(go.Figure(go.Funnel(y=["New users", "Qualified leads", "Converted leads"], x=f, marker=dict(color=PURPLE))), 260))
    if f[1] == 0:
        st.error("Qualified and converted leads are 0 on every day — the lead events are not being recorded in GA.")


def page_quality():
    st.markdown("# Data quality")
    st.markdown('<p class="sub">What was cleaned and what still needs fixing at source.</p>', unsafe_allow_html=True)
    st.markdown("### Issues log")
    st.dataframe(load("data_quality_log"), hide_index=True)
    st.markdown("### Cross-report reconciliation")
    st.dataframe(load("reconciliation"), hide_index=True)
    st.caption("Revenue reconciles in all reports; sessions and key events do not.")


PAGES = {"Sales overview": page_sales, "Traffic & acquisition": page_traffic, "Users & retention": page_users, "Data quality": page_quality}
st.sidebar.title("Ogaan")
PAGES[st.sidebar.radio("Dashboard", list(PAGES))]()
