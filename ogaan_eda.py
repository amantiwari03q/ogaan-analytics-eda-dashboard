# %% [markdown]
# # Ogaan (`ogaan-trynbuy`) — Web/App Analytics: Data Cleaning + EDA
# **Data source:** Google Analytics 4 / Firebase exports (30-Sep-2026 → 27-Oct-2026), converted from `.xlsx` to CSV.
#
# **Flow:** 1) load raw CSVs → 2) data-quality audit → 3) cleaning (duplicates etc.) → 4) EDA & business insights → 5) save clean CSVs for the Streamlit app.

# %%
from pathlib import Path
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)
sns.set_theme(style="whitegrid")
PURPLE, PALETTE = "#7c3aed", ["#7c3aed", "#a78bfa", "#c4b5fd", "#4c1d95", "#f59e0b", "#10b981"]

RAW, CLEAN, CHARTS = Path("data/csv_raw"), Path("data/csv_clean"), Path("charts")
for p in (CLEAN, CHARTS):
    p.mkdir(parents=True, exist_ok=True)

def save(fig, name):
    fig.tight_layout()
    fig.savefig(CHARTS / f"{name}.png", dpi=140)
    plt.show()

dq = []  # data-quality log
def log(table, issue, detail, action):
    dq.append(dict(table=table, issue=issue, detail=detail, action=action))

# %% [markdown]
# ## 1. Load raw CSVs
# GA exports have a metadata block (Report / Account / Property / dates) above the real table and footnotes below it.
# `read_ga()` strips those and returns `(meta, table)`.

# %%
def to_num(df):
    for c in df.columns:
        conv = pd.to_numeric(df[c], errors="coerce")
        if conv.notna().sum() == df[c].notna().sum():
            df[c] = conv
    return df

def read_ga(stem):
    raw = pd.read_csv(RAW / f"{stem}.csv", header=None, dtype=str)
    meta = {}
    if raw.iloc[0, 0] == "Report":
        blank = raw.index[raw.isna().all(axis=1)][0]
        meta = {raw.iloc[i, 0]: raw.iloc[i, 1] for i in range(blank)}
        raw = raw.iloc[blank + 1:].reset_index(drop=True)
    header = raw.iloc[0].tolist()
    body = raw.iloc[1:].reset_index(drop=True)
    empty = body.index[body.isna().all(axis=1)]
    if len(empty):
        body = body.loc[: empty[0] - 1]          # drop footnotes after the first blank row
    body.columns = header
    return meta, to_num(body.reset_index(drop=True))

P = "Traffic_acquisition_Session_primary_channel_group_Default_channel_group_1"
FILES = dict(
    aud_summary="Audiences_Audience_name",
    daily="Generate_leads_overview__Daily_Users_Leads",
    platform="Generate_leads_overview__Platform",
    channel="Generate_leads_overview__Channel",
    retention="Generate_leads_overview__Retention",
    aud_active="Generate_leads_overview__Audiences",
    cities="Generate_leads_overview__Cities",
    sources="Generate_leads_overview__Sources",
    landing="Landing_page_Landing_page_1",
    traffic_a=P, traffic_b=P + "_1",
    user_acq="User_acquisition_First_user_primary_channel_group_Default_channel_group",
    cohorts="User_acquisition_cohorts_First_user_primary_channel_group_Default_channel_group",
)
meta, T = {}, {}
for k, stem in FILES.items():
    meta[k], T[k] = read_ga(stem)
    print(f"{k:12s} shape={T[k].shape}")
print("\nReport period:", meta["platform"]["Start date"], "→", meta["platform"]["End date"], "| property:", meta["platform"]["Property"])

# %% [markdown]
# ## 2. Data-quality audit

# %%
audit = pd.DataFrame({
    k: dict(rows=len(df), cols=df.shape[1], nulls=int(df.isna().sum().sum()),
            exact_dupe_rows=int(df.duplicated().sum()),
            dupe_keys=int(df.iloc[:, 0].duplicated().sum()))
    for k, df in T.items()
}).T
print(audit)

