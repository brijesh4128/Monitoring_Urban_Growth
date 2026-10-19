"""Earth Engine analysis functions for urban growth monitoring."""
from __future__ import annotations
import ee
import json
import streamlit as st

DW_NAMES = ['Water','Trees','Grass','Flooded vegetation','Crops','Shrub and scrub','Built-up','Bare ground','Snow and ice']
DW_COLORS = ['#419BDF','#397D49','#88B053','#7A87C6','#E49635','#DFC35A','#C4281B','#A59B8F','#B39FE1']

CITY_COORDS = {
    'Ahmedabad': (72.5714, 23.0225), 'Surat': (72.8311, 21.1702),
    'Gandhinagar': (72.6369, 23.2156), 'Vadodara': (73.1812, 22.3072),
    'Delhi': (77.2090, 28.6139), 'Mumbai': (72.8777, 19.0760),
    'Bengaluru': (77.5946, 12.9716), 'Pune': (73.8567, 18.5204),
    'Hyderabad': (78.4867, 17.3850),
    'IIT Kanpur Campus': (80.2329, 26.5123),
    'IISc Bangalore Campus': (77.5671, 13.0219),
}
CAMPUS_AREAS = {'IIT Kanpur Campus', 'IISc Bangalore Campus'}

def initialize_ee(project: str) -> None:
    if not project or not project.strip():
        raise ValueError('Enter your Google Cloud project ID in the sidebar.')
    # Streamlit Cloud: configure the gcp_service_account table in Secrets.
    # Local machine: use `earthengine authenticate` once.
    if "gcp_service_account" in st.secrets:
        key = dict(st.secrets["gcp_service_account"])
        credentials = ee.ServiceAccountCredentials(
            key["client_email"], key_data=json.dumps(key)
        )
        ee.Initialize(credentials=credentials, project=project.strip())
    else:
        ee.Initialize(project=project.strip())
def initialize_ee(project: str) -> None:
    """
    Initialize Google Earth Engine.

    Local computer:
        Uses credentials from earthengine authenticate.

    Streamlit Cloud:
        Uses service-account credentials from st.secrets.
    """

    if not project or not project.strip():
        raise ValueError(
            "Enter your Google Cloud project ID."
        )

    project = project.strip()

    # Try reading Streamlit secrets safely
    try:
        service_info = dict(
            st.secrets["gcp_service_account"]
        )
    except (FileNotFoundError, KeyError):
        service_info = None

    if service_info:
        # Cloud deployment authentication
        credentials = ee.ServiceAccountCredentials(
            service_info["client_email"],
            key_data=json.dumps(service_info)
        )

        ee.Initialize(
            credentials=credentials,
            project=project
        )

    else:
        # Local authentication
        ee.Initialize(project=project)


def city_geometry(city: str):
    """Approximate study-area centers, not official campus boundaries."""
    if city not in CITY_COORDS:
        raise ValueError(f'Unsupported study area: {city}')
    lon, lat = CITY_COORDS[city]
    return ee.Geometry.Point([lon, lat]), lat, lon

def study_area(city: str, radius_km: float):
    center, lat, lon = city_geometry(city)
    return center.buffer(float(radius_km) * 1000), lat, lon

def annual_dw(year: int, area):
    """Annual modal Dynamic World class, clipped to rectangular map bounds."""
    display_area = area.bounds()
    collection = (ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')
                  .filterBounds(display_area)
                  .filterDate(f'{year}-01-01', f'{year+1}-01-01'))
    return collection.select('label').mode().clip(display_area).rename('landcover'), collection.size()

def sentinel_rgb(year: int, area, cloud_pct: int = 35):
    """Cloud-masked Sentinel-2 reflectance composite on rectangular bounds."""
    display_area = area.bounds()
    def mask_clouds(img):
        scl = img.select('SCL')
        mask = (scl.neq(3).And(scl.neq(8)).And(scl.neq(9))
                .And(scl.neq(10)).And(scl.neq(11)).And(scl.neq(1)))
        return img.updateMask(mask).select(['B2','B3','B4','B8','B11']).multiply(0.0001)
    collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                  .filterBounds(display_area)
                  .filterDate(f'{year}-01-01', f'{year+1}-01-01')
                  .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', cloud_pct)))
    return collection.map(mask_clouds).median().clip(display_area), collection.size()

def spectral_indices(image):
    return {
        'NDVI': image.normalizedDifference(['B8','B4']).rename('NDVI'),
        'NDBI': image.normalizedDifference(['B11','B8']).rename('NDBI'),
        'NDWI': image.normalizedDifference(['B3','B8']).rename('NDWI'),
    }

def area_stats(label, area, scale=20):
    """Class areas in km² within circular study area."""
    areas = ee.Image.pixelArea().divide(1e6).rename('area').addBands(label.rename('class'))
    result = areas.reduceRegion(
        reducer=ee.Reducer.sum().group(groupField=1, groupName='class'),
        geometry=area, scale=scale, maxPixels=1e9, tileScale=4)
    groups = result.get('groups').getInfo() or []
    values = {int(item['class']): float(item['sum']) for item in groups}
    return {name: round(values.get(i, 0.0), 3) for i, name in enumerate(DW_NAMES)}

def change_stats(first, last, area, scale=20):
    """New, former and stable built-up area on pixels valid in both years."""
    common = first.mask().And(last.mask())
    earlier = first.updateMask(common).eq(6)
    later = last.updateMask(common).eq(6)
    images = {
        'New built-up': later.And(earlier.Not()).selfMask().clip(area).rename('new_urban'),
        'Former built-up': earlier.And(later.Not()).selfMask().clip(area).rename('lost_urban'),
        'Stable built-up': earlier.And(later).selfMask().clip(area).rename('stable_urban'),
    }
    stats = {}
    for name, img in images.items():
        val = (ee.Image.pixelArea().divide(1e6).rename('area').updateMask(img)
               .reduceRegion(ee.Reducer.sum(), geometry=area, scale=scale,
                             maxPixels=1e9, tileScale=4).get('area').getInfo())
        stats[name] = round(float(val or 0), 3)
    stats['Net change'] = round(stats['New built-up'] - stats['Former built-up'], 3)
    baseline = stats['Stable built-up'] + stats['Former built-up']
    stats['Growth %'] = round(100 * stats['Net change'] / baseline, 2) if baseline > 0 else None
    return stats, images


def builtup_trend(start_year: int, end_year: int, area, scale: int = 20):
    """Annual Dynamic World built-up area, in km², inside the study circle.

    Returns a list of records; years without Dynamic World scenes are omitted.
    A year-to-year change is descriptive and not an accuracy assessment.
    """
    records = []
    for year in range(start_year, end_year + 1):
        landcover, count = annual_dw(year, area)
        if count.getInfo() == 0:
            continue
        builtup = landcover.eq(6).selfMask()
        area_img = ee.Image.pixelArea().divide(1e6).rename("area").updateMask(builtup)
        result = area_img.reduceRegion(
            reducer=ee.Reducer.sum(), geometry=area,
            scale=scale, maxPixels=1e9, tileScale=4
        ).get("area").getInfo()
        records.append({"Year": year, "Built-up area (km²)": round(float(result or 0), 3)})
    return records
