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

BASE_URL = "https://raw.githubusercontent.com/owid/co2-data/master"
DATA_URL = f"{BASE_URL}/owid-co2-data.csv"
CODEBOOK_URL = f"{BASE_URL}/owid-co2-codebook.csv"

FIELDS = ["co2", "co2_per_capita"]
START_YEAR = 1990
END_YEAR = 2025

raw_folder = PROJECT / "Data" / "raw"
raw_folder.mkdir(parents=True, exist_ok=True)
cache_file = raw_folder / "owid_carbon_india_1990_2025.json"

if cache_file.exists():
    saved = json.loads(cache_file.read_text(encoding="utf-8"))
    print("Using saved India carbon data.")
else:
    print("Downloading the OWID carbon dataset...")

    response = requests.get(DATA_URL, timeout=(10, 120))
    response.raise_for_status()
    reader = csv.DictReader(io.StringIO(response.text))

    required_columns = {"iso_code", "year", *FIELDS}
    if not required_columns.issubset(reader.fieldnames or []):
        raise ValueError("The downloaded CSV has unexpected columns.")

    # Preserve the original India rows for the selected period.
    india_rows = [
        row for row in reader
        if row["iso_code"] == "IND"
        and START_YEAR <= int(row["year"]) <= END_YEAR
    ]

    if not india_rows:
        raise ValueError("No India records found.")

    metadata_response = requests.get(
        CODEBOOK_URL, timeout=(10, 60)
    )
    metadata_response.raise_for_status()

    metadata = {
        row["column"]: row
        for row in csv.DictReader(
            io.StringIO(metadata_response.text)
        )
        if row["column"] in FIELDS
    }

    for field in FIELDS:
        if field not in metadata or not metadata[field].get("unit"):
            raise ValueError(f"Missing definition or unit: {field}")

    saved = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_url": DATA_URL,
        "codebook_url": CODEBOOK_URL,
        "rows": india_rows,
        "metadata": metadata,
    }

    cache_file.write_text(
        json.dumps(saved, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("India source rows and definitions saved.")

by_year = {int(row["year"]): row for row in saved["rows"]}

with MongoClient(
    f"mongodb+srv://{os.environ['MONGO_HOST']}/",
    username=os.environ["MONGO_USERNAME"],
    password=os.environ["MONGO_PASSWORD"],
    authSource="admin",
    serverSelectionTimeoutMS=10000,
    socketTimeoutMS=20000,
) as client:
    database = client[os.environ["MONGO_DATABASE"]]
    collection = database["carbon_indicators"]

    for field in FIELDS:
        records = []

        for year in range(START_YEAR, END_YEAR + 1):
            raw_value = by_year.get(year, {}).get(field, "")
            value = float(raw_value) if raw_value else None

            if value is not None and not math.isfinite(value):
                raise ValueError(f"Invalid value for {field}, {year}")

            records.append({"year": year, "value": value})

        available = [
            record for record in records
            if record["value"] is not None
        ]

        if not available:
            raise ValueError(f"No usable values for {field}")

        definition = saved["metadata"][field]

        document = {
            "_id": f"owid:IND:{field}",
            "indicator_code": field,
            "name": definition["title"],
            "category": "Carbon & Climate",
            "country": {"code": "IND", "name": "India"},
            "geographical_level": "country",
            "frequency": "annual",
            "unit": definition["unit"],
            "definition": definition["description"],
            "source": "Our World in Data",
            "underlying_source": definition["source"],
            "source_url": saved["source_url"],
            "codebook_url": saved["codebook_url"],
            "retrieved_at": saved["retrieved_at"],
            "requested_start_year": START_YEAR,
            "requested_end_year": END_YEAR,
            "available_year_count": len(available),
            "missing_year_count": len(records) - len(available),
            "latest_available": available[-1],
            "records": records,
        }

        collection.replace_one(
            {"_id": document["_id"]},
            document,
            upsert=True,
        )

        print(
            f"{field}: saved {len(available)} years with values; "
            f"latest year: {available[-1]['year']}; "
            f"unit: {definition['unit']}"
        )

print("Carbon import completed: 2 indicators.")