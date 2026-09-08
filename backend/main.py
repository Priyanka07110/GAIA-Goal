import os
import re
import csv
import io
import json
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from pymongo.errors import PyMongoError


# main.py is inside backend, so go up to the project folder.
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_FOLDER / ".env", interpolate=False)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def saved_datasets():
    return load_json(PROJECT_FOLDER / "Data" / "datasets.json")


def saved_environment():
    raw = PROJECT_FOLDER / "Data" / "raw"
    nasa = load_json(raw / "nasa_power_pune_2025.json")
    payload = nasa["payload"]
    parameters = payload["properties"]["parameter"]
    metadata = payload["parameters"]
    dates = sorted(parameters["T2M"])
    records = []
    for date_key in dates:
        records.append({
            "date": f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:]}",
            **{name: values.get(date_key) for name, values in parameters.items()},
        })
    series = {
        "_id": "nasa-power:pune:2025:daily",
        "source": "NASA POWER",
        "catalogue_id": "Atmosphere:3",
        "category": "Atmosphere",
        "location": {"name": "Pune", "latitude": 18.5204, "longitude": 73.8567},
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "time_standard": "UTC",
        "frequency": "daily",
        "retrieved_at": nasa["retrieved_at"],
        "source_url": nasa["request_url"],
        "parameters": {name: metadata[name] for name in parameters},
        "record_count": len(records),
        "records": records,
    }

    country = []
    for path in sorted(raw.glob("world_bank_IND_*.json")):
        saved = load_json(path)
        code = path.name[len("world_bank_IND_"):-len("_1990_2025.json")]
        source_metadata = saved["metadata"][1][0]
        values = {
            int(item["date"]): item.get("value")
            for item in saved["data"][1]
        }
        category = {
            "ER.H2O.FWTL.ZS": "Hydrosphere",
            "AG.LND.FRST.ZS": "Biosphere",
            "AG.LND.AGRI.ZS": "Lithosphere",
            "SP.URB.TOTL.IN.ZS": "Anthroposphere  Human Activity",
        }[code]
        records = [{"year": year, "value": values.get(year)} for year in range(1990, 2026)]
        available = [record for record in records if record["value"] is not None]
        country.append({
            "_id": f"world-bank:IND:{code}", "indicator_code": code,
            "name": source_metadata["name"], "category": category,
            "country": {"code": "IND", "name": "India"},
            "geographical_level": "country", "unit": {
                "ER.H2O.FWTL.ZS": "% of internal freshwater resources",
                "AG.LND.FRST.ZS": "% of land area", "AG.LND.AGRI.ZS": "% of land area",
                "SP.URB.TOTL.IN.ZS": "% of total population",
            }[code], "definition": source_metadata.get("sourceNote", ""),
            "source": "World Bank - World Development Indicators",
            "source_url": saved["request_url"], "metadata_url": saved["metadata_url"],
            "retrieved_at": saved["retrieved_at"], "frequency": "annual",
            "available_year_count": len(available), "missing_year_count": len(records) - len(available),
            "latest_available": available[-1], "records": records,
        })

    carbon_saved = load_json(raw / "owid_carbon_india_1990_2025.json")
    carbon = []
    carbon_labels = {"co2": "CO2 emissions", "co2_per_capita": "CO2 emissions per capita"}
    carbon_units = {"co2": "million tonnes", "co2_per_capita": "tonnes per person"}
    for code in ("co2", "co2_per_capita"):
        records = [{"year": int(row["year"]), "value": float(row[code]) if row[code] else None} for row in carbon_saved["rows"]]
        available = [record for record in records if record["value"] is not None]
        carbon.append({
            "_id": f"owid:IND:{code}", "indicator_code": code, "name": carbon_labels[code],
            "category": "Carbon & Climate", "country": {"code": "IND", "name": "India"},
            "geographical_level": "country", "frequency": "annual", "unit": carbon_units[code],
            "definition": carbon_saved["metadata"][code].get("description", ""),
            "source": "Our World in Data", "underlying_source": carbon_saved["metadata"][code].get("source", ""),
            "source_url": carbon_saved["source_url"], "codebook_url": carbon_saved["codebook_url"],
            "retrieved_at": carbon_saved["retrieved_at"], "available_year_count": len(available),
            "missing_year_count": len(records) - len(available), "latest_available": available[-1], "records": records,
        })

    csv_text = load_json(raw / "nsidc_arctic_september_v4.json")["csv"]
    ice_rows = []
    for row in csv.DictReader(io.StringIO(csv_text), skipinitialspace=True):
        if row["region"] == "N" and row["mo"] == "9":
            ice_rows.append({"year": int(row["year"]), "month": 9, "value": float(row["extent"])})
    cryosphere = {"_id": "nsidc:arctic:september:extent:v4", "name": "Arctic September mean sea-ice extent",
        "category": "Cryosphere", "source": "NSIDC Sea Ice Index", "version": "4", "region": "Arctic",
        "geographical_level": "polar region", "unit": "million square kilometres",
        "frequency": "one September monthly mean per year", "month": 9,
        "definition": "September monthly mean sea-ice extent. Extent counts ocean grid-cell areas with at least 15% ice concentration.",
        "interpretation": "This is not annual minimum extent, ice volume, glacier area, or an India-level measurement.",
        "source_url": "https://noaadata.apps.nsidc.org/NOAA/G02135/north/monthly/data/N_09_extent_v4.0.csv",
        "source_page": "https://nsidc.org/data/g02135/versions/4", "retrieved_at": load_json(raw / "nsidc_arctic_september_v4.json")["retrieved_at"],
        "available_year_count": len(ice_rows), "missing_year_count": 0, "latest_available": ice_rows[-1], "records": ice_rows}
    return {"series": series, "country": country, "carbon": carbon, "cryosphere": cryosphere}


