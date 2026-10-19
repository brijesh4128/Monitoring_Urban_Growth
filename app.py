
"""Urban growth dashboard with satellite before/after views and Folium maps."""
import os
import ee
import folium
from folium.plugins import Fullscreen, MousePosition
from streamlit_folium import st_folium
import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import (
    DW_COLORS, DW_NAMES, annual_dw, area_stats,
    change_stats, initialize_ee, sentinel_rgb,
    spectral_indices, study_area, CAMPUS_AREAS, builtup_trend
)

st.set_page_config(
    page_title="Urban Growth Observatory",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
:root { color-scheme: dark; }
.stApp { background: radial-gradient(ellipse at 80% 0%, #163d54 0%, #091726 48%, #07111d 100%); color: #e8f3f8; }
[data-testid="stSidebar"] { background: linear-gradient(180deg,#112a3d 0%,#091827 100%); border-right:1px solid #315069; }
[data-testid="stSidebar"] * { color:#e4f1f7; }
.block-container { padding-top:1.3rem; max-width:1550px; padding-bottom:3rem; }
.hero { background:linear-gradient(115deg,#12374d,#14647a 55%,#1d897f); padding:30px 34px; border-radius:20px; border:1px solid #4c9aab; box-shadow:0 14px 40px #020e1a55; margin-bottom:22px; }
.hero h1 { font-size:2.35rem; color:#fff; margin:0 0 9px; letter-spacing:-.025em; }
.hero p { color:#d9f8f5; margin:0; }
.section-head { font-size:1.35rem; font-weight:750; margin:28px 0 12px; color:#83e2e1; }
.map-label { font-weight:700; font-size:1.06rem; margin:10px 0 8px; color:#e4f6fb; }
[data-testid="stMetric"] { background:linear-gradient(145deg,#15344a,#102638); border:1px solid #2c6272; border-radius:15px; padding:15px; box-shadow:0 8px 22px #020c1750; }
[data-testid="stMetricLabel"] { color:#b6d9e6; }
[data-testid="stMetricValue"] { color:#fff; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius:15px; }
.stButton > button[kind="primary"] { background:linear-gradient(90deg,#0d9488,#0874a8); border:0; color:#fff; font-weight:700; border-radius:11px; }
.stButton > button[kind="primary"]:hover { background:linear-gradient(90deg,#0fb5a7,#0b8fc9); color:#fff; }
[data-testid="stDataFrame"], iframe { border-radius:12px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
<h1>🛰️ Urban Growth Observatory</h1>
<p>Monitoring Urban Growth Using Remote Sensing ·
Satellite imagery · Land-cover change · Interactive maps</p>
</div>
""", unsafe_allow_html=True)

st.caption(
    "Data: Google Earth Engine / Sentinel-2 Surface Reflectance / "
    "Dynamic World 10 m. Results are estimates, not surveyed ground truth."
)

# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.header("⚙️ Analysis controls")

    project = st.text_input(
        "Earth Engine Cloud project ID",
        
        value=os.getenv("EE_PROJECT_ID", "ancient-vortex-491717-f5"),
        help="Registered Google Cloud project ID, not Gmail address"
    )

    city = st.selectbox(
        "Select study area",
        [
            "IIT Kanpur Campus", "IISc Bangalore Campus",
            "Ahmedabad", "Surat", "Gandhinagar",
            "Vadodara", "Delhi", "Mumbai",
            "Bengaluru", "Pune", "Hyderabad"
        ]
    )

    if city in CAMPUS_AREAS:
        radius = st.slider(
            "Campus study radius (km)", min_value=0.5,
            max_value=5.0, value=1.5, step=0.5,
            help="Circular region around the approximate campus center; not the official campus boundary."
        )
    else:
        radius = st.slider(
            "Radius around city center (km)", 5, 30, 12
        )

    year1 = st.selectbox(
        "Before year",
        list(range(2017, 2026)),
        index=3
    )

    year2 = st.selectbox(
        "After year",
        list(range(2017, 2026)),
        index=8
    )

    cloud = st.slider(
        "Maximum Sentinel-2 scene cloudiness (%)",
        10, 90, 60, 5
    )

    run = st.button(
        "🚀 Run urban growth analysis",
        type="primary",
        use_container_width=True
    )

    if run:
        st.session_state["analysis_started"] = True

    show_trend = st.checkbox(
        "📈 Calculate annual built-up trend (slower)",
        value=False,
        help="Computes a separate Dynamic World composite for every year in the chosen interval."
    )

    st.divider()
    st.caption(
        "For local use, run `earthengine authenticate`. "
        "For cloud hosting, configure service account secrets. "
        "Study areas are approximate circles, not official city or campus boundaries."
    )

if not st.session_state.get("analysis_started", False):
    st.subheader("Explore how your city has changed")
    st.write(
        "Choose a city, select two years, enter your Earth Engine "
        "Cloud project ID, then click **Run urban growth analysis**."
    )
    st.info(
        "No satellite image is loaded until you click Run. "
        "You must have internet and Earth Engine access."
    )
    st.stop()

if year1 >= year2:
    st.error("Choose a before year earlier than the after year.")
    st.stop()

if not project.strip():
    st.error("Enter your registered Google Cloud project ID.")
    st.stop()

# ---------------- EARTH ENGINE ANALYSIS ----------------

try:
    with st.spinner(
        "Preparing satellite composites and calculating urban growth..."
    ):
        initialize_ee(project)

        area, lat, lon = study_area(city, radius)

        lc1, n1 = annual_dw(year1, area)
        lc2, n2 = annual_dw(year2, area)

        count1 = n1.getInfo()
        count2 = n2.getInfo()

        if not count1 or not count2:
            st.error(
                "Dynamic World imagery unavailable for a selected year."
            )
            st.stop()

        if show_trend:
            trend_rows = builtup_trend(year1, year2, area)
        else:
            trend_rows = []

        s1 = area_stats(lc1, area)
        s2 = area_stats(lc2, area)

        changes, masks = change_stats(lc1, lc2, area)

        rgb1, sn1 = sentinel_rgb(year1, area, cloud)
        rgb2, sn2 = sentinel_rgb(year2, area, cloud)

        rgb_count1 = sn1.getInfo()
        rgb_count2 = sn2.getInfo()

        # Rectangular map bounds around the study area.
        bounds = area.bounds().coordinates().getInfo()[0]

        west = min(p[0] for p in bounds)
        east = max(p[0] for p in bounds)
        south = min(p[1] for p in bounds)
        north = max(p[1] for p in bounds)

except Exception as exc:
    st.error(
        "Analysis failed. Check Earth Engine authentication, "
        "Cloud project registration, internet and quotas."
    )
    st.exception(exc)
    st.stop()

# ---------------- MAP FUNCTIONS ----------------

def ee_tile(image, vis, label, show=True):
    """Create an Earth Engine tile layer without Geemap."""
    info = ee.Image(image).getMapId(vis)

    return folium.TileLayer(
        tiles=info["tile_fetcher"].url_format,
        attr="Google Earth Engine",
        name=label,
        overlay=True,
        control=True,
        show=show,
        max_zoom=19
    )


def new_map():
    """Create an OpenStreetMap map fitted to the study area."""

    m = folium.Map(
        location=[lat, lon],
        zoom_start=11,
        tiles="OpenStreetMap",
        control_scale=True
    )

    m.fit_bounds(
        [[south, west], [north, east]],
        padding=(12, 12)
    )

    Fullscreen(position="topright").add_to(m)
    MousePosition(position="bottomright").add_to(m)

    folium.GeoJson(
        data=area.getInfo(),
        name="Study boundary",
        style_function=lambda feature: {
            "color": "#ffcc33",
            "weight": 2,
            "fillOpacity": 0
        }
    ).add_to(m)

    return m


def display_map(m, key, height=430):
    folium.LayerControl(collapsed=True).add_to(m)

    st_folium(
        m,
        height=height,
        width=None,
        returned_objects=[],
        key=key
    )


# ---------------- DASHBOARD METRICS ----------------

st.subheader(f"{city} · {year1} → {year2}")
st.caption(f"Approximate circular study area: {radius} km radius. Maps show surrounding imagery; statistics use the circle.")

metrics = st.columns(4)

metrics[0].metric(
    f"Built-up area {year1}",
    f"{s1['Built-up']:.2f} km²"
)

metrics[1].metric(
    f"Built-up area {year2}",
    f"{s2['Built-up']:.2f} km²"
)

metrics[2].metric(
    "Net urban change",
    f"{changes['Net change']:+.2f} km²"
)

metrics[3].metric(
    "Relative built-up growth",
    "N/A" if changes["Growth %"] is None
    else f"{changes['Growth %']:+.1f}%"
)

# ---------------- SATELLITE IMAGERY ----------------

st.markdown(
    '<div class="section-head">'
    '01 / Satellite imagery — before & after'
    '</div>',
    unsafe_allow_html=True
)

a, b = st.columns(2)

for col, yr, rgb, cnt, key in [
    (a, year1, rgb1, rgb_count1, "rgb_before"),
    (b, year2, rgb2, rgb_count2, "rgb_after")
]:
    with col:
        st.markdown(
            f'<div class="map-label">'
            f'📷 {yr} — True-color Sentinel-2'
            f'</div>',
            unsafe_allow_html=True
        )

        if cnt:
            m = new_map()

            # Display the composite across the bounding rectangle.
            # The imagery must also be unmasked outside the circle
            # in analysis.py for the entire rectangle to be visible.
            rgb_display = ee.Image(rgb)

            ee_tile(
                rgb_display,
                {
                    "bands": ["B4", "B3", "B2"],
                    "min": 0.02,
                    "max": 0.32
                },
                f"Satellite RGB {yr}"
            ).add_to(m)

            display_map(m, key)

        else:
            st.warning(
                f"No suitable Sentinel-2 scenes for {yr}. "
                "Increase the cloud threshold."
            )

# ---------------- URBAN EXPANSION ----------------

st.markdown(
    '<div class="section-head">'
    '02 / Urban expansion map'
    '</div>',
    unsafe_allow_html=True
)

st.caption(
    "🟥 New built-up · 🟪 Stable built-up · "
    "🟦 Former built-up · 🟨 Study boundary"
)

m = new_map()

ee_tile(
    masks["Stable built-up"],
    {"palette": ["#7654d3"]},
    "Stable built-up"
).add_to(m)

ee_tile(
    masks["Former built-up"],
    {"palette": ["#159bd4"]},
    "Former built-up"
).add_to(m)

ee_tile(
    masks["New built-up"],
    {"palette": ["#f42d36"]},
    "New built-up"
).add_to(m)

display_map(m, "urban_change", 520)

# ---------------- LAND COVER CLASSIFICATION ----------------

st.markdown(
    '<div class="section-head">'
    '03 / Land-use and land-cover classification'
    '</div>',
    unsafe_allow_html=True
)

a, b = st.columns(2)

for col, yr, lc, key in [
    (a, year1, lc1, "lc_before"),
    (b, year2, lc2, "lc_after")
]:
    with col:
        st.markdown(
            f"🗺️ **{yr} — Land-cover classes**"
        )

        m = new_map()

        ee_tile(
            lc,
            {
                "min": 0,
                "max": 8,
                "palette": DW_COLORS
            },
            f"Land cover {yr}"
        ).add_to(m)

        display_map(m, key)

with st.expander("Land-cover legend", expanded=True):
    legend = " &nbsp; ".join(
        f'<span style="display:inline-block;margin:5px">'
        f'<span style="color:{color}">■</span> {name}'
        f'</span>'
        for name, color in zip(DW_NAMES, DW_COLORS)
    )
    st.markdown(legend, unsafe_allow_html=True)

# ---------------- SPECTRAL INDICES ----------------

st.markdown(
    '<div class="section-head">'
    '04 / Spectral index maps'
    '</div>',
    unsafe_allow_html=True
)

if rgb_count2:
    index_name = st.selectbox(
        "Choose index",
        ["NDVI", "NDBI", "NDWI"]
    )

    idx = spectral_indices(rgb2)[index_name]

    m = new_map()

    ee_tile(
        idx,
        {
            "min": -0.5,
            "max": 0.8,
            "palette": [
                "#8c510a",
                "#f6e8c3",
                "#01665e"
            ]
        },
        f"{index_name} {year2}"
    ).add_to(m)

    display_map(m, "index_map", 470)

else:
    st.warning(
        "Spectral index maps require valid Sentinel-2 imagery."
    )

# ---------------- STATISTICS ----------------

st.markdown(
    '<div class="section-head">'
    '05 / Area statistics and charts'
    '</div>',
    unsafe_allow_html=True
)

df = pd.DataFrame({
    "Class": DW_NAMES,
    str(year1): [s1[k] for k in DW_NAMES],
    str(year2): [s2[k] for k in DW_NAMES]
})

long = df.melt(
    id_vars="Class",
    var_name="Year",
    value_name="Area (km²)"
)

a, b = st.columns(2)

with a:
    fig = px.bar(
        long,
        x="Class",
        y="Area (km²)",
        color="Year",
        barmode="group",
        title="Land-cover area by year"
    )

    fig.update_layout(
        xaxis_tickangle=-40,
        legend_title_text="Year"
    )

    st.plotly_chart(fig, use_container_width=True)

with b:
    trans = pd.DataFrame({
        "Transition": [
            "New built-up",
            "Former built-up",
            "Stable built-up"
        ],
        "Area (km²)": [
            changes[k] for k in [
                "New built-up",
                "Former built-up",
                "Stable built-up"
            ]
        ]
    })

    fig = px.bar(
        trans,
        x="Transition",
        y="Area (km²)",
        color="Transition",
        color_discrete_map={
            "New built-up": "#f42d36",
            "Former built-up": "#159bd4",
            "Stable built-up": "#7654d3"
        },
        title="Built-up change components"
    )

    st.plotly_chart(fig, use_container_width=True)

st.dataframe(
    df,
    hide_index=True,
    use_container_width=True
)

# ---------------- YEAR-WISE GROWTH TREND ----------------

st.markdown('<div class="section-head">06 / Annual built-up growth trend</div>', unsafe_allow_html=True)
if show_trend and trend_rows:
    trend_df = pd.DataFrame(trend_rows)
    trend_fig = px.line(
        trend_df, x="Year", y="Built-up area (km²)", markers=True,
        title=f"Annual Dynamic World built-up estimates: {city}"
    )
    trend_fig.update_layout(xaxis=dict(dtick=1))
    st.plotly_chart(trend_fig, use_container_width=True)
    st.dataframe(trend_df, hide_index=True, use_container_width=True)
    st.download_button(
        "⬇️ Download annual trend CSV",
        trend_df.to_csv(index=False).encode("utf-8"),
        file_name=f"{city}_{year1}_{year2}_trend.csv".replace(" ", "_"),
        mime="text/csv", use_container_width=True
    )
elif show_trend:
    st.warning("No annual trend observations were available for this period.")
else:
    st.info("Enable 'Calculate annual built-up trend' in the sidebar and click Run to generate the year-wise graph.")

# ---------------- DOWNLOAD RESULTS ----------------

a, b = st.columns(2)

with a:
    st.download_button(
        "⬇️ Download land-cover CSV",
        df.to_csv(index=False).encode(),
        file_name=f"{city}_{year1}_{year2}_landcover.csv",
        mime="text/csv",
        use_container_width=True
    )

with b:
    st.download_button(
        "⬇️ Download urban change CSV",
        pd.DataFrame([changes]).to_csv(index=False).encode(),
        file_name=f"{city}_{year1}_{year2}_urban_change.csv",
        mime="text/csv",
        use_container_width=True
    )

# ---------------- METHODOLOGY ----------------

with st.expander("Methodology and limitations"):
    st.markdown("""
**Dynamic World:** Annual modal class from Google Dynamic World V1.

**Satellite RGB:** Median Sentinel-2 Surface Reflectance Harmonized composite.

**NDVI:** (NIR − Red) / (NIR + Red)

**NDBI:** (SWIR − NIR) / (SWIR + NIR)

**NDWI:** (Green − NIR) / (Green + NIR)

**Urban growth:** Comparison of built-up land-cover classes.

**Area definition:** Campus and city study areas are circular buffers around approximate center coordinates, not official boundaries.

**Accuracy:** No independent reference samples or confusion matrix are included. The built-up results are estimates, not validated accuracy measurements.

**Comparison:** The change map and net-change metric use pixels valid in both years. Standalone annual built-up totals can differ slightly from this common-pixel comparison.

**Limitations:** Classification noise, cloud coverage,
seasonal changes and observation gaps may affect results.

The study area is an approximate circle around the selected location,
not an official city or campus boundary.

Dynamic World is a pre-trained classification product;
this application does not train a Random Forest model.
""")

st.caption(
    f"Dynamic World images: {year1} = {count1}, "
    f"{year2} = {count2} · "
    f"Sentinel-2 scenes: {year1} = {rgb_count1}, "
    f"{year2} = {rgb_count2}"
)
