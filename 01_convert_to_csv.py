"""Step 1: Convert every sheet of every uploaded Ogaan .xlsx into a CSV (exact, as-is copy).

Run:  python 01_convert_to_csv.py [path/to/xlsx_folder]
Output: data/csv_raw/<file>__<sheet>.csv   (no cleaning here, headers/metadata rows kept)
"""
import re
import sys
from pathlib import Path

import pandas as pd

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/mnt/user-data/uploads")
OUT = Path("data/csv_raw")
OUT.mkdir(parents=True, exist_ok=True)


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")


count = 0
for f in sorted(SRC.glob("*.xlsx")):
    xl = pd.ExcelFile(f)
    for sheet in xl.sheet_names:
        df = xl.parse(sheet, header=None)          # header=None -> keep the file exactly as it is
        name = f"{slug(f.stem)}__{slug(sheet)}.csv" if len(xl.sheet_names) > 1 else f"{slug(f.stem)}.csv"
        df.to_csv(OUT / name, header=False, index=False)
        print(f"{f.name} [{sheet}] -> {OUT / name}  shape={df.shape}")
        count += 1
print(f"\nDone: {count} CSV files written to {OUT}/")