# %%
# 2a. The two "Traffic acquisition" files — are they the same export downloaded twice?
a = pd.read_csv(RAW / f"{FILES['traffic_a']}.csv", header=None)
b = pd.read_csv(RAW / f"{FILES['traffic_b']}.csv", header=None)
same = a.equals(b)
print("Traffic acquisition file 1 == file 2 :", same)
if same:
    log("traffic_acquisition", "Duplicate file", "Two uploaded files are 100% identical", "Kept one, dropped the other")

# 2b. Duplicate dimension values inside a table (landing page)
dupes = T["landing"][T["landing"]["Landing page"].duplicated(keep=False)]
print("\nLanding-page keys appearing more than once:")
print(dupes)
log("landing_pages", "Duplicate key '(not set)'", "Appears twice with different metric values (GA splits it by screen class/page title)",
    "Merged into one row: sums for sessions/new users/key events/revenue, session-weighted averages for rates, max() for active users (lower bound)")

# %%
# 2c. Cross-file reconciliation — numbers that *should* agree
tr = T["traffic_a"]
recon = pd.DataFrame({
    "Sessions": {"Audiences file": T["aud_summary"].loc[0, "Sessions"], "Traffic acquisition": tr["Sessions"].sum(),
                 "Landing page": T["landing"]["Sessions"].sum()},
    "Key events": {"Audiences file": np.nan, "Traffic acquisition": tr["Key events"].sum(),
                   "Landing page": T["landing"]["Key events"].sum()},
    "Revenue": {"Audiences file": T["aud_summary"].loc[0, "Total revenue"], "Traffic acquisition": tr["Total revenue"].sum(),
                "Landing page": T["landing"]["Total revenue"].sum()},
}).round(2)
recon.loc["Platform report (key events)", "Key events"] = T["platform"]["Key events"].sum()
print(recon)
log("cross-file", "Sessions don't reconcile", f"2,115 (audiences) vs {int(tr['Sessions'].sum()):,} (channels) vs {int(T['landing']['Sessions'].sum()):,} (landing pages)",
    "Flagged only — different GA reports use different session attribution/thresholding; revenue DOES reconcile (10,078.49) in all 3")
log("cross-file", "Key events don't reconcile", "408 (channels = platform) vs 430 (landing page)", "Flagged only")

# %%
# 2d. Logical inconsistencies
print(tr[["Session primary channel group (Default channel group)", "Sessions", "Engaged sessions", "Engagement rate",
          "Average engagement time per session"]])
log("traffic_acquisition", "'Unassigned' has 0 engaged sessions but ~1,097 s engagement time",
    "172 sessions, engagement rate = 0% yet avg engagement time > 18 min", "Flagged — likely tracking/attribution bug (sessions with no session_start / source)")
ua = T["user_acq"]
log("user_acquisition", "New + Returning ≠ Total users", "e.g. Direct: 293 + 263 = 556 vs 512 total (GA counts users in both buckets over the period)", "Kept as-is; do not add the two")
n_cities, sum_city = len(T["cities"]), int(T["cities"]["Active users"].sum())
log("cities", "City users add up to more than active users", f"Σ city active users = {sum_city} vs 586 'All Users' — users seen in >1 city", "Flagged; city table used only for ranking/share, not totals")
leads = T["daily"]
print("\nQualified leads total:", leads["Qualified leads"].sum(), "| Converted leads total:", leads["Converted leads"].sum())
log("daily_users_leads", "Lead events never fire", "Qualified leads = 0 and Converted leads = 0 on all 28 days", "Flagged — 'Generate leads' funnel is untracked; fix GA event setup before reporting lead KPIs")

# %% [markdown]
# ## 3. Cleaning → tidy tables

