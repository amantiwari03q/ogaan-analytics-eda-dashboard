# Ogaan analytics — EDA + Streamlit app

## Run order
1. `python 01_convert_to_csv.py /path/to/xlsx_folder`  → `data/csv_raw/` (13 CSVs, exact copy of every sheet)
2. `python ogaan_eda.py`  (or open `ogaan_eda.ipynb`) → cleaning + EDA, writes `data/csv_clean/` and `charts/`
3. `pip install -r requirements.txt` then `streamlit run app.py`

## Cleaning done
- Duplicate file: the two "Traffic acquisition" exports were identical → one kept.
- Duplicate key: landing page `(not set)` appeared twice → merged.
- GA metadata/footers stripped, numbers typed, snake_case columns, real dates added to the daily table.
- `Delhi`/`New Delhi` merged into one metro; cities tagged Delhi NCR / Rest of India / International (manual mapping).

## Important
- The dashboard screenshots show order-system revenue by designer, which is NOT in the GA files. The designer table is a transcribed
  snapshot (`sales_designers_snapshot.csv`). For the daily revenue trend and date filter, upload an orders CSV
  (see `data/orders_template.csv`) in the app sidebar.
- App was syntax/logic smoke-tested with stubs, not in a live Streamlit session.
