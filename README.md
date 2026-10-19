# Monitoring Urban Growth Using Remote Sensing

Semester project — interactive Google Earth Engine / Streamlit dashboard.

## Features
- Ahmedabad, Surat, Gandhinagar, Vadodara, Delhi, Mumbai, Bengaluru, Pune, Hyderabad, IIT Kanpur Campus, IISc Bangalore Campus.
- Sentinel-2 cloud-masked annual true-color imagery.
- Dynamic World annual modal land-cover maps (9 classes).
- NDVI, NDBI, NDWI maps.
- New, former, and stable built-up area; net growth and percentage.
- Optional annual built-up area trend chart and CSV download.
- Dark dashboard and OpenStreetMap basemap.

## Local setup
1. Install Python 3.11 or 3.12.
2. In the project directory: `python -m pip install -r requirements.txt`
3. Authenticate Earth Engine: `earthengine authenticate`
4. Run: `python -m streamlit run app.py`
5. Enter your **registered** Earth Engine Google Cloud project ID in the sidebar.

## Deploy on Streamlit Community Cloud
1. Upload the **contents** of this folder to the root of a GitHub repository.
2. In https://share.streamlit.io choose that repository, `main` branch, and `app.py` entrypoint.
3. In Streamlit Cloud App settings → Secrets, provide the project ID and a service-account JSON key using the TOML structure in `secrets.example.toml`. **Do not publish credentials.**
4. Grant the service account the necessary Earth Engine access and use a registered, API-enabled Google Cloud project.
5. Redeploy / restart the app and run an analysis.

## Suggested semester demo
- Study area: IIT Kanpur Campus (1.5 km radius) or IISc Bangalore Campus (1.5 km radius)
- Compare 2017 and 2025; optionally enable annual trend.
- Explain satellite composites, spectral indices, Dynamic World class 6, and urban-change categories.

## Research limitations
- Campus study areas are **approximate circular buffers**, not verified official boundaries.
- Dynamic World is a **pre-trained** classification product; this project **does not train Random Forest**.
- No independent validation dataset or confusion matrix is included; **do not claim measured classification accuracy**.
- The map displays imagery across rectangular bounds; area statistics use the circular buffer.
- Standalone annual built-up areas and net change can differ due to pixels missing in one year. Change statistics use pixels valid in both years.
- Land-cover and urban growth values are estimates; classification, clouds and seasonal variability can affect results.
- The trend makes multiple Earth Engine requests and may be slower than a two-year comparison.