# %%
def snake(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

def tidy(df, first=None):
    df = df.copy()
    df.columns = [snake(c) for c in df.columns]
    if first:
        df = df.rename(columns={df.columns[0]: first})
    return df

# --- Daily users & leads (add real dates: day 0 = report start date)
start = pd.to_datetime(meta["platform"]["Start date"], format="%d-%b-%Y")
daily = tidy(T["daily"])
daily["date"] = start + pd.to_timedelta(daily["nth_day"], unit="D")
daily["total_users"] = daily["new_users"] + daily["returning_users"]
daily["new_user_share"] = (daily["new_users"] / daily["total_users"]).round(4)
daily["weekday"] = daily["date"].dt.day_name()
daily["ma7_total_users"] = daily["total_users"].rolling(7).mean().round(2)
daily = daily[["date", "nth_day", "weekday", "new_users", "returning_users", "total_users", "new_user_share",
               "ma7_total_users", "qualified_leads", "converted_leads"]]

# --- small dimension tables
platform = tidy(T["platform"], "platform")
channel_new = tidy(T["channel"], "channel")
sources = tidy(T["sources"], "source")
aud_active = tidy(T["aud_active"], "audience")
aud_summary = tidy(T["aud_summary"], "audience")
aud_summary["conversion_rate_pct"] = (aud_summary["total_users"] / aud_summary.loc[0, "total_users"] * 100).round(2)

# --- retention (cohort counts -> % of week-0)
ret = tidy(T["retention"], "cohort_week")
for w in range(1, 6):
    ret[f"w{w}_pct"] = (ret[f"week_{w}"] / ret["week_0"] * 100).round(1)

# --- traffic (duplicate file already dropped: only traffic_a is used)
traffic = tidy(T["traffic_a"], "channel")
traffic["session_share_pct"] = (traffic["sessions"] / traffic["sessions"].sum() * 100).round(1)
traffic["revenue_per_session"] = (traffic["total_revenue"] / traffic["sessions"]).round(2)
traffic["key_events_per_session"] = (traffic["key_events"] / traffic["sessions"]).round(3)

user_acq = tidy(T["user_acq"], "channel")
cohorts = tidy(T["cohorts"], "channel")
cohorts["revenue_per_new_user"] = (cohorts["total_revenue"] / cohorts["new_users"].replace(0, np.nan)).round(2)
cohorts["avg_order_value"] = (cohorts["total_revenue"] / cohorts["transactions"].replace(0, np.nan)).round(2)

# --- landing pages: merge duplicate '(not set)', add page group + template
lp = tidy(T["landing"], "landing_page")
lp["_eng_w"] = lp["average_engagement_time_per_session"] * lp["sessions"]
lp["_rate_w"] = lp["session_key_event_rate"] * lp["sessions"]
before = len(lp)
lp = (lp.groupby("landing_page", sort=False)
        .agg(sessions=("sessions", "sum"), active_users=("active_users", "max"), new_users=("new_users", "sum"),
             key_events=("key_events", "sum"), total_revenue=("total_revenue", "sum"),
             _eng_w=("_eng_w", "sum"), _rate_w=("_rate_w", "sum"))
        .reset_index())
lp["average_engagement_time_per_session"] = (lp["_eng_w"] / lp["sessions"]).round(2)
lp["session_key_event_rate"] = (lp["_rate_w"] / lp["sessions"]).round(4)
lp = lp.drop(columns=["_eng_w", "_rate_w"])
print(f"Landing pages: {before} rows -> {len(lp)} after merging duplicates")

def page_group(p):
    if p == "(not set)": return "(not set)"
    if p in ("/", "/home"): return "Home"
    for prefix, name in [("/orders", "Orders"), ("/products", "Product detail"), ("/designers", "Designers"),
                         ("/categories", "Categories"), ("/onboarding", "Onboarding"), ("/profile", "Profile"),
                         ("/checkout", "Checkout"), ("/favorites", "Favorites")]:
        if p.startswith(prefix): return name
    return "Other"

lp["page_group"] = lp["landing_page"].map(page_group)
lp["page_template"] = lp["landing_page"].str.replace(r"/\d+", "/:id", regex=True)
lp = lp.sort_values("sessions", ascending=False).reset_index(drop=True)

# --- cities: market classification (manual mapping — assumption, documented)
NCR = {"Delhi", "New Delhi", "Gurugram", "Noida", "Ghaziabad", "Faridabad", "Greater Noida", "Sonipat", "Sohna"}
INTL = {"Dubai", "Singapore", "Atlanta", "Los Altos", "Reston", "Riyadh", "Bangkok", "Melbourne", "Mountain View", "New York",
        "Sydney", "Abu Dhabi", "Ajman", "Calpella", "Cupertino", "Hamilton", "Los Altos Hills", "Los Angeles", "San Francisco",
        "Santa Clara", "Seattle", "Sharjah", "Sunnyvale", "Addison", "Adelaide", "Al Farwaniyah", "Asuncion", "Auckland",
        "Bedford", "Bellevue", "Boston", "Buraydah", "Caledon", "Campbell", "Charlotte", "Chicago", "Columbia", "Cork", "Dhaka",
        "Dibba Al-Fujairah", "Foster City", "Fremont", "Fresno", "Gurnee", "Hong Kong", "Jeddah", "Jersey City", "Kathmandu",
        "Ladera Ranch", "Langley Township", "Lewisville", "Livingston", "London", "London Colney", "Madrid", "McKinney",
        "Middletown", "Monroe Township", "Muscat", "Oakland", "Perris", "Plainfield", "Plainview", "Plano", "Prague", "Salmiya",
        "Salt Lake City", "San Diego", "San Jose", "San Mateo", "Saratoga", "Shizuoka", "Spokane", "St Albans", "Stewartby",
        "Villa Carlos Paz"}
cities = tidy(T["cities"], "city")
cities["market"] = np.where(cities["city"].isin(NCR), "Delhi NCR", np.where(cities["city"].isin(INTL), "International", "Rest of India"))
cities["metro"] = cities["city"].replace({"New Delhi": "Delhi"})
log("cities", "'Delhi' and 'New Delhi' are the same metro", "121 + 85 users listed under two names", "Added `metro` column merging them; also added `market` (Delhi NCR / Rest of India / International) — manual mapping")

# %%
# 3b. sanity checks after cleaning
assert not traffic["channel"].duplicated().any() and not lp["landing_page"].duplicated().any()
assert cities["city"].is_unique
assert daily["date"].max() == pd.to_datetime(meta["platform"]["End date"], format="%d-%b-%Y"), "date mapping is off"
assert daily["new_users"].sum() == aud_summary.loc[0, "new_users"], "daily new users should equal Audiences new users"
print("All cleaning checks passed ✔")

# %% [markdown]
# ## 4. EDA & business insights
# ### 4.1 Headline KPIs

# %%
tot_sessions, tot_rev = traffic["sessions"].sum(), traffic["total_revenue"].sum()
tot_users, purchasers = aud_summary.loc[0, "total_users"], aud_summary.loc[1, "total_users"]
transactions = cohorts["transactions"].sum()
kpi = pd.Series({
    "Total users": tot_users, "New users": aud_summary.loc[0, "new_users"], "Sessions (channel report)": tot_sessions,
    "Engagement rate %": round(traffic["engaged_sessions"].sum() / tot_sessions * 100, 1),
    "Key events": traffic["key_events"].sum(), "Revenue (GA units)": round(tot_rev, 2),
    "Purchasers": purchasers, "User→purchaser %": round(purchasers / tot_users * 100, 2),
    "Transactions (120d cohorts)": transactions, "Avg order value": round(tot_rev / transactions, 1),
    "Revenue per purchaser": round(tot_rev / purchasers, 1), "Revenue per session": round(tot_rev / tot_sessions, 2),
})
print(kpi.to_string())

# %% [markdown]
# ### 4.2 Daily users — growth, new vs returning, weekday pattern

# %%
fig, ax = plt.subplots(1, 2, figsize=(14, 4.5), gridspec_kw={"width_ratios": [2.2, 1]})
ax[0].stackplot(daily["date"], daily["returning_users"], daily["new_users"], labels=["Returning", "New"], colors=["#c4b5fd", PURPLE], alpha=.9)
ax[0].plot(daily["date"], daily["ma7_total_users"], color="#f59e0b", lw=2.2, label="7-day avg (total)")
ax[0].set_title("Daily users: new vs returning"); ax[0].legend(loc="upper left"); ax[0].tick_params(axis="x", rotation=30)
wd = daily.groupby("weekday")["total_users"].mean().reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
ax[1].bar(wd.index.str[:3], wd.values, color=PURPLE); ax[1].set_title("Avg users by weekday")
save(fig, "01_daily_users")

h1, h2 = daily.iloc[:14]["total_users"].mean(), daily.iloc[14:]["total_users"].mean()
print(f"Avg daily users: first 14 days = {h1:.1f}, last 14 days = {h2:.1f}  ({(h2 / h1 - 1) * 100:+.0f}%)")
print(f"New-user share overall: {daily['new_users'].sum() / daily['total_users'].sum() * 100:.0f}% | best day: "
      f"{daily.loc[daily['total_users'].idxmax(), 'date']:%d %b} ({daily['total_users'].max()} users) | best weekday: {wd.idxmax()}")

# %% [markdown]
# ### 4.3 Channel performance — quantity vs quality

# %%
view = traffic[["channel", "sessions", "session_share_pct", "engagement_rate", "average_engagement_time_per_session",
                "key_events", "session_key_event_rate", "total_revenue", "revenue_per_session"]]
print(view.to_string(index=False))

fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
ax[0].bar(traffic["channel"], traffic["sessions"], color=PALETTE[:3]); ax[0].set_title("Sessions")
ax[1].bar(traffic["channel"], traffic["total_revenue"], color=PALETTE[:3]); ax[1].set_title("Revenue (GA units)")
ax[2].bar(traffic["channel"], traffic["revenue_per_session"], color=PALETTE[:3]); ax[2].set_title("Revenue per session")
save(fig, "02_channels")

d, o = traffic.set_index("channel").loc["Direct"], traffic.set_index("channel").loc["Organic Search"]
print(f"\nDirect = {d.session_share_pct}% of sessions but only {d.total_revenue / tot_rev * 100:.0f}% of revenue; "
      f"Organic Search = {o.session_share_pct}% of sessions but {o.total_revenue / tot_rev * 100:.0f}% of revenue "
      f"({o.revenue_per_session / d.revenue_per_session:.1f}x revenue/session, {o.average_engagement_time_per_session / d.average_engagement_time_per_session:.1f}x engagement time).")

# %% [markdown]
# ### 4.4 Platform, sources, audiences

# %%
fig, ax = plt.subplots(1, 3, figsize=(15, 4))
ax[0].pie(platform["key_events"], labels=platform["platform"], autopct="%1.0f%%", colors=PALETTE, startangle=90); ax[0].set_title("Key events by platform")
ax[1].bar(sources["source"], sources["sessions"], color=PALETTE[:2]); ax[1].set_title("Organic sessions by source")
ax[2].bar(aud_summary["audience"], aud_summary["total_users"], color=PALETTE[:2]); ax[2].set_title("All users vs purchasers")
save(fig, "03_platform_sources_audience")
print(aud_summary.to_string(index=False))
print(f"\nPurchasers: {purchasers} of {tot_users} users ({purchasers / tot_users * 100:.1f}%); only 1 was a NEW user → buyers are almost all returning users.")
print(f"Purchasers see {aud_summary.loc[1, 'views_per_session']:.0f} views/session vs {aud_summary.loc[0, 'views_per_session']:.0f} for all users "
      f"and stay {aud_summary.loc[1, 'average_session_duration'] / aud_summary.loc[0, 'average_session_duration']:.1f}x longer.")

# %% [markdown]
# ### 4.5 Retention cohorts

# %%
weeks = [f"week_{i}" for i in range(6)]
heat = ret[[f"w{i}_pct" for i in range(1, 6)]]; heat.index = ret["cohort_week"]
fig, ax = plt.subplots(figsize=(8, 3.8))
sns.heatmap(heat, annot=True, fmt=".1f", cmap="Purples", cbar_kws={"label": "% of week-0 users"}, ax=ax)
ax.set_title("Weekly retention by cohort (% of week-0)"); ax.set_ylabel("")
save(fig, "04_retention")

wavg = {w: ret.loc[ret[f"week_{w}"].notna(), f"week_{w}"].sum() / ret.loc[ret[f"week_{w}"].notna(), "week_0"].sum() * 100 for w in range(1, 6)}
print("Weighted avg retention:", {f"W{k}": f"{v:.1f}%" for k, v in wavg.items()})

# %% [markdown]
# ### 4.6 Geography

# %%
mk = cities.groupby("market")["active_users"].sum().sort_values(ascending=False)
top = cities.groupby("metro")["active_users"].sum().sort_values(ascending=False).head(10)[::-1]
fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
ax[0].pie(mk.values, labels=mk.index, autopct="%1.0f%%", colors=PALETTE, startangle=90); ax[0].set_title("Active users by market")
ax[1].barh(top.index, top.values, color=PURPLE); ax[1].set_title("Top 10 metros")
save(fig, "05_geography")
print((mk / mk.sum() * 100).round(1).to_string())
print(f"\n{cities['city'].nunique()} cities, {(cities['active_users'] == 1).sum()} with a single user (long tail).")

# %% [markdown]
# ### 4.7 Landing pages / screens

# %%
grp = (lp.groupby("page_group")
         .agg(sessions=("sessions", "sum"), key_events=("key_events", "sum"), revenue=("total_revenue", "sum"), pages=("landing_page", "count"))
         .sort_values("sessions", ascending=False))
print(grp)
ns = lp.loc[lp["landing_page"] == "(not set)", "sessions"].sum()
print(f"\n'(not set)' = {ns / lp['sessions'].sum() * 100:.0f}% of sessions → landing-page report is almost useless until screen/page tracking is fixed.")
fig, ax = plt.subplots(figsize=(8, 4))
g2 = grp.drop(index="(not set)")
ax.barh(g2.index[::-1], g2["sessions"][::-1], color=PURPLE); ax.set_title("Sessions by page group (excl. '(not set)')")
save(fig, "06_landing_groups")

# %% [markdown]
# ### 4.8 Lead funnel

# %%
print("New users:", int(daily["new_users"].sum()), "→ Qualified leads:", int(daily["qualified_leads"].sum()), "→ Converted leads:", int(daily["converted_leads"].sum()))
print("⚠ The 'Generate leads' funnel records nothing — either no lead events are configured or they are not firing.")

# %% [markdown]
# ### 4.9 Sales dashboard snapshot (transcribed from the reference screenshot, 29-Sep → 29-Oct-2026)
# The two screenshots contain **order-system** numbers (revenue by designer) that are *not* in the GA files, so they are typed in here as a snapshot.

# %%
sales = pd.DataFrame({
    "designer": ["Anamika Khanna", "Nidhi Tholia", "PAYAL KHANDWALA", "LAJJOO", "Divya Sheth", "Pero", "Debyani", "Unattributed", "REIK", "Dareaab"],
    "units": [46, 25, 62, 37, 16, 26, 16, 19, 15, 7],
    "revenue": [9661940, 3135700, 3075150, 2418600, 1870300, 1700400, 1638000, 1482260, 1120500, 968500],
})
sales["avg_price_per_unit"] = (sales["revenue"] / sales["units"]).round(0)
sales["revenue_share_pct"] = (sales["revenue"] / sales["revenue"].sum() * 100).round(1)
sales["cum_share_pct"] = (sales["revenue"].cumsum() / sales["revenue"].sum() * 100).round(1)
print(sales.to_string(index=False))
print(f"\nTop-10 revenue = ₹{sales['revenue'].sum():,}  |  units = {sales['units'].sum()}  |  top designer share = {sales.loc[0, 'revenue_share_pct']}%")
print(f"GA records only {int(transactions)} transactions vs {sales['units'].sum()} units in the order system → GA e-commerce tracking is likely incomplete.")

fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(sales["designer"], sales["revenue"], color=PURPLE); ax.tick_params(axis="x", rotation=45); ax.set_title("Revenue by designer (₹)")
for t in ax.get_xticklabels(): t.set_ha("right")
save(fig, "07_designers")

# %% [markdown]
# ## 5. Save clean CSVs (used by the Streamlit app)

# %%
out = {"daily_users_leads": daily, "platform_key_events": platform, "channel_new_users": channel_new, "sources": sources,
       "audiences_active_users": aud_active, "audiences_summary": aud_summary, "retention_cohorts": ret,
       "traffic_acquisition": traffic, "user_acquisition": user_acq, "user_acquisition_cohorts": cohorts,
       "landing_pages": lp, "cities": cities, "sales_designers_snapshot": sales,
       "data_quality_log": pd.DataFrame(dq), "reconciliation": recon.reset_index().rename(columns={"index": "source"})}
for name, df in out.items():
    df.to_csv(CLEAN / f"{name}.csv", index=False)
print(f"{len(out)} clean CSVs saved to {CLEAN}/")
print(pd.DataFrame(dq)[["table", "issue"]].to_string(index=False))
