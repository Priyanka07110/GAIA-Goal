import json
from pathlib import Path

from openpyxl import load_workbook

# Locate the Excel file relative to this script.
project_folder = Path(__file__).resolve().parent
excel_file = project_folder / "Data" / "datasetsgg.xlsx"
json_file = project_folder / "Data" / "datasets.json"

# These names match the order of your 12 spreadsheet columns.
fields = [
    "serial_number",
    "name",
    "indicator",
    "description",
    "organization",
    "coverage",
    "time_period",
    "data_format",
    "source_url",
    "priority",
    "status",
    "notes",
]

workbook = load_workbook(excel_file, read_only=True, data_only=True)
datasets = []

for sheet in workbook:
    category_count = 0

    # Start at row 2 because row 1 contains the headings.
    for row in sheet.iter_rows(min_row=2, max_col=12, values_only=True):
        if not row[1]:
            continue

        dataset = dict(zip(fields, row))

        # Keep track of the category and original spreadsheet row.
        dataset["category"] = sheet.title
        dataset["_id"] = f"{sheet.title}:{int(row[0])}"

        datasets.append(dataset)
        category_count += 1

    print(f"{sheet.title}: {category_count} datasets")

workbook.close()

# Write one JSON array containing all dataset entries.
with json_file.open("w", encoding="utf-8") as file:
    json.dump(datasets, file, ensure_ascii=False, indent=2)

print(f"\nTotal: {len(datasets)} datasets")
print(f"Saved to: {json_file}")