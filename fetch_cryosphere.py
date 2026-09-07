import csv
import io
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

PROJECT = Path(__file__).resolve().parent
load_dotenv(PROJECT / ".env", interpolate=False)

DATA_URL = (
    "https://noaadata.apps.nsidc.org/NOAA/G02135/"
    "north/monthly/data/N_09_extent_v4.0.csv"
)
SOURCE_PAGE = "https://nsidc.org/data/g02135/versions/4"
SERIES_ID = "nsidc:arctic:september:extent:v4"
START_YEAR = 1979
END_YEAR = 2025

raw_folder = PROJECT / "Data" / "raw"
raw_folder.mkdir(parents=True, exist_ok=True)
cache_file = raw_folder / "nsidc_arctic_september_v4.json"

if cache_file.exists():
    saved = json.loads(cache_file.read_text(encoding="utf-8"))
    print("Using saved NSIDC download.")
else:
    print("Downloading NSIDC Arctic sea-ice data...")
    response = requests.get(DATA_URL, timeout=(10, 90))
    response.raise_for_status()

    reader = csv.DictReader(io.StringIO(response.text))
    headers = {
        name.strip() for name in (reader.fieldnames or [])
    }

    if not {"year", "mo", "region", "extent"}.issubset(headers):
        raise ValueError("Unexpected CSV columns; import stopped.")

    saved = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_url": DATA_URL,
        "csv": response.text,
    }

    cache_file.write_text(
        json.dumps(saved, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

by_year = {}

for original_row in csv.DictReader(io.StringIO(saved["csv"])):
    row = {
        key.strip(): value.strip()
        for key, value in original_row.items()
    }

    year = int(row["year"])

    if not START_YEAR <= year <= END_YEAR:
        continue

    if int(row["mo"]) != 9 or row["region"] != "N":
        raise ValueError("Unexpected month or hemisphere.")

    if year in by_year:
        raise ValueError(f"Duplicate year: {year}")

    value = float(row["extent"])

    # Negative values cannot represent sea-ice extent.
    if not math.isfinite(value) or value < 0:
        value = None

    by_year[year] = {
        "year": year,
        "month": 9,
        "value": value,
        "source_dataset": row.get("source_dataset"),
    }

records = [
    by_year.get(
        year,
        {
            "year": year,
            "month": 9,
            "value": None,
            "source_dataset": None,
        },
    )
    for year in range(START_YEAR, END_YEAR + 1)
]

available = [
    record for record in records
    if record["value"] is not None
]

if not available:
    raise ValueError("No usable sea-ice measurements found.")

document = {
    "_id": SERIES_ID,
    "name": "Arctic September mean sea-ice extent",
    "category": "Cryosphere",
    "source": "NSIDC Sea Ice Index",
    "version": "4",
    "region": "Arctic",
    "geographical_level": "polar region",
    "unit": "million square kilometres",
    "frequency": "one September monthly mean per year",
    "month": 9,
    "definition": (
        "September monthly mean sea-ice extent. Extent counts "
        "ocean grid-cell areas with at least 15% ice concentration."
    ),
    "interpretation": (
        "This is not annual minimum extent, ice volume, "
        "glacier area, or an India-level measurement."
    ),
    "source_url": saved["source_url"],
    "source_page": SOURCE_PAGE,
    "doi": "https://doi.org/10.7265/a98x-0f50",
    "citation": (
        "Fetterer, F., Knowles, K., Meier, W. N., Savoie, M., "
        "Windnagel, A. K. & Stafford, T. (2025). "
        "Sea Ice Index, Version 4. NSIDC. "
        "https://doi.org/10.7265/a98x-0f50. "
        "Subset: Arctic September extent, 1979–2025."
    ),
    "retrieved_at": saved["retrieved_at"],
    "requested_start_year": START_YEAR,
    "requested_end_year": END_YEAR,
    "available_year_count": len(available),
    "missing_year_count": len(records) - len(available),
    "latest_available": available[-1],
    "records": records,
}

with MongoClient(
    f"mongodb+srv://{os.environ['MONGO_HOST']}/",
    username=os.environ["MONGO_USERNAME"],
    password=os.environ["MONGO_PASSWORD"],
    authSource="admin",
    serverSelectionTimeoutMS=10000,
    socketTimeoutMS=20000,
) as client:
    database = client[os.environ["MONGO_DATABASE"]]
    database["cryosphere_indicators"].replace_one(
        {"_id": SERIES_ID},
        document,
        upsert=True,
    )

print(f"Saved {len(available)} September values.")
print("Missing years:", document["missing_year_count"])
print("Latest available:", document["latest_available"])
print("Cryosphere import completed.")