import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

# Read settings from the .env file beside this script.
project_folder = Path(__file__).resolve().parent
load_dotenv(project_folder / ".env", interpolate=False)

# Pass credentials separately to avoid URI formatting problems.
with MongoClient(
    f"mongodb+srv://{os.environ['MONGO_HOST']}/",
    username=os.environ["MONGO_USERNAME"],
    password=os.environ["MONGO_PASSWORD"],
    authSource="admin",
    serverSelectionTimeoutMS=10000,
) as client:
    client.admin.command("ping")
    print("Connected to MongoDB successfully!")

    database = client[os.environ["MONGO_DATABASE"]]
    datasets = database["datasets"]

    print("Total datasets:", datasets.count_documents({}))
    print(
        "Atmosphere datasets:",
        datasets.count_documents({"category": "Atmosphere"}),
    )

    example = datasets.find_one({"_id": "Atmosphere:1"})
    if example:
        print("Example dataset:", example["name"])