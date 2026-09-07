import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pymongo import MongoClient
from pymongo.errors import PyMongoError


# main.py is inside backend, so go up to the project folder.
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_FOLDER / ".env", interpolate=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open a shared database client and close it on shutdown."""
    required = [
        "MONGO_HOST",
        "MONGO_USERNAME",
        "MONGO_PASSWORD",
        "MONGO_DATABASE",
    ]

    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Missing .env settings: " + ", ".join(missing)
        )

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
    app.state.client.admin.command("ping")
    return {"status": "ok", "database": "connected"}


@app.get("/categories", tags=["Catalogue"])
def categories():
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
    dataset = app.state.datasets.find_one({"_id": dataset_id})

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found.",
        )

    return dataset

@app.get("/environment/nasa-power/pune", tags=["Environmental Data"])
def pune_environment():
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