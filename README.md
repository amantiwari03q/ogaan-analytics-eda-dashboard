# Ogaan Analytics: EDA + Streamlit Dashboard

End-to-end analysis of **Ogaan's** (`ogaan-trynbuy`) Google Analytics 4 / Firebase exports for **30 Sep 2026 to 27 Oct 2026**: Excel to CSV conversion, data cleaning, exploratory data analysis, and an interactive Streamlit dashboard.

**Live app:** _add your Streamlit Cloud link here_

---

## Project overview

Ogaan is an Indian designer-wear platform. The raw data came as 9 Excel exports (13 sheets) from GA4/Firebase covering traffic, acquisition, retention, geography, landing pages, audiences and a lead funnel. The goal was to clean it, find what is working and what is broken, and present it in a dashboard that business users can explore.

## What this project does

1. **Converts** every Excel sheet into CSV (`01_convert_to_csv.py`)
2. **Audits and cleans** the data (`ogaan_eda.py` / `ogaan_eda.ipynb`)
3. **Analyses** channels, daily users, retention cohorts, geography, landing pages and the lead funnel
4. **Serves** the results in a multi-page Streamlit dashboard (`app.py`)

## Data cleaning

| Issue found | Action |
|---|---|
| Two "Traffic acquisition" files were 100% identical | Kept one, dropped the duplicate |
| Landing page `(not set)` appeared twice | Merged into one row (sums for counts, session-weighted averages for rates) |
| GA exports include metadata rows and footnotes above and below the table | Stripped, numbers converted to numeric types, columns renamed to snake_case |
| Daily table only had "Nth day" | Converted to real dates using the report start date |
| `Delhi` and `New Delhi` listed as separate cities | Combined into one city for the Top 10 chart |
| Cities had no grouping | Added a `market` column (Delhi NCR / Rest of India / International), mapped manually |

## Key findings

- **Organic Search is the highest-quality channel:** 28% of sessions but 47% of revenue, which is 4.4x the revenue per session of Direct traffic.
- **Direct traffic is high volume, low value:** 64% of sessions but only 24% of revenue.
- **Few buyers:** 11 purchasers out of 604 users (1.8%), and only 1 of them was a new user.
- **Audience is growing:** average daily users in the last 14 days were 27% higher than in the first 14 days.
- **Retention:** about 13.6% of users return in week 1.
- **Lead tracking looks broken:** qualified and converted leads are 0 on all 28 days.
- **Page tracking is incomplete:** 88% of landing-page sessions are `(not set)`.
- **Reports disagree:** sessions differ across reports (2,115 / 2,128 / 2,263). Revenue reconciles in all of them.
- **E-commerce tracking gap (likely):** GA records 38 transactions, while the order system shows 269 units sold in a similar period.

## Dashboard pages

| Page | What it shows |
|---|---|
| **Sales overview** | Revenue trend, top designers, designer breakdown table, date range filter |
| **Traffic & acquisition** | Channel performance, revenue per session, platform split, landing page groups |
| **Users & retention** | Daily new vs returning users, retention heatmap, market split, top 10 cities, lead funnel |
| **Data quality** | Log of every issue found and a cross-report reconciliation table |

## Tech stack

Python, Pandas, NumPy, Matplotlib, Seaborn, Plotly, Streamlit

## Project structure

```
.
├── app.py                    # Streamlit dashboard
├── ogaan_eda.py              # Cleaning + EDA script
├── ogaan_eda.ipynb           # Same analysis as a notebook
├── 01_convert_to_csv.py      # Excel to raw CSV converter
├── requirements.txt
├── charts/                   # Charts saved by the EDA
└── data/
    ├── csv_raw/              # Exact CSV copies of every Excel sheet
    ├── csv_clean/            # Cleaned tables used by the app
    └── orders_template.csv   # Format for uploading order data
```

## How to run locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Rebuild the clean data from the Excel exports
python 01_convert_to_csv.py path/to/excel_folder
python ogaan_eda.py

# 3. Start the dashboard
streamlit run app.py
```

The app reads from `data/csv_clean/`, which is already included, so step 2 is only needed if the source data changes. Run all commands from the project root folder.

## Important notes

- **Sales data:** the designer sales table comes from a reference dashboard screenshot (29 Sep to 29 Oct 2026), because order-level data was not part of the GA exports. To see the daily revenue trend with the date filter, upload an orders CSV in the app sidebar (columns: `date, designer, units, revenue`). See `data/orders_template.csv`.
- **Currency:** GA revenue is in the GA property's currency, which is not stated in the exports. Do not compare it directly with the rupee figures from the sales dashboard.
- **Market grouping:** the Delhi NCR / Rest of India / International mapping was done manually and may need review.