SAVED_ENVIRONMENT = saved_environment()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open a shared database client and close it on shutdown."""
    if os.getenv("GAIA_DATA_MODE", "atlas").lower() == "saved":
        app.state.mode = "saved"
        app.state.client = None
        app.state.datasets = None
        yield
        return

    required = [
        "MONGO_HOST",
        "MONGO_USERNAME",
        "MONGO_PASSWORD",
        "MONGO_DATABASE",
    ]

    missing = [name for name in required if not os.getenv(name)]
    if missing:
        app.state.mode = "saved"
        app.state.client = None
        app.state.datasets = None
        yield
        return

    client = MongoClient(
        f"mongodb+srv://{os.environ['MONGO_HOST']}/",
        username=os.environ["MONGO_USERNAME"],
        password=os.environ["MONGO_PASSWORD"],
        authSource="admin",
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=20000,
    )

    app.state.client = client
    app.state.mode = os.getenv("GAIA_DATA_MODE", "atlas")
    app.state.datasets = client[
        os.environ["MONGO_DATABASE"]
    ]["datasets"]

    try:
        yield
    finally:
        client.close()


app = FastAPI(
    title="Gaia Goal Backend",
    description="Search and explore the Gaia Goal dataset catalogue.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_origins=["null"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(PyMongoError)
async def database_error_handler(request, exception):
    # Return a useful message without exposing connection credentials.
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "Database request failed. Check the Atlas connection "
                "and try again."
            )
        },
    )


@app.get("/", tags=["Overview"])
def home():
    return {
        "project": "Gaia Goal",
        "service": "Dataset catalogue API",
        "documentation": "/docs",
        "health_check": "/health",
    }


@app.get("/health", tags=["Overview"])
def health():
    if app.state.mode == "saved":
        return {"status": "ok", "database": "saved snapshots", "mode": "saved-data"}
    app.state.client.admin.command("ping")
    return {"status": "ok", "database": "connected", "mode": app.state.mode}


@app.get("/categories", tags=["Catalogue"])
def categories():
    if app.state.mode == "saved":
        rows = {}
        for item in saved_datasets():
            rows[item["category"]] = rows.get(item["category"], 0) + 1
        return {"total_categories": len(rows), "total_datasets": sum(rows.values()),
                "categories": [{"name": name, "count": count} for name, count in sorted(rows.items())]}
    pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]

    rows = list(app.state.datasets.aggregate(pipeline))

    return {
        "total_categories": len(rows),
        "total_datasets": sum(row["count"] for row in rows),
        "categories": [
            {"name": row["_id"], "count": row["count"]}
            for row in rows
        ],
    }


@app.get("/datasets", tags=["Catalogue"])
def list_datasets(
    search: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=100),
    priority: str | None = Query(default=None, max_length=30),
    status: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    if app.state.mode == "saved":
        items = saved_datasets()
        if category: items = [item for item in items if item.get("category") == category]
        if priority: items = [item for item in items if item.get("priority") == priority]
        if status: items = [item for item in items if item.get("status") == status]
        if search:
            needle = search.strip().lower()
            items = [item for item in items if any(needle in str(item.get(field, "")).lower() for field in ("name", "indicator", "description", "organization", "coverage"))]
        total = len(items)
        start = (page - 1) * page_size
        return {"total": total, "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size,
                "items": items[start:start + page_size]}
    filters = {}

    for field, value in (
        ("category", category),
        ("priority", priority),
        ("status", status),
    ):
        if value and value.strip():
            filters[field] = value.strip()

    if search and search.strip():
        # Treat the search as ordinary text, not a regex expression.
        pattern = re.escape(search.strip())
        filters["$or"] = [
            {field: {"$regex": pattern, "$options": "i"}}
            for field in (
                "name",
                "indicator",
                "description",
                "organization",
                "coverage",
            )
        ]

    collection = app.state.datasets
    total = collection.count_documents(filters)

    cursor = (
        collection.find(filters)
        .sort([("category", 1), ("serial_number", 1), ("_id", 1)])
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "items": list(cursor),
    }


@app.get("/datasets/{dataset_id}", tags=["Catalogue"])
def dataset_details(dataset_id: str):
    if app.state.mode == "saved":
        dataset = next((item for item in saved_datasets() if item["_id"] == dataset_id), None)
        if dataset is None:
            raise HTTPException(status_code=404, detail="Dataset not found.")
        return dataset
    dataset = app.state.datasets.find_one({"_id": dataset_id})

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found.",
        )

    return dataset

@app.get("/environment/nasa-power/pune", tags=["Environmental Data"])
def pune_environment():
    if app.state.mode == "saved":
        return SAVED_ENVIRONMENT["series"]
    database = app.state.client[os.environ["MONGO_DATABASE"]]

    series = database["environmental_series"].find_one(
        {"_id": "nasa-power:pune:2025:daily"}
    )

    if series is None:
        raise HTTPException(
            status_code=404,
            detail="Pune data has not been downloaded yet.",
        )

    return series

@app.get("/environment/monthly", tags=["Environmental Data"])
def monthly_environment(
    series_id: str = Query(
        default="nasa-power:pune:2025:daily",
        max_length=200,
    ),
):
    if app.state.mode == "saved":
        series = SAVED_ENVIRONMENT["series"]
        from calendar import monthrange
        from collections import defaultdict
        groups = defaultdict(list)
        for record in series["records"]: groups[record["date"][:7]].append(record)
        monthly_records = []
        for month, records in sorted(groups.items()):
            expected_days = monthrange(*map(int, month.split("-")))[1]
            summary = {"month": month, "expected_days": expected_days, "valid_days": {}}
            for parameter in ("T2M", "RH2M", "WS2M", "PRECTOTCORR"):
                values = [record[parameter] for record in records if record.get(parameter) is not None]
                summary["valid_days"][parameter] = len(values)
                summary[parameter] = None if len(values) != expected_days else round(sum(values), 2) if parameter == "PRECTOTCORR" else round(sum(values) / len(values), 2)
            monthly_records.append(summary)
        return {"series_id": series["_id"], "source": series["source"], "source_url": series["source_url"], "retrieved_at": series["retrieved_at"], "location": series["location"], "time_standard": "UTC", "frequency": "monthly", "record_count": len(monthly_records), "records": monthly_records}
    database = app.state.client[os.environ["MONGO_DATABASE"]]
    series = database["environmental_series"].find_one(
        {"_id": series_id}
    )

    if series is None:
        raise HTTPException(
            status_code=404,
            detail="Environmental series not found.",
        )

    required = {"T2M", "RH2M", "WS2M", "PRECTOTCORR"}

    if (
        series.get("frequency") != "daily"
        or not required.issubset(series.get("parameters", {}))
        or series["parameters"]["PRECTOTCORR"]["units"] != "mm/day"
    ):
        raise HTTPException(
            status_code=422,
            detail="This series is not supported by this summary.",
        )

    from calendar import monthrange
    from collections import defaultdict

    groups = defaultdict(list)

    for record in series["records"]:
        month = record["date"][:7]
        groups[month].append(record)

    monthly_records = []

    for month, records in sorted(groups.items()):
        year_number, month_number = map(int, month.split("-"))
        expected_days = monthrange(year_number, month_number)[1]

        summary = {
            "month": month,
            "expected_days": expected_days,
            "valid_days": {},
        }

        for parameter in sorted(required):
            values = [
                record[parameter]
                for record in records
                if record.get(parameter) is not None
            ]

            summary["valid_days"][parameter] = len(values)

            # Return no monthly value if the month is incomplete.
            if len(values) != expected_days:
                summary[parameter] = None
            elif parameter == "PRECTOTCORR":
                summary[parameter] = round(sum(values), 2)
            else:
                summary[parameter] = round(
                    sum(values) / len(values), 2
                )

        monthly_records.append(summary)

    return {
        "series_id": series["_id"],
        "source": series["source"],
        "source_url": series["source_url"],
        "retrieved_at": series["retrieved_at"],
        "location": series["location"],
        "time_standard": series["time_standard"],
        "frequency": "monthly",
        "parameters": {
            "T2M": {
                "label": "Mean temperature at 2 metres",
                "unit": series["parameters"]["T2M"]["units"],
                "aggregation": "mean",
            },
            "RH2M": {
                "label": "Mean relative humidity at 2 metres",
                "unit": series["parameters"]["RH2M"]["units"],
                "aggregation": "mean",
            },
            "WS2M": {
                "label": "Mean wind speed at 2 metres",
                "unit": series["parameters"]["WS2M"]["units"],
                "aggregation": "mean",
            },
            "PRECTOTCORR": {
                "label": "Total corrected precipitation",
                "unit": "mm",
                "aggregation": "sum of daily amounts",
            },
        },
        "completeness_rule": (
            "Monthly values are null unless every day has a value."
        ),
        "record_count": len(monthly_records),
        "records": monthly_records,
    }

@app.get("/environment/country-indicators", tags=["Environmental Data"])
def list_country_indicators():
    if app.state.mode == "saved":
        return {"total": len(SAVED_ENVIRONMENT["country"]), "items": [{key: value for key, value in item.items() if key != "records"} for item in SAVED_ENVIRONMENT["country"]]}
    database = app.state.client[os.environ["MONGO_DATABASE"]]

    items = list(
        database["country_indicators"]
        .find({}, {"records": 0})
        .sort("category", 1)
    )

    return {"total": len(items), "items": items}


@app.get(
    "/environment/country-indicators/{indicator_code}",
    tags=["Environmental Data"],
)
def country_indicator_details(indicator_code: str):
    if app.state.mode == "saved":
        document = next((item for item in SAVED_ENVIRONMENT["country"] if item["indicator_code"] == indicator_code), None)
        if document is None: raise HTTPException(status_code=404, detail="This indicator has not been imported.")
        return document
    database = app.state.client[os.environ["MONGO_DATABASE"]]

    document = database["country_indicators"].find_one(
        {"_id": f"world-bank:IND:{indicator_code}"}
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="This indicator has not been imported.",
        )

    return document

@app.get("/environment/carbon", tags=["Environmental Data"])
def carbon_indicators():
    if app.state.mode == "saved":
        return {"total": len(SAVED_ENVIRONMENT["carbon"]), "items": [{key: value for key, value in item.items() if key != "records"} for item in SAVED_ENVIRONMENT["carbon"]]}
    database = app.state.client[os.environ["MONGO_DATABASE"]]

    items = list(
        database["carbon_indicators"]
        .find({}, {"records": 0})
        .sort("indicator_code", 1)
    )

    return {"total": len(items), "items": items}


@app.get(
    "/environment/carbon/{indicator_code}",
    tags=["Environmental Data"],
)
def carbon_indicator_details(indicator_code: str):
    if app.state.mode == "saved":
        document = next((item for item in SAVED_ENVIRONMENT["carbon"] if item["indicator_code"] == indicator_code), None)
        if document is None: raise HTTPException(status_code=404, detail="Carbon indicator not found.")
        return document
    database = app.state.client[os.environ["MONGO_DATABASE"]]

    document = database["carbon_indicators"].find_one(
        {"_id": f"owid:IND:{indicator_code}"}
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Carbon indicator not found.",
        )

    return document

@app.get("/environment/cryosphere", tags=["Environmental Data"])
def cryosphere_data():
    if app.state.mode == "saved":
        return SAVED_ENVIRONMENT["cryosphere"]
    database = app.state.client[os.environ["MONGO_DATABASE"]]

    document = database["cryosphere_indicators"].find_one(
        {"_id": "nsidc:arctic:september:extent:v4"}
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Cryosphere data has not been imported.",
        )

    return document


app.mount("/app", StaticFiles(directory=PROJECT_FOLDER / "frontend", html=True), name="frontend")