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

RAW_FOLDER = PROJECT / "Data" / "raw"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

START_YEAR = 1990
END_YEAR = 2025

# Code, project category, and unit from the indicator definition.
INDICATORS = [
    (
        "ER.H2O.FWTL.ZS",
        "Hydrosphere",
        "% of internal freshwater resources",
    ),
    ("AG.LND.FRST.ZS", "Biosphere", "% of land area"),
    ("AG.LND.AGRI.ZS", "Lithosphere", "% of land area"),
    (
        "SP.URB.TOTL.IN.ZS",
        "Anthroposphere  Human Activity",
        "% of total population",
    ),
]


def download_json(url, params):
    response = requests.get(url, params=params, timeout=(10, 60))
    response.raise_for_status()
    body = response.json()

    if (
        not isinstance(body, list)
        or len(body) != 2
        or not isinstance(body[0], dict)
        or not isinstance(body[1], list)
        or not body[1]
    ):
        raise ValueError("The World Bank returned no usable data.")

    if int(body[0].get("pages", 1)) > 1:
        raise ValueError("Response has additional pages; import stopped.")

    return body, response.url


with MongoClient(
    f"mongodb+srv://{os.environ['MONGO_HOST']}/",
    username=os.environ["MONGO_USERNAME"],
    password=os.environ["MONGO_PASSWORD"],
    authSource="admin",
    serverSelectionTimeoutMS=10000,
    socketTimeoutMS=20000,
) as client:
    database = client[os.environ["MONGO_DATABASE"]]
    collection = database["country_indicators"]

    completed = []
    failed = []

    for code, category, unit in INDICATORS:
        print(f"\nProcessing {category}: {code}")

        try:
            cache_file = RAW_FOLDER / (
                f"world_bank_IND_{code}_{START_YEAR}_{END_YEAR}.json"
            )

            if cache_file.exists():
                saved = json.loads(
                    cache_file.read_text(encoding="utf-8")
                )
                print("Using saved download.")
            else:
                data, request_url = download_json(
                    f"https://api.worldbank.org/v2/country/IND/indicator/{code}",
                    {
                        "format": "json",
                        "source": 2,
                        "date": f"{START_YEAR}:{END_YEAR}",
                        "per_page": 1000,
                    },
                )

                metadata, metadata_url = download_json(
                    f"https://api.worldbank.org/v2/indicator/{code}",
                    {"format": "json", "source": 2, "per_page": 1000},
                )

                saved = {
                    "retrieved_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "request_url": request_url,
                    "metadata_url": metadata_url,
                    "data": data,
                    "metadata": metadata,
                }

                cache_file.write_text(
                    json.dumps(saved, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            source_metadata = saved["metadata"][1][0]
            if source_metadata["id"] != code:
                raise ValueError("Indicator metadata does not match.")

            by_year = {}

            for item in saved["data"][1]:
                if (
                    item["indicator"]["id"] != code
                    or item["countryiso3code"] != "IND"
                ):
                    raise ValueError("Unexpected indicator or country.")

                year = int(item["date"])
                value = item["value"]

                if value is not None and (
                    not isinstance(value, (int, float))
                    or not math.isfinite(value)
                ):
                    raise ValueError("Unexpected measurement value.")

                by_year[year] = {
                    "year": year,
                    "value": value,
                    "observation_status": item.get("obs_status", ""),
                }

            records = [
                by_year.get(
                    year,
                    {
                        "year": year,
                        "value": None,
                        "observation_status": "",
                    },
                )
                for year in range(START_YEAR, END_YEAR + 1)
            ]

            available = [
                record for record in records
                if record["value"] is not None
            ]

            if not available:
                raise ValueError("No non-missing measurements returned.")

            document = {
                "_id": f"world-bank:IND:{code}",
                "source": "World Bank — World Development Indicators",
                "indicator_code": code,
                "name": source_metadata["name"],
                "category": category,
                "country": {"code": "IND", "name": "India"},
                "geographical_level": "country",
                "unit": unit,
                "definition": source_metadata.get("sourceNote", ""),
                "source_organization": source_metadata.get(
                    "sourceOrganization", ""
                ),
                "source_url": saved["request_url"],
                "metadata_url": saved["metadata_url"],
                "retrieved_at": saved["retrieved_at"],
                "source_last_updated": saved["data"][0].get(
                    "lastupdated"
                ),
                "frequency": "annual",
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

            completed.append(code)
            print(
                f"Saved: {len(available)} years with values; "
                f"latest available year: {available[-1]['year']}"
            )

        except (requests.RequestException, ValueError, KeyError) as error:
            failed.append(code)
            print(f"Could not import {code}: {error}")

    print(f"\nCompleted: {len(completed)} of {len(INDICATORS)} indicators")
    if failed:
        print("Needs attention:", ", ".join(failed))