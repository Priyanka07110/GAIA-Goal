# GAIA-Goal

## Run the presentation prototype

The FastAPI backend now serves the dashboard at `http://127.0.0.1:8000/app/`. The prototype preserves the existing catalogue and environmental API routes, and adds an explicit saved-data mode for reliable presentations. Saved mode reads the committed snapshots under `Data/raw`; it does not claim that remote satellite tiles work offline.

From PowerShell in the repository folder:

```powershell
\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:GAIA_DATA_MODE = "saved"
\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/app/](http://127.0.0.1:8000/app/) in a browser. API documentation remains at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). To use MongoDB Atlas instead, omit `GAIA_DATA_MODE` and use the existing `.env` settings. Never put those settings into frontend files.

## What is implemented

- Overview with the 105-entry catalogue count, seven integrated category summaries and saved-data labeling.
- Category explorer with real NASA POWER monthly weather charts, four World Bank country indicators, two OWID carbon indicators and the NSIDC Arctic September series.
- Analytics charts that preserve incompatible units as separate series and keep country values independent from map movement.
- Dataset catalogue search, category and priority filters, pagination and source links.
- Earth map with Pune, India and Himalaya presets, pan/zoom, opacity and a dated NASA GIBS layer. Remote imagery needs network access and is marked as not yet visually verified.
- SDG 13 view based on official UN Goal 13 wording, with intended-contribution labels, evidence links and a separate fixed prototype checklist.
- Sources and methods view covering geography, units, retrieval context and limitations.

## Three-minute demo

1. Start in Overview: point out 105 catalogue entries versus seven integrated category views.
2. Open Earth explorer and show Pune monthly temperature, humidity, wind and precipitation as separate charts.
3. Open Analytics: explain that India country indicators and CO2 are annual saved measurements, not forecasts.
4. Open Dataset library: search `NASA`, filter Atmosphere, and open the source link.
5. Open Earth explorer map: try Pune, India and Himalayas presets and adjust opacity; mention that satellite tiles are remote.
6. Finish on SDG 13: show 13.3, 13.1 and 13.2 evidence, then explain that prototype progress is not SDG achievement.

## Known limitations

- Saved snapshots are historical and are not a live feed. Importers remain separate long-running scripts.
- NASA GIBS availability, snow-cover visualization and map rendering still need a manual browser verification pass.
- The current cryosphere data is Arctic September sea-ice extent, not Himalayan glacier data and not annual minimum extent.
- Himalayan glacier outlines are pending an official, manageable source with verified CRS and alignment.
- AI integration and automated end-to-end tests are planned, so the prototype makes no model or learning-outcome claims.
Gaia Goal is an AI-powered climate intelligence and environmental monitoring platform designed to integrate diverse environmental data sources, analyze climate-related indicators, visualize environmental changes, identify anomalies, and support data-driven climate action aligned with SDG 13.
Problem Statement - To design and develop an AI-powered climate intelligence and environmental monitoring platform that integrates data from multiple environmental sources, including satellite data, ground sensors, climate indicators, and research datasets, to analyze climate-related changes, monitor environmental conditions, visualize trends, identify anomalies, and generate data-driven insights that support better understanding and decision-making towards SDG 13: Climate Action.

Feature Requirements
1. Executive Dashboard
2. Global Ecosystem Overview
3. Satellite Data Module
4. Ground Sensor Network
5. Climate Indicator Database
6. AI Data Fusion Engine
7. Carbon Emission Analytics
8. Deforestation Monitoring
9. Glacier and Ice Monitoring
10. Air Quality Monitoring
11. Ocean Health Monitoring
12. Extreme Weather Monitoring
13. Biodiversity Index
14. Climate Risk Heatmap
15. AI Prediction Panel
16. SDG 13 Progress Tracker
17. Research Dataset Repository
18. Reports Module
19. Alerts and Notifications
20. User and Organization Management

Date - 27/07/2026
We have created a git hub project and a readme file. Discussed on the Assignment 1 Contents and divided the task
