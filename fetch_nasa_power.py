import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

PROJECT = Path(__file__).resolve().parent
load_dotenv(PROJECT / ".env", interpolate=False)

# Our first location and historical period.
LATITUDE = 18.5204
LONGITUDE = 73.8567
START = date(2025, 1, 1)
END = date(2025, 12, 31)

PARAMETERS = ["T2M", "RH2M", "PRECTOTCORR", "WS2M"]
SERIES_ID = "nasa-power:pune:2025:daily"
API_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

raw_folder = PROJECT / "Data" / "raw"
raw_folder.mkdir(parents=True, exist_ok=True)
raw_file = raw_folder / "nasa_power_pune_2025.json"

# Reuse an existing download when rerunning the script.
if raw_file.exists():
    saved = json.loads(raw_file.read_text(encoding="utf-8"))
    print("Using the saved NASA download.")
else:
    print("Downloading NASA POWER data for Pune...")

    response = requests.get(
        API_URL,
        params={
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "start": START.strftime("%Y%m%d"),
            "end": END.strftime("%Y%m%d"),
            "parameters": ",".join(PARAMETERS),
            "community": "AG",
            "format": "JSON",
            "time-standard": "UTC",
        },
        timeout=(10, 90),
    )
    response.raise_for_status()

    payload = response.json()
    if "parameter" not in payload.get("properties", {}):
        raise ValueError("NASA returned an unexpected response.")

    saved = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "request_url": response.url,
        "payload": payload,
    }

    raw_file.write_text(
        json.dumps(saved, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Original NASA response saved.")

payload = saved["payload"]
values = payload["properties"]["parameter"]
metadata = payload["parameters"]
fill_value = payload.get("header", {}).get("fill_value", -999)

# Check that NASA returned all four requested parameters and units.
for parameter in PARAMETERS:
    if parameter not in values or not metadata.get(parameter, {}).get("units"):
        raise ValueError(f"Missing parameter or units: {parameter}")

records = []
missing = {parameter: 0 for parameter in PARAMETERS}
day = START

while day <= END:
    key = day.strftime("%Y%m%d")
    record = {"date": day.isoformat()}

    for parameter in PARAMETERS:
        value = values[parameter].get(key)

        # Missing data must not become a false zero on a chart.
        if (
            value is None
            or value == fill_value
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            value = None
            missing[parameter] += 1

        record[parameter] = value

    records.append(record)
    day += timedelta(days=1)

for parameter in PARAMETERS:
    if missing[parameter] == len(records):
        raise ValueError(f"No usable values returned for {parameter}")

series = {
    "_id": SERIES_ID,
    "source": "NASA POWER",
    "catalogue_id": "Atmosphere:3",
    "category": "Atmosphere",
    "location": {
        "name": "Pune",
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
    },
    "start_date": START.isoformat(),
    "end_date": END.isoformat(),
    "time_standard": "UTC",
    "frequency": "daily",
    "retrieved_at": saved["retrieved_at"],
    "source_url": saved["request_url"],
    "source_header": payload.get("header", {}),
    "source_geometry": payload.get("geometry", {}),
    "parameters": {
        parameter: metadata[parameter]
        for parameter in PARAMETERS
    },
    "missing_values": missing,
    "record_count": len(records),
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

    # Updating the same ID prevents duplicates on repeat runs.
    database["environmental_series"].replace_one(
        {"_id": SERIES_ID},
        series,
        upsert=True,
    )

print(f"Saved {len(records)} daily records to MongoDB.")
print("Missing values:", missing)
print("Parameter units:")
for parameter in PARAMETERS:
    print(parameter, metadata[parameter]["units"])